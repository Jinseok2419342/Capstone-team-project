from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.notifier import EmailNotifier, ExpirationScheduler
from app.store import Store


class NotificationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / "notifications.db")
        self.store.initialize()

    def create_expired(self, name: str = "Lunch") -> dict:
        return self.store.create_item(
            {"name": name, "category": "food",
             "expires_at": datetime.now(timezone.utc) - timedelta(days=1)}
        )

    def test_separate_schedulers_deliver_one_message_per_expiry_cycle(self) -> None:
        self.create_expired()
        sender = Mock()
        sender.send_due.return_value = (True, None)
        schedulers = [ExpirationScheduler(Store(self.store.db_path), sender) for _ in range(2)]
        barrier = Barrier(2)
        original = Store.get_due_notifications_candidates

        def simultaneous_candidates(store: Store, now=None) -> list[dict]:
            items = original(store, now)
            barrier.wait(timeout=5)
            return items

        with patch.object(Store, "get_due_notifications_candidates", simultaneous_candidates):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda scheduler: scheduler.run_once(), schedulers))

        self.assertEqual(sender.send_due.call_count, 1)
        self.assertEqual(len(self.store.list_notifications()), 1)
        self.assertEqual(self.store.list_notifications()[0]["status"], "sent")
        self.assertCountEqual(
            [row["type"] for row in self.store.list_activities()], ["item_due", "email_sent"]
        )

    def test_separate_schedulers_cannot_both_retry_a_failed_notification(self) -> None:
        self.create_expired()
        sender = Mock()
        sender.send_due.return_value = (False, "Temporary mail failure")
        ExpirationScheduler(self.store, sender).run_once()
        sender.reset_mock()
        sender.send_due.return_value = (True, None)
        schedulers = [
            ExpirationScheduler(Store(self.store.db_path), sender, retry_after_seconds=0)
            for _ in range(2)
        ]
        barrier = Barrier(2)
        original = Store.list_retryable_due_notifications

        def simultaneous_retries(store: Store, *args, **kwargs) -> list[dict]:
            retries = original(store, *args, **kwargs)
            barrier.wait(timeout=5)
            return retries

        with patch.object(Store, "list_retryable_due_notifications", simultaneous_retries):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda scheduler: scheduler.run_once(), schedulers))
        self.assertEqual(sender.send_due.call_count, 1)
        self.assertEqual(self.store.list_notifications()[0]["status"], "sent")

    def test_recovery_after_candidate_snapshot_prevents_obsolete_email(self) -> None:
        item = self.create_expired()
        sender = Mock()
        original = self.store.create_notification

        def recover_before_delivery(*args, **kwargs) -> dict:
            notification = original(*args, **kwargs)
            self.store.mark_recovered(item["id"])
            return notification

        with patch.object(self.store, "create_notification", recover_before_delivery):
            ExpirationScheduler(self.store, sender).run_once()
        sender.send_due.assert_not_called()
        self.assertEqual(self.store.get_item(item["id"])["status"], "recovered")

    def test_sender_exception_records_failure_and_continues_other_items(self) -> None:
        self.create_expired("First")
        self.create_expired("Second")
        sender = Mock()
        sender.send_due.side_effect = [RuntimeError("SMTP disconnected"), (True, None)]
        with self.assertLogs("app.notifier", level="ERROR"):
            ExpirationScheduler(self.store, sender).run_once()
        self.assertCountEqual(
            [row["status"] for row in self.store.list_notifications()], ["failed", "sent"]
        )

    def test_stop_reports_live_send_and_start_does_not_revive_stopping_worker(self) -> None:
        self.create_expired("First")
        self.create_expired("Second")
        entered, release = Event(), Event()
        sender = Mock()

        def block_delivery(item: dict) -> tuple[bool, None]:
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test did not release sender")
            return True, None

        sender.send_due.side_effect = block_delivery
        scheduler = ExpirationScheduler(self.store, sender)
        scheduler.start()
        try:
            self.assertTrue(entered.wait(timeout=5))
            worker = scheduler._thread
            self.assertFalse(scheduler.stop(timeout=0.01))
            scheduler.start()
            self.assertIs(scheduler._thread, worker)
            self.assertTrue(scheduler._stop.is_set())
        finally:
            release.set()
            self.assertTrue(scheduler.stop(timeout=5))
        self.assertEqual(sender.send_due.call_count, 1)
        self.assertEqual(scheduler.run_once(), [])

    def test_stop_also_waits_for_manual_scheduler_pass(self) -> None:
        self.create_expired()
        entered, release = Event(), Event()
        sender = Mock()

        def block_delivery(item: dict) -> tuple[bool, None]:
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test did not release sender")
            return True, None

        sender.send_due.side_effect = block_delivery
        scheduler = ExpirationScheduler(self.store, sender)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(scheduler.run_once)
            try:
                self.assertTrue(entered.wait(timeout=5))
                self.assertFalse(scheduler.stop(timeout=0.01))
                scheduler.start()
                self.assertTrue(scheduler._stop.is_set())
                self.assertIsNone(scheduler._thread)
            finally:
                release.set()
                future.result(timeout=5)
        self.assertTrue(scheduler.stop(timeout=1))

    def test_email_uses_one_consistent_settings_snapshot(self) -> None:
        settings = {
            "admin_email": "admin@example.test", "smtp_username": "sender@example.test",
            "smtp_host": "mail.example.test", "smtp_port": 587, "smtp_use_tls": True,
        }
        getter = Mock(side_effect=[settings, {}])
        notifier = EmailNotifier(SimpleNamespace(smtp_password="test-only-password"), getter)
        with patch("app.notifier.smtplib.SMTP") as smtp:
            sent, error = notifier.send_due(
                {"id": 1, "name": "<object>\r\nBcc: unintended@example.test", "expires_at": "2026-09-01"}
            )
        self.assertTrue(sent)
        self.assertIsNone(error)
        getter.assert_called_once_with()
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertIsNone(message["Bcc"])
        self.assertNotIn("\n", str(message["Subject"]))
        self.assertIn("&lt;object&gt;", message.get_body(preferencelist=("html",)).get_content())


if __name__ == "__main__":
    unittest.main()
