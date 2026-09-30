"""Small, thread-safe SQLite persistence layer for the lost-item service.

The store deliberately opens a fresh SQLite connection for every operation.  A
``Store`` instance can therefore be shared by the camera, scheduler and web
server threads without sharing a connection between them.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


CATEGORY_RETENTION_DAYS = {
    "valuable": 90,
    "general": 60,
    "food": 1,
}
ITEM_STATUSES = frozenset({"stored", "due", "recovered", "disposed"})
REVIEW_STATUSES = frozenset({"pending", "needs_review", "confirmed", "dismissed"})
ITEM_SOURCE_KINDS = frozenset({"camera", "demo", "manual"})
NOTIFICATION_STATUSES = frozenset({"pending", "sent", "failed"})


def classify_retention(category: str) -> int:
    """Return the default retention period for an item category."""

    normalized = str(category).strip().lower()
    try:
        return CATEGORY_RETENTION_DAYS[normalized]
    except KeyError as exc:
        allowed = ", ".join(CATEGORY_RETENTION_DAYS)
        raise ValueError(f"category must be one of: {allowed}") from exc


def _as_utc(value: datetime | str, *, field: str = "datetime") -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    else:
        raise TypeError(f"{field} must be a datetime or ISO-8601 string")

    # A naive timestamp is treated as UTC.  This keeps the storage API useful
    # for OpenCV workers while ensuring that every persisted value is explicit.
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _iso_utc(value: datetime | str) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _serialize_bbox(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise ValueError("bbox_json must contain valid JSON") from exc
    return _json_dumps(value)


def _serialize_ai_raw(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return _json_dumps(value)


def _legacy_review_status(provider: Any) -> str:
    """Interpret historical provider labels only at the compatibility boundary."""

    normalized = str(provider or "").strip().lower()
    if normalized == "pending":
        return "pending"
    if normalized == "offline" or normalized.endswith("_review"):
        return "needs_review"
    return "confirmed"


def _review_status(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized not in REVIEW_STATUSES:
        raise ValueError("invalid item review status")
    return normalized


class Store:
    """SQLite-backed repository.

    Call :meth:`initialize` once at application startup.  All public methods
    return ordinary dictionaries/lists so they can be sent directly through a
    JSON API (apart from the intentionally raw ``bbox_json`` compatibility
    field; the parsed value is exposed as ``bbox``).
    """

    _ITEM_UPDATE_FIELDS = frozenset(
        {
            "name",
            "description",
            "category",
            "retention_days",
            "detected_at",
            "expires_at",
            "status",
            "recovered_at",
            "bbox_json",
            "confidence",
            "image_path",
            "background_path",
            "provider",
            "review_status",
            "review_reason",
            "ai_raw",
        }
    )

    def __init__(self, db_path: str | os.PathLike[str]):
        self.db_path = os.fspath(db_path)
        self._maintenance_condition = threading.Condition()
        self._maintenance_active = False
        self._maintenance_owner: int | None = None
        self._active_operations = 0

    @contextmanager
    def maintenance_window(self) -> Iterator[None]:
        """Prevent Store operations from interleaving with maintenance work."""

        owner = threading.get_ident()
        with self._maintenance_condition:
            while self._maintenance_active or self._active_operations:
                self._maintenance_condition.wait()
            self._maintenance_active = True
            self._maintenance_owner = owner
        try:
            yield
        finally:
            with self._maintenance_condition:
                self._maintenance_active = False
                self._maintenance_owner = None
                self._maintenance_condition.notify_all()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        owner_operation = False
        current_thread = threading.get_ident()
        with self._maintenance_condition:
            while (
                self._maintenance_active
                and self._maintenance_owner != current_thread
            ):
                self._maintenance_condition.wait()
            if self._maintenance_owner == current_thread:
                owner_operation = True
            else:
                self._active_operations += 1

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                check_same_thread=True,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
        finally:
            if connection is not None:
                connection.close()
            if not owner_operation:
                with self._maintenance_condition:
                    self._active_operations -= 1
                    if self._active_operations == 0:
                        self._maintenance_condition.notify_all()

    def initialize(self) -> None:
        """Create the database and schema if they do not already exist."""

        if self.db_path != ":memory:" and not self.db_path.startswith("file:"):
            Path(self.db_path).expanduser().resolve().parent.mkdir(
                parents=True, exist_ok=True
            )

        with self._connection() as connection:
            # WAL gives the web dashboard responsive reads while a camera worker
            # writes an observation.  SQLite ignores this for in-memory DBs.
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT NOT NULL,
                    description     TEXT NOT NULL DEFAULT '',
                    category        TEXT NOT NULL
                                    CHECK (category IN ('valuable','general','food')),
                    retention_days  INTEGER NOT NULL CHECK (retention_days > 0),
                    detected_at     TEXT NOT NULL,
                    expires_at      TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'stored'
                                    CHECK (status IN ('stored','due','recovered','disposed')),
                    recovered_at    TEXT,
                    bbox_json       TEXT,
                    confidence      REAL,
                    image_path      TEXT,
                    background_path TEXT,
                    provider        TEXT,
                    review_status   TEXT NOT NULL DEFAULT 'confirmed'
                                    CHECK (review_status IN ('pending','needs_review','confirmed','dismissed')),
                    review_reason   TEXT,
                    source_kind     TEXT NOT NULL DEFAULT 'manual'
                                    CHECK (source_kind IN ('camera','demo','manual')),
                    source_event_id TEXT,
                    tracking_revision INTEGER NOT NULL DEFAULT 0,
                    ai_raw          TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_items_status_expires
                    ON items(status, expires_at);
                CREATE INDEX IF NOT EXISTS idx_items_detected
                    ON items(detected_at DESC);

                CREATE TABLE IF NOT EXISTS activities (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    type            TEXT NOT NULL,
                    message         TEXT NOT NULL,
                    item_id         INTEGER,
                    metadata_json   TEXT,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_activities_created
                    ON activities(created_at DESC);

                CREATE TABLE IF NOT EXISTS notifications (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    type            TEXT NOT NULL,
                    message         TEXT NOT NULL DEFAULT '',
                    item_id         INTEGER,
                    status          TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending','sent','failed')),
                    scheduled_for   TEXT NOT NULL,
                    sent_at         TEXT,
                    failed_at       TEXT,
                    error           TEXT,
                    metadata_json   TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    delivery_token  TEXT,
                    delivery_lease_until TEXT,
                    FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_notifications_status_schedule
                    ON notifications(status, scheduled_for);
                -- The original index deduplicated an item forever.  Drop it
                -- during every idempotent initialization so existing databases
                -- gain expiry-cycle-aware notification semantics.
                DROP INDEX IF EXISTS uq_disposal_due_per_item;
                CREATE UNIQUE INDEX IF NOT EXISTS uq_disposal_due_per_item_schedule
                    ON notifications(item_id, type, scheduled_for)
                    WHERE item_id IS NOT NULL AND type = 'disposal_due';

                CREATE TABLE IF NOT EXISTS settings (
                    key             TEXT PRIMARY KEY,
                    value_json      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );
                """
            )
            # Serialize check-and-add migrations when multiple workers start.
            connection.execute("BEGIN IMMEDIATE")
            item_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(items)").fetchall()
            }
            if "background_path" not in item_columns:
                connection.execute("ALTER TABLE items ADD COLUMN background_path TEXT")
            if "review_status" not in item_columns:
                connection.execute(
                    "ALTER TABLE items ADD COLUMN review_status TEXT NOT NULL "
                    "DEFAULT 'confirmed' CHECK (review_status IN "
                    "('pending','needs_review','confirmed','dismissed'))"
                )
                connection.execute(
                    """
                    UPDATE items SET review_status = CASE
                        WHEN lower(trim(coalesce(provider, ''))) = 'pending' THEN 'pending'
                        WHEN lower(trim(coalesce(provider, ''))) = 'offline'
                          OR substr(lower(trim(coalesce(provider, ''))), -7) = '_review'
                        THEN 'needs_review' ELSE 'confirmed' END
                    """
                )
            if "review_reason" not in item_columns:
                connection.execute("ALTER TABLE items ADD COLUMN review_reason TEXT")
            if "source_kind" not in item_columns:
                connection.execute(
                    "ALTER TABLE items ADD COLUMN source_kind TEXT NOT NULL "
                    "DEFAULT 'manual' CHECK (source_kind IN ('camera','demo','manual'))"
                )
                connection.execute(
                    """
                    UPDATE items SET source_kind = CASE
                        WHEN lower(trim(coalesce(provider, ''))) = 'demo'
                          OR ai_raw = 'built-in deterministic presentation preset'
                        THEN 'demo'
                        WHEN bbox_json IS NOT NULL THEN 'camera'
                        ELSE 'manual' END
                    """
                )
            if "source_event_id" not in item_columns:
                connection.execute("ALTER TABLE items ADD COLUMN source_event_id TEXT")
            if "tracking_revision" not in item_columns:
                connection.execute(
                    "ALTER TABLE items ADD COLUMN tracking_revision INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_items_source_event "
                "ON items(source_event_id) WHERE source_event_id IS NOT NULL"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_review_detected "
                "ON items(review_status, detected_at DESC, id DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_category_detected "
                "ON items(category, detected_at DESC, id DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_name "
                "ON items(name COLLATE NOCASE, id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_expires "
                "ON items(expires_at, id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_source_detected "
                "ON items(source_kind, detected_at DESC, id DESC)"
            )
            notification_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(notifications)")
            }
            for column in ("delivery_token", "delivery_lease_until"):
                if column not in notification_columns:
                    connection.execute(f"ALTER TABLE notifications ADD COLUMN {column} TEXT")
            connection.commit()

    def backup_to(self, destination: str | os.PathLike[str]) -> Path:
        """Create a transactionally consistent SQLite backup.

        SQLite's online backup API also includes committed WAL pages, unlike a
        plain file copy.  Refusing to overwrite an existing file makes reset
        snapshots append-only from the application's point of view.
        """

        destination_path = Path(destination).expanduser().resolve()
        if destination_path.exists():
            raise FileExistsError(f"backup already exists: {destination_path}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as source:
            with closing(sqlite3.connect(destination_path)) as target:
                source.backup(target)
                target.commit()
        return destination_path

    def reset_operational_data(self) -> dict[str, int]:
        """Delete runtime records atomically while preserving settings.

        This method intentionally does not create an activity after the reset:
        an initialization is expected to leave all three operational tables
        empty.  The caller must create a backup before invoking it.
        """

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            counts = {
                "items": int(
                    connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
                ),
                "activities": int(
                    connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
                ),
                "notifications": int(
                    connection.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
                ),
                "settings_preserved": int(
                    connection.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
                ),
            }
            # Child rows are deleted first so this remains correct if foreign
            # key actions become stricter in a future migration.
            connection.execute("DELETE FROM notifications")
            connection.execute("DELETE FROM activities")
            connection.execute("DELETE FROM items")
            # Keep AUTOINCREMENT sequences. Reusing an item id would also
            # reuse /api/items/<id>/image, allowing a browser or intermediary
            # cache to associate an old capture with a newly detected item.
            connection.commit()
        return counts

    @staticmethod
    def _item_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        item["bbox"] = _safe_json_loads(item.get("bbox_json"))
        return item

    @staticmethod
    def _activity_from_row(row: sqlite3.Row) -> dict[str, Any]:
        activity = dict(row)
        activity["metadata"] = _safe_json_loads(activity.get("metadata_json"), {})
        return activity

    @staticmethod
    def _notification_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        notification = dict(row)
        # Delivery ownership is internal and must not appear in dashboard data.
        notification.pop("delivery_token", None)
        notification.pop("delivery_lease_until", None)
        notification["metadata"] = _safe_json_loads(
            notification.get("metadata_json"), {}
        )
        return notification

    def create_item(self, data: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")

        category = str(data.get("category", "general")).strip().lower()
        default_retention = classify_retention(category)
        retention_days = int(data.get("retention_days", default_retention))
        if retention_days <= 0:
            raise ValueError("retention_days must be positive")

        detected_dt = _as_utc(data.get("detected_at", _utc_now()), field="detected_at")
        if data.get("expires_at") is None:
            expires_dt = detected_dt + timedelta(days=retention_days)
        else:
            expires_dt = _as_utc(data["expires_at"], field="expires_at")

        status = str(data.get("status", "stored")).strip().lower()
        if status not in ITEM_STATUSES:
            raise ValueError("invalid item status")
        source_kind = str(data.get("source_kind", "manual")).strip().lower()
        if source_kind not in ITEM_SOURCE_KINDS:
            raise ValueError("invalid item source kind")

        now = _iso_utc(_utc_now())
        recovered_at = data.get("recovered_at")
        if recovered_at is None and status == "recovered":
            recovered_at = now
        elif recovered_at is not None:
            recovered_at = _iso_utc(recovered_at)

        bbox_value = data.get("bbox", data.get("bbox_json"))
        values = {
            "name": str(data.get("name") or "알 수 없는 물건").strip(),
            "description": str(data.get("description") or ""),
            "category": category,
            "retention_days": retention_days,
            "detected_at": _iso_utc(detected_dt),
            "expires_at": _iso_utc(expires_dt),
            "status": status,
            "recovered_at": recovered_at,
            "bbox_json": _serialize_bbox(bbox_value),
            "confidence": data.get("confidence"),
            "image_path": data.get("image_path"),
            "background_path": data.get("background_path"),
            "provider": data.get("provider"),
            "review_status": _review_status(
                data.get("review_status", _legacy_review_status(data.get("provider")))
            ),
            "review_reason": data.get("review_reason"),
            "source_kind": source_kind,
            "source_event_id": str(data["source_event_id"]).strip() or None
                if data.get("source_event_id") is not None else None,
            "ai_raw": _serialize_ai_raw(data.get("ai_raw")),
            "created_at": now,
            "updated_at": now,
        }

        columns = tuple(values)
        placeholders = ",".join("?" for _ in columns)
        with self._connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO items ({','.join(columns)}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
            item_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            connection.commit()
        return self._item_from_row(row)  # type: ignore[return-value]

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (int(item_id),)
            ).fetchone()
        return self._item_from_row(row)

    def get_item_by_source_event(self, event_id: str) -> dict[str, Any] | None:
        normalized = str(event_id).strip()
        if not normalized:
            return None
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM items WHERE source_event_id = ?", (normalized,)
            ).fetchone()
        return self._item_from_row(row)

    def list_active_items(self) -> list[dict[str, Any]]:
        """Return every trackable item, independent of dashboard history limits."""

        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM items WHERE status IN ('stored', 'due') "
                "AND review_status != 'dismissed' "
                "AND source_kind != 'demo' "
                "AND bbox_json IS NOT NULL ORDER BY detected_at DESC, id DESC"
            ).fetchall()
        return [self._item_from_row(row) for row in rows]  # type: ignore[misc]

    def list_active_demo_items(self, limit: int = 1) -> list[dict[str, Any]]:
        """Return presentation records without risking real inventory actions."""

        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM items WHERE source_kind = 'demo' "
                "AND status IN ('stored', 'due') AND review_status != 'dismissed' "
                "ORDER BY detected_at DESC, id DESC LIMIT ?",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [self._item_from_row(row) for row in rows]  # type: ignore[misc]

    def item_stats(
        self, now: datetime | str | None = None, lead_days: int = 7
    ) -> dict[str, int]:
        """Count the complete inventory rather than a page of recent records."""

        now_dt = _as_utc(now or _utc_now(), field="now")
        deadline = now_dt + timedelta(days=max(0, int(lead_days)))
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(CASE WHEN status = 'stored' AND expires_at > ? THEN 1 END) AS active,
                       COUNT(CASE WHEN status = 'stored'
                                   AND expires_at > ? AND expires_at <= ?
                                  THEN 1 END) AS due_soon,
                       COUNT(CASE WHEN status = 'due'
                                   OR (status = 'stored' AND expires_at <= ?) THEN 1 END) AS expired,
                       COUNT(CASE WHEN status = 'recovered' THEN 1 END) AS recovered,
                       COUNT(CASE WHEN review_status = 'needs_review'
                                   AND status IN ('stored', 'due') THEN 1 END) AS review_needed
                  FROM items WHERE review_status != 'dismissed'
                """,
                (_iso_utc(now_dt), _iso_utc(now_dt), _iso_utc(deadline), _iso_utc(now_dt)),
            ).fetchone()
        return {key: int(row[key]) for key in ("active", "due_soon", "expired", "recovered", "review_needed")}

    def mark_interrupted_classifications(self) -> int:
        """At startup, retain abandoned provisional rows for manual review.

        Call before starting classification workers. In-memory jobs cannot be
        resumed after a process restart, so leaving these rows as ``pending``
        would display an analysis spinner permanently.
        """

        now = _iso_utc(_utc_now())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT id FROM items WHERE review_status = 'pending'"
            ).fetchall()
            connection.execute(
                """
                UPDATE items
                   SET provider = 'offline_review', name = ?, description = ?,
                       ai_raw = ?, updated_at = ?, review_status = 'needs_review',
                       review_reason = 'interrupted'
                 WHERE review_status = 'pending'
                """,
                (
                    "확인 필요한 새 물품",
                    "앱이 재시작되어 AI 분석이 중단되었습니다. 감지 기록을 확인해 주세요.",
                    "classification interrupted by restart",
                    now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO activities(type, message, item_id, created_at)
                VALUES ('classification_interrupted', ?, ?, ?)
                """,
                [
                    ("앱 재시작으로 중단된 AI 분석을 확인 필요 상태로 전환했습니다.", row["id"], now)
                    for row in rows
                ],
            )
            connection.commit()
        return len(rows)

    def list_items(
        self,
        status: str | None = None,
        q: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if status is not None:
            normalized_status = str(status).strip().lower()
            if normalized_status not in ITEM_STATUSES:
                raise ValueError("invalid item status")
            clauses.append("status = ?")
            parameters.append(normalized_status)
        if q is not None and str(q).strip():
            needle = f"%{str(q).strip()}%"
            clauses.append(
                "(name LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE "
                "OR category LIKE ? COLLATE NOCASE)"
            )
            parameters.extend((needle, needle, needle))

        safe_limit = max(1, min(int(limit), 1000))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(safe_limit)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM items{where} "
                "ORDER BY detected_at DESC, id DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [self._item_from_row(row) for row in rows]  # type: ignore[misc]

    def list_items_page(
        self,
        status: str | None = None,
        q: str | None = None,
        category: str | None = None,
        sort: str = "newest",
        limit: int = 48,
        offset: int = 0,
        review: str | None = None,
        now: datetime | str | None = None,
        lead_days: int = 7,
    ) -> dict[str, Any]:
        """Filter and sort the complete inventory before selecting one page.

        Effective expiry filters include stored rows whose scheduler transition
        has not happened yet. Raw ``stored``/``due`` filters remain available.
        Dismissed evidence is visible only when explicitly requested. Count and
        rows share a read snapshot, including when the requested offset is
        clamped after an item disappears from the final page.
        """

        normalized_status = str(status or "").strip().lower()
        normalized_category = str(category or "").strip().lower()
        normalized_review = str(review or "").strip().lower()
        normalized_sort = str(sort).strip().lower()
        orderings = {
            "newest": "detected_at DESC, id DESC",
            "expiring": "expires_at ASC, id ASC",
            "name": "name COLLATE NOCASE ASC, id ASC",
        }
        if normalized_sort not in orderings:
            raise ValueError("invalid item sort")
        allowed_statuses = ITEM_STATUSES | {"", "all", "active", "holding", "due_soon", "expired", "dismissed", "attention"}
        if normalized_status not in allowed_statuses:
            raise ValueError("invalid item status")
        if normalized_category and normalized_category not in CATEGORY_RETENTION_DAYS:
            raise ValueError("invalid item category")
        if normalized_review and normalized_review not in REVIEW_STATUSES:
            raise ValueError("invalid item review status")
        safe_limit = max(1, min(int(limit), 100))
        requested_offset = max(0, int(offset))
        now_dt = _as_utc(now or _utc_now(), field="now")
        now_value = _iso_utc(now_dt)
        deadline = _iso_utc(now_dt + timedelta(days=max(0, int(lead_days))))
        clauses: list[str] = []
        parameters: list[Any] = []
        if normalized_status == "dismissed":
            clauses.append("review_status = 'dismissed'")
        elif normalized_review != "dismissed":
            clauses.append("review_status != 'dismissed'")
        if normalized_status in ITEM_STATUSES:
            clauses.append("status = ?")
            parameters.append(normalized_status)
        elif normalized_status == "holding":
            clauses.append("status IN ('stored', 'due')")
        elif normalized_status == "active":
            clauses.append("status = 'stored' AND expires_at > ?")
            parameters.append(now_value)
        elif normalized_status == "due_soon":
            clauses.append("status = 'stored' AND expires_at > ? AND expires_at <= ?")
            parameters.extend((now_value, deadline))
        elif normalized_status == "expired":
            clauses.append("(status = 'due' OR (status = 'stored' AND expires_at <= ?))")
            parameters.append(now_value)
        elif normalized_status == "attention":
            clauses.append("(status = 'due' OR (status = 'stored' AND expires_at <= ?))")
            parameters.append(deadline)
        if normalized_category:
            clauses.append("category = ?")
            parameters.append(normalized_category)
        if normalized_review:
            clauses.append("review_status = ?")
            parameters.append(normalized_review)
        if q is not None and str(q).strip():
            literal = str(q).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append(
                "(name LIKE ? ESCAPE '\\' COLLATE NOCASE OR "
                "description LIKE ? ESCAPE '\\' COLLATE NOCASE OR "
                "category LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            )
            parameters.extend((f"%{literal}%",) * 3)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as connection:
            connection.execute("BEGIN")
            total = int(connection.execute(
                f"SELECT COUNT(*) FROM items{where}", parameters
            ).fetchone()[0])
            last_offset = ((total - 1) // safe_limit) * safe_limit if total else 0
            actual_offset = last_offset if requested_offset >= total else requested_offset
            rows = connection.execute(
                f"SELECT * FROM items{where} ORDER BY {orderings[normalized_sort]} LIMIT ? OFFSET ?",
                (*parameters, safe_limit, actual_offset),
            ).fetchall()
        return {
            "items": [self._item_from_row(row) for row in rows],
            "total": total, "limit": safe_limit, "offset": actual_offset,
        }

    def list_attention_items(
        self, now: datetime | str | None = None, lead_days: int = 7, limit: int = 8
    ) -> list[dict[str, Any]]:
        return self.list_items_page(
            status="attention", sort="expiring", limit=limit, now=now, lead_days=lead_days
        )["items"]

    def list_review_items(self, limit: int = 8) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM items WHERE review_status = 'needs_review' "
                "AND status IN ('stored', 'due') ORDER BY detected_at DESC, id DESC LIMIT ?",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [self._item_from_row(row) for row in rows]  # type: ignore[misc]

    def update_item(
        self,
        item_id: int,
        updates: Mapping[str, Any],
        *,
        activity_type: str | None = None,
        activity_message: str | None = None,
        activity_metadata: Any = None,
    ) -> dict[str, Any] | None:
        if not isinstance(updates, Mapping):
            raise TypeError("updates must be a mapping")

        normalized: dict[str, Any] = {
            key: value for key, value in updates.items() if key in self._ITEM_UPDATE_FIELDS
        }
        if "bbox" in updates:
            normalized["bbox_json"] = updates["bbox"]
        if not normalized:
            return self.get_item(item_id)

        if "category" in normalized:
            category = str(normalized["category"]).strip().lower()
            classify_retention(category)
            normalized["category"] = category
        if "review_status" in normalized:
            normalized["review_status"] = _review_status(normalized["review_status"])
        if "status" in normalized:
            status = str(normalized["status"]).strip().lower()
            if status not in ITEM_STATUSES:
                raise ValueError("invalid item status")
            normalized["status"] = status
        if "retention_days" in normalized:
            normalized["retention_days"] = int(normalized["retention_days"])
            if normalized["retention_days"] <= 0:
                raise ValueError("retention_days must be positive")
        for key in ("detected_at", "expires_at", "recovered_at"):
            if key in normalized and normalized[key] is not None:
                normalized[key] = _iso_utc(normalized[key])
        if "bbox_json" in normalized:
            normalized["bbox_json"] = _serialize_bbox(normalized["bbox_json"])
        if "ai_raw" in normalized:
            normalized["ai_raw"] = _serialize_ai_raw(normalized["ai_raw"])
        if "review_reason" in normalized and normalized["review_reason"] is not None:
            normalized["review_reason"] = str(normalized["review_reason"])
        if activity_type is not None and not str(activity_type).strip():
            raise ValueError("activity type is required")
        metadata_json = None if activity_metadata is None else _json_dumps(activity_metadata)

        normalized["updated_at"] = _iso_utc(_utc_now())
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        parameters = list(normalized.values())
        tracking_fields = [
            field for field in ("bbox_json", "image_path", "background_path", "status")
            if field in normalized
        ]
        if tracking_fields:
            comparisons: list[str] = []
            tracking_values: list[Any] = []
            for field in tracking_fields:
                if field == "status":
                    # stored/due is a retention transition, not new physical
                    # evidence. It must not invalidate an observed removal.
                    comparisons.append(
                        "(status IS NOT ? AND NOT (status IN ('stored', 'due') "
                        "AND ? IN ('stored', 'due')))"
                    )
                    tracking_values.extend((normalized[field], normalized[field]))
                else:
                    comparisons.append(f"{field} IS NOT ?")
                    tracking_values.append(normalized[field])
            differences = " OR ".join(comparisons)
            assignments += f", tracking_revision = tracking_revision + CASE WHEN {differences} THEN 1 ELSE 0 END"
            parameters.extend(tracking_values)
        parameters.append(int(item_id))
        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE items SET {assignments} WHERE id = ?", parameters
            )
            if cursor.rowcount == 0:
                connection.commit()
                return None
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (int(item_id),)
            ).fetchone()
            if activity_type is not None and row is not None:
                message = str(activity_message or "{name} 정보를 수정했습니다.").format(name=row["name"])
                connection.execute(
                    "INSERT INTO activities(type, message, item_id, metadata_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(activity_type).strip(), message, int(item_id), metadata_json, normalized["updated_at"]),
                )
            connection.commit()
        return self._item_from_row(row)

    def apply_item_action(
        self,
        item_id: int,
        action: str,
        *,
        activity_type: str | None = None,
        activity_message: str | None = None,
        activity_metadata: Any = None,
        review_reason: str | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Atomically apply recover, dispose, restore, or evidence dismissal.

        The returned ``outcome`` is one of ``changed``, ``unchanged``,
        ``conflict``, or ``not_found``. Repeating an action that has already
        reached its requested state is an idempotent ``unchanged`` result. A
        recover against a disposed item (or dispose against a recovered item)
        is a ``conflict``. Restoring an already-active item is also an
        idempotent no-op.

        When ``activity_type`` is supplied, the state update and activity row
        are committed in the same SQLite transaction. ``activity_message`` may
        contain a trusted ``{name}`` placeholder, which is expanded from the
        item row read inside that transaction. Compatibility wrappers below do
        not request an activity and preserve their historical return shape.
        """

        normalized_action = str(action).strip().lower()
        if normalized_action not in {"recover", "dispose", "restore", "dismiss"}:
            raise ValueError("action must be recover, dispose, restore, or dismiss")

        normalized_activity_type: str | None = None
        if activity_type is not None:
            normalized_activity_type = str(activity_type).strip()
            if not normalized_activity_type:
                raise ValueError("activity type is required")
        metadata_json = (
            None
            if normalized_activity_type is None or activity_metadata is None
            else _json_dumps(activity_metadata)
        )
        now_dt = _as_utc(now or _utc_now(), field="now")
        now_value = _iso_utc(now_dt)
        numeric_item_id = int(item_id)

        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                current_row = connection.execute(
                    "SELECT * FROM items WHERE id = ?", (numeric_item_id,)
                ).fetchone()
                if current_row is None:
                    connection.commit()
                    return {
                        "action": normalized_action,
                        "outcome": "not_found",
                        "previous_status": None,
                        "target_status": None,
                        "item": None,
                        "activity": None,
                    }

                previous_status = str(current_row["status"])
                previous_review = str(current_row["review_status"])
                target_review = previous_review
                target_reason = current_row["review_reason"]
                if normalized_action == "dismiss":
                    target_status = previous_status
                    target_review = "dismissed"
                    target_reason = str(review_reason or "dismissed")
                    outcome = "unchanged" if previous_review == "dismissed" else "changed"
                elif normalized_action == "restore" and previous_review == "dismissed":
                    target_status = (
                        "due" if _as_utc(current_row["expires_at"], field="expires_at") <= now_dt
                        else "stored"
                    )
                    target_review = "needs_review"
                    target_reason = "restored"
                    outcome = "changed"
                elif previous_review == "dismissed":
                    target_status = "recovered" if normalized_action == "recover" else "disposed"
                    outcome = "conflict"
                elif normalized_action == "recover":
                    target_status = "recovered"
                    if previous_status == target_status:
                        outcome = "unchanged"
                    elif previous_status in {"stored", "due"}:
                        outcome = "changed"
                    else:
                        outcome = "conflict"
                elif normalized_action == "dispose":
                    target_status = "disposed"
                    if previous_status == target_status:
                        outcome = "unchanged"
                    elif previous_status in {"stored", "due"}:
                        outcome = "changed"
                    else:
                        outcome = "conflict"
                else:
                    if previous_status in {"recovered", "disposed"}:
                        target_status = (
                            "due"
                            if _as_utc(current_row["expires_at"], field="expires_at")
                            <= now_dt
                            else "stored"
                        )
                        outcome = "changed"
                    else:
                        target_status = previous_status
                        outcome = "unchanged"

                if outcome != "changed":
                    connection.commit()
                    return {
                        "action": normalized_action,
                        "outcome": outcome,
                        "previous_status": previous_status,
                        "target_status": target_status,
                        "previous_review_status": previous_review,
                        "target_review_status": target_review,
                        "item": self._item_from_row(current_row),
                        "activity": None,
                    }

                recovered_at = (
                    current_row["recovered_at"] if normalized_action == "dismiss"
                    else now_value if target_status == "recovered" else None
                )
                cursor = connection.execute(
                    """
                    UPDATE items
                       SET status = ?, recovered_at = ?, updated_at = ?,
                           review_status = ?, review_reason = ?,
                           tracking_revision = tracking_revision + 1
                     WHERE id = ? AND status = ? AND review_status = ?
                    """,
                    (
                        target_status,
                        recovered_at,
                        now_value,
                        target_review,
                        target_reason,
                        numeric_item_id,
                        previous_status,
                        previous_review,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("item lifecycle transition lost its write lock")

                updated_row = connection.execute(
                    "SELECT * FROM items WHERE id = ?", (numeric_item_id,)
                ).fetchone()
                if updated_row is None:
                    raise RuntimeError("item disappeared during lifecycle transition")

                activity_row: sqlite3.Row | None = None
                if normalized_activity_type is not None:
                    default_messages = {
                        "recover": "{name}을(를) 회수 처리했습니다.",
                        "dispose": "{name}을(를) 폐기 처리했습니다.",
                        "restore": "{name}을(를) 보관 목록으로 되돌렸습니다.",
                        "dismiss": "{name}을(를) 오감지로 제외하고 증거를 보존했습니다.",
                    }
                    message_template = activity_message or default_messages[normalized_action]
                    message = str(message_template).format(name=str(updated_row["name"]))
                    activity_cursor = connection.execute(
                        """
                        INSERT INTO activities(
                            type, message, item_id, metadata_json, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            normalized_activity_type,
                            message,
                            numeric_item_id,
                            metadata_json,
                            now_value,
                        ),
                    )
                    activity_row = connection.execute(
                        "SELECT * FROM activities WHERE id = ?",
                        (activity_cursor.lastrowid,),
                    ).fetchone()
                    if activity_row is None:
                        raise RuntimeError("lifecycle activity was not persisted")

                connection.commit()
                return {
                    "action": normalized_action,
                    "outcome": "changed",
                    "previous_status": previous_status,
                    "target_status": target_status,
                    "previous_review_status": previous_review,
                    "target_review_status": target_review,
                    "item": self._item_from_row(updated_row),
                    "activity": (
                        self._activity_from_row(activity_row)
                        if activity_row is not None
                        else None
                    ),
                }
            except Exception:
                connection.rollback()
                raise

    def mark_recovered(self, item_id: int) -> dict[str, Any] | None:
        """Compatibility wrapper returning the current item without logging."""

        return self.apply_item_action(item_id, "recover")["item"]

    def mark_disposed(self, item_id: int) -> dict[str, Any] | None:
        """Compatibility wrapper returning the current item without logging."""

        return self.apply_item_action(item_id, "dispose")["item"]

    def restore_item(self, item_id: int) -> dict[str, Any] | None:
        """Compatibility wrapper returning the current item without logging."""

        return self.apply_item_action(item_id, "restore")["item"]

    def extend_item(
        self,
        item_id: int,
        days: int,
        *,
        cancel_pending: bool = False,
        activity_type: str | None = None,
        activity_message: str | None = None,
        activity_metadata: Any = None,
    ) -> dict[str, Any] | None:
        extension_days = int(days)
        if extension_days <= 0:
            raise ValueError("days must be positive")
        if activity_type is not None and not str(activity_type).strip():
            raise ValueError("activity type is required")
        metadata_json = None if activity_metadata is None else _json_dumps(activity_metadata)

        now_dt = _utc_now()
        now = _iso_utc(now_dt)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?",
                (int(item_id),),
            ).fetchone()
            if row is None:
                connection.commit()
                return None

            expires_dt = _as_utc(row["expires_at"]) + timedelta(days=extension_days)
            status = row["status"]
            if status in ("stored", "due"):
                status = "stored" if expires_dt > now_dt else "due"
            connection.execute(
                """
                UPDATE items
                   SET expires_at = ?, retention_days = ?, status = ?, updated_at = ?
                 WHERE id = ?
                """,
                (
                    _iso_utc(expires_dt),
                    int(row["retention_days"]) + extension_days,
                    status,
                    now,
                    int(item_id),
                ),
            )
            if cancel_pending and row["review_status"] == "pending":
                connection.execute(
                    """
                    UPDATE items SET review_status = 'needs_review', review_reason = 'retention_changed',
                        provider = 'manual_review', name = ?, description = ? WHERE id = ?
                    """,
                    ("확인 필요한 새 물품", "관리자가 보관 기한을 변경했습니다. 물품 이름과 분류를 확인해 주세요.", int(item_id)),
                )
            result = connection.execute(
                "SELECT * FROM items WHERE id = ?", (int(item_id),)
            ).fetchone()
            if activity_type is not None and result is not None:
                message = str(activity_message or f"{{name}}의 보관 기한을 {extension_days}일 연장했습니다.").format(name=result["name"])
                connection.execute(
                    "INSERT INTO activities(type, message, item_id, metadata_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(activity_type).strip(), message, int(item_id), metadata_json, now),
                )
            connection.commit()
        return self._item_from_row(result)

    def delete_item(self, item_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM items WHERE id = ?", (int(item_id),)
            )
            connection.commit()
        return cursor.rowcount > 0

    def create_activity(
        self,
        type: str,
        message: str,
        item_id: int | None = None,
        metadata: Any = None,
    ) -> dict[str, Any]:
        activity_type = str(type).strip()
        if not activity_type:
            raise ValueError("activity type is required")
        now = _iso_utc(_utc_now())
        metadata_json = None if metadata is None else _json_dumps(metadata)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO activities(type, message, item_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_type, str(message), item_id, metadata_json, now),
            )
            row = connection.execute(
                "SELECT * FROM activities WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._activity_from_row(row)

    def list_activities(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM activities
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._activity_from_row(row) for row in rows]

    def create_notification(
        self,
        notification_type: str | Mapping[str, Any],
        message: str = "",
        item_id: int | None = None,
        scheduled_for: datetime | str | None = None,
        metadata: Any = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        """Create a notification, idempotently for ``disposal_due`` items.

        A mapping may be passed as the first argument as a convenience for API
        handlers.  It can contain ``type`` or ``notification_type``.
        """

        if isinstance(notification_type, Mapping):
            payload = notification_type
            notification_type = payload.get("type", payload.get("notification_type", ""))
            message = str(payload.get("message", message))
            item_id = payload.get("item_id", item_id)
            scheduled_for = payload.get("scheduled_for", scheduled_for)
            metadata = payload.get("metadata", metadata)
            status = str(payload.get("status", status))

        normalized_type = str(notification_type).strip()
        if not normalized_type:
            raise ValueError("notification_type is required")
        normalized_status = str(status).strip().lower()
        if normalized_status not in NOTIFICATION_STATUSES:
            raise ValueError("invalid notification status")

        now_dt = _utc_now()
        now = _iso_utc(now_dt)
        schedule = _iso_utc(scheduled_for or now_dt)
        sent_at = now if normalized_status == "sent" else None
        failed_at = now if normalized_status == "failed" else None
        metadata_json = None if metadata is None else _json_dumps(metadata)

        with self._connection() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO notifications(
                        type, message, item_id, status, scheduled_for,
                        sent_at, failed_at, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_type,
                        str(message),
                        item_id,
                        normalized_status,
                        schedule,
                        sent_at,
                        failed_at,
                        metadata_json,
                        now,
                        now,
                    ),
                )
                notification_id = int(cursor.lastrowid)
            except sqlite3.IntegrityError:
                # The partial unique index makes concurrent scheduler passes
                # safe.  Returning the existing record keeps this operation
                # naturally idempotent.
                if normalized_type != "disposal_due" or item_id is None:
                    raise
                existing = connection.execute(
                    """
                    SELECT * FROM notifications
                     WHERE item_id = ?
                       AND type = 'disposal_due'
                       AND scheduled_for = ?
                    """,
                    (item_id, schedule),
                ).fetchone()
                if existing is None:
                    raise
                connection.rollback()
                return self._notification_from_row(existing)  # type: ignore[return-value]

            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?", (notification_id,)
            ).fetchone()
            connection.commit()
        return self._notification_from_row(row)  # type: ignore[return-value]

    def list_notifications(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = []
        where = ""
        if status is not None:
            normalized_status = str(status).strip().lower()
            if normalized_status not in NOTIFICATION_STATUSES:
                raise ValueError("invalid notification status")
            where = " WHERE status = ?"
            parameters.append(normalized_status)
        parameters.append(max(1, min(int(limit), 1000)))
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM notifications{where} "
                "ORDER BY scheduled_for DESC, id DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [self._notification_from_row(row) for row in rows]  # type: ignore[misc]

    def mark_notification_sent(
        self,
        notification_id: int,
        sent_at: datetime | str | None = None,
        *,
        delivery_token: str | None = None,
        log_activity: bool = False,
    ) -> dict[str, Any] | None:
        now = _iso_utc(sent_at or _utc_now())
        condition = " AND delivery_token = ?" if delivery_token is not None else ""
        parameters: list[Any] = [now, now, int(notification_id)]
        if delivery_token is not None:
            parameters.append(delivery_token)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE notifications
                   SET status = 'sent', sent_at = ?, failed_at = NULL,
                       error = NULL, updated_at = ?, delivery_token = NULL,
                       delivery_lease_until = NULL
                 WHERE id = ? AND status != 'sent'
                """ + condition,
                parameters,
            )
            if delivery_token is not None and cursor.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?", (int(notification_id),)
            ).fetchone()
            if log_activity and cursor.rowcount == 1 and row is not None:
                connection.execute(
                    """
                    INSERT INTO activities(type, message, item_id, created_at)
                    SELECT 'email_sent', name || ' 기한 알림 메일을 발송했습니다.', id, ?
                      FROM items WHERE id = ?
                    """,
                    (now, row["item_id"]),
                )
            connection.commit()
        return self._notification_from_row(row)

    def mark_notification_failed(
        self,
        notification_id: int,
        error: str | None = None,
        failed_at: datetime | str | None = None,
        *,
        delivery_token: str | None = None,
    ) -> dict[str, Any] | None:
        now = _iso_utc(failed_at or _utc_now())
        condition = " AND delivery_token = ?" if delivery_token is not None else ""
        parameters: list[Any] = [
            now, None if error is None else str(error), now, int(notification_id)
        ]
        if delivery_token is not None:
            parameters.append(delivery_token)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE notifications
                   SET status = 'failed', failed_at = ?, error = ?, updated_at = ?,
                       delivery_token = NULL, delivery_lease_until = NULL
                 WHERE id = ? AND status != 'sent'
                """ + condition,
                parameters,
            )
            if delivery_token is not None and cursor.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?", (int(notification_id),)
            ).fetchone()
            connection.commit()
        return self._notification_from_row(row)

    def claim_due_notification(
        self,
        notification_id: int,
        *,
        now: datetime | str | None = None,
        retry_after_seconds: float = 300.0,
        lease_seconds: float = 300.0,
    ) -> dict[str, Any] | None:
        """Lease a current-cycle delivery to one scheduler without holding a DB lock.

        A crashed sender's claim becomes retryable after the lease expires.
        Completion must pass the returned token so a late sender cannot replace
        a newer attempt's result. SMTP cannot guarantee exactly-once delivery
        across a crash after the server accepts a message.
        """

        retry_delay = float(retry_after_seconds)
        lease_duration = float(lease_seconds)
        if retry_delay < 0 or lease_duration <= 0:
            raise ValueError("retry delay must be nonnegative and lease duration positive")
        now_dt = _as_utc(now or _utc_now(), field="now")
        now_value = _iso_utc(now_dt)
        retry_cutoff = _iso_utc(now_dt - timedelta(seconds=retry_delay))
        lease_until = _iso_utc(now_dt + timedelta(seconds=lease_duration))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            notification = connection.execute(
                """
                SELECT n.* FROM notifications AS n
                JOIN items AS i ON i.id = n.item_id
                WHERE n.id = ? AND n.type = 'disposal_due'
                  AND n.status IN ('pending', 'failed') AND i.status = 'due'
                  AND i.review_status != 'dismissed'
                  AND i.expires_at = n.scheduled_for AND i.expires_at <= ?
                  AND (n.delivery_lease_until IS NULL OR n.delivery_lease_until <= ?)
                  AND (n.updated_at <= ? OR (
                      n.status = 'pending' AND n.delivery_token IS NULL
                      AND n.failed_at IS NULL
                  ))
                """,
                (int(notification_id), now_value, now_value, retry_cutoff),
            ).fetchone()
            if notification is None:
                connection.commit()
                return None
            item_row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (notification["item_id"],)
            ).fetchone()
            token = uuid.uuid4().hex
            connection.execute(
                """
                UPDATE notifications SET status = 'pending', delivery_token = ?,
                    delivery_lease_until = ?, updated_at = ? WHERE id = ?
                """,
                (token, lease_until, now_value, int(notification_id)),
            )
            connection.commit()
        return {"token": token, "item": self._item_from_row(item_row)}

    def process_expirations(
        self, now: datetime | str | None = None, *, log_activity: bool = False
    ) -> list[dict[str, Any]]:
        """Atomically move newly expired stored items into the due state."""

        now_value = _iso_utc(now or _utc_now())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT id FROM items
                 WHERE status = 'stored' AND expires_at <= ?
                   AND review_status != 'dismissed'
                 ORDER BY expires_at, id
                """,
                (now_value,),
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                connection.execute(
                    f"UPDATE items SET status = 'due', updated_at = ? "
                    f"WHERE status = 'stored' AND id IN ({placeholders})",
                    (now_value, *ids),
                )
                changed = connection.execute(
                    f"SELECT * FROM items WHERE id IN ({placeholders}) "
                    "ORDER BY expires_at, id",
                    ids,
                ).fetchall()
            else:
                changed = []
            if log_activity:
                connection.executemany(
                    """
                    INSERT INTO activities(type, message, item_id, created_at)
                    VALUES ('item_due', ?, ?, ?)
                    """,
                    [
                        (f"{row['name']}의 보관 기한이 도래했습니다.", row["id"], now_value)
                        for row in changed
                    ],
                )
            connection.commit()
        return [self._item_from_row(row) for row in changed]  # type: ignore[misc]

    def get_due_notifications_candidates(
        self, now: datetime | str | None = None
    ) -> list[dict[str, Any]]:
        """Return due items that do not yet have a disposal-due notification."""

        now_value = _iso_utc(now or _utc_now())
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT i.*
                  FROM items AS i
                 WHERE i.status = 'due'
                   AND i.review_status != 'dismissed'
                   AND i.expires_at <= ?
                   AND NOT EXISTS (
                       SELECT 1 FROM notifications AS n
                        WHERE n.item_id = i.id
                          AND n.type = 'disposal_due'
                          AND n.scheduled_for = i.expires_at
                   )
                 ORDER BY i.expires_at, i.id
                """,
                (now_value,),
            ).fetchall()
        return [self._item_from_row(row) for row in rows]  # type: ignore[misc]

    def list_retryable_due_notifications(
        self,
        now: datetime | str | None = None,
        retry_after_seconds: int | float = 300,
        limit: int = 50,
    ) -> list[dict[str, dict[str, Any]]]:
        """Return stale pending/failed current-cycle notifications ready to retry.

        Each result has the explicit shape ``{"notification": <dict>,
        "item": <dict>}``.  Superseded failures are excluded: the item must
        still be due and its current ``expires_at`` must exactly match the
        notification's ``scheduled_for`` value.
        """

        retry_delay = float(retry_after_seconds)
        if retry_delay < 0:
            raise ValueError("retry_after_seconds cannot be negative")
        safe_limit = max(1, min(int(limit), 1000))
        now_dt = _as_utc(now or _utc_now(), field="now")
        now_value = _iso_utc(now_dt)
        retry_cutoff = _iso_utc(now_dt - timedelta(seconds=retry_delay))

        results: list[dict[str, dict[str, Any]]] = []
        with self._connection() as connection:
            # SQLite does not start a read transaction for a bare SELECT.
            # Pin the snapshot while materializing each joined pair.
            connection.execute("BEGIN")
            pairs = connection.execute(
                """
                SELECT n.id AS notification_id, i.id AS item_id
                  FROM notifications AS n
                  JOIN items AS i ON i.id = n.item_id
                 WHERE n.type = 'disposal_due'
                   AND n.status IN ('pending', 'failed')
                   AND i.status = 'due'
                   AND i.review_status != 'dismissed'
                   AND i.expires_at = n.scheduled_for
                   AND i.expires_at <= ?
                   AND n.updated_at <= ?
                   AND (n.delivery_lease_until IS NULL OR n.delivery_lease_until <= ?)
                 ORDER BY n.updated_at, n.id
                 LIMIT ?
                """,
                (now_value, retry_cutoff, now_value, safe_limit),
            ).fetchall()
            for pair in pairs:
                notification_row = connection.execute(
                    "SELECT * FROM notifications WHERE id = ?",
                    (pair["notification_id"],),
                ).fetchone()
                item_row = connection.execute(
                    "SELECT * FROM items WHERE id = ?", (pair["item_id"],)
                ).fetchone()
                # The inner join and per-operation connection guarantee both
                # rows exist for the duration of this read transaction.
                results.append(
                    {
                        "notification": self._notification_from_row(
                            notification_row
                        ),  # type: ignore[dict-item]
                        "item": self._item_from_row(item_row),  # type: ignore[dict-item]
                    }
                )
        return results

    def get_settings(self, defaults: Mapping[str, Any] | None = None) -> dict[str, Any]:
        settings = dict(defaults or {})
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT key, value_json FROM settings ORDER BY key"
            ).fetchall()
        for row in rows:
            # A corrupt individual setting must not prevent the dashboard from
            # loading.  Preserve the raw value so it can still be corrected.
            parsed = _safe_json_loads(row["value_json"], row["value_json"])
            settings[row["key"]] = parsed
        return settings

    def update_settings(self, values: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(values, Mapping):
            raise TypeError("values must be a mapping")
        if not values:
            return self.get_settings()

        now = _iso_utc(_utc_now())
        rows: list[tuple[str, str, str]] = []
        for key, value in values.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                raise ValueError("setting keys cannot be empty")
            rows.append((normalized_key, _json_dumps(value), now))

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                """
                INSERT INTO settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            connection.commit()
        return self.get_settings()
