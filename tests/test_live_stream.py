"""Synthetic stream rehearsals of the real capture -> inventory -> HTTP path.

These are software regressions, not a camera accuracy or Raspberry Pi benchmark.
Only camera input and remote VLM responses are replaced. The capture/dispatcher
threads, detector, motion/settle state machine, SQLite, classification executor,
application lifespan and API serialization execute normally. Short timing and
640x360 frames make the fixture fast; detector sensitivity stays at app defaults.
The unrelated expiration scheduler is disabled so no SMTP service is contacted.
"""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from collections import OrderedDict
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app import main
from app.ai import Classification, ObjectClassifier
from app.store import Store
from app.vision import VisionMonitor


class _SceneCamera:
    """A continuously readable camera whose scene changes at test checkpoints."""

    def __init__(self, frame):
        self._frame = frame.copy()
        self._lock = threading.Lock()
        self.released = threading.Event()

    def show(self, frame):
        with self._lock:
            self._frame = frame.copy()

    def read(self):
        # Yield CPU to the actual callback/executor threads between reads.
        if self.released.wait(0.004):
            return False, None
        with self._lock:
            return True, self._frame.copy()

    def release(self):
        self.released.set()


class DemoStreamTests(unittest.TestCase):
    @staticmethod
    def scene(*objects):
        frame = np.full((360, 640, 3), 205, np.uint8)
        # Stationary, distributed features let normal camera stabilization run.
        for x in (45, 160, 320, 485, 595):
            for y in (45, 310):
                cv2.circle(frame, (x, y), 7, (100, 115, 130), -1)
                cv2.line(frame, (x - 12, y - 12), (x + 8, y - 12), (155, 160, 165), 2)
        for left, top, style in objects:
            color = (30, 45, 65) if style == 0 else (75, 55, 25)
            cv2.rectangle(frame, (left, top), (left + 95, top + 75), color, -1)
            cv2.line(frame, (left + 8, top + 8), (left + 85, top + 65), (130, 150, 175), 5)
            cv2.circle(frame, (left + 68, top + 22), 10, (175, 185, 190), -1)
            if style:
                cv2.line(frame, (left + 12, top + 56), (left + 50, top + 16), (190, 120, 90), 6)
        return frame

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        captures = root / "captures"
        captures.mkdir()
        self.store = Store(root / "stream.sqlite3")
        self.store.initialize()
        # These timing settings are specific to the generated stream fixture.
        self.store.update_settings({
            "camera_width": 640, "camera_height": 360,
            "camera_fps": 60, "monitor_fps": 60,
            "settle_seconds": 0.04, "stable_seconds": 0.04,
            "preview_stream_fps": 15, "preview_max_width": 640,
        })
        self.stack.enter_context(patch.object(main, "store", self.store))
        self.stack.enter_context(patch.object(main, "config", replace(
            main.config, data_dir=root, capture_dir=captures, db_path=self.store.db_path,
            classifier_workers=1, classification_slots=2,
            openai_api_key="", gemini_api_key="", smtp_password="",
        )))
        self.stack.enter_context(patch.object(main, "classification_pool"))
        self.stack.enter_context(patch.object(main, "classification_slots", threading.BoundedSemaphore(2)))
        self.stack.enter_context(patch.object(main, "_reference_cache", OrderedDict()))
        self.stack.enter_context(patch.object(main, "_reference_cache_bytes", 0))
        self.stack.enter_context(patch.object(main, "_service_shutdown", threading.Event()))
        self.stack.enter_context(patch.object(main, "_reset_recovery_thread", None))
        self.stack.enter_context(patch.object(main, "scheduler", Mock()))
        self.classification_entered = threading.Event()
        self.classification_release = threading.Event()
        self.classification_release.set()
        self.classifier = Mock(spec=ObjectClassifier)
        self.classifier.classify.side_effect = self.classify
        self.stack.enter_context(patch.object(main, "classifier", self.classifier))
        self.deliveries = []
        self.diagnostics = []

        def on_change(event):
            acknowledged = main.handle_vision_change(event)
            if acknowledged:
                self.deliveries.append(event)
            return acknowledged

        def on_diagnostic(event):
            self.diagnostics.append(event)
            main.vision_event_callback(event)

        self.monitor = VisionMonitor(
            lambda: {**main.current_settings(), "camera_warmup_seconds": 0.04},
            on_change, main.active_items_for_vision, on_diagnostic,
        )
        self.camera = _SceneCamera(self.scene())
        self.stack.enter_context(patch.object(main, "vision", self.monitor))
        self.stack.enter_context(patch.object(self.monitor, "_open_capture", return_value=(self.camera, None)))
        # The context runs the real app lifespan, starting both vision threads
        # and a real bounded classification executor, and drains them on exit.
        self.client = self.stack.enter_context(TestClient(main.app))
        # Release a deliberately delayed fake VLM before lifespan cleanup joins.
        self.stack.callback(self.classification_release.set)
        self.wait_until(lambda: self.monitor.get_status()["baseline_ready"], "initial stable scene")

    def classify(self, images, *, scene_images):
        self.classification_entered.set()
        if not self.classification_release.wait(8):
            raise TimeoutError("test did not release synthetic VLM response")
        return Classification(
            "Synthetic desk item", "Generated stream fixture", "general", 0.96,
            "synthetic_vlm", action="added", raw="synthetic regression response",
        )

    def wait_until(self, predicate, checkpoint, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            threading.Event().wait(0.01)
        self.fail(
            f"Timed out at {checkpoint}; camera={self.monitor.get_status()}; "
            f"deliveries={[(event.kind, event.matched_item_id) for event in self.deliveries]}; "
            f"items={[(item['id'], item['status'], item['review_status'], item['bbox']) for item in self.store.list_items()]}"
        )

    def item(self, item_id):
        response = self.client.get(f"/api/items/{item_id}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def wait_for_delivery(self, count):
        self.wait_until(lambda: len(self.deliveries) >= count, f"{count} acknowledged changes")
        self.wait_until(
            lambda: self.monitor.get_status()["phase"] == "monitoring"
            and self.monitor.get_status()["pending_changes"] == 0,
            "scene receipt applied",
        )

    def assert_quiet_frames(self, event_count):
        starting = self.monitor.get_status()["frame_sequence"]
        self.wait_until(
            lambda: self.monitor.get_status()["frame_sequence"] >= starting + 8,
            "unchanged live scene",
        )
        self.assertEqual(len(self.deliveries), event_count)
        status = self.client.get("/api/health").json()["camera"]
        self.assertTrue(status["camera_connected"])
        self.assertTrue(status["inventory_connected"])
        self.assertEqual(status["pending_changes"], 0)
        self.assertEqual(status["uncommitted_changes"], 0)
        self.assertIsNone(status["last_error"])
        self.assertEqual(status["phase"], "monitoring")

    def assert_evidence_and_api(self, item_id):
        response = self.client.get(f"/api/items/{item_id}/image")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertIsNotNone(cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR))
        args, kwargs = self.classifier.classify.call_args
        self.assertEqual(len(args[0]), 2)
        self.assertEqual(len(kwargs["scene_images"]), 2)
        for jpeg in [*args[0], *kwargs["scene_images"]]:
            self.assertIsNotNone(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR))

    def test_add_move_remove_and_place_again_through_real_stream(self):
        self.classification_release.clear()
        self.camera.show(self.scene((180, 135, 0)))
        self.wait_for_delivery(1)
        self.assertTrue(self.classification_entered.wait(1))
        initial = self.store.list_items()[0]
        item_id = initial["id"]
        pending = self.item(item_id)
        self.assertEqual(pending["review_status"], "pending")
        self.assertEqual(pending["status"], "stored")
        self.assertEqual(pending["source_kind"], "camera")
        self.assert_evidence_and_api(item_id)
        self.classification_release.set()
        self.wait_until(lambda: self.store.get_item(item_id)["review_status"] == "confirmed", "AI metadata commit")
        added = self.item(item_id)
        self.assertEqual(added["name"], "Synthetic desk item")
        self.assertEqual(added["retention_days"], 60)
        original_image = self.store.get_item(item_id)["image_path"]

        self.camera.show(self.scene((250, 135, 0)))
        self.wait_for_delivery(2)
        moved = self.item(item_id)
        self.assertEqual(moved["status"], "stored")
        self.assertGreater(moved["bbox"][0], added["bbox"][0])
        self.assertGreater(moved["tracking_revision"], added["tracking_revision"])
        self.assertEqual(self.deliveries[1].matched_item_id, item_id)
        self.assertEqual(self.deliveries[1].expected_revision, added["tracking_revision"])
        self.assertFalse(Path(original_image).exists())
        self.assert_evidence_and_api(item_id)

        self.camera.show(self.scene())
        self.wait_for_delivery(3)
        removed = self.item(item_id)
        self.assertEqual(removed["status"], "recovered")
        self.assertEqual(self.deliveries[2].expected_revision, moved["tracking_revision"])
        self.assertEqual(self.client.get("/api/items?status=stored").json()["total"], 0)
        self.assertEqual(self.client.get("/api/items?status=recovered").json()["items"][0]["id"], item_id)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assertEqual(self.classifier.classify.call_count, 1)
        self.assert_quiet_frames(3)

        # Reappearing after confirmed removal is a fresh observation. The old
        # history stays recovered instead of being silently reassigned.
        self.camera.show(self.scene((180, 135, 0)))
        self.wait_for_delivery(4)
        self.wait_until(lambda: self.classifier.classify.call_count == 2, "second classification")
        active = self.client.get("/api/items?status=stored").json()["items"]
        self.assertEqual(len(active), 1)
        self.assertNotEqual(active[0]["id"], item_id)
        self.assertEqual(self.item(item_id)["status"], "recovered")
        self.assertEqual(len(self.store.list_items()), 2)
        self.assertEqual([event.kind for event in self.deliveries], ["added", "moved", "removed", "added"])
        self.assertEqual(len({event.event_id for event in self.deliveries}), 4)
        types = [entry["type"] for entry in self.store.list_activities(limit=100) if entry["item_id"] == item_id]
        self.assertEqual(types.count("item_detected"), 1)
        self.assertEqual(types.count("item_moved"), 1)
        self.assertEqual(types.count("item_recovered"), 1)
        self.assert_quiet_frames(4)

    def test_pending_vlm_does_not_block_move_remove_or_resurrect_removed_item(self):
        self.classification_release.clear()
        self.camera.show(self.scene((180, 135, 0)))
        self.wait_for_delivery(1)
        self.assertTrue(self.classification_entered.wait(1))
        item_id = self.store.list_items()[0]["id"]
        added = self.item(item_id)
        self.assertEqual(added["review_status"], "pending")

        self.camera.show(self.scene((250, 135, 0)))
        self.wait_for_delivery(2)
        moved = self.item(item_id)
        self.assertEqual(moved["review_status"], "pending")
        self.assertGreater(moved["bbox"][0], added["bbox"][0])
        moved_capture = self.store.get_item(item_id)["image_path"]
        moved_bytes = Path(moved_capture).read_bytes()

        self.camera.show(self.scene())
        self.wait_for_delivery(3)
        recovered = self.item(item_id)
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["review_status"], "pending")
        self.assertFalse(self.classification_release.is_set())
        self.assert_quiet_frames(3)

        self.classification_release.set()
        self.wait_until(lambda: self.store.get_item(item_id)["review_status"] == "confirmed", "late AI metadata")
        final = self.item(item_id)
        self.assertEqual(final["status"], "recovered")
        self.assertEqual(final["bbox"], moved["bbox"])
        self.assertEqual(final["tracking_revision"], recovered["tracking_revision"])
        self.assertEqual(self.store.get_item(item_id)["image_path"], moved_capture)
        self.assertEqual(Path(moved_capture).read_bytes(), moved_bytes)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assertEqual(len(self.store.list_items()), 1)
        self.assertEqual(self.classifier.classify.call_count, 1)
        self.assertEqual([event.kind for event in self.deliveries], ["added", "moved", "removed"])
        self.assertEqual([event.matched_item_id for event in self.deliveries[1:]], [item_id, item_id])
        self.assert_evidence_and_api(item_id)
        self.assert_quiet_frames(3)

    def test_two_items_keep_independent_ids_when_one_moves_and_other_is_removed(self):
        self.camera.show(self.scene((145, 135, 0), (400, 135, 1)))
        self.wait_for_delivery(2)
        self.wait_until(
            lambda: all(item["review_status"] == "confirmed" for item in self.store.list_items()),
            "both AI descriptions",
        )
        initial = sorted(self.store.list_items(), key=lambda item: item["bbox"][0])
        self.assertEqual(len(initial), 2)
        left, right = initial
        self.assertEqual(self.client.get("/api/items?status=stored").json()["total"], 2)

        # A single stable scene now contains both a relocation and a removal.
        # Actual batch delivery must neither duplicate nor exchange item IDs.
        self.camera.show(self.scene((225, 135, 0)))
        self.wait_for_delivery(4)
        self.assertEqual(
            {(event.kind, event.matched_item_id) for event in self.deliveries[2:]},
            {("moved", left["id"]), ("removed", right["id"])},
        )
        moved = self.item(left["id"])
        self.assertGreater(moved["bbox"][0], left["bbox"][0])
        self.assertEqual(moved["status"], "stored")
        self.assertEqual(self.item(right["id"])["status"], "recovered")
        self.assertEqual([entry["id"] for entry in main.active_items_for_vision()], [left["id"]])
        self.assertEqual(len(self.store.list_items()), 2)
        self.assert_quiet_frames(4)

        self.camera.show(self.scene())
        self.wait_for_delivery(5)
        self.assertEqual(self.deliveries[4].kind, "removed")
        self.assertEqual(self.deliveries[4].matched_item_id, left["id"])
        self.assertEqual(self.deliveries[4].expected_revision, moved["tracking_revision"])
        self.assertEqual(self.client.get("/api/items?status=recovered").json()["total"], 2)
        self.assertEqual(self.client.get("/api/items?status=stored").json()["total"], 0)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assertEqual(self.classifier.classify.call_count, 2)
        self.assert_quiet_frames(5)


if __name__ == "__main__":
    unittest.main()
