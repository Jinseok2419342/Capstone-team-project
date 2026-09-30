from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.store import Store


class InventoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "inventory.db"
        self.store = Store(self.path)
        self.store.initialize()
        self.now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)

    def create(self, **values) -> dict:
        return self.store.create_item({
            "name": "Item", "detected_at": self.now,
            "expires_at": self.now + timedelta(days=20), **values,
        })

    def test_pagination_and_filters_reach_items_beyond_latest_500(self) -> None:
        old = self.create(name="Old food", category="food", detected_at=self.now - timedelta(days=90))
        # One insert transaction keeps this a small regression test on a Pi.
        stamp = self.now.isoformat(timespec="microseconds").replace("+00:00", "Z")
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executemany(
                "INSERT INTO items(name,category,retention_days,detected_at,expires_at,status,created_at,updated_at) "
                "VALUES (?, 'general', 60, ?, ?, 'recovered', ?, ?)",
                [(f"Newer {index:04d}", stamp, stamp, stamp, stamp) for index in range(625)],
            )
            connection.commit()
        page = self.store.list_items_page(category="food")
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["id"], old["id"])
        self.assertEqual(self.store.list_items_page(sort="expiring", limit=1)["items"][0]["status"], "recovered")
        seen = []
        for offset in range(0, 626, 48):
            page = self.store.list_items_page(limit=48, offset=offset)
            self.assertEqual(page["total"], 626)
            seen.extend(item["id"] for item in page["items"])
        self.assertEqual(len(seen), 626)
        self.assertEqual(len(set(seen)), 626)
        self.assertEqual(seen[-1], old["id"])
        final = self.store.list_items_page(limit=48, offset=9000)
        self.assertEqual(final["offset"], 624)
        self.assertEqual(len(final["items"]), 2)
        self.assertEqual(self.store.list_items_page(limit=48, offset=625)["offset"], 625)

    def test_literal_search_and_stable_name_sort(self) -> None:
        percent = self.create(name="100% cotton")
        underscore = self.create(name="Model_A")
        slash = self.create(name="Case\\label")
        plain = self.create(name="100x cotton", description="ModelXA")
        for query, expected in (("%", percent), ("_", underscore), ("\\", slash), ("100x", plain)):
            with self.subTest(query=query):
                result = self.store.list_items_page(q=query)
                self.assertEqual([item["id"] for item in result["items"]], [expected["id"]])
        twins = [self.create(name="Same") for _ in range(2)]
        ordered = self.store.list_items_page(q="same", sort="name")
        self.assertEqual([item["id"] for item in ordered["items"]], [item["id"] for item in twins])
        for arguments in ({"sort": "id; DELETE FROM items"}, {"status": "invalid"},
                          {"category": "invalid"}, {"review": "invalid"}):
            with self.assertRaises(ValueError):
                self.store.list_items_page(**arguments)

    def test_effective_filters_stats_and_attention_share_expiry_boundaries(self) -> None:
        overdue = self.create(name="Scheduler not run yet", expires_at=self.now)
        due = self.create(name="Already due", status="due")
        soon = self.create(name="Soon", expires_at=self.now + timedelta(days=7), review_status="needs_review")
        future = self.create(name="Future")
        self.create(status="recovered", expires_at=self.now - timedelta(days=2), review_status="needs_review")
        self.create(review_status="dismissed", expires_at=self.now - timedelta(days=1))
        expected = {
            "holding": {overdue["id"], due["id"], soon["id"], future["id"]},
            "active": {soon["id"], future["id"]},
            "due_soon": {soon["id"]},
            "expired": {overdue["id"], due["id"]},
            "attention": {overdue["id"], due["id"], soon["id"]},
        }
        for status, ids in expected.items():
            result = self.store.list_items_page(status=status, now=self.now, lead_days=7)
            self.assertEqual({item["id"] for item in result["items"]}, ids)
        self.assertEqual(self.store.item_stats(self.now, 7), {
            "active": 2, "due_soon": 1, "expired": 2, "recovered": 1, "review_needed": 1,
        })
        self.assertEqual({item["id"] for item in self.store.list_review_items()}, {soon["id"]})
        review_page = self.store.list_items_page(status="holding", review="needs_review", now=self.now)
        self.assertEqual(review_page["total"], self.store.item_stats(self.now, 7)["review_needed"])
        self.assertEqual({item["id"] for item in review_page["items"]}, {soon["id"]})
        self.assertEqual(self.store.list_items_page(review="needs_review", now=self.now)["total"], 2)
        self.assertEqual({item["id"] for item in self.store.list_attention_items(self.now, 7)}, expected["attention"])
        self.assertEqual(self.store.list_items_page(status="stored", now=self.now)["total"], 3)
        self.assertEqual(self.store.list_items_page(status="due", now=self.now)["total"], 1)

    def test_count_and_page_use_one_read_snapshot(self) -> None:
        originals = [self.create(name=str(index)) for index in range(3)]
        original_connect = sqlite3.connect
        database_path = self.path

        class DeleteDuringCount(sqlite3.Connection):
            def execute(self, sql, parameters=(), /):
                cursor = super().execute(sql, parameters)
                if sql.startswith("SELECT COUNT(*) FROM items"):
                    with closing(original_connect(database_path)) as other:
                        other.execute("DELETE FROM items")
                        other.commit()
                return cursor

        with patch("app.store.sqlite3.connect", side_effect=lambda *args, **kwargs:
                   original_connect(*args, factory=DeleteDuringCount, **kwargs)):
            page = self.store.list_items_page(limit=2, offset=2)
        self.assertEqual(page["total"], 3)
        self.assertEqual([item["id"] for item in page["items"]], [originals[0]["id"]])
        self.assertEqual(self.store.list_items_page()["total"], 0)

    def test_legacy_review_migration_preserves_provider_and_explicit_later_review(self) -> None:
        legacy = Path(self.directory.name) / "legacy.db"
        providers = ["pending", "offline", "openai_review", "manual_review", "openai", "demo", None]
        with closing(sqlite3.connect(legacy)) as connection:
            connection.executescript(
                """
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
                    category TEXT NOT NULL, retention_days INTEGER NOT NULL,
                    detected_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL,
                    recovered_at TEXT, bbox_json TEXT, confidence REAL, image_path TEXT,
                    provider TEXT, ai_raw TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                "INSERT INTO items(name,category,retention_days,detected_at,expires_at,status,provider,created_at,updated_at) "
                "VALUES ('Legacy','general',60,'2026-01-01T00:00:00.000000Z','2026-03-01T00:00:00.000000Z','stored',?,'2026-01-01','2026-01-01')",
                [(provider,) for provider in providers],
            )
            connection.execute("UPDATE items SET bbox_json = '[1,2,3,4]' WHERE id IN (1,4,5,6)")
            # Historical manual edits replaced provider='demo' but kept ai_raw.
            connection.execute(
                "UPDATE items SET ai_raw = 'built-in deterministic presentation preset' WHERE id = 4"
            )
            connection.commit()
        migrated = Store(legacy)
        migrated.initialize()
        expected = ["pending", "needs_review", "needs_review", "needs_review", "confirmed", "confirmed", "confirmed"]
        sources = ["camera", "manual", "manual", "demo", "camera", "demo", "manual"]
        for item_id, (provider, state) in enumerate(zip(providers, expected), 1):
            item = migrated.get_item(item_id)
            self.assertEqual(item["provider"], provider)
            self.assertEqual(item["review_status"], state)
            self.assertEqual(item["tracking_revision"], 0)
            self.assertEqual(item["source_kind"], sources[item_id - 1])
        self.assertEqual({item["id"] for item in migrated.list_active_items()}, {1, 5})
        self.assertEqual({item["id"] for item in migrated.list_active_demo_items(limit=10)}, {4, 6})
        migrated.update_item(2, {"review_status": "confirmed", "review_reason": "manual_confirmation"})
        migrated.update_item(6, {"provider": "manual", "ai_raw": "changed metadata", "source_kind": "camera"})
        migrated.initialize()
        self.assertEqual(migrated.get_item(2)["review_status"], "confirmed")
        self.assertEqual(migrated.get_item(2)["provider"], "offline")
        self.assertEqual(migrated.get_item(6)["source_kind"], "demo")
        with self.assertRaises(ValueError):
                migrated.update_item(2, {"review_status": "unsupported"})

    def test_demo_source_is_immutable_and_independent_of_provider(self) -> None:
        demo = self.create(source_kind="demo", provider="demo", bbox=[1, 2, 3, 4])
        camera = self.create(source_kind="camera", provider="openai", bbox=[5, 6, 7, 8])
        manual = self.create()
        edited = self.store.update_item(demo["id"], {
            "provider": "manual", "source_kind": "camera", "review_status": "confirmed",
        })
        self.assertEqual(edited["source_kind"], "demo")
        self.assertEqual(edited["provider"], "manual")
        self.assertEqual(manual["source_kind"], "manual")
        self.assertEqual([item["id"] for item in self.store.list_active_items()], [camera["id"]])
        self.assertEqual([item["id"] for item in self.store.list_active_demo_items()], [demo["id"]])
        with self.assertRaises(ValueError):
            self.create(source_kind="unsupported")

    def test_active_demo_query_reaches_old_demo_and_skips_other_inventory(self) -> None:
        older = self.create(source_kind="demo", name="Older demo", detected_at=self.now - timedelta(days=3))
        newer = self.create(source_kind="demo", name="Newer demo", detected_at=self.now - timedelta(days=2))
        self.create(source_kind="demo", status="recovered")
        self.create(source_kind="demo", status="disposed")
        self.create(source_kind="demo", review_status="dismissed")
        stamp = self.now.isoformat(timespec="microseconds").replace("+00:00", "Z")
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executemany(
                "INSERT INTO items(name,category,retention_days,detected_at,expires_at,status,created_at,updated_at) "
                "VALUES (?, 'general', 60, ?, ?, 'stored', ?, ?)",
                [(f"Real inventory {index}", stamp, stamp, stamp, stamp) for index in range(120)],
            )
            connection.commit()
        self.assertEqual([item["id"] for item in self.store.list_active_demo_items()], [newer["id"]])
        self.assertEqual([item["id"] for item in self.store.list_active_demo_items(limit=1000)],
                         [newer["id"], older["id"]])
        self.store.apply_item_action(newer["id"], "recover")
        self.assertEqual([item["id"] for item in self.store.list_active_demo_items()], [older["id"]])

    def test_dismissal_preserves_evidence_and_can_be_restored(self) -> None:
        original = self.create(
            expires_at=self.now - timedelta(days=1), provider="openai", review_status="needs_review",
            image_path="item.jpg", background_path="background.jpg", ai_raw="original AI evidence",
            bbox=[1, 2, 3, 4], source_event_id="source-one",
        )
        dismissed = self.store.apply_item_action(
            original["id"], "dismiss", review_reason="false_detection", activity_type="item_dismissed", now=self.now
        )
        item = dismissed["item"]
        self.assertEqual(dismissed["outcome"], "changed")
        self.assertEqual(item["review_status"], "dismissed")
        self.assertEqual(item["review_reason"], "false_detection")
        self.assertEqual(item["tracking_revision"], 1)
        for field in ("status", "ai_raw", "provider", "image_path", "background_path", "bbox", "source_event_id"):
            self.assertEqual(item[field], original[field])
        self.assertEqual(self.store.list_active_items(), [])
        self.assertEqual(self.store.list_items_page()["total"], 0)
        self.assertEqual(self.store.list_items_page(status="stored")["total"], 0)
        self.assertEqual(self.store.list_items_page(status="dismissed")["total"], 1)
        self.assertEqual(self.store.list_items_page(review="dismissed")["total"], 1)
        self.assertEqual(self.store.apply_item_action(original["id"], "dismiss")["outcome"], "unchanged")
        for action in ("recover", "dispose"):
            self.assertEqual(self.store.apply_item_action(original["id"], action)["outcome"], "conflict")
        restored = self.store.apply_item_action(original["id"], "restore", activity_type="item_restored", now=self.now)["item"]
        self.assertEqual(restored["status"], "due")
        self.assertEqual(restored["review_status"], "needs_review")
        self.assertEqual(restored["review_reason"], "restored")
        self.assertEqual(restored["tracking_revision"], 2)
        self.assertEqual(len(self.store.list_activities()), 2)

    def test_dismissed_items_never_expire_or_enter_notification_delivery(self) -> None:
        hidden = self.create(expires_at=self.now - timedelta(days=1), review_status="dismissed", bbox=[1, 2, 3, 4])
        due = self.create(status="due", expires_at=self.now - timedelta(days=1))
        notification = self.store.create_notification("disposal_due", item_id=due["id"], scheduled_for=due["expires_at"])
        self.store.apply_item_action(due["id"], "dismiss")
        self.assertEqual(self.store.process_expirations(self.now), [])
        self.assertEqual(self.store.get_item(hidden["id"])["status"], "stored")
        self.assertEqual(self.store.get_due_notifications_candidates(self.now), [])
        self.assertEqual(self.store.list_retryable_due_notifications(self.now + timedelta(days=365), 0), [])
        self.assertIsNone(self.store.claim_due_notification(notification["id"], now=self.now + timedelta(days=365), retry_after_seconds=0))
        self.assertTrue(all(value == 0 for value in self.store.item_stats(self.now).values()))

    def test_tracking_revision_changes_only_for_tracking_mutations(self) -> None:
        original = self.create(bbox=[1, 2, 3, 4], image_path="one.jpg", provider="pending")
        updated = self.store.update_item(original["id"], {
            "name": "AI named item", "expires_at": self.now + timedelta(days=90),
            "provider": "openai", "review_status": "confirmed", "review_reason": None,
        })
        self.assertEqual(updated["tracking_revision"], 0)
        updated = self.store.update_item(original["id"], {"bbox": [1, 2, 3, 4], "image_path": "one.jpg", "status": "stored"})
        self.assertEqual(updated["tracking_revision"], 0)
        updated = self.store.update_item(original["id"], {"bbox": [5, 2, 3, 4], "image_path": "two.jpg"})
        self.assertEqual(updated["tracking_revision"], 1)
        recovered = self.store.apply_item_action(original["id"], "recover")["item"]
        self.assertEqual(recovered["tracking_revision"], 2)
        self.assertEqual(self.store.apply_item_action(original["id"], "recover")["item"]["tracking_revision"], 2)

    def test_retention_status_changes_preserve_observed_tracking_revision(self) -> None:
        original = self.create(bbox=[1, 2, 3, 4], provider="pending")
        observed_revision = original["tracking_revision"]
        for status, expiry in (("due", self.now - timedelta(days=1)),
                               ("stored", self.now + timedelta(days=1))):
            updated = self.store.update_item(original["id"], {
                "name": "Classified item", "category": "food", "status": status,
                "expires_at": expiry, "review_status": "confirmed", "provider": "openai",
            })
            self.assertEqual(updated["tracking_revision"], observed_revision)
        self.store.update_item(original["id"], {"status": "due", "expires_at": self.now - timedelta(days=1)})
        with patch("app.store._utc_now", return_value=self.now):
            extended = self.store.extend_item(original["id"], 7)
        self.assertEqual(extended["status"], "stored")
        self.assertEqual(extended["tracking_revision"], observed_revision)
        # The physical removal still matches the same tracked observation.
        recovered = self.store.apply_item_action(original["id"], "recover")["item"]
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["tracking_revision"], observed_revision + 1)

    def test_source_event_identity_is_unique_across_store_connections(self) -> None:
        def insert(_: int) -> dict | None:
            try:
                return Store(self.path).create_item({"source_event_id": "event-123", "name": "One observation"})
            except sqlite3.IntegrityError:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            created = [item for item in pool.map(insert, range(8)) if item is not None]
        self.assertEqual(len(created), 1)
        item = self.store.get_item_by_source_event("event-123")
        self.assertEqual(item["id"], created[0]["id"])
        self.assertIsNone(self.store.get_item_by_source_event("missing"))
        self.store.update_item(item["id"], {"source_event_id": "replacement"})
        self.assertEqual(self.store.get_item_by_source_event("event-123")["id"], item["id"])
        self.create()
        self.create()

    def test_mutation_and_activity_failures_roll_back_together(self) -> None:
        original = self.create(provider="pending", bbox=[1, 2, 3, 4])
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(
                "CREATE TRIGGER reject_activity BEFORE INSERT ON activities "
                "BEGIN SELECT RAISE(ABORT, 'forced activity failure'); END;"
            )
        operations = [
            lambda: self.store.update_item(original["id"], {"name": "Manual", "review_status": "confirmed"}, activity_type="item_edited"),
            lambda: self.store.extend_item(original["id"], 7, cancel_pending=True, activity_type="item_extended"),
            lambda: self.store.apply_item_action(original["id"], "dismiss", activity_type="item_dismissed"),
        ]
        for operation in operations:
            with self.assertRaises(sqlite3.IntegrityError):
                operation()
            self.assertEqual(self.store.get_item(original["id"]), original)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DROP TRIGGER reject_activity")
        extended = self.store.extend_item(original["id"], 7, cancel_pending=True, activity_type="item_extended")
        self.assertEqual(extended["review_status"], "needs_review")
        self.assertEqual(extended["review_reason"], "retention_changed")
        self.assertEqual(extended["provider"], "manual_review")
        self.assertEqual(extended["tracking_revision"], 0)
        self.assertEqual(len(self.store.list_activities()), 1)


if __name__ == "__main__":
    unittest.main()
