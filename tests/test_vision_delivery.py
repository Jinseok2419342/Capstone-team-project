from __future__ import annotations

import queue
import threading
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from app.vision import ChangeEvent, VisionMonitor


class VisionDeliveryTests(unittest.TestCase):
    @staticmethod
    def event(item_id=None):
        return ChangeEvent("added", (40, 50, 60, 70), None, None, None, 0.9, matched_item_id=item_id)

    def start_dispatcher(self, monitor, callbacks, diagnostics=None):
        done = threading.Event()
        stop = threading.Event()
        worker = threading.Thread(target=monitor._dispatch_callbacks, args=(callbacks, done, diagnostics, stop))
        worker.start()

        def cleanup():
            stop.set()
            done.set()
            worker.join(2)
            self.assertFalse(worker.is_alive())

        self.addCleanup(cleanup)
        return worker, done, stop

    def test_partial_batch_retries_only_uncommitted_event_with_same_identity(self) -> None:
        first, second = self.event(), self.event()
        calls = []

        def apply(event):
            calls.append(event.event_id)
            return not (event is second and calls.count(second.event_id) == 1)

        monitor = VisionMonitor(lambda: {}, apply, lambda: [])
        callbacks = queue.Queue()
        batch = monitor._queue_changes([first, second], monitor.DEFAULTS, callbacks, 0)
        self.start_dispatcher(monitor, callbacks)
        self.assertTrue(batch.done.wait(2))
        self.assertTrue(batch.succeeded)
        self.assertEqual(calls, [first.event_id, second.event_id, second.event_id])
        self.assertNotEqual(first.event_id, second.event_id)
        self.assertEqual(monitor.get_status()["callback_retry_count"], 1)
        self.assertEqual(monitor.get_status()["pending_changes"], 0)
        self.assertIsNone(monitor.get_status()["last_error"])

    def test_callback_exception_retries_and_none_remains_compatible_success(self) -> None:
        apply = Mock(side_effect=[OSError("database busy"), None])
        monitor = VisionMonitor(lambda: {}, apply, lambda: [])
        callbacks = queue.Queue()
        event = self.event()
        batch = monitor._queue_changes([event], monitor.DEFAULTS, callbacks, 0)
        self.start_dispatcher(monitor, callbacks)
        self.assertTrue(batch.done.wait(2))
        self.assertTrue(batch.succeeded)
        self.assertEqual(apply.call_count, 2)
        self.assertEqual(callbacks.unfinished_tasks, 0)

    def test_full_queue_retains_batch_until_capacity_is_available(self) -> None:
        apply = Mock(return_value=True)
        monitor = VisionMonitor(lambda: {}, apply, lambda: [])
        callbacks = queue.Queue(maxsize=1)
        callbacks.put(("event", {"type": "busy"}))
        batch = monitor._queue_changes([self.event()], monitor.DEFAULTS, callbacks, 0)
        self.assertFalse(batch.queued)
        self.assertFalse(batch.done.is_set())
        self.assertEqual(monitor.get_status()["pending_changes"], 1)
        callbacks.get_nowait()
        callbacks.task_done()
        monitor._try_queue_batch(callbacks, batch)
        self.start_dispatcher(monitor, callbacks)
        self.assertTrue(batch.done.wait(1))
        self.assertTrue(batch.succeeded)
        apply.assert_called_once()

    def test_diagnostics_do_not_consume_change_capacity(self) -> None:
        apply = Mock(return_value=True)
        monitor = VisionMonitor(lambda: {}, apply, lambda: [], lambda event: None)
        monitor._callback_queue = callbacks = queue.Queue(maxsize=1)
        monitor._diagnostic_queue = diagnostics = queue.Queue(maxsize=2)
        monitor._emit_event(callbacks, "one")
        monitor._emit_event(callbacks, "two")
        self.assertTrue(diagnostics.full())
        self.assertTrue(callbacks.empty())
        batch = monitor._queue_changes([self.event()], monitor.DEFAULTS, callbacks, 0)
        self.assertTrue(batch.queued)
        self.start_dispatcher(monitor, callbacks, diagnostics)
        self.assertTrue(batch.done.wait(1))
        apply.assert_called_once()

    def test_privacy_cancels_remaining_batch_after_inflight_commit(self) -> None:
        entered = threading.Event()
        resume = threading.Event()
        calls = []

        def apply(event):
            calls.append(event.event_id)
            entered.set()
            resume.wait(2)
            return True

        monitor = VisionMonitor(lambda: {}, apply, lambda: [])
        callbacks = queue.Queue()
        first, second = self.event(), self.event()
        batch = monitor._queue_changes([first, second], monitor.DEFAULTS, callbacks, 0)
        self.start_dispatcher(monitor, callbacks)
        try:
            self.assertTrue(entered.wait(1))
            monitor.set_privacy(True)
        finally:
            resume.set()
        self.assertTrue(batch.done.wait(1))
        self.assertEqual(calls, [first.event_id])
        self.assertEqual(batch.committed, 1)
        self.assertFalse(batch.succeeded)
        self.assertEqual(monitor.get_status()["uncommitted_changes"], 1)

    def test_shutdown_ends_failed_retries_and_reports_uncommitted_work(self) -> None:
        attempted = threading.Event()

        def apply(event):
            attempted.set()
            return False

        monitor = VisionMonitor(lambda: {}, apply, lambda: [])
        callbacks = queue.Queue()
        batch = monitor._queue_changes([self.event()], monitor.DEFAULTS, callbacks, 0)
        worker, done, stop = self.start_dispatcher(monitor, callbacks)
        self.assertTrue(attempted.wait(1))
        stop.set()
        done.set()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(batch.done.is_set())
        self.assertFalse(batch.succeeded)
        self.assertEqual(monitor.get_status()["uncommitted_changes"], 1)
        self.assertIn("uncommitted", monitor.get_status()["last_error"])

    def test_rebaseline_cancels_a_batch_waiting_for_capacity(self) -> None:
        monitor = VisionMonitor(lambda: {}, Mock(), lambda: [])
        callbacks = queue.Queue(maxsize=1)
        callbacks.put(("event", {}))
        batch = monitor._queue_changes([self.event()], monitor.DEFAULTS, callbacks, 0)
        monitor.rebaseline()
        monitor._try_queue_batch(callbacks, batch)
        self.assertTrue(batch.done.is_set())
        self.assertFalse(batch.queued)
        monitor._change_callback.assert_not_called()
        self.assertEqual(monitor.get_status()["uncommitted_changes"], 1)

    def _exercise_delayed_commit(self, reconnect=False) -> None:
        config = dict(VisionMonitor.DEFAULTS, camera_warmup_seconds=0.03, stable_seconds=0,
                      settle_seconds=0, monitor_fps=60, stabilize_camera=False,
                      camera_failures_before_retry=1, camera_retry_seconds=0.25)
        empty = np.full((240, 320, 3), 205, np.uint8)
        present = empty.copy()
        cv2.rectangle(present, (105, 75), (205, 175), (20, 28, 36), -1)
        cv2.circle(present, (155, 125), 22, (65, 75, 85), -1)
        entered = threading.Event()
        resume = threading.Event()
        waiting_preview = threading.Event()
        removed = threading.Event()
        inventory = []
        deliveries = []
        inventory_lock = threading.Lock()

        def apply(event):
            deliveries.append(event)
            if event.kind == "added":
                entered.set()
                if not resume.wait(3):
                    return False
                with inventory_lock:
                    inventory.append({"id": 73, "bbox": event.bbox,
                                      "reference_jpeg": event.after_jpeg,
                                      "background_jpeg": event.before_jpeg,
                                      "tracking_revision": 1})
            elif event.kind == "removed":
                with inventory_lock:
                    inventory.clear()
                removed.set()
            return True

        def active():
            with inventory_lock:
                return list(inventory)

        monitor = VisionMonitor(lambda: config, apply, active)
        camera = Mock()
        reads = [0]

        def read():
            monitor._stop_event.wait(0.002)
            reads[0] += 1
            if reconnect and entered.is_set():
                return False, None
            show_empty = not monitor.get_status()["baseline_ready"] or entered.is_set()
            return True, (empty if show_empty else present).copy()

        reconnected_camera = Mock()
        reconnected_read = threading.Event()

        def read_after_reconnect():
            monitor._stop_event.wait(0.002)
            reconnected_read.set()
            return True, empty.copy()

        reconnected_camera.read.side_effect = read_after_reconnect

        def preview(frame, phase, *args, **kwargs):
            if entered.is_set() and phase == "commit_pending" and (not reconnect or reconnected_read.is_set()):
                waiting_preview.set()
            return True

        camera.read.side_effect = read
        with patch.object(monitor, "_open_capture", side_effect=[(camera, None), (reconnected_camera, None)]) as opener, \
             patch.object(monitor, "_publish_live_preview", side_effect=preview), \
             patch.object(monitor, "_detect_changes", wraps=monitor._detect_changes) as detect:
            monitor.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(waiting_preview.wait(1))
                self.assertEqual(detect.call_count, 1)
                self.assertEqual(monitor.get_status()["pending_changes"], 1)
                self.assertGreater(monitor.get_status()["frame_sequence"], 3)
                self.assertEqual(opener.call_count, 2 if reconnect else 1)
                resume.set()
                self.assertTrue(removed.wait(2))
            finally:
                resume.set()
                self.assertTrue(monitor.stop(timeout=2))
        self.assertEqual([event.kind for event in deliveries], ["added", "removed"])
        self.assertEqual(deliveries[1].matched_item_id, 73)
        self.assertEqual(deliveries[1].expected_revision, 1)
        self.assertEqual(inventory, [])

    def test_delayed_added_commit_then_removal_keeps_correct_inventory_id(self) -> None:
        self._exercise_delayed_commit()

    def test_reconnect_while_commit_pending_keeps_scene_until_acknowledged(self) -> None:
        self._exercise_delayed_commit(reconnect=True)

    def test_offline_manual_reconcile_survives_later_settings_rebaseline(self) -> None:
        config = dict(VisionMonitor.DEFAULTS, stable_seconds=0, camera_warmup_seconds=0)
        monitor = VisionMonitor(lambda: config, lambda event: True, lambda: [])
        monitor.rebaseline(reconcile_items=True)
        monitor.rebaseline()
        stop, done = threading.Event(), threading.Event()
        camera = Mock()
        reads = [0]

        def read():
            reads[0] += 1
            if reads[0] > 1:
                stop.set()
            return True, np.full((120, 160, 3), 205, np.uint8)

        camera.read.side_effect = read
        with patch.object(monitor, "_open_capture", return_value=(camera, None)), \
             patch.object(monitor, "_publish_live_preview"), \
             patch.object(monitor, "_reconcile_absent_active_items", return_value=[]) as reconcile:
            monitor._run(stop, queue.Queue(), done)
        reconcile.assert_called_once()
        self.assertIsNone(monitor.get_status()["last_error"])

    def test_failed_inventory_read_preserves_last_snapshot_and_marks_it_unavailable(self) -> None:
        getter = Mock(side_effect=[
            [{"id": 4, "bbox": [20, 30, 40, 50], "tracking_revision": 8}],
            OSError("DB unavailable"),
            None,
        ])
        monitor = VisionMonitor(lambda: {}, lambda event: True, getter)
        previous = monitor._fetch_active_boxes(320, 240, [])
        self.assertTrue(monitor.get_status()["inventory_connected"])
        self.assertEqual(previous[0].tracking_revision, 8)
        for _ in range(2):
            self.assertIs(monitor._fetch_active_boxes(320, 240, previous), previous)
            self.assertFalse(monitor.get_status()["inventory_connected"])

    def _exercise_inventory_failure(self, fail_initially):
        config = dict(VisionMonitor.DEFAULTS, stable_seconds=0, settle_seconds=0,
                      camera_warmup_seconds=0, monitor_fps=60,
                      active_items_refresh_seconds=0.25, stabilize_camera=False)
        available = threading.Event()
        paused = threading.Event()
        resumed = threading.Event()
        delivered = []
        reads = [0]

        def active():
            reads[0] += 1
            if not available.is_set() and (fail_initially or reads[0] > 1):
                raise OSError("inventory unavailable")
            return []

        def apply(event):
            delivered.append(event)
            resumed.set()
            return True

        monitor = VisionMonitor(lambda: config, apply, active)
        empty = np.full((240, 320, 3), 205, np.uint8)
        present = empty.copy()
        cv2.rectangle(present, (105, 75), (205, 175), (20, 28, 36), -1)
        camera = Mock()

        def read():
            monitor._stop_event.wait(0.002)
            return True, (present if fail_initially or monitor.get_status()["baseline_ready"] else empty).copy()

        def preview(frame, phase, *args, **kwargs):
            if phase == "inventory_unavailable":
                paused.set()
            if fail_initially and available.is_set() and phase == "monitoring":
                resumed.set()
            return True

        camera.read.side_effect = read
        with patch.object(monitor, "_open_capture", return_value=(camera, None)), \
             patch.object(monitor, "_publish_live_preview", side_effect=preview), \
             patch.object(monitor, "_detect_changes", wraps=monitor._detect_changes) as detect:
            monitor.start()
            try:
                self.assertTrue(paused.wait(1))
                detect.assert_not_called()
                self.assertEqual(delivered, [])
                self.assertFalse(monitor.get_status()["inventory_connected"])
                if fail_initially:
                    self.assertFalse(monitor.get_status()["baseline_ready"])
                available.set()
                self.assertTrue(resumed.wait(2))
                self.assertTrue(monitor.get_status()["inventory_connected"])
            finally:
                self.assertTrue(monitor.stop(timeout=2))
        self.assertEqual([event.kind for event in delivered], [] if fail_initially else ["added"])

    def test_initial_inventory_failure_pauses_detection_but_keeps_preview_running(self):
        self._exercise_inventory_failure(fail_initially=True)

    def test_inventory_failure_before_detection_preserves_scene_for_later_retry(self):
        self._exercise_inventory_failure(fail_initially=False)


if __name__ == "__main__":
    unittest.main()
