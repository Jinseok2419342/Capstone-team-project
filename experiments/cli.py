"""Command-line workflow for creating, validating, replaying, and scoring data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from .ablation import PROFILE_DESCRIPTIONS, profile_names
from .csvio import read_episodes, read_events, validate_dataset, write_dataset
from .matching import match_events
from .metrics import DetectionMetrics, compute_detection_metrics
from .pair_runner import build_pair_dataset
from .schema import EPISODE_CSV_FIELDS, EVENT_CSV_FIELDS, SCHEMA_VERSION
from .vision_pairs import PAIR_MANIFEST_FIELDS, read_pair_manifest


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _unit_interval(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("value must be between 0 and 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re:Found paper experiment data and metrics",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create empty manual experiment tables")
    init.add_argument("output_dir", type=Path)
    init.add_argument("--protocol-version", default="refound-events-v1")

    validate = commands.add_parser("validate", help="validate episode/event CSV files")
    validate.add_argument("--episodes", required=True, type=Path)
    validate.add_argument("--events", required=True, type=Path)

    pairs = commands.add_parser(
        "run-pairs",
        help="evaluate one stable before/after manifest with cumulative ablations",
    )
    pairs.add_argument("--manifest", required=True, type=Path)
    pairs.add_argument("--output-dir", required=True, type=Path)
    pairs.add_argument("--run-id", required=True)
    pairs.add_argument(
        "--profiles",
        default="full",
        help=f"comma-separated profiles in paper order: {', '.join(profile_names())}",
    )
    pairs.add_argument("--protocol-version", default="stable-pair-v1")
    pairs.add_argument("--config-json", type=Path)
    pairs.add_argument("--device", default="")
    pairs.add_argument("--os-version", default=None)
    pairs.add_argument("--camera-model", default="")
    pairs.add_argument("--software-version", default=None)
    pairs.add_argument("--operator", default="")
    pairs.add_argument("--iou", type=_unit_interval, default=0.30)

    summarize = commands.add_parser("summarize", help="create paper-facing metric tables")
    summarize.add_argument("--episodes", required=True, type=Path)
    summarize.add_argument("--events", required=True, type=Path)
    summarize.add_argument("--output-dir", required=True, type=Path)
    summarize.add_argument("--stage", choices=("local", "final"), default="final")
    summarize.add_argument("--iou", type=_unit_interval, default=0.30)
    summarize.add_argument("--window-seconds", type=_positive_float)
    summarize.add_argument("--stem", default=None)
    return parser


def _parse_profiles(value: str) -> tuple[str, ...]:
    profiles = tuple(part.strip() for part in value.split(",") if part.strip())
    if not profiles:
        raise ValueError("--profiles must include at least one name")
    available = set(profile_names())
    unknown = [profile for profile in profiles if profile not in available]
    if unknown:
        raise ValueError(
            f"unknown profiles {unknown!r}; choose from {', '.join(profile_names())}"
        )
    if len(set(profiles)) != len(profiles):
        raise ValueError("--profiles contains a duplicate name")
    return profiles


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _ensure_new_targets(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        rendered = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"refusing to replace existing artifacts: {rendered}")


def _write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_csv_new(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _command_init(args: argparse.Namespace, stdout: TextIO) -> int:
    output = args.output_dir.expanduser().resolve()
    episodes_path = output / "episodes.csv"
    events_path = output / "events.csv"
    pairs_path = output / "pair_manifest.csv"
    protocol_path = output / "protocol.json"
    _ensure_new_targets([episodes_path, events_path, pairs_path, protocol_path])
    write_dataset(episodes_path, events_path, [], [])
    _write_csv_new(pairs_path, PAIR_MANIFEST_FIELDS, [])
    _write_json_new(
        protocol_path,
        {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": args.protocol_version,
            "created_at": _utc_now(),
            "ground_truth_event_kinds": ["added", "removed", "moved", "none"],
            "prediction_stages": ["local", "final"],
            "bbox_format": "x;y;width;height",
            "notes": [
                "Record none as expected_event_count=0 without a ground-truth event row.",
                "verify_removed is a local intermediate prediction, never final ground truth.",
                "Exclude warm-up, disconnect, and missing-baseline time from eligible monitoring seconds.",
            ],
        },
    )
    print(f"Created experiment workspace: {output}", file=stdout)
    return 0


def _command_validate(args: argparse.Namespace, stdout: TextIO) -> int:
    episodes = read_episodes(args.episodes)
    events = read_events(args.events)
    issues = validate_dataset(episodes, events)
    errors = [issue for issue in issues if issue.is_error]
    for issue in issues:
        print(str(issue), file=stdout)
    if errors:
        print(f"Invalid dataset: {len(errors)} error(s)", file=stdout)
        return 1
    print(
        f"Valid dataset: {len(episodes)} episodes, {len(events)} event rows",
        file=stdout,
    )
    return 0


def _command_run_pairs(args: argparse.Namespace, stdout: TextIO) -> int:
    manifest = args.manifest.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    profiles = _parse_profiles(args.profiles)
    overrides = _load_json_object(args.config_json)
    trials = read_pair_manifest(manifest)
    dataset = build_pair_dataset(
        trials,
        manifest_dir=manifest.parent,
        run_id=args.run_id,
        profiles=profiles,
        protocol_version=args.protocol_version,
        config_overrides=overrides,
        device=args.device,
        os_version=args.os_version,
        camera_model=args.camera_model,
        software_version=args.software_version,
        operator=args.operator,
    )

    episodes_path = output / "episodes.csv"
    events_path = output / "events.csv"
    trials_path = output / "pair_trials.csv"
    metadata_path = output / "run_metadata.json"
    config_paths = [output / "configs" / f"{profile}.json" for profile in profiles]
    summary_paths = _summary_paths(output, "summary-local")
    _ensure_new_targets(
        [episodes_path, events_path, trials_path, metadata_path, *config_paths, *summary_paths]
    )
    write_dataset(episodes_path, events_path, dataset.episodes, dataset.events)
    fieldnames = _trial_fieldnames(dataset.trial_rows)
    _write_csv_new(trials_path, fieldnames, list(dataset.trial_rows))
    for profile, path in zip(profiles, config_paths):
        _write_json_new(path, dataset.configs[profile])
    _write_json_new(
        metadata_path,
        {
            "created_at": _utc_now(),
            "base_run_id": args.run_id,
            "protocol_version": args.protocol_version,
            "profiles": list(profiles),
            "profile_descriptions": {
                profile: PROFILE_DESCRIPTIONS[profile] for profile in profiles
            },
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "manifest_name": manifest.name,
            "trial_count": len(trials),
            "scoring": {
                "prediction_stage": "local",
                "iou_threshold": args.iou,
                "allowed_window_seconds": None,
            },
            "stable_pair_scope": (
                "local detector only; capture settling, callback, database, and VLM latency excluded"
            ),
        },
    )
    summaries = summarize_by_run(
        list(dataset.episodes),
        list(dataset.events),
        stage="local",
        iou_threshold=args.iou,
        allowed_window_seconds=None,
    )
    write_metric_tables(output, "summary-local", summaries)
    print(
        f"Completed {len(trials)} trials x {len(profiles)} profiles in {output}",
        file=stdout,
    )
    return 0


def _command_summarize(args: argparse.Namespace, stdout: TextIO) -> int:
    episodes = read_episodes(args.episodes)
    events = read_events(args.events)
    issues = validate_dataset(episodes, events)
    errors = [issue for issue in issues if issue.is_error]
    if errors:
        raise ValueError("dataset validation failed: " + "; ".join(str(item) for item in errors))
    summaries = summarize_by_run(
        episodes,
        events,
        stage=args.stage,
        iou_threshold=args.iou,
        allowed_window_seconds=args.window_seconds,
    )
    stem = args.stem or f"summary-{args.stage}"
    write_metric_tables(args.output_dir.expanduser().resolve(), stem, summaries)
    print(f"Wrote {len(summaries)} run summaries", file=stdout)
    return 0


def summarize_by_run(
    episodes,
    events,
    *,
    stage: str,
    iou_threshold: float,
    allowed_window_seconds: float | None,
) -> dict[str, DetectionMetrics]:
    run_ids = sorted({episode.run_id for episode in episodes})
    summaries: dict[str, DetectionMetrics] = {}
    for run_id in run_ids:
        run_episodes = [episode for episode in episodes if episode.run_id == run_id]
        run_events = [event for event in events if event.run_id == run_id]
        matched = match_events(
            run_episodes,
            run_events,
            iou_threshold=iou_threshold,
            allowed_window_seconds=allowed_window_seconds,
            prediction_stage=stage,  # type: ignore[arg-type]
        )
        summaries[run_id] = compute_detection_metrics(matched)
    return summaries


def _summary_paths(output: Path, stem: str) -> list[Path]:
    return [
        output / f"{stem}.json",
        output / f"{stem}-overall.csv",
        output / f"{stem}-by-kind.csv",
    ]


def write_metric_tables(
    output: Path,
    stem: str,
    summaries: dict[str, DetectionMetrics],
) -> None:
    paths = _summary_paths(output, stem)
    _ensure_new_targets(paths)
    payload = {
        "generated_at": _utc_now(),
        "runs": {
            run_id: _metrics_payload(metrics)
            for run_id, metrics in summaries.items()
        },
    }
    _write_json_new(paths[0], payload)
    overall_rows = [_overall_row(run_id, metrics) for run_id, metrics in summaries.items()]
    overall_fields = tuple(overall_rows[0]) if overall_rows else ("run_id",)
    _write_csv_new(paths[1], overall_fields, overall_rows)
    class_rows = [
        {
            "run_id": run_id,
            "prediction_stage": metrics.prediction_stage,
            **asdict(class_metric),
        }
        for run_id, metrics in summaries.items()
        for class_metric in metrics.by_kind.values()
    ]
    class_fields = tuple(class_rows[0]) if class_rows else ("run_id",)
    # Nested interval objects are expanded to stable scalar columns below.
    flattened = [_flatten_class_row(row) for row in class_rows]
    if flattened:
        class_fields = tuple(flattened[0])
    _write_csv_new(paths[2], class_fields, flattened)


def _metrics_payload(metrics: DetectionMetrics) -> dict[str, Any]:
    payload = _overall_row("", metrics)
    payload.pop("run_id", None)
    payload["by_kind"] = {
        name: asdict(value) for name, value in metrics.by_kind.items()
    }
    payload["bbox_iou"] = asdict(metrics.bbox_iou)
    payload["selected_event_latency_ms"] = asdict(metrics.selected_event_latency_ms)
    payload["provisional_db_latency_ms"] = asdict(metrics.provisional_db_latency_ms)
    payload["ai_round_trip_latency_ms"] = asdict(metrics.ai_round_trip_latency_ms)
    payload["final_commit_latency_ms"] = asdict(metrics.final_commit_latency_ms)
    return payload


def _overall_row(run_id: str, metrics: DetectionMetrics) -> dict[str, Any]:
    total_tp = sum(item.true_positives for item in metrics.by_kind.values())
    total_fp = sum(item.false_positives for item in metrics.by_kind.values())
    total_fn = sum(item.false_negatives for item in metrics.by_kind.values())
    return {
        "run_id": run_id,
        "prediction_stage": metrics.prediction_stage,
        "iou_threshold": metrics.iou_threshold,
        "allowed_window_seconds": metrics.allowed_window_seconds,
        "episode_count": metrics.episode_count,
        "ground_truth_event_count": metrics.ground_truth_event_count,
        "scored_prediction_count": metrics.scored_prediction_count,
        "ignored_prediction_count": metrics.ignored_prediction_count,
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "micro_precision": metrics.micro_precision,
        "micro_recall": metrics.micro_recall,
        "micro_f1": metrics.micro_f1,
        "macro_precision": metrics.macro_precision,
        "macro_recall": metrics.macro_recall,
        "macro_f1": metrics.macro_f1,
        "false_event_count": metrics.false_event_count,
        "none_episode_count": metrics.none_episode_count,
        "none_episode_false_trigger_count": metrics.none_episode_false_trigger_count,
        "none_episode_false_trigger_rate": metrics.none_episode_false_trigger_rate,
        "none_episode_false_trigger_ci_lower": (
            metrics.none_episode_false_trigger_interval.lower
            if metrics.none_episode_false_trigger_interval
            else None
        ),
        "none_episode_false_trigger_ci_upper": (
            metrics.none_episode_false_trigger_interval.upper
            if metrics.none_episode_false_trigger_interval
            else None
        ),
        "none_monitoring_hours": metrics.none_monitoring_hours,
        "false_events_per_hour": metrics.false_events_per_hour,
        "duplicate_prediction_count": metrics.duplicate_prediction_count,
        "moved_identity_scorable_count": metrics.moved_identity_scorable_count,
        "moved_id_preserved_count": metrics.moved_id_preserved_count,
        "moved_id_preservation_rate": metrics.moved_id_preservation_rate,
        "moved_id_preservation_ci_lower": (
            metrics.moved_id_preservation_interval.lower
            if metrics.moved_id_preservation_interval
            else None
        ),
        "moved_id_preservation_ci_upper": (
            metrics.moved_id_preservation_interval.upper
            if metrics.moved_id_preservation_interval
            else None
        ),
        "duplicate_id_created_count": metrics.duplicate_id_created_count,
        "duplicate_id_creation_rate": metrics.duplicate_id_creation_rate,
        "bbox_iou_count": metrics.bbox_iou.count,
        "bbox_iou_mean": metrics.bbox_iou.mean,
        "bbox_iou_p50": metrics.bbox_iou.p50,
        "bbox_iou_p95": metrics.bbox_iou.p95,
        "selected_event_latency_ms_count": metrics.selected_event_latency_ms.count,
        "selected_event_latency_ms_mean": metrics.selected_event_latency_ms.mean,
        "selected_event_latency_ms_p50": metrics.selected_event_latency_ms.p50,
        "selected_event_latency_ms_p95": metrics.selected_event_latency_ms.p95,
        "provisional_db_latency_ms_count": metrics.provisional_db_latency_ms.count,
        "provisional_db_latency_ms_p50": metrics.provisional_db_latency_ms.p50,
        "provisional_db_latency_ms_p95": metrics.provisional_db_latency_ms.p95,
        "ai_round_trip_latency_ms_count": metrics.ai_round_trip_latency_ms.count,
        "ai_round_trip_latency_ms_p50": metrics.ai_round_trip_latency_ms.p50,
        "ai_round_trip_latency_ms_p95": metrics.ai_round_trip_latency_ms.p95,
        "final_commit_latency_ms_count": metrics.final_commit_latency_ms.count,
        "final_commit_latency_ms_p50": metrics.final_commit_latency_ms.p50,
        "final_commit_latency_ms_p95": metrics.final_commit_latency_ms.p95,
    }


def _flatten_class_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    precision_interval = result.pop("precision_interval", None)
    recall_interval = result.pop("recall_interval", None)
    for prefix, interval in (
        ("precision", precision_interval),
        ("recall", recall_interval),
    ):
        result[f"{prefix}_ci_lower"] = (
            "" if not interval else interval.get("lower", "")
        )
        result[f"{prefix}_ci_upper"] = (
            "" if not interval else interval.get("upper", "")
        )
        result[f"{prefix}_ci_confidence"] = (
            "" if not interval else interval.get("confidence", "")
        )
    return result


def _trial_fieldnames(rows) -> tuple[str, ...]:
    preferred = (
        "run_id",
        "trial_id",
        "profile",
        "scenario",
        "lighting",
        "nuisance",
        "event_ground_truth",
        "bbox_ground_truth",
        "predicted_events_json",
        "prediction_count",
        "global_change_suppressed",
        "detection_latency_ms",
        "process_cpu_ms",
        "process_cpu_percent",
    )
    available = {key for row in rows for key in row}
    ordered = [key for key in preferred if key in available]
    ordered.extend(sorted(available.difference(ordered)))
    return tuple(ordered)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _command_init(args, output)
        if args.command == "validate":
            return _command_validate(args, output)
        if args.command == "run-pairs":
            return _command_run_pairs(args, output)
        if args.command == "summarize":
            return _command_summarize(args, output)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=errors)
        return 2
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
