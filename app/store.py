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
            item_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(items)").fetchall()
            }
            if "background_path" not in item_columns:
                connection.execute("ALTER TABLE items ADD COLUMN background_path TEXT")
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

    def update_item(
        self, item_id: int, updates: Mapping[str, Any]
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

        normalized["updated_at"] = _iso_utc(_utc_now())
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        parameters = list(normalized.values()) + [int(item_id)]
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
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Atomically apply a recover, dispose, or restore lifecycle action.

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
        if normalized_action not in {"recover", "dispose", "restore"}:
            raise ValueError("action must be recover, dispose, or restore")

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
                if normalized_action == "recover":
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
                        "item": self._item_from_row(current_row),
                        "activity": None,
                    }

                recovered_at = now_value if target_status == "recovered" else None
                cursor = connection.execute(
                    """
                    UPDATE items
                       SET status = ?, recovered_at = ?, updated_at = ?
                     WHERE id = ? AND status = ?
                    """,
                    (
                        target_status,
                        recovered_at,
                        now_value,
                        numeric_item_id,
                        previous_status,
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

    def extend_item(self, item_id: int, days: int) -> dict[str, Any] | None:
        extension_days = int(days)
        if extension_days <= 0:
            raise ValueError("days must be positive")

        now_dt = _utc_now()
        now = _iso_utc(now_dt)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT expires_at, retention_days, status FROM items WHERE id = ?",
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
            result = connection.execute(
                "SELECT * FROM items WHERE id = ?", (int(item_id),)
            ).fetchone()
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
        self, notification_id: int, sent_at: datetime | str | None = None
    ) -> dict[str, Any] | None:
        now = _iso_utc(sent_at or _utc_now())
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE notifications
                   SET status = 'sent', sent_at = ?, failed_at = NULL,
                       error = NULL, updated_at = ?
                 WHERE id = ?
                """,
                (now, now, int(notification_id)),
            )
            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?", (int(notification_id),)
            ).fetchone()
            connection.commit()
        return self._notification_from_row(row)

    def mark_notification_failed(
        self,
        notification_id: int,
        error: str | None = None,
        failed_at: datetime | str | None = None,
    ) -> dict[str, Any] | None:
        now = _iso_utc(failed_at or _utc_now())
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE notifications
                   SET status = 'failed', failed_at = ?, error = ?, updated_at = ?
                 WHERE id = ?
                """,
                (now, None if error is None else str(error), now, int(notification_id)),
            )
            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?", (int(notification_id),)
            ).fetchone()
            connection.commit()
        return self._notification_from_row(row)

    def process_expirations(
        self, now: datetime | str | None = None
    ) -> list[dict[str, Any]]:
        """Atomically move newly expired stored items into the due state."""

        now_value = _iso_utc(now or _utc_now())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT id FROM items
                 WHERE status = 'stored' AND expires_at <= ?
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
            pairs = connection.execute(
                """
                SELECT n.id AS notification_id, i.id AS item_id
                  FROM notifications AS n
                  JOIN items AS i ON i.id = n.item_id
                 WHERE n.type = 'disposal_due'
                   AND n.status IN ('pending', 'failed')
                   AND i.status = 'due'
                   AND i.expires_at = n.scheduled_for
                   AND i.expires_at <= ?
                   AND n.updated_at <= ?
                 ORDER BY n.updated_at, n.id
                 LIMIT ?
                """,
                (now_value, retry_cutoff, safe_limit),
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
