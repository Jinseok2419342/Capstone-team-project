from __future__ import annotations

import csv
import os
import threading
from dataclasses import fields
from pathlib import Path
from typing import Iterable, Mapping, TypeVar

from .schema import (
    EPISODE_CSV_FIELDS,
    EVENT_CSV_FIELDS,
    EpisodeRecord,
    EventRecord,
    RecordValidationError,
    ValidationIssue,
    parse_iso8601,
    validate_episode,
    validate_event,
)


_WRITE_LOCK = threading.RLock()
_RecordT = TypeVar("_RecordT", EpisodeRecord, EventRecord)


class CsvFormatError(ValueError):
    """Raised for an incompatible header or a malformed CSV value."""


class DuplicateRecordError(ValueError):
    """Raised before append when an experiment identifier already exists."""


def _as_optional_int(value: str, field: str) -> int | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise CsvFormatError(f"{field} must be an integer, got {value!r}") from exc


def _as_required_int(value: str, field: str) -> int:
    parsed = _as_optional_int(value, field)
    if parsed is None:
        raise CsvFormatError(f"{field} must not be blank")
    return parsed


def _as_optional_float(value: str, field: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise CsvFormatError(f"{field} must be a number, got {value!r}") from exc


def _as_required_float(value: str, field: str) -> float:
    parsed = _as_optional_float(value, field)
    if parsed is None:
        raise CsvFormatError(f"{field} must not be blank")
    return parsed


def _as_optional_bool(value: str, field: str) -> bool | None:
    if value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise CsvFormatError(f"{field} must be true, false or blank, got {value!r}")


def _as_required_bool(value: str, field: str) -> bool:
    parsed = _as_optional_bool(value, field)
    if parsed is None:
        raise CsvFormatError(f"{field} must not be blank")
    return parsed


def _episode_from_row(row: Mapping[str, str]) -> EpisodeRecord:
    integer_fields = {
        "expected_event_count",
        "callback_dropped_count",
        "remote_request_count",
        "upload_bytes",
    }
    optional_float_fields = {
        "observed_monitor_fps",
        "cpu_avg_pct",
        "cpu_peak_pct",
        "rss_avg_mb",
        "rss_peak_mb",
        "temp_avg_c",
        "temp_peak_c",
        "estimated_cost_krw",
    }
    values: dict[str, object] = dict(row)
    for field in integer_fields:
        values[field] = _as_required_int(row[field], field)
    for field in optional_float_fields:
        values[field] = _as_optional_float(row[field], field)
    for field in ("eligible_monitoring_seconds", "camera_disconnect_seconds"):
        values[field] = _as_required_float(row[field], field)
    values["episode_complete"] = _as_required_bool(
        row["episode_complete"], "episode_complete"
    )
    return EpisodeRecord(**values)  # type: ignore[arg-type]


def _event_from_row(row: Mapping[str, str]) -> EventRecord:
    values: dict[str, object] = dict(row)
    for field in (
        "bbox_x",
        "bbox_y",
        "bbox_w",
        "bbox_h",
        "frame_width",
        "frame_height",
    ):
        values[field] = _as_optional_int(row[field], field)
    for field in ("confidence", "ai_confidence"):
        values[field] = _as_optional_float(row[field], field)
    values["ai_uncertain"] = _as_optional_bool(row["ai_uncertain"], "ai_uncertain")
    values["abstained"] = _as_required_bool(row["abstained"], "abstained")
    return EventRecord(**values)  # type: ignore[arg-type]


def _record_to_row(record: _RecordT, field_names: tuple[str, ...]) -> dict[str, object]:
    available = {field.name for field in fields(record)}
    if available != set(field_names):
        missing = sorted(set(field_names) - available)
        extra = sorted(available - set(field_names))
        raise CsvFormatError(f"record/header mismatch; missing={missing}, extra={extra}")
    result: dict[str, object] = {}
    for field in field_names:
        value = getattr(record, field)
        if value is None:
            result[field] = ""
        elif isinstance(value, bool):
            result[field] = "true" if value else "false"
        else:
            result[field] = value
    return result


def _read_rows(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual = tuple(reader.fieldnames or ())
            if actual != expected_fields:
                raise CsvFormatError(
                    f"unexpected CSV header in {path}: expected {expected_fields}, got {actual}"
                )
            rows: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise CsvFormatError(
                        f"row {line_number} in {path} has more values than the header"
                    )
                if any(value is None for value in row.values()):
                    raise CsvFormatError(
                        f"row {line_number} in {path} has fewer values than the header"
                    )
                rows.append(dict(row))  # type: ignore[arg-type]
            return rows
    except UnicodeDecodeError as exc:
        raise CsvFormatError(f"{path} is not valid UTF-8 CSV") from exc


def read_episodes(path: str | Path) -> list[EpisodeRecord]:
    csv_path = Path(path)
    records: list[EpisodeRecord] = []
    for line_number, row in enumerate(_read_rows(csv_path, EPISODE_CSV_FIELDS), start=2):
        try:
            record = _episode_from_row(row)
        except (CsvFormatError, TypeError) as exc:
            raise CsvFormatError(f"invalid episode row {line_number}: {exc}") from exc
        issues = validate_episode(record)
        if any(issue.is_error for issue in issues):
            raise RecordValidationError(issues)
        records.append(record)
    return records


def read_events(path: str | Path) -> list[EventRecord]:
    csv_path = Path(path)
    records: list[EventRecord] = []
    for line_number, row in enumerate(_read_rows(csv_path, EVENT_CSV_FIELDS), start=2):
        try:
            record = _event_from_row(row)
        except (CsvFormatError, TypeError) as exc:
            raise CsvFormatError(f"invalid event row {line_number}: {exc}") from exc
        issues = validate_event(record)
        if any(issue.is_error for issue in issues):
            raise RecordValidationError(issues)
        records.append(record)
    return records


def _validate_existing_header(path: Path, expected_fields: tuple[str, ...]) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    actual = tuple(header)
    if actual != expected_fields:
        raise CsvFormatError(
            f"unexpected CSV header in {path}: expected {expected_fields}, got {actual}"
        )


def _append_rows(
    path: Path,
    field_names: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    mode = "w" if needs_header else "a"
    with path.open(mode, encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, lineterminator="\n")
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def _write_new_rows(
    path: Path,
    field_names: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    """Create one complete CSV and refuse to replace an existing artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def append_episode(path: str | Path, record: EpisodeRecord) -> None:
    issues = validate_episode(record)
    if any(issue.is_error for issue in issues):
        raise RecordValidationError(issues)
    csv_path = Path(path)
    with _WRITE_LOCK:
        _validate_existing_header(csv_path, EPISODE_CSV_FIELDS)
        if csv_path.exists() and csv_path.stat().st_size:
            if any(existing.key == record.key for existing in read_episodes(csv_path)):
                raise DuplicateRecordError(
                    f"episode {record.run_id}/{record.episode_id} already exists"
                )
        _append_rows(
            csv_path,
            EPISODE_CSV_FIELDS,
            [_record_to_row(record, EPISODE_CSV_FIELDS)],
        )


def append_events(
    path: str | Path,
    records: Iterable[EventRecord],
    *,
    episodes_path: str | Path | None = None,
) -> None:
    pending = list(records)
    issues = [issue for record in pending for issue in validate_event(record)]
    if any(issue.is_error for issue in issues):
        raise RecordValidationError(issues)

    pending_keys = [record.key for record in pending]
    if len(set(pending_keys)) != len(pending_keys):
        raise DuplicateRecordError("event batch contains a duplicate event ID")

    if episodes_path is not None:
        episode_keys = {record.key for record in read_episodes(episodes_path)}
        missing = sorted({record.episode_key for record in pending} - episode_keys)
        if missing:
            rendered = ", ".join(f"{run_id}/{episode_id}" for run_id, episode_id in missing)
            raise ValueError(f"events reference unknown episodes: {rendered}")

    if not pending:
        return

    csv_path = Path(path)
    with _WRITE_LOCK:
        _validate_existing_header(csv_path, EVENT_CSV_FIELDS)
        if csv_path.exists() and csv_path.stat().st_size:
            existing_keys = {record.key for record in read_events(csv_path)}
            duplicates = sorted(existing_keys.intersection(pending_keys))
            if duplicates:
                rendered = ", ".join("/".join(key) for key in duplicates)
                raise DuplicateRecordError(f"events already exist: {rendered}")
        _append_rows(
            csv_path,
            EVENT_CSV_FIELDS,
            [_record_to_row(record, EVENT_CSV_FIELDS) for record in pending],
        )


def validate_dataset(
    episodes: Iterable[EpisodeRecord], events: Iterable[EventRecord]
) -> list[ValidationIssue]:
    episode_records = list(episodes)
    event_records = list(events)
    issues = [issue for record in episode_records for issue in validate_episode(record)]
    issues.extend(issue for record in event_records for issue in validate_event(record))

    episode_keys: set[tuple[str, str]] = set()
    episode_by_key: dict[tuple[str, str], EpisodeRecord] = {}
    for record in episode_records:
        if record.key in episode_keys:
            issues.append(
                ValidationIssue(
                    code="duplicate_episode_id",
                    message="run_id/episode_id pair must be unique",
                    table="dataset",
                    record_id="/".join(record.key),
                )
            )
        episode_keys.add(record.key)
        episode_by_key.setdefault(record.key, record)

    event_keys: set[tuple[str, str, str]] = set()
    ground_truth_counts: dict[tuple[str, str], int] = {}
    for record in event_records:
        if record.key in event_keys:
            issues.append(
                ValidationIssue(
                    code="duplicate_event_id",
                    message="event_id must be unique within an episode",
                    table="dataset",
                    record_id="/".join(record.key),
                )
            )
        event_keys.add(record.key)
        if record.episode_key not in episode_keys:
            issues.append(
                ValidationIssue(
                    code="orphan_event",
                    message="event references an episode that does not exist",
                    table="dataset",
                    record_id="/".join(record.key),
                )
            )
        if record.record_role == "ground_truth":
            ground_truth_counts[record.episode_key] = (
                ground_truth_counts.get(record.episode_key, 0) + 1
            )

        episode = episode_by_key.get(record.episode_key)
        if episode is not None:
            try:
                episode_start = parse_iso8601(episode.started_at)
                lower_bound = (
                    parse_iso8601(episode.action_end_at)
                    if record.record_role == "prediction" and episode.action_end_at
                    else episode_start
                )
                episode_end = (
                    parse_iso8601(episode.ended_at) if episode.ended_at else None
                )
            except (TypeError, ValueError):
                lower_bound = None
                episode_end = None
            if lower_bound is not None:
                for field in (
                    "event_at",
                    "provisional_db_at",
                    "ai_request_at",
                    "ai_response_at",
                    "final_commit_at",
                ):
                    raw_timestamp = getattr(record, field)
                    if not raw_timestamp:
                        continue
                    try:
                        timestamp = parse_iso8601(raw_timestamp)
                    except (TypeError, ValueError):
                        continue
                    if timestamp < lower_bound:
                        issues.append(
                            ValidationIssue(
                                code="timestamp_before_episode_window",
                                message=(
                                    "prediction timestamps must not precede action_end_at"
                                    if record.record_role == "prediction"
                                    and episode.action_end_at
                                    else "timestamp must not precede started_at"
                                ),
                                table="dataset",
                                record_id="/".join(record.key),
                                field=field,
                            )
                        )
                    if episode_end is not None and timestamp > episode_end:
                        issues.append(
                            ValidationIssue(
                                code="timestamp_after_episode",
                                message="timestamp must not follow ended_at",
                                table="dataset",
                                record_id="/".join(record.key),
                                field=field,
                            )
                        )

    for record in episode_records:
        actual = ground_truth_counts.get(record.key, 0)
        if actual != record.expected_event_count:
            issues.append(
                ValidationIssue(
                    code="ground_truth_count_mismatch",
                    message=(
                        f"expected_event_count is {record.expected_event_count}, "
                        f"but {actual} ground-truth event rows were found"
                    ),
                    table="dataset",
                    record_id="/".join(record.key),
                    field="expected_event_count",
                )
            )
    return issues


def write_dataset(
    episodes_path: str | Path,
    events_path: str | Path,
    episodes: Iterable[EpisodeRecord],
    events: Iterable[EventRecord],
) -> None:
    """Validate and write a new two-table dataset without quadratic appends.

    Both targets must be new files.  Event headers are still created when a
    dataset contains only no-event episodes, which keeps later validation and
    summarisation commands deterministic.
    """

    episode_records = list(episodes)
    event_records = list(events)
    issues = validate_dataset(episode_records, event_records)
    errors = [issue for issue in issues if issue.is_error]
    if errors:
        raise RecordValidationError(errors)

    episode_csv = Path(episodes_path)
    event_csv = Path(events_path)
    if episode_csv.resolve() == event_csv.resolve():
        raise ValueError("episode and event CSV paths must be different")
    existing = [path for path in (episode_csv, event_csv) if path.exists()]
    if existing:
        rendered = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"refusing to replace existing experiment files: {rendered}")

    _write_new_rows(
        episode_csv,
        EPISODE_CSV_FIELDS,
        [_record_to_row(record, EPISODE_CSV_FIELDS) for record in episode_records],
    )
    _write_new_rows(
        event_csv,
        EVENT_CSV_FIELDS,
        [_record_to_row(record, EVENT_CSV_FIELDS) for record in event_records],
    )
