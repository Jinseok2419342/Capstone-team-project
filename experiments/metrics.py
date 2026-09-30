"""Paper-facing metrics for episode-level Re:Found event evaluation."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist, fmean, median
from .matching import MatchResult, MatchedEvent
from .schema import parse_iso8601


SCORED_EVENT_KINDS = ("added", "removed", "moved")


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    upper: float
    confidence: float = 0.95


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    event_kind: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    precision_interval: ConfidenceInterval | None
    recall_interval: ConfidenceInterval | None

    @property
    def support(self) -> int:
        return self.true_positives + self.false_negatives

    @property
    def predicted(self) -> int:
        return self.true_positives + self.false_positives


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    count: int
    mean: float | None
    median: float | None
    p50: float | None
    p95: float | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class DetectionMetrics:
    """All core detection, identity, localization, and latency measures."""

    by_kind: Mapping[str, ClassMetrics]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    prediction_stage: str
    iou_threshold: float
    allowed_window_seconds: float | None
    episode_count: int
    ground_truth_event_count: int
    scored_prediction_count: int
    ignored_prediction_count: int
    false_event_count: int
    none_episode_count: int
    none_episode_false_trigger_count: int
    none_episode_false_trigger_rate: float | None
    none_episode_false_trigger_interval: ConfidenceInterval | None
    none_monitoring_hours: float
    false_events_per_hour: float | None
    duplicate_prediction_count: int
    moved_identity_scorable_count: int
    moved_id_preserved_count: int
    moved_id_preservation_rate: float | None
    moved_id_preservation_interval: ConfidenceInterval | None
    duplicate_id_created_count: int
    duplicate_id_creation_rate: float | None
    bbox_iou: DistributionSummary
    selected_event_latency_ms: DistributionSummary
    provisional_db_latency_ms: DistributionSummary
    ai_round_trip_latency_ms: DistributionSummary
    final_commit_latency_ms: DistributionSummary

    @property
    def final_prediction_count(self) -> int:
        """Backward-compatible alias; prefer ``scored_prediction_count``."""

        return self.scored_prediction_count

    @property
    def ignored_intermediate_count(self) -> int:
        """Backward-compatible alias; prefer ``ignored_prediction_count``."""

        return self.ignored_prediction_count

    @property
    def local_event_latency_ms(self) -> DistributionSummary:
        """Backward-compatible alias for the selected prediction stage latency."""

        return self.selected_event_latency_ms


@dataclass(frozen=True, slots=True)
class McNemarResult:
    first_only_correct: int
    second_only_correct: int
    discordant_pairs: int
    exact_p_value: float


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def precision_recall_f1(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> tuple[float, float, float]:
    """Calculate the three standard detection ratios with zero-safe outputs."""

    if min(true_positives, false_positives, false_negatives) < 0:
        raise ValueError("confusion counts must be non-negative")
    precision = _safe_ratio(true_positives, true_positives + false_positives)
    recall = _safe_ratio(true_positives, true_positives + false_negatives)
    f1 = _safe_ratio(2 * true_positives, 2 * true_positives + false_positives + false_negatives)
    return precision, recall, f1


def wilson_interval(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> ConfidenceInterval | None:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    if successes < 0 or trials < 0 or successes > trials:
        raise ValueError("successes and trials must satisfy 0 <= successes <= trials")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if trials == 0:
        return None

    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    proportion = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    centre = (proportion + z_squared / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return ConfidenceInterval(
        lower=max(0.0, centre - radius),
        upper=min(1.0, centre + radius),
        confidence=confidence,
    )


def percentile(values: Sequence[float], percentile_value: float) -> float:
    """Linear (R-7) percentile, matching common dataframe defaults."""

    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= percentile_value <= 100.0:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(float(value) for value in values)
    if not all(math.isfinite(value) for value in ordered):
        raise ValueError("percentile values must be finite")
    position = (len(ordered) - 1) * percentile_value / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize_distribution(values: Iterable[float]) -> DistributionSummary:
    numbers = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError("distribution values must be finite")
    if not numbers:
        return DistributionSummary(0, None, None, None, None, None, None)
    return DistributionSummary(
        count=len(numbers),
        mean=fmean(numbers),
        median=median(numbers),
        p50=percentile(numbers, 50.0),
        p95=percentile(numbers, 95.0),
        minimum=min(numbers),
        maximum=max(numbers),
    )


def _elapsed_ms(start_at, end_text: str) -> float | None:
    if not end_text:
        return None
    elapsed = (parse_iso8601(end_text) - start_at).total_seconds() * 1000.0
    if elapsed < 0:
        raise ValueError(f"negative pipeline latency for timestamp {end_text!r}")
    return elapsed


def _matched_latency_values(
    result: MatchResult,
) -> tuple[list[float], list[float], list[float], list[float]]:
    local: list[float] = []
    provisional: list[float] = []
    ai_round_trip: list[float] = []
    final_commit: list[float] = []

    for episode_result in result.episodes:
        start_at = episode_result.window_start_at
        for match in episode_result.matches:
            prediction = match.prediction
            local.append(match.latency_seconds * 1000.0)
            provisional_value = _elapsed_ms(start_at, prediction.provisional_db_at)
            if provisional_value is not None:
                provisional.append(provisional_value)
            if prediction.ai_request_at and prediction.ai_response_at:
                request_at = parse_iso8601(prediction.ai_request_at)
                response_at = parse_iso8601(prediction.ai_response_at)
                duration = (response_at - request_at).total_seconds() * 1000.0
                if duration < 0:
                    raise ValueError(
                        f"negative AI round-trip latency for event {prediction.key!r}"
                    )
                ai_round_trip.append(duration)
            final_value = _elapsed_ms(start_at, prediction.final_commit_at)
            if final_value is not None:
                final_commit.append(final_value)
    return local, provisional, ai_round_trip, final_commit


def _class_metrics(
    event_kind: str,
    matches: Sequence[MatchedEvent],
    false_positives,
    false_negatives,
    confidence: float,
) -> ClassMetrics:
    true_positive_count = sum(match.event_kind == event_kind for match in matches)
    false_positive_count = sum(event.event_kind == event_kind for event in false_positives)
    false_negative_count = sum(event.event_kind == event_kind for event in false_negatives)
    precision, recall, f1 = precision_recall_f1(
        true_positive_count, false_positive_count, false_negative_count
    )
    return ClassMetrics(
        event_kind=event_kind,
        true_positives=true_positive_count,
        false_positives=false_positive_count,
        false_negatives=false_negative_count,
        precision=precision,
        recall=recall,
        f1=f1,
        precision_interval=wilson_interval(
            true_positive_count,
            true_positive_count + false_positive_count,
            confidence=confidence,
        ),
        recall_interval=wilson_interval(
            true_positive_count,
            true_positive_count + false_negative_count,
            confidence=confidence,
        ),
    )


def compute_detection_metrics(
    result: MatchResult,
    *,
    confidence: float = 0.95,
) -> DetectionMetrics:
    """Aggregate an immutable :class:`MatchResult` into paper-ready metrics."""

    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    matches = result.matches
    false_positives = result.false_positives
    false_negatives = result.false_negatives

    metrics_by_kind = {
        event_kind: _class_metrics(
            event_kind,
            matches,
            false_positives,
            false_negatives,
            confidence,
        )
        for event_kind in SCORED_EVENT_KINDS
    }
    macro_precision = fmean(item.precision for item in metrics_by_kind.values())
    macro_recall = fmean(item.recall for item in metrics_by_kind.values())
    macro_f1 = fmean(item.f1 for item in metrics_by_kind.values())
    total_true_positives = sum(item.true_positives for item in metrics_by_kind.values())
    total_false_positives = sum(item.false_positives for item in metrics_by_kind.values())
    total_false_negatives = sum(item.false_negatives for item in metrics_by_kind.values())
    micro_precision, micro_recall, micro_f1 = precision_recall_f1(
        total_true_positives,
        total_false_positives,
        total_false_negatives,
    )

    none_episodes = tuple(
        episode for episode in result.episodes if episode.is_none_episode
    )
    none_false_trigger_count = sum(bool(episode.false_positives) for episode in none_episodes)
    none_episode_count = len(none_episodes)
    none_false_trigger_rate = (
        none_false_trigger_count / none_episode_count if none_episode_count else None
    )
    false_event_count = sum(len(episode.false_positives) for episode in none_episodes)
    none_monitoring_seconds = sum(
        episode.episode.eligible_monitoring_seconds for episode in none_episodes
    )
    none_monitoring_hours = none_monitoring_seconds / 3600.0
    false_events_per_hour = (
        false_event_count / none_monitoring_hours if none_monitoring_hours > 0 else None
    )

    scored_identity = tuple(
        match
        for match in matches
        if match.event_kind == "moved" and match.id_preserved is not None
    )
    preserved_count = sum(match.id_preserved is True for match in scored_identity)
    duplicate_id_count = sum(
        match.duplicate_id_created is True for match in scored_identity
    )
    identity_count = len(scored_identity)
    identity_rate = preserved_count / identity_count if identity_count else None
    duplicate_id_rate = duplicate_id_count / identity_count if identity_count else None

    local, provisional, ai_round_trip, final_commit = _matched_latency_values(result)
    return DetectionMetrics(
        by_kind=metrics_by_kind,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        micro_f1=micro_f1,
        prediction_stage=result.prediction_stage,
        iou_threshold=result.iou_threshold,
        allowed_window_seconds=result.allowed_window_seconds,
        episode_count=len(result.episodes),
        ground_truth_event_count=len(matches) + len(false_negatives),
        scored_prediction_count=len(matches) + len(false_positives),
        ignored_prediction_count=len(result.ignored_predictions),
        false_event_count=false_event_count,
        none_episode_count=none_episode_count,
        none_episode_false_trigger_count=none_false_trigger_count,
        none_episode_false_trigger_rate=none_false_trigger_rate,
        none_episode_false_trigger_interval=wilson_interval(
            none_false_trigger_count, none_episode_count, confidence=confidence
        ),
        none_monitoring_hours=none_monitoring_hours,
        false_events_per_hour=false_events_per_hour,
        duplicate_prediction_count=len(result.duplicate_predictions),
        moved_identity_scorable_count=identity_count,
        moved_id_preserved_count=preserved_count,
        moved_id_preservation_rate=identity_rate,
        moved_id_preservation_interval=wilson_interval(
            preserved_count, identity_count, confidence=confidence
        ),
        duplicate_id_created_count=duplicate_id_count,
        duplicate_id_creation_rate=duplicate_id_rate,
        bbox_iou=summarize_distribution(match.bbox_iou for match in matches),
        selected_event_latency_ms=summarize_distribution(local),
        provisional_db_latency_ms=summarize_distribution(provisional),
        ai_round_trip_latency_ms=summarize_distribution(ai_round_trip),
        final_commit_latency_ms=summarize_distribution(final_commit),
    )


def mcnemar_exact(
    first_correct: Sequence[bool],
    second_correct: Sequence[bool],
) -> McNemarResult:
    """Two-sided exact McNemar test for paired episode success vectors."""

    if len(first_correct) != len(second_correct):
        raise ValueError("paired result vectors must have the same length")
    first_only = sum(bool(first) and not bool(second) for first, second in zip(first_correct, second_correct))
    second_only = sum(not bool(first) and bool(second) for first, second in zip(first_correct, second_correct))
    discordant = first_only + second_only
    if discordant == 0:
        p_value = 1.0
    else:
        smaller = min(first_only, second_only)
        lower_tail = sum(math.comb(discordant, index) for index in range(smaller + 1)) / (2**discordant)
        p_value = min(1.0, 2.0 * lower_tail)
    return McNemarResult(first_only, second_only, discordant, p_value)


def bootstrap_interval(
    values: Sequence[float],
    *,
    statistic: Callable[[Sequence[float]], float] = fmean,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Deterministic percentile bootstrap interval for episode-level values."""

    observations = tuple(float(value) for value in values)
    if not observations or not all(math.isfinite(value) for value in observations):
        raise ValueError("bootstrap values must be a non-empty finite sequence")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if resamples < 1:
        raise ValueError("resamples must be positive")

    generator = random.Random(seed)
    sample_size = len(observations)
    estimates = [
        float(statistic([observations[generator.randrange(sample_size)] for _ in range(sample_size)]))
        for _ in range(resamples)
    ]
    tail = (1.0 - confidence) * 50.0
    return ConfidenceInterval(
        lower=percentile(estimates, tail),
        upper=percentile(estimates, 100.0 - tail),
        confidence=confidence,
    )
