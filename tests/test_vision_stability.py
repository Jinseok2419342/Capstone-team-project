from __future__ import annotations

import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.vision import VisionMonitor


class VisionStabilityTests(unittest.TestCase):
    """Synthetic 720p fixtures exercise nuisance rejection without a camera."""

    @classmethod
    def setUpClass(cls) -> None:
        y, x = np.indices((720, 1280))
        plane = (180 + 5 * np.sin(x / 31) + 4 * np.cos(y / 27)).astype(np.uint8)
        cls.weak_scene = np.repeat(plane[:, :, None], 3, axis=2)
        cls.rich_scene = cls.weak_scene.copy()
        for row in range(4):
            for col in range(6):
                left, top = 40 + col * 210, 40 + row * 175
                cv2.rectangle(
                    cls.weak_scene, (left, top), (left + 100, top + 75),
                    (165, 165, 165), 2,
                )
                cv2.rectangle(
                    cls.rich_scene, (left, top), (left + 100, top + 75),
                    (60 + (col * 17) % 70, 85, 110), 3,
                )
                cv2.circle(cls.rich_scene, (left + 50, top + 35), 12, (95, 105, 135), -1)

    def setUp(self) -> None:
        self.monitor = VisionMonitor(lambda: {}, lambda event: None, lambda: [])
        self.config = dict(VisionMonitor.DEFAULTS, stabilization_analysis_width=360)

    def test_subthreshold_frames_skip_jitter_and_contours_with_exact_empty_result(self) -> None:
        reference = np.full((720, 1280), 100, dtype=np.uint8)
        cases = [reference.copy(), np.full_like(reference, 107)]
        threshold_boundary = reference.copy()
        threshold_boundary[200:300, 500:650] += self.config["motion_threshold"]
        cases.append(threshold_boundary)

        for current in cases:
            with self.subTest(maximum=int(current.max())), \
                 patch.object(self.monitor, "_persistent_edge_jitter_mask") as jitter, \
                 patch("app.vision.cv2.findContours") as contours:
                result = self.monitor._has_motion(
                    reference, current, self.config, already_aligned=True,
                )
                self.assertEqual(result, (False, 0.0))
                jitter.assert_not_called()
                contours.assert_not_called()

    def test_evidence_above_threshold_still_reaches_motion_mask(self) -> None:
        reference = np.full((720, 1280), 100, dtype=np.uint8)
        current = reference.copy()
        current[200:250, 500:550] = 170
        with patch.object(
            self.monitor, "_persistent_edge_jitter_mask",
            wraps=self.monitor._persistent_edge_jitter_mask,
        ) as jitter:
            moving, ratio = self.monitor._has_motion(
                reference, current, self.config, already_aligned=True,
            )
        self.assertTrue(moving)
        self.assertGreater(ratio, self.config["motion_min_ratio"])
        jitter.assert_called_once()

    def test_global_exposure_difference_retains_local_object_evidence(self) -> None:
        reference = np.full((720, 1280), 100, dtype=np.uint8)
        current = np.full_like(reference, 115)
        current[200:240, 500:540] = 45
        valid = np.full_like(reference, 255)
        valid[:5] = 0

        difference = self.monitor._compensated_gray_difference(
            reference, current, valid, self.config, allow_local=False,
        )

        expected = np.zeros_like(reference)
        expected[200:240, 500:540] = 70
        np.testing.assert_array_equal(difference, expected)

    def test_static_low_contrast_noise_and_brightness_do_not_emit_changes(self) -> None:
        # This fixture produced a high-confidence ~1.4 px affine warp under
        # sigma-2 noise in the original 360 px estimator. Analysis may choose
        # such a transform; preview geometry must be handled independently.
        rng = np.random.default_rng(20260918)
        y, x = np.indices(self.weak_scene.shape[:2])
        cases = {
            "sensor_noise": self.weak_scene.astype(np.float32)
            + rng.normal(0, 2, self.weak_scene.shape),
            "brightness_gradient": self.weak_scene.astype(np.float32)
            + (20 * (x / 1280 - 0.5))[:, :, None],
        }
        reference = self.monitor._prepare_gray(self.weak_scene)
        for name, changed in cases.items():
            with self.subTest(case=name):
                current = np.clip(changed, 0, 255).astype(np.uint8)
                moving, _ = self.monitor._has_motion(
                    reference, self.monitor._prepare_gray(current), self.config,
                )
                events, globally_changed = self.monitor._detect_changes(
                    self.weak_scene, current, [], self.config,
                )
                self.assertFalse(moving)
                self.assertFalse(globally_changed)
                self.assertEqual(events, [])

    def test_smooth_local_illumination_does_not_create_an_object(self) -> None:
        y, x = np.indices(self.rich_scene.shape[:2])
        light = 40 * np.exp(-((x - 540) ** 2 / 320 ** 2 + (y - 290) ** 2 / 220 ** 2))
        current = np.clip(
            self.rich_scene.astype(np.float32) + light[:, :, None], 0, 255,
        ).astype(np.uint8)
        events, globally_changed = self.monitor._detect_changes(
            self.rich_scene, current, [], self.config,
        )
        self.assertFalse(globally_changed)
        self.assertEqual(events, [])

    def test_compact_and_thin_objects_still_trigger_motion_at_720p(self) -> None:
        reference = self.monitor._prepare_gray(self.rich_scene)
        for width, height in ((32, 44), (12, 130)):
            with self.subTest(size=(width, height)):
                current = self.rich_scene.copy()
                current[300:300 + height, 650:650 + width] = (25, 35, 45)
                moving, ratio = self.monitor._has_motion(
                    reference, self.monitor._prepare_gray(current), self.config,
                )
                self.assertTrue(moving, ratio)

    def test_accumulated_slow_object_movement_survives_alignment(self) -> None:
        baseline = self.rich_scene.copy()
        baseline[285:350, 655:736] = (25, 35, 45)
        reference = self.monitor._prepare_gray(baseline)
        for shift in (12, 20):
            with self.subTest(shift=shift):
                current = self.rich_scene.copy()
                current[285:350, 655 + shift:736 + shift] = (25, 35, 45)
                moving, ratio = self.monitor._has_motion(
                    reference, self.monitor._prepare_gray(current), self.config,
                )
                self.assertTrue(moving, ratio)

    def test_large_low_contrast_object_is_not_treated_as_local_lighting(self) -> None:
        reference = np.full((720, 1280), 180, dtype=np.uint8)
        for width, height in ((200, 180), (400, 280)):
            with self.subTest(size=(width, height)):
                current = reference.copy()
                current[200:200 + height, 500:500 + width] = 150
                moving, ratio = self.monitor._has_motion(
                    reference, current, self.config, already_aligned=True,
                )
                self.assertTrue(moving, ratio)


if __name__ == "__main__":
    unittest.main()
