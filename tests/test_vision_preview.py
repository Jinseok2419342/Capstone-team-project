from __future__ import annotations

import queue
import threading
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from app.vision import VisionMonitor, _ActiveBox, _FramePacer


class FramePacerTests(unittest.TestCase):
    def test_ten_fps_camera_keeps_seven_processed_frames_per_second(self) -> None:
        pacer = _FramePacer()
        accepted = [index for index in range(100) if pacer.ready(index / 10, 7)]
        self.assertEqual(len(accepted), 70)
        for second in range(10):
            self.assertEqual(sum(second * 10 <= value < (second + 1) * 10 for value in accepted), 7)
        self.assertTrue(all(1 <= right - left <= 2 for left, right in zip(accepted, accepted[1:])))

    def test_processing_pause_discards_old_deadlines_without_catchup_burst(self) -> None:
        pacer = _FramePacer()
        self.assertTrue(pacer.ready(0, 7))
        self.assertFalse(pacer.ready(0.1, 7))
        self.assertTrue(pacer.ready(10, 7))
        for _ in range(10):
            self.assertFalse(pacer.ready(10, 7))
        self.assertFalse(pacer.ready(10.1, 7))
        self.assertTrue(pacer.ready(10.2, 7))


class VisionPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = VisionMonitor(lambda: {}, lambda event: None, lambda: [])
        self.config = dict(VisionMonitor.DEFAULTS, preview_max_width=800, preview_stream_fps=5)

    def test_estimated_alignment_does_not_move_or_resample_raw_preview_pixels(self) -> None:
        frame = np.random.default_rng(7).integers(0, 256, (240, 320, 3), dtype=np.uint8)
        original = frame.copy()
        transforms = (
            np.float32([[1, 0, 0], [0, 1, 0]]),
            np.float32([[0.9986, -0.00006, 1.337], [0.00006, 0.9986, 0.436]]),
        )
        published = []
        with patch("app.vision.time.monotonic", return_value=0) as clock, \
             patch("app.vision.time.strftime", return_value="2026-09-18 12:00:00"), \
             patch.object(self.monitor, "_publish_frame", side_effect=lambda image, *a, **k: published.append(image.copy())):
            for index, transform in enumerate(transforms):
                clock.return_value = index * 0.2
                self.assertTrue(self.monitor._publish_live_preview(
                    frame, "monitoring", False, [], self.config,
                    current_to_reference=transform,
                ))
        np.testing.assert_array_equal(published[0], published[1])
        np.testing.assert_array_equal(published[1][100:190], original[100:190])
        np.testing.assert_array_equal(frame, original)

    def test_inverse_alignment_and_preview_scale_project_only_display_boxes(self) -> None:
        frame = np.full((720, 1280, 3), 180, dtype=np.uint8)
        active = _ActiveBox(9, (400, 240, 80, 48))
        current_to_reference = np.float32([[1, 0, -16], [0, 1, 8]])
        transform_copy = current_to_reference.copy()
        with patch("app.vision.time.monotonic", return_value=1), \
             patch.object(self.monitor, "_draw_overlay", wraps=self.monitor._draw_overlay) as overlay, \
             patch.object(self.monitor, "_publish_frame") as publish:
            self.monitor._publish_live_preview(
                frame, "monitoring", False, [active], self.config,
                current_to_reference=current_to_reference,
            )
        projection = overlay.call_args.kwargs["reference_to_preview"]
        self.assertEqual(self.monitor._preview_bbox(active.bbox, projection, 800, 450), (260, 145, 50, 30))
        self.assertEqual(publish.call_args.args[0].shape, (450, 800, 3))
        self.assertEqual(active.bbox, (400, 240, 80, 48))
        np.testing.assert_array_equal(current_to_reference, transform_copy)
        self.assertEqual(self.monitor.get_status()["preview_width"], 800)

    def test_preview_throttling_and_downscaling_leave_evidence_at_source_resolution(self) -> None:
        before = np.full((720, 1280, 3), 205, dtype=np.uint8)
        after = before.copy()
        cv2.rectangle(after, (600, 300), (690, 420), (25, 35, 45), -1)
        original = after.copy()
        config = dict(self.config, preview_jpeg_quality=67, jpeg_quality=88)
        with patch("app.vision.time.monotonic", return_value=0) as clock, \
             patch.object(self.monitor, "_encode_jpeg", wraps=self.monitor._encode_jpeg) as encode:
            outcomes = []
            for now in (0, 0.05, 0.2):
                clock.return_value = now
                outcomes.append(self.monitor._publish_live_preview(
                    after, "monitoring", False, [], config,
                ))
            self.assertEqual(outcomes, [True, False, True])
            self.assertEqual(encode.call_count, 2)
            self.assertEqual(encode.call_args.args[0].shape, (450, 800, 3))
            self.assertEqual(encode.call_args.args[1], 67)
            events, globally_changed = self.monitor._detect_changes(
                before, after, [], config, already_aligned=True,
            )
        self.assertFalse(globally_changed)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.kind, "added")
        self.assertGreater(event.bbox[0], 550)
        self.assertGreater(event.bbox[3], 120)
        crop = cv2.imdecode(np.frombuffer(event.after_jpeg, np.uint8), cv2.IMREAD_COLOR)
        scene = cv2.imdecode(np.frombuffer(event.scene_after_jpeg, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(crop.shape[:2], (event.bbox[3], event.bbox[2]))
        self.assertEqual(scene.shape[1], config["ai_scene_max_width"])
        np.testing.assert_array_equal(after, original)

    def test_already_aligned_core_keeps_events_without_repeating_alignment(self) -> None:
        before = np.full((240, 320, 3), 205, dtype=np.uint8)
        after = before.copy()
        cv2.rectangle(after, (100, 65), (190, 170), (25, 35, 45), -1)
        expected_events, expected_global = self.monitor._detect_changes(before, after, [], self.config)
        with patch.object(self.monitor, "_estimate_euclidean_alignment") as affine, \
             patch.object(self.monitor, "_estimate_translation") as translation:
            events, globally_changed = self.monitor._detect_changes(
                before, after, [], self.config, already_aligned=True,
            )
        affine.assert_not_called()
        translation.assert_not_called()
        self.assertEqual(
            [replace(event, event_id="") for event in events],
            [replace(event, event_id="") for event in expected_events],
        )
        self.assertEqual(globally_changed, expected_global)
        self.assertEqual([event.kind for event in events], ["added"])

    def test_supported_gray_and_bgra_inputs_can_be_previewed(self) -> None:
        for frame in (
            np.full((240, 320), 180, dtype=np.uint8),
            np.full((240, 320, 4), 180, dtype=np.uint8),
        ):
            with self.subTest(channels=frame.shape), \
                 patch("app.vision.time.monotonic", return_value=float(frame.ndim)), \
                 patch.object(self.monitor, "_publish_frame") as publish:
                self.assertTrue(self.monitor._publish_live_preview(
                    frame, "monitoring", False, [], self.config,
                ))
                self.assertEqual(publish.call_args.args[0].shape[:2], (240, 320))

    def test_baseline_gray_cache_refreshes_after_rebaseline(self) -> None:
        config = dict(self.config, stable_seconds=0, settle_seconds=0, camera_warmup_seconds=0)
        monitor = VisionMonitor(lambda: config, lambda event: None, lambda: [])
        stop = threading.Event()
        done = threading.Event()
        monitor._stop_event = stop
        camera = Mock()
        now = [0.0]
        count = [0]

        def read():
            count[0] += 1
            now[0] += 1
            if count[0] == 3:
                monitor.rebaseline()
            if count[0] > 6:
                stop.set()
                return False, None
            return True, np.full((120, 160, 3), 100 if count[0] < 3 else 160, dtype=np.uint8)

        camera.read.side_effect = read
        identity = np.float32([[1, 0, 0], [0, 1, 0]])
        with patch("app.vision.time.monotonic", side_effect=lambda: now[0]), \
             patch.object(monitor, "_open_capture", return_value=(camera, None)), \
             patch.object(monitor, "_prepare_gray", wraps=monitor._prepare_gray) as prepare, \
             patch.object(monitor, "_estimate_euclidean_alignment", return_value=(identity, 1.0)) as align, \
             patch.object(monitor, "_has_motion", return_value=(False, 0)), \
             patch.object(monitor, "_publish_live_preview", return_value=True):
            monitor._run(stop, queue.Queue(), done)
        self.assertIsNone(monitor.get_status()["last_error"])
        self.assertEqual(prepare.call_count, 6)
        references = [call.args[0] for call in align.call_args_list]
        self.assertEqual([int(gray[0, 0]) for gray in references], [100, 160, 160, 160])
        self.assertIs(references[1], references[2])
        self.assertIs(references[2], references[3])
        camera.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
