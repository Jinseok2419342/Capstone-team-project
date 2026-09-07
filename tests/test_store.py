from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

from app.store import Store, classify_retention


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "lost-found.sqlite3"
        self.store = Store(self.db_path)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_get_list_update_and_retention_defaults(self) -> None:
        detected = datetime(2026, 1, 10, 3, 4, 5, tzinfo=timezone.utc)
        item = self.store.create_item(
            {
                "name": "무선 이어폰",
                "description": "흰색 충전 케이스",
                "category": "valuable",
                "detected_at": detected,
                "bbox": {"x": 10, "y": 20, "width": 30, "height": 40},
                "confidence": 0.94,
                "provider": "test",
                "ai_raw": {"label": "earbuds"},
            }
        )

        self.assertEqual(classify_retention("valuable"), 90)
        self.assertEqual(classify_retention("general"), 60)
        self.assertEqual(classify_retention("food"), 1)
        with self.assertRaises(ValueError):
            classify_retention("unknown")

        self.assertEqual(item["retention_days"], 90)
        self.assertEqual(parse_utc(item["expires_at"]), detected + timedelta(days=90))
        self.assertEqual(item["bbox"]["width"], 30)
        self.assertEqual(json.loads(item["bbox_json"]), item["bbox"])
        self.assertTrue(item["detected_at"].endswith("Z"))

        fetched = self.store.get_item(item["id"])
        self.assertEqual(fetched["name"], "무선 이어폰")
        self.assertEqual(self.store.list_items(q="충전")[0]["id"], item["id"])
        self.assertEqual(self.store.list_items(status="stored")[0]["id"], item["id"])

        original_created_at = item["created_at"]
        updated = self.store.update_item(
            item["id"],
            {
                "name": "AirPods",
                "bbox": [1, 2, 3, 4],
                # Non-whitelisted fields are deliberately ignored.
                "id": 999,
                "created_at": "2000-01-01T00:00:00Z",
            },
        )
        self.assertEqual(updated["id"], item["id"])
        self.assertEqual(updated["name"], "AirPods")
        self.assertEqual(updated["bbox"], [1, 2, 3, 4])
        self.assertEqual(updated["created_at"], original_created_at)

    def test_item_recovery_restore_extend_and_delete_lifecycle(self) -> None:
        item = self.store.create_item({"name": "우산", "category": "general"})
        recovered = self.store.mark_recovered(item["id"])
        self.assertEqual(recovered["status"], "recovered")
        self.assertIsNotNone(recovered["recovered_at"])

        # A recovered item cannot accidentally be disposed by a stale UI action.
        unchanged = self.store.mark_disposed(item["id"])
        self.assertEqual(unchanged["status"], "recovered")

        restored = self.store.restore_item(item["id"])
        self.assertEqual(restored["status"], "stored")
        self.assertIsNone(restored["recovered_at"])

        old_expiry = parse_utc(restored["expires_at"])
        extended = self.store.extend_item(item["id"], 7)
        self.assertEqual(parse_utc(extended["expires_at"]), old_expiry + timedelta(days=7))
        self.assertEqual(extended["retention_days"], 67)
        with self.assertRaises(ValueError):
            self.store.extend_item(item["id"], 0)

        disposed = self.store.mark_disposed(item["id"])
        self.assertEqual(disposed["status"], "disposed")
        self.assertEqual(self.store.mark_disposed(item["id"])["status"], "disposed")
        self.assertEqual(self.store.mark_recovered(item["id"])["status"], "disposed")
        self.assertIsNone(self.store.mark_disposed(999999))

        due_item = self.store.create_item(
            {"name": "폐기 대기 음식", "category": "food", "status": "due"}
        )
        self.assertEqual(self.store.mark_disposed(due_item["id"])["status"], "disposed")

        self.assertTrue(self.store.delete_item(item["id"]))
        self.assertFalse(self.store.delete_item(item["id"]))
        self.assertIsNone(self.store.get_item(item["id"]))

    def test_atomic_item_actions_are_idempotent_and_report_conflicts(self) -> None:
        item = self.store.create_item({"name": "검은 우산", "category": "general"})

        recovered = self.store.apply_item_action(
            item["id"],
            "recover",
            activity_type="item_recovered",
            activity_message="{name}을(를) 회수했습니다.",
        )
        self.assertEqual(recovered["outcome"], "changed")
        self.assertEqual(recovered["previous_status"], "stored")
        self.assertEqual(recovered["item"]["status"], "recovered")
        self.assertIsNotNone(recovered["item"]["recovered_at"])
        self.assertEqual(recovered["activity"]["item_id"], item["id"])

        repeated = self.store.apply_item_action(
            item["id"],
            "recover",
            activity_type="item_recovered",
            activity_message="{name}을(를) 회수했습니다.",
        )
        self.assertEqual(repeated["outcome"], "unchanged")
        self.assertIsNone(repeated["activity"])

        conflict = self.store.apply_item_action(
            item["id"],
            "dispose",
            activity_type="item_disposed",
            activity_message="{name}을(를) 폐기했습니다.",
        )
        self.assertEqual(conflict["outcome"], "conflict")
        self.assertEqual(conflict["item"]["status"], "recovered")

        restored = self.store.apply_item_action(
            item["id"],
            "restore",
            activity_type="item_restored",
            activity_message="{name}을(를) 복원했습니다.",
        )
        self.assertEqual(restored["outcome"], "changed")
        self.assertEqual(restored["item"]["status"], "stored")
        self.assertIsNone(restored["item"]["recovered_at"])
        repeated_restore = self.store.apply_item_action(
            item["id"],
            "restore",
            activity_type="item_restored",
            activity_message="{name}을(를) 복원했습니다.",
        )
        self.assertEqual(repeated_restore["outcome"], "unchanged")

        due_item = self.store.create_item(
            {"name": "기한 지난 음식", "category": "food", "status": "due"}
        )
        disposed = self.store.apply_item_action(
            due_item["id"],
            "dispose",
            activity_type="item_disposed",
            activity_message="{name}을(를) 폐기했습니다.",
        )
        self.assertEqual(disposed["outcome"], "changed")
        self.assertEqual(disposed["item"]["status"], "disposed")

        expired_terminal = self.store.create_item(
            {
                "name": "만료된 회수 물품",
                "category": "general",
                "status": "recovered",
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            }
        )
        restored_due = self.store.apply_item_action(
            expired_terminal["id"],
            "restore",
            activity_type="item_restored",
            activity_message="{name}을(를) 복원했습니다.",
        )
        self.assertEqual(restored_due["outcome"], "changed")
        self.assertEqual(restored_due["item"]["status"], "due")

        missing = self.store.apply_item_action(
            999999,
            "recover",
            activity_type="item_recovered",
            activity_message="{name}을(를) 회수했습니다.",
        )
        self.assertEqual(missing["outcome"], "not_found")
        self.assertIsNone(missing["item"])

        item_activities = [
            activity
            for activity in self.store.list_activities(50)
            if activity["item_id"] == item["id"]
        ]
        self.assertEqual(
            [activity["type"] for activity in reversed(item_activities)],
            ["item_recovered", "item_restored"],
        )

    def test_lifecycle_activity_foreign_key_is_preserved_on_item_delete(self) -> None:
        item = self.store.create_item({"name": "FK 확인 물품", "category": "general"})
        transition = self.store.apply_item_action(
            item["id"],
            "recover",
            activity_type="item_recovered",
            activity_message="{name}을(를) 회수했습니다.",
        )
        activity_id = transition["activity"]["id"]

        self.assertTrue(self.store.delete_item(item["id"]))
        activity = next(
            row for row in self.store.list_activities() if row["id"] == activity_id
        )
        self.assertIsNone(activity["item_id"])
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_atomic_item_action_rolls_back_when_activity_insert_fails(self) -> None:
        item = self.store.create_item({"name": "롤백 확인 물품", "category": "general"})
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TRIGGER fail_lifecycle_activity
                BEFORE INSERT ON activities
                WHEN NEW.type = 'item_recovered'
                BEGIN
                    SELECT RAISE(ABORT, 'forced lifecycle activity failure');
                END;
                """
            )
            connection.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            self.store.apply_item_action(
                item["id"],
                "recover",
                activity_type="item_recovered",
                activity_message="{name}을(를) 회수했습니다.",
            )

        unchanged = self.store.get_item(item["id"])
        self.assertEqual(unchanged["status"], "stored")
        self.assertIsNone(unchanged["recovered_at"])
        self.assertFalse(
            any(
                activity["item_id"] == item["id"]
                for activity in self.store.list_activities()
            )
        )

    def test_competing_atomic_item_actions_have_one_winner(self) -> None:
        item = self.store.create_item({"name": "동시 처리 물품", "category": "general"})
        barrier = Barrier(2)

        def apply(action: str) -> dict:
            barrier.wait(timeout=5)
            return self.store.apply_item_action(
                item["id"],
                action,
                activity_type={
                    "recover": "item_recovered",
                    "dispose": "item_disposed",
                }[action],
                activity_message=f"{{name}} {action}",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(apply, ("recover", "dispose")))

        self.assertEqual(
            sorted(result["outcome"] for result in results),
            ["changed", "conflict"],
        )
        final_item = self.store.get_item(item["id"])
        self.assertIn(final_item["status"], {"recovered", "disposed"})
        activities = [
            activity
            for activity in self.store.list_activities()
            if activity["item_id"] == item["id"]
        ]
        self.assertEqual(len(activities), 1)
        expected_type = (
            "item_recovered"
            if final_item["status"] == "recovered"
            else "item_disposed"
        )
        self.assertEqual(activities[0]["type"], expected_type)

    def test_expiration_is_atomic_and_idempotent(self) -> None:
        now = datetime(2026, 4, 1, 12, tzinfo=timezone.utc)
        expired = self.store.create_item(
            {
                "name": "샌드위치",
                "category": "food",
                "detected_at": now - timedelta(days=2),
                "expires_at": now - timedelta(seconds=1),
            }
        )
        future = self.store.create_item(
            {
                "name": "노트",
                "category": "general",
                "detected_at": now,
                "expires_at": now + timedelta(days=1),
            }
        )

        changed = self.store.process_expirations(now)
        self.assertEqual([row["id"] for row in changed], [expired["id"]])
        self.assertEqual(changed[0]["status"], "due")
        self.assertEqual(self.store.process_expirations(now), [])
        self.assertEqual(self.store.get_item(future["id"])["status"], "stored")

    def test_notification_candidate_deduplication_and_statuses(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        item = self.store.create_item(
            {
                "name": "도시락",
                "category": "food",
                "detected_at": now - timedelta(days=12),
                "expires_at": now - timedelta(days=10),
            }
        )
        self.store.process_expirations(now)
        self.assertEqual(
            [candidate["id"] for candidate in self.store.get_due_notifications_candidates(now)],
            [item["id"]],
        )

        def create_same_cycle(_: int) -> dict:
            return self.store.create_notification(
                item_id=item["id"],
                notification_type="disposal_due",
                message="폐기 기한이 도래했습니다.",
                status="pending",
                scheduled_for=item["expires_at"],
                metadata={"source": "scheduler"},
            )

        # The unique cycle key must also hold under concurrent scheduler runs.
        with ThreadPoolExecutor(max_workers=6) as pool:
            concurrent = list(pool.map(create_same_cycle, range(12)))
        self.assertEqual(len({row["id"] for row in concurrent}), 1)
        notification = concurrent[0]
        self.assertEqual(self.store.get_due_notifications_candidates(now), [])
        self.assertEqual(notification["metadata"], {"source": "scheduler"})
        stale_pending = self.store.list_retryable_due_notifications(
            now + timedelta(seconds=301), retry_after_seconds=300
        )
        self.assertEqual(stale_pending[0]["notification"]["id"], notification["id"])

        failed = self.store.mark_notification_failed(
            notification["id"], "SMTP unavailable", failed_at=now
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "SMTP unavailable")
        # A failed notification remains deduped for its cycle, but becomes
        # retryable only after the requested backoff interval.
        self.assertEqual(self.store.get_due_notifications_candidates(now), [])
        self.assertEqual(
            self.store.list_retryable_due_notifications(
                now + timedelta(seconds=299), retry_after_seconds=300
            ),
            [],
        )
        retryable = self.store.list_retryable_due_notifications(
            now + timedelta(seconds=300), retry_after_seconds=300
        )
        self.assertEqual(len(retryable), 1)
        self.assertEqual(set(retryable[0]), {"notification", "item"})
        self.assertEqual(retryable[0]["notification"]["id"], notification["id"])
        self.assertEqual(retryable[0]["item"]["id"], item["id"])
        with self.assertRaises(ValueError):
            self.store.list_retryable_due_notifications(retry_after_seconds=-1)

        # Extending the expiry creates a new notification cycle.  The old
        # failed record neither blocks the new candidate nor enters retries.
        extended = self.store.extend_item(item["id"], 20)
        self.assertEqual(extended["status"], "stored")
        cycle_two_now = now + timedelta(days=11)
        self.store.process_expirations(cycle_two_now)
        cycle_two_candidates = self.store.get_due_notifications_candidates(cycle_two_now)
        self.assertEqual([row["id"] for row in cycle_two_candidates], [item["id"]])
        self.assertEqual(
            self.store.list_retryable_due_notifications(
                cycle_two_now, retry_after_seconds=0
            ),
            [],
        )

        def create_cycle_two(_: int) -> dict:
            return self.store.create_notification(
                item_id=item["id"],
                notification_type="disposal_due",
                scheduled_for=extended["expires_at"],
            )

        with ThreadPoolExecutor(max_workers=6) as pool:
            cycle_two_rows = list(pool.map(create_cycle_two, range(12)))
        self.assertEqual(len({row["id"] for row in cycle_two_rows}), 1)
        cycle_two = cycle_two_rows[0]
        self.assertNotEqual(cycle_two["id"], notification["id"])
        self.assertEqual(self.store.get_due_notifications_candidates(cycle_two_now), [])
        sent = self.store.mark_notification_sent(cycle_two["id"])
        self.assertEqual(sent["status"], "sent")
        self.assertIsNotNone(sent["sent_at"])
        self.assertIsNone(sent["error"])
        self.assertEqual(len(self.store.list_notifications(status="sent")), 1)
        self.assertEqual(len(self.store.list_notifications(status="failed")), 1)

    def test_initialize_migrates_notification_dedupe_index(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("DROP INDEX uq_disposal_due_per_item_schedule")
            connection.execute(
                """
                CREATE UNIQUE INDEX uq_disposal_due_per_item
                    ON notifications(item_id, type)
                    WHERE item_id IS NOT NULL AND type = 'disposal_due'
                """
            )
            connection.commit()

        self.store.initialize()
        with closing(sqlite3.connect(self.db_path)) as connection:
            names = {
                row[1] for row in connection.execute("PRAGMA index_list(notifications)")
            }
            columns = [
                row[2]
                for row in connection.execute(
                    "PRAGMA index_info(uq_disposal_due_per_item_schedule)"
                )
            ]
        self.assertNotIn("uq_disposal_due_per_item", names)
        self.assertIn("uq_disposal_due_per_item_schedule", names)
        self.assertEqual(columns, ["item_id", "type", "scheduled_for"])

    def test_backup_and_operational_reset_preserve_settings(self) -> None:
        self.store.update_settings(
            {"motion_threshold": 37, "admin_email": "admin@example.test"}
        )
        item = self.store.create_item({"name": "Reset test", "category": "general"})
        self.store.create_activity(
            "item_detected", "created for reset test", item_id=item["id"]
        )
        self.store.create_notification(
            "disposal_due",
            item_id=item["id"],
            scheduled_for=item["expires_at"],
        )

        backup_path = Path(self.temp_dir.name) / "backups" / "database.sqlite3"
        self.assertEqual(self.store.backup_to(backup_path), backup_path.resolve())
        with self.assertRaises(FileExistsError):
            self.store.backup_to(backup_path)

        removed = self.store.reset_operational_data()
        self.assertEqual(
            removed,
            {
                "items": 1,
                "activities": 1,
                "notifications": 1,
                "settings_preserved": 2,
            },
        )
        self.assertEqual(self.store.list_items(), [])
        self.assertEqual(self.store.list_activities(), [])
        self.assertEqual(self.store.list_notifications(), [])
        self.assertEqual(
            self.store.get_settings(),
            {"admin_email": "admin@example.test", "motion_threshold": 37},
        )

        # The backup is a usable pre-reset database, including committed WAL
        # contents. Item ids deliberately remain monotonic after reset so an
        # old cached /items/<id>/image URL can never identify a new object.
        backup_store = Store(backup_path)
        self.assertEqual(backup_store.get_item(item["id"])["name"], "Reset test")
        self.assertEqual(len(backup_store.list_activities()), 1)
        self.assertEqual(len(backup_store.list_notifications()), 1)
        self.assertEqual(
            self.store.create_item({"name": "First after reset", "category": "food"})[
                "id"
            ],
            item["id"] + 1,
        )

    def test_activities_settings_and_parallel_connections(self) -> None:
        item = self.store.create_item({"name": "학생증", "category": "valuable"})
        activity = self.store.create_activity(
            "detected",
            "새 물건을 감지했습니다.",
            item_id=item["id"],
            metadata={"camera": 0},
        )
        self.assertEqual(activity["metadata"], {"camera": 0})
        self.assertEqual(self.store.list_activities()[0]["id"], activity["id"])

        self.assertEqual(
            self.store.get_settings({"motion_threshold": 25}),
            {"motion_threshold": 25},
        )
        settings = self.store.update_settings(
            {
                "motion_threshold": 40,
                "email_enabled": True,
                "regions": ["front-desk"],
            }
        )
        self.assertEqual(settings["motion_threshold"], 40)
        self.assertIs(settings["email_enabled"], True)
        merged = self.store.get_settings(
            {"motion_threshold": 10, "settle_seconds": 3}
        )
        self.assertEqual(merged["motion_threshold"], 40)
        self.assertEqual(merged["settle_seconds"], 3)

        # One Store object is safe to share because each task opens its own
        # SQLite connection.
        def add_item(index: int) -> int:
            return self.store.create_item(
                {"name": f"병렬-{index}", "category": "general"}
            )["id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            ids = list(pool.map(add_item, range(12)))
        self.assertEqual(len(set(ids)), 12)
        self.assertEqual(len(self.store.list_items(q="병렬")), 12)


if __name__ == "__main__":
    unittest.main()
