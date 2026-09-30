from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import unittest
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app import main
from app.ai import Classification, ObjectClassifier
from app.store import Store
from app.vision import ChangeEvent


class AppResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        captures = root / "captures"
        captures.mkdir()
        self.store = Store(root / "app.sqlite3")
        self.store.initialize()
        self.stack.enter_context(patch.object(main, "store", self.store))
        self.stack.enter_context(patch.object(main.scheduler, "store", self.store))
        self.stack.enter_context(patch.object(main, "config", replace(
            main.config, data_dir=root, capture_dir=captures, db_path=self.store.db_path,
        )))
        self.stack.enter_context(patch.object(main, "classification_slots", threading.BoundedSemaphore(1)))
        self.stack.enter_context(patch.object(main, "_service_shutdown", threading.Event()))
        self.stack.enter_context(patch.object(main, "_reset_lock", threading.Lock()))
        self.stack.enter_context(patch.object(main, "_reset_recovery_thread", None))
        self.stack.enter_context(patch.object(main.vision, "rebaseline"))
        self.stack.enter_context(patch.object(main.vision, "set_privacy"))
        # Most route tests intentionally avoid lifespan/camera/SMTP startup.
        self.client = TestClient(main.app)
        self.stack.callback(self.client.close)
        self.event = ChangeEvent(
            kind="added", bbox=(10, 20, 30, 40), confidence=0.9,
            before_jpeg=b"before", after_jpeg=b"after", crop_jpeg=b"crop",
        )

    def test_invalid_settings_leave_entire_update_unchanged(self) -> None:
        self.store.update_settings({"site_name": "Original", "motion_threshold": 20})
        before = self.store.get_settings()
        for values in (
            {"motion_threshold": "oops"}, {"camera_index": 1.5},
            {"motion_threshold": True}, {"privacy_mode": "maybe"},
            {"stable_seconds": "NaN"}, {"stable_seconds": "Infinity"},
            {"smtp_port": None}, {"camera_retry_seconds": -1},
            {"admin_email": "person@example.com\nBcc: other@example.com"},
            {"openai_model": " "},
        ):
            with self.subTest(values=values):
                response = self.client.put("/api/settings", json={"site_name": "Changed", **values})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(self.store.get_settings(), before)

    def test_settings_support_valid_numeric_strings_and_explicit_false(self) -> None:
        response = self.client.put("/api/settings", json={
            "camera_index": "2", "stable_seconds": "1.25", "privacy_mode": "false",
        })
        self.assertEqual(response.status_code, 200, response.text)
        values = response.json()["settings"]
        self.assertEqual(values["camera_index"], 2)
        self.assertEqual(values["stable_seconds"], 1.25)
        self.assertIs(values["privacy_mode"], False)

    def test_concurrent_privacy_updates_keep_live_and_saved_state_in_order(self) -> None:
        first_applying = threading.Event()
        resume_first = threading.Event()
        second_finished = threading.Event()
        applied = []
        errors = []

        def apply_privacy(value):
            if threading.current_thread().name == "first-privacy-update":
                first_applying.set()
                resume_first.wait(3)
            applied.append(value)

        def update(value):
            try:
                main.update_settings({"privacy_mode": value})
            except Exception as exc:
                errors.append(exc)
            finally:
                if value:
                    second_finished.set()

        first = threading.Thread(target=update, args=(False,), name="first-privacy-update")
        second = threading.Thread(target=update, args=(True,))
        with patch.object(main.vision, "set_privacy", side_effect=apply_privacy):
            first.start()
            try:
                self.assertTrue(first_applying.wait(1))
                second.start()
                # The older request is paused inside the camera update. A
                # newer privacy write must wait for that update to finish.
                self.assertFalse(second_finished.wait(0.2))
            finally:
                resume_first.set()
                first.join(2)
                if second.ident is not None:
                    second.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(applied, [False, True])
        self.assertIs(self.store.get_settings()["privacy_mode"], True)

    def test_failed_provisional_persistence_removes_captures(self) -> None:
        with patch.object(self.store, "create_item", side_effect=RuntimeError("DB unavailable")):
            with self.assertRaises(RuntimeError):
                main.create_provisional_item(self.event)
        self.assertEqual(list(main.config.capture_dir.iterdir()), [])
        self.assertEqual(self.store.list_items(), [])

    def test_partial_capture_write_failure_removes_first_capture(self) -> None:
        save_capture = main.save_capture

        def fail_background(image, prefix="item"):
            if prefix == "background":
                raise OSError("disk full")
            return save_capture(image, prefix)

        with patch.object(main, "save_capture", side_effect=fail_background):
            with self.assertRaises(OSError):
                main.create_provisional_item(self.event)
        self.assertEqual(list(main.config.capture_dir.iterdir()), [])

    def test_capture_write_failure_removes_its_partial_file(self) -> None:
        write_bytes = Path.write_bytes

        def partial_write(path, content):
            write_bytes(path, content[:2])
            raise OSError("disk full during write")

        with patch.object(Path, "write_bytes", autospec=True, side_effect=partial_write):
            with self.assertRaisesRegex(OSError, "disk full"):
                main.save_capture(b"image bytes")

        self.assertEqual(list(main.config.capture_dir.iterdir()), [])

    def test_activity_failure_keeps_committed_item_available_for_analysis(self) -> None:
        with patch.object(self.store, "create_activity", side_effect=RuntimeError("activity failure")):
            with self.assertLogs("lost-item-admin", level="ERROR"):
                item = main.create_provisional_item(self.event)
        self.assertEqual(self.store.get_item(item["id"])["provider"], "pending")
        self.assertTrue(Path(item["image_path"]).exists())

    def test_executor_rejection_preserves_item_and_releases_slot(self) -> None:
        with patch.object(main, "classification_pool") as pool:
            pool.submit.side_effect = RuntimeError("executor is stopping")
            with self.assertLogs("lost-item-admin", level="WARNING"):
                main.handle_vision_change(self.event)
        item = self.store.list_items()[0]
        self.assertEqual(item["provider"], "offline_review")
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        main.classification_slots.release()

    def test_rejected_submission_preserves_concurrent_manual_edit(self) -> None:
        def edit_then_reject(worker, item_id, event, *context):
            main.edit_item(item_id, main.ItemEdit(name="Administrator name", confirm_review=True))
            return False

        with patch.object(main, "submit_classification", side_effect=edit_then_reject):
            main.handle_vision_change(self.event)

        item = self.store.list_items()[0]
        self.assertEqual(item["name"], "Administrator name")
        self.assertEqual(item["provider"], "manual")

    def test_late_classification_preserves_manual_extension(self) -> None:
        item = main.create_provisional_item(self.event)
        response = self.client.post(f"/api/items/{item['id']}/extend", json={"days": 7})
        self.assertEqual(response.status_code, 200)
        manual_expiry = response.json()["expires_at"]
        result = Classification("음식", "음식 설명", "food", 0.95, "test", action="added")
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=result):
            main.classify_existing_item(item["id"], self.event)
        preserved = self.store.get_item(item["id"])
        self.assertEqual(preserved["expires_at"], manual_expiry)
        self.assertEqual(preserved["provider"], "manual_review")
        self.assertNotEqual(preserved["name"], "분석 중인 새 물품")

    def test_manual_edit_resolves_review_and_rejects_empty_names(self) -> None:
        item = self.store.create_item({"name": "확인 필요", "category": "general", "provider": "offline_review"})
        for body in ({}, {"name": "   "}):
            response = self.client.patch(f"/api/items/{item['id']}", json=body)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.store.get_item(item["id"])["provider"], "offline_review")
        response = self.client.patch(f"/api/items/{item['id']}", json={"name": "  우산  ", "confirm_review": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "우산")
        self.assertEqual(response.json()["provider"], "manual")

    def test_startup_restores_privacy_before_camera_and_recovers_pending_jobs(self) -> None:
        pending = main.create_provisional_item(self.event)
        self.store.update_settings({"privacy_mode": True})
        order = []
        pools = []
        with patch.object(main.vision, "set_privacy", side_effect=lambda value: order.append(("privacy", value))), \
             patch.object(main.vision, "start", side_effect=lambda: order.append(("start", None))), \
             patch.object(main.vision, "stop", return_value=True), \
             patch.object(main.scheduler, "start"), patch.object(main.scheduler, "stop", return_value=True), \
             patch.object(main, "classification_pool"):
            for _ in range(2):
                with TestClient(main.app):
                    pools.append(main.classification_pool)
                    self.assertEqual(main.classification_pool.submit(lambda: 42).result(), 42)
        self.assertIsNot(pools[0], pools[1])
        self.assertEqual(order, [("privacy", True), ("start", None)] * 2)
        self.assertEqual(self.store.get_item(pending["id"])["provider"], "offline_review")

    def test_reset_waits_for_camera_and_notification_workers(self) -> None:
        for camera_done, scheduler_done, mode in (
            (False, True, "backup"), (True, False, "backup"),
            (False, True, "quick"), (True, False, "quick"),
        ):
            finish_worker = threading.Event()
            payload = {"mode": mode, "confirmation": "시연 초기화" if mode == "quick" else "초기화"}

            def slow_stop(timeout=None):
                if timeout is None:
                    return False
                return finish_worker.wait(0.05)

            with self.subTest(camera_done=camera_done, mode=mode), \
                 patch.object(main.vision, "stop", side_effect=(None if camera_done else slow_stop), return_value=True), \
                 patch.object(main.scheduler, "stop", side_effect=(None if scheduler_done else slow_stop), return_value=True), \
                 patch.object(main.vision, "start") as camera_start, \
                 patch.object(main.scheduler, "start") as scheduler_start, \
                 patch.object(main, "backup_and_reset_operational_data") as reset:
                recovery = None
                try:
                    response = self.client.post("/api/maintenance/reset", json=payload)
                    self.assertEqual(response.status_code, 409)
                    self.assertIn("자동 재개", response.json()["detail"])
                    recovery = main._reset_recovery_thread
                    self.assertIsNotNone(recovery)
                    self.assertTrue(main._reset_lock.locked())
                    camera_start.assert_not_called()
                    scheduler_start.assert_not_called()
                    retry = self.client.post("/api/maintenance/reset", json=payload)
                    self.assertEqual(retry.status_code, 409)
                    reset.assert_not_called()
                finally:
                    finish_worker.set()
                    if recovery is not None:
                        recovery.join(2)
                self.assertFalse(recovery.is_alive())
                self.assertFalse(main._reset_lock.locked())
                camera_start.assert_called_once()
                scheduler_start.assert_called_once()
                reset.assert_not_called()

    def test_lifespan_shutdown_cancels_deferred_reset_restart(self) -> None:
        recovery_waiting = threading.Event()
        foreground_stops = []

        def camera_stop(timeout=None):
            if timeout is None:
                foreground_stops.append(True)
                return len(foreground_stops) > 1
            recovery_waiting.set()
            main._service_shutdown.wait(0.05)
            return False

        with patch.object(main.vision, "start") as camera_start, \
             patch.object(main.vision, "stop", side_effect=camera_stop), \
             patch.object(main.scheduler, "start") as scheduler_start, \
             patch.object(main.scheduler, "stop", return_value=True), \
             patch.object(main, "classification_pool"), \
             patch.object(main, "backup_and_reset_operational_data") as reset:
            with TestClient(main.app) as client:
                response = client.post("/api/maintenance/reset", json={"confirmation": "초기화"})
                self.assertEqual(response.status_code, 409)
                self.assertTrue(recovery_waiting.wait(1))
                recovery = main._reset_recovery_thread
                self.assertIsNotNone(recovery)
            self.assertFalse(recovery.is_alive())
            self.assertFalse(main._reset_lock.locked())
            camera_start.assert_called_once()
            scheduler_start.assert_called_once()
            reset.assert_not_called()

    def test_empty_camera_stream_can_be_cancelled(self) -> None:
        async def exercise():
            response = main.camera_stream()
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(anext(response.body_iterator), timeout=0.01)
            await response.body_iterator.aclose()
        with patch.object(main.vision, "get_jpeg", return_value=b""):
            asyncio.run(exercise())


class AIConfidenceValidationTests(unittest.TestCase):
    def test_invalid_confidence_never_authorizes_automatic_actions(self) -> None:
        classifier = ObjectClassifier(Mock(), lambda: {})
        for action in ("added", "removed"):
            for confidence in (None, "wrong", "NaN", float("inf"), float("nan"), True, [], {}, -0.1, 1.4):
                with self.subTest(action=action, confidence=confidence):
                    result = classifier._normalize(json.dumps({
                        "action": action, "confidence": confidence,
                        "estimated_value_krw": float("inf"),
                    }), "test")
                    self.assertEqual(result.confidence, 0.0)
                    self.assertEqual(result.action, "uncertain")
                    self.assertIsNone(result.estimated_value_krw)


if __name__ == "__main__":
    unittest.main()
