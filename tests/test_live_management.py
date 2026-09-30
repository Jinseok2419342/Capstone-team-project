"""Continuous management workflows against isolated SQLite and real HTTP routes.

Initial rows represent observations already accepted from a camera; this file
never uses presentation/demo endpoints. The actual notifier and scheduler run
through the maintenance API with only SMTP transport replaced. A shared test
clock advances expiry/retry boundaries without sleeping or changing item rows
behind the API. App lifespan is intentionally omitted to avoid opening hardware.
"""

from __future__ import annotations

import smtplib
import tempfile
import unittest
from collections import OrderedDict
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app import main
from app.notifier import EmailNotifier, ExpirationScheduler
from app.store import Store


class LiveManagementTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.captures = root / "captures"
        self.captures.mkdir()
        self.now = datetime(2026, 9, 18, 9, tzinfo=timezone.utc)
        self.stack.enter_context(patch("app.store._utc_now", side_effect=lambda: self.now))
        self.stack.enter_context(patch.object(main, "utc_now", side_effect=lambda: self.now))
        scheduler_datetime = self.stack.enter_context(patch("app.notifier.datetime"))
        scheduler_datetime.now.side_effect = lambda tz=None: self.now
        self.store = Store(root / "management.sqlite3")
        self.store.initialize()
        self.store.update_settings({
            "admin_email": "administrator@example.test",
            "smtp_host": "smtp.example.test", "smtp_port": 587,
            "smtp_username": "sender@example.test", "smtp_use_tls": True,
            "alert_lead_days": 7,
        })
        self.stack.enter_context(patch.object(main, "store", self.store))
        test_config = replace(
            main.config, data_dir=root, capture_dir=self.captures, db_path=self.store.db_path,
            smtp_password="synthetic-test-password", openai_api_key="", gemini_api_key="",
        )
        self.stack.enter_context(patch.object(main, "config", test_config))
        self.stack.enter_context(patch.object(main, "_reference_cache", OrderedDict()))
        self.stack.enter_context(patch.object(main, "_reference_cache_bytes", 0))
        self.stack.enter_context(patch.object(main.vision, "get_status", return_value={"running": False}))
        self.notifier = EmailNotifier(test_config, main.current_settings)
        self.scheduler = ExpirationScheduler(self.store, self.notifier, retry_after_seconds=300)
        self.stack.enter_context(patch.object(main, "notifier", self.notifier))
        self.stack.enter_context(patch.object(main, "scheduler", self.scheduler))
        self.smtp_factory = self.stack.enter_context(patch("app.notifier.smtplib.SMTP"))
        self.smtp_ssl = self.stack.enter_context(patch("app.notifier.smtplib.SMTP_SSL"))
        self.smtp = self.smtp_factory.return_value.__enter__.return_value
        self.client = TestClient(main.app)
        self.stack.callback(self.client.close)

    def observation(self, name="Unidentified observation", **values):
        frame = np.full((60, 80, 3), 205, np.uint8)
        cv2.rectangle(frame, (15, 10), (60, 45), (35, 60, 100), -1)
        ok, encoded = cv2.imencode(".jpg", frame)
        self.assertTrue(ok)
        image = main.save_capture(encoded.tobytes())
        background = main.save_capture(encoded.tobytes(), prefix="background")
        return self.store.create_item({
            "name": name, "category": "general", "provider": "offline_review",
            "review_status": "needs_review", "review_reason": "offline",
            "source_kind": "camera", "bbox": [30, 40, 80, 60],
            "image_path": image, "background_path": background,
            "detected_at": self.now, "expires_at": self.now + timedelta(days=20),
            **values,
        })

    def get(self, path, **params):
        response = self.client.get(path, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def action(self, item_id, action, *, expected=200, **body):
        response = self.client.post(f"/api/items/{item_id}/{action}", json=body or None)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def edit(self, item_id, **body):
        current = self.get(f"/api/items/{item_id}")
        response = self.client.patch(f"/api/items/{item_id}", json={
            "expected_updated_at": current["updated_at"], **body,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def check_expirations(self, processed):
        response = self.client.post("/api/maintenance/check-expirations")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"ok": True, "processed": processed})

    def assert_stats(self, *, active, due_soon=0, expired=0, recovered=0, review_needed=0):
        dashboard = self.get("/api/dashboard")
        expected = dict(active=active, due_soon=due_soon, expired=expired,
                        recovered=recovered, review_needed=review_needed)
        self.assertEqual(dashboard["stats"], expected)
        for key, status in (("active", "active"), ("due_soon", "due_soon"),
                            ("expired", "expired"), ("recovered", "recovered")):
            self.assertEqual(self.get("/api/items", status=status)["total"], expected[key])
        self.assertEqual(
            self.get("/api/items", status="holding", review="needs_review")["total"], review_needed,
        )
        attention = self.get("/api/items", status="attention")
        self.assertEqual(
            {item["id"] for item in dashboard["attention_items"]},
            {item["id"] for item in attention["items"]},
        )
        return dashboard

    def assert_evidence_preserved(self, original):
        current = self.store.get_item(original["id"])
        for field in ("image_path", "background_path", "bbox", "source_kind"):
            self.assertEqual(current[field], original[field])
        for path in (original["image_path"], original["background_path"]):
            self.assertTrue(Path(path).is_file())
        response = self.client.get(f"/api/items/{original['id']}/image")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, Path(original["image_path"]).read_bytes())

    def test_review_expiry_renewal_notification_and_final_lifecycle(self):
        original = self.observation()
        item_id = original["id"]
        self.assert_stats(active=1, review_needed=1)
        confirmed = self.edit(
            item_id, name="Packaged lunch", description="Sealed container", category="food", confirm_review=True,
        )
        self.assertEqual(confirmed["review_status"], "confirmed")
        self.assertEqual(confirmed["provider"], "manual")
        self.assertEqual(confirmed["retention_days"], 1)
        first_expiry = main.parse_dt(confirmed["expires_at"])
        self.assertEqual(first_expiry, self.now + timedelta(days=1))
        self.assert_stats(active=1, due_soon=1)
        self.check_expirations(0)
        self.smtp.send_message.assert_not_called()

        self.now = first_expiry  # The exact inclusive expiry boundary.
        self.assert_stats(active=0, expired=1)
        self.check_expirations(1)
        first = self.store.list_notifications()[0]
        self.assertEqual(first["status"], "sent")
        self.assertEqual(first["item_id"], item_id)
        self.assertEqual(main.parse_dt(first["scheduled_for"]), first_expiry)
        self.assertEqual(self.smtp.send_message.call_count, 1)
        message = self.smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "administrator@example.test")
        self.assertIn("Packaged lunch", str(message["Subject"]))
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 1)

        extended = self.action(item_id, "extend", days=7)
        second_expiry = main.parse_dt(extended["expires_at"])
        self.assertEqual(second_expiry, first_expiry + timedelta(days=7))
        self.assertEqual(extended["status"], "stored")
        self.assertEqual(extended["retention_days"], 8)
        self.assertEqual(extended["tracking_revision"], original["tracking_revision"])
        self.assert_stats(active=1, due_soon=1)
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 1)
        self.now = second_expiry
        self.check_expirations(1)
        notifications = self.store.list_notifications()
        self.assertEqual(len(notifications), 2)
        self.assertEqual({row["status"] for row in notifications}, {"sent"})
        self.assertEqual({main.parse_dt(row["scheduled_for"]) for row in notifications}, {first_expiry, second_expiry})
        self.assertEqual(self.smtp.send_message.call_count, 2)

        disposed = self.action(item_id, "dispose")
        self.assertEqual(disposed["status"], "disposed")
        self.action(item_id, "dispose")  # Double clicking must not duplicate history.
        self.action(item_id, "recover", expected=409)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assert_stats(active=0)
        restored = self.action(item_id, "restore")
        self.assertEqual(restored["status"], "due")
        self.assertEqual(self.get("/api/items", status="expired")["items"][0]["id"], item_id)
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 2)
        self.assertEqual(self.action(item_id, "recover")["status"], "recovered")
        self.action(item_id, "recover")
        self.assert_stats(active=0, recovered=1)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assert_evidence_preserved(original)
        types = [row["type"] for row in self.store.list_activities(limit=100)]
        for kind in ("item_reviewed", "item_extended", "item_disposed", "item_restored", "item_recovered"):
            self.assertEqual(types.count(kind), 1)
        self.assertEqual(types.count("item_due"), 2)
        self.assertEqual(types.count("email_sent"), 2)
        self.smtp_ssl.assert_not_called()

    def test_extension_cancels_old_failed_delivery_and_current_cycle_retries_once(self):
        original = self.observation(expires_at=self.now + timedelta(hours=1))
        item_id = original["id"]
        self.edit(item_id, name="Blue umbrella", confirm_review=True)
        self.smtp.send_message.side_effect = [
            smtplib.SMTPServerDisconnected("first cycle unavailable"),
            smtplib.SMTPServerDisconnected("new cycle unavailable"), None,
        ]
        self.now += timedelta(hours=1)
        with self.assertLogs("app.notifier", level="ERROR"):
            self.check_expirations(1)
        old = self.store.list_notifications()[0]
        self.assertEqual(old["status"], "failed")
        self.assertIn("first cycle", old["error"])

        extended = self.action(item_id, "extend", days=2)
        self.now += timedelta(minutes=6)
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 1)
        self.assertEqual(len(self.store.list_notifications()), 1)
        self.assertEqual(self.get("/api/dashboard")["notifications"][0]["status"], "failed")

        self.now = main.parse_dt(extended["expires_at"])
        with self.assertLogs("app.notifier", level="ERROR"):
            self.check_expirations(1)
        current = max(self.store.list_notifications(), key=lambda row: row["id"])
        self.assertNotEqual(current["id"], old["id"])
        self.assertEqual(current["status"], "failed")
        self.assertEqual(self.smtp.send_message.call_count, 2)
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 2)
        self.now += timedelta(minutes=5)
        self.check_expirations(0)
        self.check_expirations(0)
        by_id = {row["id"]: row for row in self.store.list_notifications()}
        self.assertEqual(set(by_id), {old["id"], current["id"]})
        self.assertEqual(by_id[old["id"]]["status"], "failed")
        self.assertEqual(by_id[current["id"]]["status"], "sent")
        self.assertEqual(self.smtp.send_message.call_count, 3)
        self.assertEqual(len({str(call.args[0]["Subject"]) for call in self.smtp.send_message.call_args_list}), 1)

        self.action(item_id, "recover")
        self.now += timedelta(days=3)
        self.check_expirations(0)
        self.assertEqual(self.smtp.send_message.call_count, 3)
        self.assert_stats(active=0, recovered=1)
        self.assert_evidence_preserved(original)

    def test_dismiss_restore_and_lifecycle_keep_search_pages_and_stats_consistent(self):
        first = self.observation("Alpha_umbrella", expires_at=self.now + timedelta(days=10))
        second = self.observation("Beta case", category="valuable", review_status="confirmed")
        third = self.observation("Gamma 100% bag", expires_at=self.now + timedelta(days=1))
        fourth = self.observation("Delta cup", category="food", review_status="confirmed",
                                  expires_at=self.now + timedelta(days=2))
        fifth = self.observation("Epsilon cable", review_status="confirmed")
        originals = [first, second, third, fourth, fifth]
        self.assert_stats(active=5, due_soon=2, review_needed=2)
        initial_pages = [self.get("/api/items", sort="name", limit=2, offset=offset) for offset in (0, 2, 4)]
        self.assertTrue(all(page["total"] == 5 for page in initial_pages))
        self.assertEqual(len({row["id"] for page in initial_pages for row in page["items"]}), 5)
        self.assertEqual(self.get("/api/items", q="_")["items"][0]["id"], first["id"])

        self.action(first["id"], "dismiss")
        self.assertEqual(self.get("/api/items", q="_")["total"], 0)
        self.assertEqual(self.get("/api/items", status="dismissed", q="_")["items"][0]["id"], first["id"])
        self.assertEqual(self.get("/api/items")["total"], 4)
        self.assert_stats(active=4, due_soon=2, review_needed=1)
        self.assert_evidence_preserved(first)
        self.edit(third["id"], name="Gamma 100% bag", confirm_review=True)
        literal = self.get("/api/items", q="100%", category="general", review="confirmed")
        self.assertEqual([row["id"] for row in literal["items"]], [third["id"]])

        restored = self.action(first["id"], "restore")
        self.assertEqual(restored["review_status"], "needs_review")
        self.assert_stats(active=5, due_soon=2, review_needed=1)
        self.edit(first["id"], name="Alpha reviewed umbrella", confirm_review=True)
        self.assertEqual(self.get("/api/items", q="_")["total"], 0)
        self.assertEqual(self.get("/api/items", q="reviewed")["items"][0]["id"], first["id"])
        self.action(second["id"], "dispose")
        self.action(third["id"], "recover")
        self.action(fifth["id"], "dismiss")
        self.assert_stats(active=2, due_soon=1, recovered=1)
        visible = {first["id"], second["id"], third["id"], fourth["id"]}
        final_pages = [self.get("/api/items", sort="name", limit=2, offset=offset) for offset in (0, 2)]
        self.assertTrue(all(page["total"] == 4 for page in final_pages))
        self.assertEqual({row["id"] for page in final_pages for row in page["items"]}, visible)
        self.assertEqual(self.get("/api/items", sort="name", limit=2, offset=4)["offset"], 2)
        self.assertEqual({row["id"] for row in main.active_items_for_vision()}, {first["id"], fourth["id"]})
        for original in originals:
            self.assert_evidence_preserved(original)
        self.check_expirations(0)
        self.smtp.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
