"""Turn a stable-pair manifest into append-only research CSV records."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .ablation import PROFILE_CONTROLLED_KEYS, build_vision_config
from .schema import EpisodeRecord, EventRecord, format_iso8601, validate_episode, validate_event
from .vision_pairs import PairDetectionResult, PairTrial, detect_stable_pair


@dataclass(frozen=True, slots=True)
class PairDatasetRun:
    episodes: tuple[EpisodeRecord, ...]
    events: tuple[EventRecord, ...]
    trial_rows: tuple[dict[str, Any], ...]
    configs: dict[str, dict[str, Any]]


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def detector_source_version(project_root: Path | None = None) -> str:
    """Return a stable identifier even when the project is not a Git clone."""

    root = Path(project_root or Path(__file__).resolve().parents[1])
    digest = hashlib.sha256()
    paths = [
        root / "app" / "vision.py",
        root / "experiments" / "ablation.py",
        root / "experiments" / "vision_pairs.py",
        root / "experiments" / "pair_runner.py",
    ]
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"vision-sha256:{digest.hexdigest()[:16]}"


def build_pair_dataset(
    trials: Iterable[PairTrial],
    *,
    manifest_dir: Path,
    run_id: str,
    profiles: Iterable[str],
    protocol_version: str,
    config_overrides: dict[str, Any] | None = None,
    device: str = "",
    os_version: str | None = None,
    camera_model: str = "",
    software_version: str | None = None,
    operator: str = "",
) -> PairDatasetRun:
    """Evaluate every trial/profile combination without writing partial files."""

    trial_list = list(trials)
    profile_list = list(profiles)
    if not trial_list:
        raise ValueError("pair manifest contains no trials")
    if not profile_list:
        raise ValueError("at least one ablation profile is required")
    if len(set(profile_list)) != len(profile_list):
        raise ValueError("ablation profile list contains duplicates")
    protected_overrides = sorted(
        PROFILE_CONTROLLED_KEYS.intersection((config_overrides or {}).keys())
    )
    if protected_overrides:
        raise ValueError(
            "config overrides cannot replace profile-controlled switches: "
            + ", ".join(protected_overrides)
        )
    for trial in trial_list:
        if trial.event_ground_truth != "none" and trial.bbox_ground_truth is None:
            raise ValueError(
                f"trial {trial.trial_id!r}: positive ground truth requires bbox_ground_truth"
            )

    configs = {
        profile_name: build_vision_config(profile_name, config_overrides)
        for profile_name in profile_list
    }
    detected_version = software_version or detector_source_version()
    detected_os = os_version or platform.platform()
    episodes: list[EpisodeRecord] = []
    events: list[EventRecord] = []
    trial_rows: list[dict[str, Any]] = []

    for profile_name in profile_list:
        config = configs[profile_name]
        config_sha256 = canonical_json_sha256(config)
        profile_run_id = f"{run_id}__{profile_name}"
        for trial in trial_list:
            action_end = datetime.now(timezone.utc)
            result = detect_stable_pair(
                trial,
                manifest_dir=manifest_dir,
                profile=profile_name,
                config_overrides=config_overrides,
            )
            ended = datetime.now(timezone.utc)
            episode = _episode_record(
                result,
                run_id=profile_run_id,
                protocol_version=protocol_version,
                action_end=action_end,
                ended=ended,
                config_sha256=config_sha256,
                device=device,
                os_version=detected_os,
                camera_model=camera_model,
                software_version=detected_version,
                operator=operator,
            )
            episode_events = _event_records(
                result,
                run_id=profile_run_id,
                action_end=action_end,
                predicted_at=action_end
                + timedelta(milliseconds=result.detection_latency_ms),
            )
            _raise_record_issues(episode, episode_events)
            episodes.append(episode)
            events.extend(episode_events)
            row = result.as_row()
            row.update(
                {
                    "run_id": profile_run_id,
                    "protocol_version": protocol_version,
                    "config_sha256": config_sha256,
                    "software_version": detected_version,
                    "action_end_at": format_iso8601(action_end),
                    "ended_at": format_iso8601(ended),
                }
            )
            trial_rows.append(row)

    return PairDatasetRun(
        episodes=tuple(episodes),
        events=tuple(events),
        trial_rows=tuple(trial_rows),
        configs=configs,
    )


def _episode_record(
    result: PairDetectionResult,
    *,
    run_id: str,
    protocol_version: str,
    action_end: datetime,
    ended: datetime,
    config_sha256: str,
    device: str,
    os_version: str,
    camera_model: str,
    software_version: str,
    operator: str,
) -> EpisodeRecord:
    has_ground_truth = result.trial.event_ground_truth != "none"
    return EpisodeRecord(
        run_id=run_id,
        episode_id=result.trial.trial_id,
        protocol_version=protocol_version,
        started_at=format_iso8601(action_end),
        action_start_at=format_iso8601(action_end),
        action_end_at=format_iso8601(action_end),
        ended_at=format_iso8601(ended),
        # One stable pair is one detector invocation, not continuous monitoring.
        # Keep any source-video duration only in pair_trials.csv so FP/hour
        # cannot be manufactured from a discrete-pair evaluation.
        eligible_monitoring_seconds=0.0,
        episode_complete=True,
        device=device,
        os_version=os_version,
        camera_model=camera_model,
        software_version=software_version,
        config_sha256=config_sha256,
        scenario=result.trial.scenario,
        lighting=result.trial.lighting,
        nuisance=result.trial.nuisance,
        expected_event_count=1 if has_ground_truth else 0,
        callback_dropped_count=0,
        camera_disconnect_seconds=0.0,
        operator=operator,
        notes=_join_notes(
            "stable-pair core evaluation; excludes capture settling and VLM latency",
            "single-call CPU timing is stored only in pair_trials.csv, not episode resource fields",
            (
                f"source segment {result.trial.source_segment_seconds:g}s; excluded from FP/hour"
                if result.trial.source_segment_seconds > 0
                else ""
            ),
            "global scene change suppressed" if result.global_change_suppressed else "",
            result.trial.notes,
        ),
    )


def _event_records(
    result: PairDetectionResult,
    *,
    run_id: str,
    action_end: datetime,
    predicted_at: datetime,
) -> list[EventRecord]:
    records: list[EventRecord] = []
    trial = result.trial
    if trial.event_ground_truth != "none":
        bbox = trial.bbox_ground_truth
        records.append(
            EventRecord(
                run_id=run_id,
                episode_id=trial.trial_id,
                event_id="gt-001",
                pipeline_id=result.profile,
                record_role="ground_truth",
                stage="ground_truth",
                event_kind=trial.event_ground_truth,  # type: ignore[arg-type]
                event_at=format_iso8601(action_end),
                object_id=trial.active_item_id or "",
                bbox_x=bbox[0] if bbox else None,
                bbox_y=bbox[1] if bbox else None,
                bbox_w=bbox[2] if bbox else None,
                bbox_h=bbox[3] if bbox else None,
                frame_width=result.frame_width,
                frame_height=result.frame_height,
            )
        )
    for index, event in enumerate(result.events, start=1):
        x, y, width, height = event.bbox
        records.append(
            EventRecord(
                run_id=run_id,
                episode_id=trial.trial_id,
                event_id=f"local-{index:03d}",
                pipeline_id=result.profile,
                record_role="prediction",
                stage="local",
                event_kind=event.kind,
                event_at=format_iso8601(predicted_at),
                matched_item_id=(
                    "" if event.matched_item_id is None else str(event.matched_item_id)
                ),
                bbox_x=x,
                bbox_y=y,
                bbox_w=width,
                bbox_h=height,
                frame_width=result.frame_width,
                frame_height=result.frame_height,
                confidence=float(event.confidence),
                notes=(
                    "global_change_suppressed"
                    if result.global_change_suppressed
                    else ""
                ),
            )
        )
    return records


def _join_notes(*values: str) -> str:
    return "; ".join(value.strip() for value in values if value and value.strip())


def _raise_record_issues(
    episode: EpisodeRecord,
    events: Iterable[EventRecord],
) -> None:
    issues = validate_episode(episode)
    for event in events:
        issues.extend(validate_event(event))
    errors = [str(issue) for issue in issues if issue.is_error]
    if errors:
        raise ValueError("generated invalid experiment records: " + "; ".join(errors))
