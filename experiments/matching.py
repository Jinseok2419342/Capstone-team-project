"""Episode-level one-to-one matching for Re:Found experiment records.

Final predictions are scored by default; replay runners can explicitly select
the local stage.  In either mode, ``verify_removed`` remains available for
pipeline diagnostics but cannot accidentally become a scored detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Literal, Sequence

from .schema import EpisodeRecord, EventRecord, FINAL_EVENT_KINDS, parse_iso8601


@dataclass(frozen=True, slots=True)
class MatchedEvent:
    """One ground-truth event and its unique final prediction."""

    episode: EpisodeRecord
    ground_truth: EventRecord
    prediction: EventRecord
    bbox_iou: float
    latency_seconds: float
    id_preserved: bool | None
    duplicate_id_created: bool | None

    @property
    def event_kind(self) -> str:
        return self.ground_truth.event_kind


@dataclass(frozen=True, slots=True)
class EpisodeMatch:
    """Complete scoring outcome for one episode."""

    episode: EpisodeRecord
    matches: tuple[MatchedEvent, ...]
    false_positives: tuple[EventRecord, ...]
    false_negatives: tuple[EventRecord, ...]
    duplicate_predictions: tuple[EventRecord, ...]
    ignored_predictions: tuple[EventRecord, ...]
    window_start_at: datetime
    window_end_at: datetime

    @property
    def is_none_episode(self) -> bool:
        return not self.false_negatives and not self.matches and self.episode.expected_event_count == 0


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Dataset-wide immutable result returned by :func:`match_events`."""

    episodes: tuple[EpisodeMatch, ...]
    iou_threshold: float
    allowed_window_seconds: float | None
    prediction_stage: Literal["local", "final"]

    @property
    def matches(self) -> tuple[MatchedEvent, ...]:
        return tuple(match for episode in self.episodes for match in episode.matches)

    @property
    def false_positives(self) -> tuple[EventRecord, ...]:
        return tuple(event for episode in self.episodes for event in episode.false_positives)

    @property
    def false_negatives(self) -> tuple[EventRecord, ...]:
        return tuple(event for episode in self.episodes for event in episode.false_negatives)

    @property
    def duplicate_predictions(self) -> tuple[EventRecord, ...]:
        return tuple(
            event for episode in self.episodes for event in episode.duplicate_predictions
        )

    @property
    def ignored_predictions(self) -> tuple[EventRecord, ...]:
        return tuple(event for episode in self.episodes for event in episode.ignored_predictions)


def bbox_iou(
    first: Sequence[float] | None,
    second: Sequence[float] | None,
) -> float:
    """Return intersection-over-union for two ``(x, y, width, height)`` boxes."""

    if first is None or second is None or len(first) != 4 or len(second) != 4:
        return 0.0
    ax, ay, aw, ah = (float(value) for value in first)
    bx, by, bw, bh = (float(value) for value in second)
    values = (ax, ay, aw, ah, bx, by, bw, bh)
    if not all(math.isfinite(value) for value in values) or min(aw, ah, bw, bh) <= 0:
        return 0.0

    intersection_w = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    intersection_h = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    intersection = intersection_w * intersection_h
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0.0 else 0.0


def _normalized_bbox(event: EventRecord) -> tuple[float, float, float, float] | None:
    bbox = event.bbox
    if bbox is None:
        return None
    x, y, width, height = bbox
    if event.frame_width and event.frame_height:
        return (
            x / event.frame_width,
            y / event.frame_height,
            width / event.frame_width,
            height / event.frame_height,
        )
    return float(x), float(y), float(width), float(height)


def event_bbox_iou(first: EventRecord, second: EventRecord) -> float:
    """Compare event boxes, normalizing when both declare their frame size."""

    if (
        first.frame_width
        and first.frame_height
        and second.frame_width
        and second.frame_height
    ):
        return bbox_iou(_normalized_bbox(first), _normalized_bbox(second))
    return bbox_iou(first.bbox, second.bbox)


def _event_order(event: EventRecord) -> tuple[datetime, str]:
    return parse_iso8601(event.event_at), event.event_id


def _episode_window(
    episode: EpisodeRecord,
    ground_truth: Sequence[EventRecord],
    allowed_window_seconds: float | None,
) -> tuple[datetime, datetime]:
    if not episode.episode_complete or not episode.ended_at:
        raise ValueError(
            f"episode {episode.key!r} is incomplete and cannot be scored"
        )
    if episode.action_end_at:
        window_start = parse_iso8601(episode.action_end_at)
    elif ground_truth:
        window_start = min(parse_iso8601(event.event_at) for event in ground_truth)
    else:
        window_start = parse_iso8601(episode.started_at)

    episode_end = parse_iso8601(episode.ended_at)
    if allowed_window_seconds is None:
        window_end = episode_end
    else:
        window_end = min(
            episode_end,
            window_start + timedelta(seconds=allowed_window_seconds),
        )
    return window_start, window_end


