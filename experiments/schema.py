from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


SCHEMA_VERSION = "1"

RecordRole = Literal["ground_truth", "prediction"]
EventStage = Literal["ground_truth", "local", "final"]
EventKind = Literal["added", "removed", "moved", "verify_removed"]
IssueSeverity = Literal["error", "warning"]

RECORD_ROLES = frozenset(("ground_truth", "prediction"))
EVENT_STAGES = frozenset(("ground_truth", "local", "final"))
EVENT_KINDS = frozenset(("added", "removed", "moved", "verify_removed"))
FINAL_EVENT_KINDS = frozenset(("added", "removed", "moved"))


EPISODE_CSV_FIELDS = (
    "schema_version",
    "run_id",
    "episode_id",
    "protocol_version",
    "started_at",
    "action_start_at",
    "action_end_at",
    "ended_at",
    "eligible_monitoring_seconds",
    "episode_complete",
    "device",
    "os_version",
    "camera_model",
    "software_version",
    "config_sha256",
    "scenario",
    "lighting",
    "nuisance",
    "expected_event_count",
    "callback_dropped_count",
    "camera_disconnect_seconds",
    "observed_monitor_fps",
    "cpu_avg_pct",
    "cpu_peak_pct",
    "rss_avg_mb",
    "rss_peak_mb",
    "temp_avg_c",
    "temp_peak_c",
    "remote_request_count",
    "upload_bytes",
    "estimated_cost_krw",
    "operator",
    "notes",
)

EVENT_CSV_FIELDS = (
    "schema_version",
    "run_id",
    "episode_id",
    "event_id",
    "pipeline_id",
    "record_role",
    "stage",
    "event_kind",
    "event_at",
    "object_id",
    "matched_item_id",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "frame_width",
    "frame_height",
    "confidence",
    "object_name",
    "category",
    "provisional_db_at",
    "ai_request_at",
    "ai_response_at",
    "final_commit_at",
    "ai_provider",
    "ai_model",
    "ai_action",
    "ai_name",
    "ai_category",
    "ai_confidence",
    "ai_uncertain",
    "abstained",
    "error_type",
    "notes",
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    table: Literal["episodes", "events", "dataset"]
    record_id: str = ""
    field: str = ""
    severity: IssueSeverity = "error"

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def __str__(self) -> str:
        location = self.table
        if self.record_id:
            location += f"[{self.record_id}]"
        if self.field:
            location += f".{self.field}"
        return f"{location}: {self.message} ({self.code})"


class RecordValidationError(ValueError):
    """Raised when a record cannot safely be written to the experiment log."""

    def __init__(self, issues: list[ValidationIssue] | tuple[ValidationIssue, ...]):
        self.issues = tuple(issue for issue in issues if issue.is_error)
        message = "; ".join(str(issue) for issue in self.issues)
        super().__init__(message or "Experiment record validation failed")


@dataclass(frozen=True, slots=True)
class EpisodeRecord:
    run_id: str
    episode_id: str
    started_at: str
    ended_at: str
    eligible_monitoring_seconds: float
    schema_version: str = SCHEMA_VERSION
    protocol_version: str = ""
    action_start_at: str = ""
    action_end_at: str = ""
    episode_complete: bool = True
    device: str = ""
    os_version: str = ""
    camera_model: str = ""
    software_version: str = ""
    config_sha256: str = ""
    scenario: str = ""
    lighting: str = ""
    nuisance: str = ""
    expected_event_count: int = 0
    callback_dropped_count: int = 0
    camera_disconnect_seconds: float = 0.0
    observed_monitor_fps: float | None = None
    cpu_avg_pct: float | None = None
    cpu_peak_pct: float | None = None
    rss_avg_mb: float | None = None
    rss_peak_mb: float | None = None
    temp_avg_c: float | None = None
    temp_peak_c: float | None = None
    remote_request_count: int = 0
    upload_bytes: int = 0
    estimated_cost_krw: float | None = None
    operator: str = ""
    notes: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return self.run_id, self.episode_id


@dataclass(frozen=True, slots=True)
class EventRecord:
    run_id: str
    episode_id: str
    event_id: str
    record_role: RecordRole
    stage: EventStage
    event_kind: EventKind
    event_at: str
    schema_version: str = SCHEMA_VERSION
    pipeline_id: str = ""
    object_id: str = ""
    matched_item_id: str = ""
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    confidence: float | None = None
    object_name: str = ""
    category: str = ""
    provisional_db_at: str = ""
    ai_request_at: str = ""
    ai_response_at: str = ""
    final_commit_at: str = ""
    ai_provider: str = ""
    ai_model: str = ""
    ai_action: str = ""
    ai_name: str = ""
    ai_category: str = ""
    ai_confidence: float | None = None
    ai_uncertain: bool | None = None
    abstained: bool = False
    error_type: str = ""
    notes: str = ""

    @property
    def episode_key(self) -> tuple[str, str]:
        return self.run_id, self.episode_id

    @property
    def key(self) -> tuple[str, str, str]:
        return self.run_id, self.episode_id, self.event_id

    @property
    def bbox(self) -> tuple[int, int, int, int] | None:
        values = (self.bbox_x, self.bbox_y, self.bbox_w, self.bbox_h)
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            return None
        return values  # type: ignore[return-value]


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and reject timezone-naive values."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset or Z suffix")
    return parsed