def _identity_outcome(
    ground_truth: EventRecord,
    prediction: EventRecord,
) -> tuple[bool | None, bool | None]:
    if ground_truth.event_kind != "moved" or not ground_truth.object_id:
        return None, None
    preserved = prediction.matched_item_id == ground_truth.object_id
    duplicate_created = (
        not preserved
        and bool(prediction.object_id)
        and prediction.object_id != ground_truth.object_id
    )
    return preserved, duplicate_created


def _minimum_cost_assignment(costs: Sequence[Sequence[float]]) -> list[int]:
    """Solve a rectangular assignment where rows <= columns (Hungarian method)."""

    row_count = len(costs)
    if row_count == 0:
        return []
    column_count = len(costs[0])
    if row_count > column_count or any(len(row) != column_count for row in costs):
        raise ValueError("assignment matrix must be rectangular with rows <= columns")

    u = [0.0] * (row_count + 1)
    v = [0.0] * (column_count + 1)
    assigned_row = [0] * (column_count + 1)
    predecessor = [0] * (column_count + 1)

    for row_index in range(1, row_count + 1):
        assigned_row[0] = row_index
        minimum = [math.inf] * (column_count + 1)
        used = [False] * (column_count + 1)
        column = 0
        while True:
            used[column] = True
            current_row = assigned_row[column]
            delta = math.inf
            next_column = 0
            for candidate in range(1, column_count + 1):
                if used[candidate]:
                    continue
                reduced = costs[current_row - 1][candidate - 1] - u[current_row] - v[candidate]
                if reduced < minimum[candidate]:
                    minimum[candidate] = reduced
                    predecessor[candidate] = column
                if minimum[candidate] < delta:
                    delta = minimum[candidate]
                    next_column = candidate
            for candidate in range(column_count + 1):
                if used[candidate]:
                    u[assigned_row[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            column = next_column
            if assigned_row[column] == 0:
                break
        while True:
            previous = predecessor[column]
            assigned_row[column] = assigned_row[previous]
            column = previous
            if column == 0:
                break

    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        if assigned_row[column]:
            assignment[assigned_row[column] - 1] = column - 1
    return assignment


def match_episode(
    episode: EpisodeRecord,
    ground_truth: Iterable[EventRecord],
    predictions: Iterable[EventRecord],
    *,
    iou_threshold: float = 0.3,
    allowed_window_seconds: float | None = None,
    prediction_stage: Literal["local", "final"] = "final",
    strict_expected_count: bool = True,
) -> EpisodeMatch:
    """Match a single episode with exact, deterministic one-to-one assignment.

    The optimization first maximizes match cardinality, then prefers earlier
    predictions (so the first duplicate is the TP), and finally higher IoU.
    """

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be between 0 and 1")
    if allowed_window_seconds is not None and (
        not math.isfinite(allowed_window_seconds) or allowed_window_seconds < 0
    ):
        raise ValueError("allowed_window_seconds must be finite and non-negative")
    if prediction_stage not in ("local", "final"):
        raise ValueError("prediction_stage must be 'local' or 'final'")

    truth = tuple(
        sorted(
            (
                event
                for event in ground_truth
                if event.record_role == "ground_truth" and event.stage == "ground_truth"
            ),
            key=_event_order,
        )
    )
    supplied_predictions = tuple(
        sorted(
            (event for event in predictions if event.record_role == "prediction"),
            key=_event_order,
        )
    )
    scored_predictions = tuple(
        event
        for event in supplied_predictions
        if event.stage == prediction_stage and event.event_kind in FINAL_EVENT_KINDS
    )
    ignored = tuple(event for event in supplied_predictions if event not in scored_predictions)

    for event in (*truth, *supplied_predictions):
        if event.episode_key != episode.key:
            raise ValueError(
                f"event {event.key!r} does not belong to episode {episode.key!r}"
            )
    if strict_expected_count and len(truth) != episode.expected_event_count:
        raise ValueError(
            f"episode {episode.key!r} declares expected_event_count="
            f"{episode.expected_event_count}, but has {len(truth)} ground-truth records"
        )

    window_start, window_end = _episode_window(
        episode, truth, allowed_window_seconds
    )
    prediction_times = [parse_iso8601(event.event_at) for event in scored_predictions]

    eligible: list[list[bool]] = []
    overlaps: list[list[float]] = []
    for expected in truth:
        expected_eligible: list[bool] = []
        expected_overlaps: list[float] = []
        for prediction, prediction_at in zip(scored_predictions, prediction_times):
            overlap = event_bbox_iou(expected, prediction)
            expected_overlaps.append(overlap)
            expected_eligible.append(
                expected.event_kind == prediction.event_kind
                and window_start <= prediction_at <= window_end
                and overlap >= iou_threshold
            )
        eligible.append(expected_eligible)
        overlaps.append(expected_overlaps)

    assignment: list[int] = []
    if truth:
        truth_count = len(truth)
        prediction_count = len(scored_predictions)
        cardinality_bonus = float(truth_count + 1)
        forbidden_cost = cardinality_bonus * (truth_count + 2)
        costs: list[list[float]] = []
        for truth_index in range(truth_count):
            row: list[float] = []
            for prediction_index in range(prediction_count):
                if not eligible[truth_index][prediction_index]:
                    row.append(forbidden_cost)
                    continue
                # A temporal preference implements the protocol's "first
                # duplicate is TP" rule. IoU resolves assignments that use
                # the same set of prediction timestamps.
                temporal = (prediction_count - prediction_index) / (prediction_count + 1)
                score = cardinality_bonus + temporal + overlaps[truth_index][prediction_index] * 1e-6
                row.append(-score)
            row.extend(0.0 for _ in range(truth_count))
            costs.append(row)
        assignment = _minimum_cost_assignment(costs)

    matched_prediction_indexes: set[int] = set()
    matched: list[MatchedEvent] = []
    for truth_index, prediction_index in enumerate(assignment):
        if prediction_index < 0 or prediction_index >= len(scored_predictions):
            continue
        if not eligible[truth_index][prediction_index]:
            continue
        expected = truth[truth_index]
        prediction = scored_predictions[prediction_index]
        matched_prediction_indexes.add(prediction_index)
        id_preserved, duplicate_id_created = _identity_outcome(expected, prediction)
        matched.append(
            MatchedEvent(
                episode=episode,
                ground_truth=expected,
                prediction=prediction,
                bbox_iou=overlaps[truth_index][prediction_index],
                latency_seconds=(prediction_times[prediction_index] - window_start).total_seconds(),
                id_preserved=id_preserved,
                duplicate_id_created=duplicate_id_created,
            )
        )

    matched_truth_ids = {item.ground_truth.event_id for item in matched}
    false_negatives = tuple(
        event for event in truth if event.event_id not in matched_truth_ids
    )
    false_positives = tuple(
        event
        for index, event in enumerate(scored_predictions)
        if index not in matched_prediction_indexes
    )
    duplicate_predictions = tuple(
        prediction
        for prediction_index, prediction in enumerate(scored_predictions)
        if prediction_index not in matched_prediction_indexes
        and any(row[prediction_index] for row in eligible)
    )

    return EpisodeMatch(
        episode=episode,
        matches=tuple(sorted(matched, key=lambda item: _event_order(item.prediction))),
        false_positives=false_positives,
        false_negatives=false_negatives,
        duplicate_predictions=duplicate_predictions,
        ignored_predictions=ignored,
        window_start_at=window_start,
        window_end_at=window_end,
    )


def match_events(
    episodes: Iterable[EpisodeRecord],
    events: Iterable[EventRecord],
    *,
    iou_threshold: float = 0.3,
    allowed_window_seconds: float | None = None,
    prediction_stage: Literal["local", "final"] = "final",
    strict_expected_counts: bool = True,
) -> MatchResult:
    """Group records by ``(run_id, episode_id)`` and score all episodes."""

    episode_records = tuple(episodes)
    event_records = tuple(events)
    episode_by_key = {episode.key: episode for episode in episode_records}
    if len(episode_by_key) != len(episode_records):
        raise ValueError("episode keys must be unique")

    event_keys = [event.key for event in event_records]
    if len(set(event_keys)) != len(event_keys):
        raise ValueError("event keys must be unique")
    unknown = [event.key for event in event_records if event.episode_key not in episode_by_key]
    if unknown:
        raise ValueError(f"events reference unknown episodes: {unknown!r}")

    grouped_truth: dict[tuple[str, str], list[EventRecord]] = {
        key: [] for key in episode_by_key
    }
    grouped_predictions: dict[tuple[str, str], list[EventRecord]] = {
        key: [] for key in episode_by_key
    }
    for event in event_records:
        if event.record_role == "ground_truth":
            grouped_truth[event.episode_key].append(event)
        elif event.record_role == "prediction":
            grouped_predictions[event.episode_key].append(event)
        else:
            raise ValueError(f"unsupported record_role {event.record_role!r}")

    outcomes = tuple(
        match_episode(
            episode,
            grouped_truth[episode.key],
            grouped_predictions[episode.key],
            iou_threshold=iou_threshold,
            allowed_window_seconds=allowed_window_seconds,
            prediction_stage=prediction_stage,
            strict_expected_count=strict_expected_counts,
        )
        for episode in sorted(episode_records, key=lambda item: item.key)
    )
    return MatchResult(
        episodes=outcomes,
        iou_threshold=iou_threshold,
        allowed_window_seconds=allowed_window_seconds,
        prediction_stage=prediction_stage,
    )