def format_iso8601(value: datetime) -> str:
    """Return a stable UTC representation suitable for the CSV files."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_id(*parts: object) -> str:
    return "/".join(str(part) for part in parts if part not in (None, ""))


def _issue(
    issues: list[ValidationIssue],
    *,
    code: str,
    message: str,
    table: Literal["episodes", "events", "dataset"],
    record_id: str,
    field: str = "",
    severity: IssueSeverity = "error",
) -> None:
    issues.append(
        ValidationIssue(
            code=code,
            message=message,
            table=table,
            record_id=record_id,
            field=field,
            severity=severity,
        )
    )


def _valid_identifier(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if len(value) > 128:
        return False
    return not any(unicodedata.category(char).startswith("C") for char in value)


def _validate_identifier(
    issues: list[ValidationIssue],
    *,
    value: object,
    table: Literal["episodes", "events"],
    record_id: str,
    field: str,
    required: bool,
) -> None:
    if value == "" and not required:
        return
    if not _valid_identifier(value):
        _issue(
            issues,
            code="invalid_id",
            message=(
                "must be a non-empty identifier of at most 128 characters "
                "without surrounding whitespace or control characters"
            ),
            table=table,
            record_id=record_id,
            field=field,
        )


def _validate_timestamp(
    issues: list[ValidationIssue],
    *,
    value: object,
    table: Literal["episodes", "events"],
    record_id: str,
    field: str,
    required: bool,
) -> datetime | None:
    if value == "" and not required:
        return None
    try:
        return parse_iso8601(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        _issue(
            issues,
            code="invalid_timestamp",
            message=str(exc),
            table=table,
            record_id=record_id,
            field=field,
        )
        return None


def _validate_finite_number(
    issues: list[ValidationIssue],
    *,
    value: object,
    table: Literal["episodes", "events"],
    record_id: str,
    field: str,
    minimum: float | None = None,
    maximum: float | None = None,
    optional: bool = True,
) -> None:
    if value is None and optional:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _issue(
            issues,
            code="invalid_number",
            message="must be a finite number",
            table=table,
            record_id=record_id,
            field=field,
        )
        return
    number = float(value)
    if not math.isfinite(number):
        _issue(
            issues,
            code="invalid_number",
            message="must be a finite number",
            table=table,
            record_id=record_id,
            field=field,
        )
    elif minimum is not None and number < minimum:
        _issue(
            issues,
            code="out_of_range",
            message=f"must be at least {minimum:g}",
            table=table,
            record_id=record_id,
            field=field,
        )
    elif maximum is not None and number > maximum:
        _issue(
            issues,
            code="out_of_range",
            message=f"must be at most {maximum:g}",
            table=table,
            record_id=record_id,
            field=field,
        )


def _validate_nonnegative_integer(
    issues: list[ValidationIssue],
    *,
    value: object,
    table: Literal["episodes", "events"],
    record_id: str,
    field: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _issue(
            issues,
            code="invalid_integer",
            message="must be a non-negative integer",
            table=table,
            record_id=record_id,
            field=field,
        )


def validate_episode(record: EpisodeRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = _record_id(record.run_id, record.episode_id)

    if record.schema_version != SCHEMA_VERSION:
        _issue(
            issues,
            code="unsupported_schema_version",
            message=f"expected schema version {SCHEMA_VERSION!r}",
            table="episodes",
            record_id=record_id,
            field="schema_version",
        )

    for field in ("run_id", "episode_id"):
        _validate_identifier(
            issues,
            value=getattr(record, field),
            table="episodes",
            record_id=record_id,
            field=field,
            required=True,
        )

    started = _validate_timestamp(
        issues,
        value=record.started_at,
        table="episodes",
        record_id=record_id,
        field="started_at",
        required=True,
    )
    ended = _validate_timestamp(
        issues,
        value=record.ended_at,
        table="episodes",
        record_id=record_id,
        field="ended_at",
        required=record.episode_complete,
    )
    action_start = _validate_timestamp(
        issues,
        value=record.action_start_at,
        table="episodes",
        record_id=record_id,
        field="action_start_at",
        required=False,
    )
    action_end = _validate_timestamp(
        issues,
        value=record.action_end_at,
        table="episodes",
        record_id=record_id,
        field="action_end_at",
        required=False,
    )

    ordered = [
        ("started_at", started),
        ("action_start_at", action_start),
        ("action_end_at", action_end),
        ("ended_at", ended),
    ]
    present = [(name, value) for name, value in ordered if value is not None]
    for (left_name, left), (right_name, right) in zip(present, present[1:]):
        if left > right:
            _issue(
                issues,
                code="timestamp_order",
                message=f"must not be earlier than {left_name}",
                table="episodes",
                record_id=record_id,
                field=right_name,
            )

    if not isinstance(record.episode_complete, bool):
        _issue(
            issues,
            code="invalid_boolean",
            message="must be true or false",
            table="episodes",
            record_id=record_id,
            field="episode_complete",
        )
    elif not record.episode_complete:
        _issue(
            issues,
            code="incomplete_episode",
            message="may be appended during collection but cannot be scored until finalized",
            table="episodes",
            record_id=record_id,
            field="episode_complete",
            severity="warning",
        )

    for field in (
        "expected_event_count",
        "callback_dropped_count",
        "remote_request_count",
        "upload_bytes",
    ):
        _validate_nonnegative_integer(
            issues,
            value=getattr(record, field),
            table="episodes",
            record_id=record_id,
            field=field,
        )

    for field in (
        "eligible_monitoring_seconds",
        "camera_disconnect_seconds",
        "observed_monitor_fps",
        "cpu_avg_pct",
        "cpu_peak_pct",
        "rss_avg_mb",
        "rss_peak_mb",
        "estimated_cost_krw",
    ):
        _validate_finite_number(
            issues,
            value=getattr(record, field),
            table="episodes",
            record_id=record_id,
            field=field,
            minimum=0.0,
            optional=field != "eligible_monitoring_seconds",
        )
    for field in ("temp_avg_c", "temp_peak_c"):
        _validate_finite_number(
            issues,
            value=getattr(record, field),
            table="episodes",
            record_id=record_id,
            field=field,
        )

    if started is not None and ended is not None:
        wall_seconds = max(0.0, (ended - started).total_seconds())
        for field in ("eligible_monitoring_seconds", "camera_disconnect_seconds"):
            value = getattr(record, field)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and float(value) > wall_seconds + 1e-6
            ):
                _issue(
                    issues,
                    code="duration_exceeds_episode",
                    message=f"must not exceed the {wall_seconds:g}s episode wall duration",
                    table="episodes",
                    record_id=record_id,
                    field=field,
                )
        eligible = record.eligible_monitoring_seconds
        disconnected = record.camera_disconnect_seconds
        if (
            isinstance(eligible, (int, float))
            and not isinstance(eligible, bool)
            and math.isfinite(float(eligible))
            and isinstance(disconnected, (int, float))
            and not isinstance(disconnected, bool)
            and math.isfinite(float(disconnected))
            and float(eligible) + float(disconnected) > wall_seconds + 1e-6
        ):
            _issue(
                issues,
                code="accounted_time_exceeds_episode",
                message="eligible monitoring plus camera disconnect time exceeds wall duration",
                table="episodes",
                record_id=record_id,
                field="eligible_monitoring_seconds",
            )

    if record.config_sha256:
        digest = record.config_sha256
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            _issue(
                issues,
                code="invalid_sha256",
                message="must contain exactly 64 hexadecimal characters",
                table="episodes",
                record_id=record_id,
                field="config_sha256",
            )
    return issues


def validate_event(record: EventRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = _record_id(record.run_id, record.episode_id, record.event_id)

    if record.schema_version != SCHEMA_VERSION:
        _issue(
            issues,
            code="unsupported_schema_version",
            message=f"expected schema version {SCHEMA_VERSION!r}",
            table="events",
            record_id=record_id,
            field="schema_version",
        )

    for field in ("run_id", "episode_id", "event_id"):
        _validate_identifier(
            issues,
            value=getattr(record, field),
            table="events",
            record_id=record_id,
            field=field,
            required=True,
        )
    for field in ("pipeline_id", "object_id", "matched_item_id"):
        _validate_identifier(
            issues,
            value=getattr(record, field),
            table="events",
            record_id=record_id,
            field=field,
            required=False,
        )

    if record.record_role not in RECORD_ROLES:
        _issue(
            issues,
            code="invalid_record_role",
            message=f"must be one of {sorted(RECORD_ROLES)}",
            table="events",
            record_id=record_id,
            field="record_role",
        )
    if record.stage not in EVENT_STAGES:
        _issue(
            issues,
            code="invalid_stage",
            message=f"must be one of {sorted(EVENT_STAGES)}",
            table="events",
            record_id=record_id,
            field="stage",
        )
    if record.event_kind not in EVENT_KINDS:
        _issue(
            issues,
            code="invalid_event_kind",
            message=f"must be one of {sorted(EVENT_KINDS)}",
            table="events",
            record_id=record_id,
            field="event_kind",
        )

    if record.record_role == "ground_truth" and record.stage != "ground_truth":
        _issue(
            issues,
            code="role_stage_mismatch",
            message="ground-truth records must use the ground_truth stage",
            table="events",
            record_id=record_id,
            field="stage",
        )
    if record.record_role == "prediction" and record.stage == "ground_truth":
        _issue(
            issues,
            code="role_stage_mismatch",
            message="prediction records must use the local or final stage",
            table="events",
            record_id=record_id,
            field="stage",
        )
    if record.record_role == "ground_truth" and record.event_kind == "verify_removed":
        _issue(
            issues,
            code="invalid_ground_truth_kind",
            message="verify_removed is an intermediate prediction, not ground truth",
            table="events",
            record_id=record_id,
            field="event_kind",
        )
    if record.stage == "final" and record.event_kind == "verify_removed":
        _issue(
            issues,
            code="invalid_final_kind",
            message="verify_removed cannot be used as a final event kind",
            table="events",
            record_id=record_id,
            field="event_kind",
        )

    _validate_timestamp(
        issues,
        value=record.event_at,
        table="events",
        record_id=record_id,
        field="event_at",
        required=True,
    )
    pipeline_times: list[tuple[str, datetime]] = []
    for field in (
        "provisional_db_at",
        "ai_request_at",
        "ai_response_at",
        "final_commit_at",
    ):
        parsed = _validate_timestamp(
            issues,
            value=getattr(record, field),
            table="events",
            record_id=record_id,
            field=field,
            required=False,
        )
        if parsed is not None:
            pipeline_times.append((field, parsed))
    for (left_name, left), (right_name, right) in zip(
        pipeline_times, pipeline_times[1:]
    ):
        if left > right:
            _issue(
                issues,
                code="timestamp_order",
                message=f"must not be earlier than {left_name}",
                table="events",
                record_id=record_id,
                field=right_name,
            )

    bbox_fields = ("bbox_x", "bbox_y", "bbox_w", "bbox_h")
    bbox_values = [getattr(record, field) for field in bbox_fields]
    if any(value is not None for value in bbox_values) and any(
        value is None for value in bbox_values
    ):
        _issue(
            issues,
            code="partial_bbox",
            message="bbox_x, bbox_y, bbox_w and bbox_h must be supplied together",
            table="events",
            record_id=record_id,
            field="bbox",
        )
    elif all(value is None for value in bbox_values):
        _issue(
            issues,
            code="missing_bbox",
            message="is structurally valid but cannot match at a positive IoU threshold",
            table="events",
            record_id=record_id,
            field="bbox",
            severity="warning",
        )
    elif all(value is not None for value in bbox_values):
        for field, value in zip(bbox_fields, bbox_values):
            if isinstance(value, bool) or not isinstance(value, int):
                _issue(
                    issues,
                    code="invalid_bbox",
                    message="bbox coordinates and dimensions must be integers",
                    table="events",
                    record_id=record_id,
                    field=field,
                )
        if all(isinstance(value, int) and not isinstance(value, bool) for value in bbox_values):
            if record.bbox_x < 0 or record.bbox_y < 0:  # type: ignore[operator]
                _issue(
                    issues,
                    code="invalid_bbox",
                    message="bbox origin must be non-negative",
                    table="events",
                    record_id=record_id,
                    field="bbox",
                )
            if record.bbox_w <= 0 or record.bbox_h <= 0:  # type: ignore[operator]
                _issue(
                    issues,
                    code="invalid_bbox",
                    message="bbox width and height must be positive",
                    table="events",
                    record_id=record_id,
                    field="bbox",
                )

    frame_values = (record.frame_width, record.frame_height)
    if (record.frame_width is None) != (record.frame_height is None):
        _issue(
            issues,
            code="partial_frame_size",
            message="frame_width and frame_height must be supplied together",
            table="events",
            record_id=record_id,
            field="frame_width",
        )
    elif all(value is not None for value in frame_values):
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in frame_values
        ):
            _issue(
                issues,
                code="invalid_frame_size",
                message="frame dimensions must be positive integers",
                table="events",
                record_id=record_id,
                field="frame_width",
            )
        elif record.bbox is not None:
            x, y, width, height = record.bbox
            if x + width > record.frame_width or y + height > record.frame_height:  # type: ignore[operator]
                _issue(
                    issues,
                    code="bbox_out_of_frame",
                    message="bbox must fit inside the declared frame dimensions",
                    table="events",
                    record_id=record_id,
                    field="bbox",
                )

    for field in ("confidence", "ai_confidence"):
        _validate_finite_number(
            issues,
            value=getattr(record, field),
            table="events",
            record_id=record_id,
            field=field,
            minimum=0.0,
            maximum=1.0,
        )
    for field in ("ai_uncertain", "abstained"):
        value = getattr(record, field)
        if value is not None and not isinstance(value, bool):
            _issue(
                issues,
                code="invalid_boolean",
                message="must be true, false or blank",
                table="events",
                record_id=record_id,
                field=field,
            )
    return issues
