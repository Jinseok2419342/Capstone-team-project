from __future__ import annotations

import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.vision import VisionMonitor, _ActiveBox


class VisionDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = []
        self.monitor = VisionMonitor(lambda: {}, self.events.append, lambda: [])
        self.config = dict(VisionMonitor.DEFAULTS)
        self.config.update(
            {
                "compensate_lighting": False,
                "min_change_area": 80,
                "min_change_area_ratio": 0,
                "change_threshold": 15,
                "contour_merge_gap": 8,
                "bbox_padding": 2,
            }
        )

    @staticmethod
    def frame(with_object: bool) -> np.ndarray:
        frame = np.full((240, 320, 3), 205, dtype=np.uint8)
        if with_object:
            cv2.rectangle(frame, (105, 75), (205, 175), (20, 28, 36), -1)
            cv2.circle(frame, (155, 125), 22, (65, 75, 85), -1)
        return frame

    @staticmethod
    def textured_frame(with_object: bool = False) -> np.ndarray:
        y, x = np.indices((240, 320))
        texture = (174 + ((x // 24 + y // 20) % 2) * 15).astype(np.uint8)
        frame = np.dstack(
            (texture, np.clip(texture + 7, 0, 255), np.clip(texture + 13, 0, 255))
        ).astype(np.uint8)
        for center in ((38, 42), (278, 38), (44, 205), (274, 202)):
            cv2.circle(frame, center, 8, (65, 95, 125), -1)
        if with_object:
            cv2.rectangle(frame, (118, 82), (202, 158), (24, 35, 48), -1)
            cv2.line(frame, (128, 94), (190, 146), (112, 132, 152), 4)
        return frame

    @staticmethod
    def translate(frame: np.ndarray, dx: float, dy: float) -> np.ndarray:
        return cv2.warpAffine(
            frame,
            np.float32([[1, 0, dx], [0, 1, dy]]),
            (frame.shape[1], frame.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

    @staticmethod
    def autofocus_breathing(
        frame: np.ndarray, scale: float = 1.015
    ) -> np.ndarray:
        """Synthetic cheap-webcam zoom, non-rigid lens drift and MJPEG noise."""

        height, width = frame.shape[:2]
        transform = cv2.getRotationMatrix2D(
            (width / 2.0, height / 2.0), 0.18, scale
        )
        warped = cv2.warpAffine(
            frame,
            transform,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        y, x = np.indices((height, width), dtype=np.float32)
        warped = cv2.remap(
            warped,
            x + 1.5 * np.sin(y / 41.0),
            y + 1.4 * np.sin(x / 53.0),
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        band_top = max(0, height - 50)
        warped[band_top:] = cv2.GaussianBlur(
            warped[band_top:], (0, 0), 4.0
        )
        ok, encoded = cv2.imencode(
            ".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 76]
        )
        if not ok:
            raise AssertionError("failed to encode autofocus fixture")
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None:
            raise AssertionError("failed to decode autofocus fixture")
        return decoded

    @staticmethod
    def relocation_background() -> np.ndarray:
        """A desk with distinctly dark and light placement surfaces."""

        image = np.full((360, 640, 3), (218, 218, 218), dtype=np.uint8)
        cv2.rectangle(image, (35, 90), (275, 235), (32, 34, 37), -1)
        # Fixed marks keep the scene realistic without participating in the
        # foreground masks used by relocation matching.
        for x in range(55, 270, 32):
            cv2.circle(image, (x, 110 + (x // 32) % 4 * 28), 2, (47, 49, 52), -1)
        cv2.line(image, (300, 75), (610, 75), (204, 204, 204), 2)
        cv2.circle(image, (580, 285), 7, (198, 198, 198), -1)
        return image

    @staticmethod
    def draw_remote(
        image: np.ndarray, left: int, top: int, scale: float = 1.0
    ) -> None:
        """Draw a feature-rich remote into ``image`` with a capsule mask."""

        width, height = 180, 62
        object_image = np.zeros((height, width, 3), dtype=np.uint8)
        object_mask = np.zeros((height, width), dtype=np.uint8)
        radius = height // 2 - 2
        cv2.rectangle(
            object_mask,
            (radius, 2),
            (width - radius, height - 3),
            255,
            -1,
        )
        cv2.circle(object_mask, (radius, height // 2), radius, 255, -1)
        cv2.circle(object_mask, (width - radius, height // 2), radius, 255, -1)
        object_image[object_mask > 0] = (84, 88, 93)
        cv2.ellipse(
            object_image,
            (width - 31, height // 2),
            (24, 24),
            0,
            0,
            360,
            (101, 105, 111),
            -1,
        )
        cv2.circle(object_image, (width - 31, height // 2), 14, (76, 80, 85), 2)
        buttons = (
            (35, 18),
            (58, 17),
            (82, 18),
            (106, 17),
            (42, 42),
            (70, 42),
            (101, 41),
        )
        for index, center in enumerate(buttons):
            color = (198, 200, 203) if index == 6 else (126, 130, 135)
            cv2.circle(object_image, center, 7 if index < 4 else 8, color, -1)
            angle = (index * 37 + 15) * np.pi / 180.0
            offset = (
                int(round(np.cos(angle) * 4)),
                int(round(np.sin(angle) * 4)),
            )
            cv2.line(
                object_image,
                (center[0] - offset[0], center[1] - offset[1]),
                (center[0] + offset[0], center[1] + offset[1]),
                (42, 45, 49),
                2,
            )
        cv2.rectangle(object_image, (116, 13), (125, 49), (54, 58, 63), 2)

        output_size = (
            max(16, int(round(width * scale))),
            max(16, int(round(height * scale))),
        )
        object_image = cv2.resize(
            object_image, output_size, interpolation=cv2.INTER_LINEAR
        )
        object_mask = cv2.resize(
            object_mask, output_size, interpolation=cv2.INTER_NEAREST
        )
        region = image[top : top + output_size[1], left : left + output_size[0]]
        region[object_mask > 0] = object_image[object_mask > 0]

    @staticmethod
    def draw_different_elongated_item(
        image: np.ndarray, left: int, top: int
    ) -> None:
        """Draw a similarly sized but visually unrelated striped case."""

        cv2.rectangle(
            image,
            (left, top),
            (left + 180, top + 62),
            (155, 45, 32),
            -1,
        )
        cv2.rectangle(
            image,
            (left + 4, top + 4),
            (left + 176, top + 58),
            (185, 62, 42),
            3,
        )
        for offset in range(-35, 190, 24):
            cv2.line(
                image,
                (left + max(0, offset), top + 61),
                (left + min(180, offset + 55), top),
                (225, 180, 72),
                5,
            )
        cv2.circle(image, (left + 155, top + 31), 12, (38, 50, 175), -1)

    def test_addition_emits_crop_and_bbox(self) -> None:
        events, global_change = self.monitor._detect_changes(
            self.frame(False), self.frame(True), [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.kind, "added")
        self.assertIsNone(event.matched_item_id)
        self.assertGreater(len(event.crop_jpeg or b""), 100)
        self.assertGreater(len(event.scene_before_jpeg or b""), 100)
        self.assertGreater(len(event.scene_after_jpeg or b""), 100)
        scene = cv2.imdecode(
            np.frombuffer(event.scene_after_jpeg or b"", np.uint8),
            cv2.IMREAD_COLOR,
        )
        self.assertIsNotNone(scene)
        self.assertEqual(scene.shape[:2], (240, 320))
        x, y, width, height = event.bbox
        self.assertLessEqual(x, 105)
        self.assertLessEqual(y, 75)
        self.assertGreaterEqual(x + width, 205)
        self.assertGreaterEqual(y + height, 175)

    def test_removal_matches_active_item(self) -> None:
        before = self.frame(True)
        x, y, width, height = (100, 70, 110, 110)
        ok, encoded = cv2.imencode(".jpg", before[y : y + height, x : x + width])
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", self.frame(False)[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = [
            _ActiveBox(
                item_id=42,
                bbox=(x, y, width, height),
                reference_jpeg=encoded.tobytes(),
                background_jpeg=background.tobytes(),
            )
        ]
        events, global_change = self.monitor._detect_changes(
            before, self.frame(False), active, self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "removed")
        self.assertEqual(events[0].matched_item_id, 42)
        self.assertGreater(len(events[0].before_jpeg or b""), 100)

    def test_screen_change_does_not_false_recover_tracked_item(self) -> None:
        before = self.frame(True)
        x, y, width, height = (100, 70, 110, 110)
        ok, encoded = cv2.imencode(".jpg", before[y : y + height, x : x + width])
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", self.frame(False)[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = [
            _ActiveBox(
                7,
                (x, y, width, height),
                encoded.tobytes(),
                background.tobytes(),
            )
        ]
        for color in ((230, 230, 230), (0, 255, 0), (0, 0, 255)):
            changed = before.copy()
            cv2.circle(changed, (155, 125), 22, color, -1)
            events, global_change = self.monitor._detect_changes(
                before, changed, active, self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, "verify_removed")
            self.assertEqual(events[0].matched_item_id, 7)

    def test_missing_reference_requests_ai_verification_not_local_recovery(self) -> None:
        events, _ = self.monitor._detect_changes(
            self.frame(True),
            self.frame(False),
            [_ActiveBox(item_id=9, bbox=(100, 70, 110, 110))],
            self.config,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "verify_removed")
        self.assertEqual(events[0].matched_item_id, 9)

    def test_invalid_identical_tracking_pair_does_not_create_blind_zone(self) -> None:
        before = self.frame(True)
        bbox = (100, 70, 110, 110)
        x, y, width, height = bbox
        ok, invalid_pair = cv2.imencode(
            ".jpg", before[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        after = before.copy()
        cv2.rectangle(after, (125, 92), (190, 150), (145, 30, 180), -1)
        active = _ActiveBox(
            91,
            bbox,
            invalid_pair.tobytes(),
            invalid_pair.tobytes(),
        )

        events, global_change = self.monitor._detect_changes(
            before, after, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertIn(("verify_removed", 91), {
            (event.kind, event.matched_item_id) for event in events
        })
        self.assertTrue(
            any(event.kind == "added" and event.matched_item_id is None for event in events)
        )

    def test_jittered_near_duplicate_tracking_pair_does_not_create_blind_zone(self) -> None:
        before = self.textured_frame(True)
        bbox = (88, 58, 134, 134)
        x, y, width, height = bbox
        crop = before[y : y + height, x : x + width]
        shifted = cv2.warpAffine(
            crop,
            np.float32([[1, 0, 0.55], [0, 1, -0.45]]),
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        ok, reference = cv2.imencode(
            ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 88]
        )
        self.assertTrue(ok)
        ok, invalid_background = cv2.imencode(
            ".jpg", shifted, [cv2.IMWRITE_JPEG_QUALITY, 82]
        )
        self.assertTrue(ok)
        after = before.copy()
        cv2.rectangle(after, (145, 112), (205, 170), (30, 180, 225), -1)
        active = _ActiveBox(
            92,
            bbox,
            reference.tobytes(),
            invalid_background.tobytes(),
        )

        events, global_change = self.monitor._detect_changes(
            before, after, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertIn(
            ("verify_removed", 92),
            {(event.kind, event.matched_item_id) for event in events},
        )
        self.assertTrue(
            any(event.kind == "added" and event.matched_item_id is None for event in events)
        )

    def test_legacy_low_texture_edge_band_does_not_create_blind_zone(self) -> None:
        before = np.full((480, 640, 3), 202, dtype=np.uint8)
        bbox = (167, 18, 259, 61)
        x, y, width, height = bbox
        yy, xx = np.indices((height, width))
        saved_background_gray = np.clip(
            198.0 + 2.0 * np.sin(xx / 31.0) + 1.5 * np.cos(yy / 9.0),
            0,
            255,
        ).astype(np.uint8)
        saved_reference_gray = np.clip(
            saved_background_gray.astype(np.float32)
            + 4.0 * np.sin((xx + yy) / 17.0)
            + 2.0,
            0,
            255,
        ).astype(np.uint8)
        saved_background = np.dstack((saved_background_gray,) * 3)
        saved_reference = np.dstack((saved_reference_gray,) * 3)
        before[y : y + height, x : x + width] = saved_reference
        ok, reference_jpeg = cv2.imencode(
            ".jpg", saved_reference, [cv2.IMWRITE_JPEG_QUALITY, 82]
        )
        self.assertTrue(ok)
        ok, background_jpeg = cv2.imencode(
            ".jpg", saved_background, [cv2.IMWRITE_JPEG_QUALITY, 88]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            93,
            bbox,
            reference_jpeg.tobytes(),
            background_jpeg.tobytes(),
        )
        self.assertEqual(
            self.monitor._active_tracking_state(before, active), "unusable"
        )

        after = before.copy()
        cv2.rectangle(after, (252, 24), (320, 74), (25, 115, 215), -1)
        events, global_change = self.monitor._detect_changes(
            before, after, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertIn(
            ("verify_removed", 93),
            {(event.kind, event.matched_item_id) for event in events},
        )
        self.assertTrue(
            any(event.kind == "added" and event.matched_item_id is None for event in events)
        )

    def test_whole_frame_change_is_suppressed(self) -> None:
        before = np.zeros((240, 320, 3), dtype=np.uint8)
        after = np.full_like(before, 255)
        events, global_change = self.monitor._detect_changes(before, after, [], self.config)
        self.assertTrue(global_change)
        self.assertEqual(events, [])

    def test_subpixel_camera_jitter_is_not_motion_or_change(self) -> None:
        self.config["compensate_lighting"] = True
        self.config["motion_threshold"] = 9
        self.config["change_threshold"] = 9
        before = self.textured_frame()
        for dx, dy in ((0.8, -0.95), (-2.4, 1.7), (4.0, -3.0)):
            after = self.translate(before, dx, dy)
            moving, ratio = self.monitor._has_motion(
                self.monitor._prepare_gray(before),
                self.monitor._prepare_gray(after),
                self.config,
            )
            self.assertFalse(moving, (dx, dy, ratio))
            events, global_change = self.monitor._detect_changes(
                before, after, [], self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(events, [], (dx, dy))

    def test_autofocus_breathing_and_blurred_edge_band_are_not_motion(self) -> None:
        # These were the deliberately aggressive values previously used by
        # the accumulated-baseline check.  Even there, optical motion alone
        # must not keep the monitor in its settling state forever.
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 24,
                "motion_min_area": 80,
                "motion_min_ratio": 0.00025,
                "change_threshold": 24,
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
            }
        )
        before = self.textured_frame()
        for scale in (1.015, 1.025):
            after = self.autofocus_breathing(before, scale)

            moving, ratio = self.monitor._has_motion(
                self.monitor._prepare_gray(before),
                self.monitor._prepare_gray(after),
                self.config,
            )
            self.assertFalse(moving, (scale, ratio))
            events, global_change = self.monitor._detect_changes(
                before, after, [], self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(events, [], scale)

    def test_real_compact_object_and_hand_survive_optical_jitter_filter(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 24,
                "motion_min_area": 80,
                "motion_min_ratio": 0.00025,
            }
        )
        before = self.textured_frame()
        cases = []
        compact = before.copy()
        cv2.rectangle(compact, (145, 95), (165, 135), (25, 38, 52), -1)
        cases.append(("compact", compact))
        hand = before.copy()
        cv2.ellipse(hand, (160, 120), (32, 70), 15, 0, 360, (70, 120, 190), -1)
        cases.append(("hand", hand))

        for name, changed in cases:
            after = self.autofocus_breathing(changed)
            moving, ratio = self.monitor._has_motion(
                self.monitor._prepare_gray(before),
                self.monitor._prepare_gray(after),
                self.config,
            )
            self.assertTrue(moving, (name, ratio))

    def test_near_identity_alignment_does_not_resample_still_preview(self) -> None:
        before = self.textured_frame()
        noisy_estimate = self.translate(before, 0.12, -0.11)
        alignment = self.monitor._estimate_euclidean_alignment(
            self.monitor._prepare_gray(before),
            self.monitor._prepare_gray(noisy_estimate),
            self.config,
        )
        self.assertIsNotNone(alignment)
        assert alignment is not None
        np.testing.assert_array_equal(
            alignment[0],
            np.float32([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        )
        aligned, valid = self.monitor._warp_affine(before, alignment[0])
        self.assertIs(aligned, before)
        self.assertTrue(np.all(valid == 255))

    def test_camera_warmup_delays_initial_baseline(self) -> None:
        config = dict(VisionMonitor.DEFAULTS)
        self.assertGreaterEqual(config["camera_warmup_seconds"], 3.0)
        self.assertFalse(
            self.monitor._camera_warmup_complete(100.0, 102.9, config)
        )
        self.assertTrue(
            self.monitor._camera_warmup_complete(100.0, 103.0, config)
        )
        self.assertTrue(self.monitor._camera_warmup_complete(None, 0.0, config))

    def test_distributed_features_allow_larger_desk_bump(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 9,
                "change_threshold": 9,
            }
        )
        before = self.textured_frame()
        after = self.translate(before, 15.0, -9.0)
        moving, ratio = self.monitor._has_motion(
            self.monitor._prepare_gray(before),
            self.monitor._prepare_gray(after),
            self.config,
        )
        self.assertFalse(moving, ratio)
        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(events, [])

    def test_tiny_rotation_and_autofocus_scale_are_stabilized(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 9,
                "change_threshold": 9,
            }
        )
        before = self.textured_frame()
        transform = cv2.getRotationMatrix2D((160, 120), 0.45, 1.015)
        after = cv2.warpAffine(
            before,
            transform,
            (320, 240),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(events, [])

    def test_jitter_plus_new_object_keeps_canonical_bbox(self) -> None:
        self.config["compensate_lighting"] = True
        before = self.textured_frame(False)
        after = self.translate(self.textured_frame(True), 4.5, -3.25)
        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.kind, "added")
        x, y, width, height = event.bbox
        self.assertLessEqual(x, 118)
        self.assertLessEqual(y, 82)
        self.assertGreaterEqual(x + width, 202)
        self.assertGreaterEqual(y + height, 158)

    def test_sparse_scene_new_object_is_not_mistaken_for_camera_move(self) -> None:
        before = np.full((240, 320, 3), 195, dtype=np.uint8)
        cv2.rectangle(before, (100, 82), (155, 137), (42, 52, 62), -1)
        cv2.line(before, (104, 86), (150, 133), (125, 135, 145), 3)
        after = before.copy()
        cv2.rectangle(after, (200, 92), (255, 147), (28, 42, 72), -1)
        cv2.circle(after, (227, 119), 12, (94, 114, 154), -1)

        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "added")
        self.assertGreaterEqual(events[0].bbox[0], 190)

    def test_small_dense_item_survives_high_min_area_and_can_be_removed(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 9,
                "change_threshold": 9,
                "min_change_area": 1800,
            }
        )
        empty = np.full((240, 320, 3), 205, dtype=np.uint8)
        present = empty.copy()
        cv2.rectangle(present, (145, 95), (165, 135), (25, 38, 52), -1)
        cv2.line(present, (148, 99), (162, 130), (115, 130, 145), 2)

        additions, global_change = self.monitor._detect_changes(
            empty, present, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(additions), 1)
        added = additions[0]
        self.assertLess(added.bbox[2], 70)
        self.assertLess(added.bbox[3], 90)

        x, y, width, height = added.bbox
        ok, reference = cv2.imencode(
            ".jpg", present[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = [
            _ActiveBox(
                88,
                added.bbox,
                reference.tobytes(),
                background.tobytes(),
            )
        ]
        removals, global_change = self.monitor._detect_changes(
            present, empty, active, self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0].kind, "removed")
        self.assertEqual(removals[0].matched_item_id, 88)
        for light_shift in (-30, 30):
            shifted_empty = np.clip(
                empty.astype(np.int16) + light_shift, 0, 255
            ).astype(np.uint8)
            shifted_removals, global_change = self.monitor._detect_changes(
                present, shifted_empty, active, self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(
                [(event.kind, event.matched_item_id) for event in shifted_removals],
                [("removed", 88)],
            )

    def test_tracked_item_relocation_emits_one_moved_event_and_stays_removable(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 9,
                "change_threshold": 9,
                "min_change_area": 1800,
            }
        )
        empty = np.full((240, 320, 3), 205, dtype=np.uint8)

        def item_at(left: int) -> np.ndarray:
            image = empty.copy()
            cv2.rectangle(image, (left, 90), (left + 55, 145), (30, 45, 65), -1)
            cv2.line(
                image,
                (left + 5, 95),
                (left + 50, 140),
                (120, 135, 155),
                3,
            )
            return image

        original = item_at(100)
        addition = self.monitor._detect_changes(empty, original, [], self.config)[0][0]
        x, y, width, height = addition.bbox
        ok, reference = cv2.imencode(
            ".jpg", original[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            51, addition.bbox, reference.tobytes(), background.tobytes()
        )

        relocated = item_at(125)
        events, global_change = self.monitor._detect_changes(
            original, relocated, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        moved = events[0]
        self.assertEqual(moved.kind, "moved")
        self.assertEqual(moved.matched_item_id, 51)
        self.assertGreater(moved.bbox[0], addition.bbox[0])
        clean_crop = cv2.imdecode(
            np.frombuffer(moved.before_jpeg or b"", np.uint8), cv2.IMREAD_COLOR
        )
        self.assertIsNotNone(clean_crop)
        self.assertGreater(float(np.mean(clean_crop)), 195.0)

        updated = _ActiveBox(
            51,
            moved.bbox,
            moved.after_jpeg,
            moved.before_jpeg,
        )
        removals, global_change = self.monitor._detect_changes(
            relocated, empty, [updated], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0].kind, "removed")
        self.assertEqual(removals[0].matched_item_id, 51)

    def test_textured_item_moves_between_different_backgrounds_and_remains_removable(self) -> None:
        self.config.update(
            {
                "stabilize_camera": False,
                "compensate_lighting": False,
                "change_threshold": 12,
                "min_change_area": 500,
                "min_change_area_ratio": 0,
                "bbox_padding": 5,
            }
        )
        empty = self.relocation_background()
        original = empty.copy()
        self.draw_remote(original, 70, 132)
        relocated = empty.copy()
        self.draw_remote(relocated, 315, 128, 1.12)

        additions, global_change = self.monitor._detect_changes(
            empty, original, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(additions), 1)
        addition = additions[0]
        x, y, width, height = addition.bbox
        ok, reference = cv2.imencode(
            ".jpg", original[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            61,
            addition.bbox,
            reference.tobytes(),
            background.tobytes(),
        )

        events, global_change = self.monitor._detect_changes(
            original, relocated, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(
            [(event.kind, event.matched_item_id) for event in events],
            [("moved", 61)],
        )
        moved = events[0]
        self.assertGreater(moved.bbox[0], 290)
        self.assertNotEqual(moved.bbox[2:], addition.bbox[2:])

        updated = _ActiveBox(
            61,
            moved.bbox,
            moved.after_jpeg,
            moved.before_jpeg,
        )
        removals, global_change = self.monitor._detect_changes(
            relocated, empty, [updated], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(
            [(event.kind, event.matched_item_id) for event in removals],
            [("removed", 61)],
        )

    def test_different_textured_object_is_not_paired_as_relocation(self) -> None:
        self.config.update(
            {
                "stabilize_camera": False,
                "compensate_lighting": False,
                "change_threshold": 12,
                "min_change_area": 500,
                "min_change_area_ratio": 0,
                "bbox_padding": 5,
            }
        )
        empty = self.relocation_background()
        original = empty.copy()
        self.draw_remote(original, 70, 132)
        replacement = empty.copy()
        self.draw_different_elongated_item(replacement, 315, 128)

        addition = self.monitor._detect_changes(
            empty, original, [], self.config
        )[0][0]
        x, y, width, height = addition.bbox
        ok, reference = cv2.imencode(
            ".jpg", original[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            62,
            addition.bbox,
            reference.tobytes(),
            background.tobytes(),
        )

        events, global_change = self.monitor._detect_changes(
            original, replacement, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertFalse(any(event.kind == "moved" for event in events))
        self.assertIn(
            ("removed", 62),
            {(event.kind, event.matched_item_id) for event in events},
        )
        self.assertTrue(
            any(
                event.kind == "added" and event.matched_item_id is None
                for event in events
            )
        )

    def test_new_item_beside_active_item_remains_an_addition(self) -> None:
        empty = self.frame(False)
        original = self.frame(True)
        x, y, width, height = (100, 70, 110, 110)
        ok, reference = cv2.imencode(
            ".jpg", original[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            4, (x, y, width, height), reference.tobytes(), background.tobytes()
        )
        after = original.copy()
        cv2.rectangle(after, (207, 92), (255, 150), (75, 24, 135), -1)
        events, global_change = self.monitor._detect_changes(
            original, after, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "added")
        self.assertIsNone(events[0].matched_item_id)

    def test_overlapping_duplicate_active_rows_are_both_removed(self) -> None:
        before = self.frame(True)
        empty = self.frame(False)
        bbox = (100, 70, 110, 110)
        x, y, width, height = bbox
        ok, reference = cv2.imencode(
            ".jpg", before[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = [
            _ActiveBox(1, bbox, reference.tobytes(), background.tobytes()),
            _ActiveBox(2, bbox, reference.tobytes(), background.tobytes()),
        ]
        events, global_change = self.monitor._detect_changes(
            before, empty, active, self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(
            {(event.kind, event.matched_item_id) for event in events},
            {("removed", 1), ("removed", 2)},
        )

    def test_large_phone_screen_change_never_recovers_but_later_removal_does(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "motion_threshold": 9,
                "change_threshold": 9,
                "min_change_area": 1800,
            }
        )
        empty = np.full((360, 360, 3), 200, dtype=np.uint8)

        def phone(screen_value: int) -> np.ndarray:
            image = empty.copy()
            cv2.rectangle(image, (100, 100), (199, 259), (15, 15, 15), -1)
            cv2.rectangle(
                image, (105, 105), (194, 254), (screen_value,) * 3, -1
            )
            return image

        screen_off = phone(40)
        screen_on = phone(250)
        added = self.monitor._detect_changes(empty, screen_off, [], self.config)[0][0]
        x, y, width, height = added.bbox
        ok, reference = cv2.imencode(
            ".jpg", screen_off[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            19, added.bbox, reference.tobytes(), background.tobytes()
        )

        screen_events, _ = self.monitor._detect_changes(
            screen_off, screen_on, [active], self.config
        )
        self.assertEqual(len(screen_events), 1)
        self.assertEqual(screen_events[0].kind, "verify_removed")
        self.assertEqual(screen_events[0].matched_item_id, 19)
        removal_events, _ = self.monitor._detect_changes(
            screen_on, empty, [active], self.config
        )
        self.assertEqual(len(removal_events), 1)
        self.assertEqual(removal_events[0].kind, "removed")
        self.assertEqual(removal_events[0].matched_item_id, 19)

    def test_stale_active_box_does_not_hide_new_item_in_same_area(self) -> None:
        empty = self.frame(False)
        registered = self.frame(True)
        bbox = (100, 70, 110, 110)
        x, y, width, height = bbox
        ok, reference = cv2.imencode(
            ".jpg", registered[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            71,
            bbox,
            reference.tobytes(),
            background.tobytes(),
        )
        replacement = empty.copy()
        cv2.rectangle(replacement, (125, 95), (184, 154), (140, 35, 180), -1)
        cv2.line(replacement, (130, 105), (177, 146), (230, 190, 245), 4)

        events, global_change = self.monitor._detect_changes(
            empty, replacement, [active], self.config
        )
        self.assertFalse(global_change)
        self.assertIn(("removed", 71), {
            (event.kind, event.matched_item_id) for event in events
        })
        self.assertTrue(
            any(event.kind == "added" and event.matched_item_id is None for event in events)
        )

    def test_manual_rebaseline_reconciles_only_strong_background_match(self) -> None:
        present = self.frame(True)
        empty = self.frame(False)
        bbox = (100, 70, 110, 110)
        x, y, width, height = bbox
        ok, reference = cv2.imencode(
            ".jpg", present[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        ok, background = cv2.imencode(
            ".jpg", empty[y : y + height, x : x + width]
        )
        self.assertTrue(ok)
        active = _ActiveBox(
            73, bbox, reference.tobytes(), background.tobytes()
        )

        self.assertEqual(
            self.monitor._reconcile_absent_active_items(
                present, [active], self.config
            ),
            [],
        )
        events = self.monitor._reconcile_absent_active_items(
            empty, [active], self.config
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "removed")
        self.assertEqual(events[0].matched_item_id, 73)
        self.assertGreater(len(events[0].scene_after_jpeg or b""), 100)

        initial_generation = self.monitor._current_rebaseline_generation()
        self.assertFalse(
            self.monitor._should_reconcile_generation(initial_generation)
        )
        self.monitor.rebaseline(reconcile_items=True)
        manual_generation = self.monitor._current_rebaseline_generation()
        self.assertTrue(
            self.monitor._should_reconcile_generation(manual_generation)
        )
        self.assertFalse(
            self.monitor._should_reconcile_generation(manual_generation)
        )

    def test_thin_pen_like_item_is_detected_with_production_min_area(self) -> None:
        self.config.update(
            {
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
                "change_threshold": 24,
            }
        )
        before = np.full((480, 640, 3), 205, dtype=np.uint8)
        after = before.copy()
        cv2.rectangle(after, (225, 225), (305, 230), (25, 35, 45), -1)
        cv2.circle(after, (228, 227), 4, (65, 75, 85), -1)

        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "added")

    def test_strong_item_near_frame_edge_is_not_silently_dropped(self) -> None:
        self.config.update(
            {
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
                "change_threshold": 24,
            }
        )
        before = np.full((480, 640, 3), 205, dtype=np.uint8)
        after = before.copy()
        cv2.rectangle(after, (3, 185), (75, 260), (25, 35, 45), -1)
        cv2.line(after, (12, 195), (65, 248), (115, 135, 155), 5)

        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "added")

    def test_full_width_optical_edge_strip_is_suppressed(self) -> None:
        self.config.update(
            {
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
                "change_threshold": 24,
            }
        )
        before = np.full((480, 640, 3), 205, dtype=np.uint8)
        after = before.copy()
        after[:5, :] = 135

        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(events, [])

    def test_large_low_contrast_item_is_one_candidate_not_four_fragments(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "compensate_local_lighting": True,
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
                "change_threshold": 24,
                "motion_threshold": 40,
            }
        )
        y, x = np.indices((480, 640))
        plane = (200 + ((x // 24 + y // 20) % 2) * 4).astype(np.uint8)
        before = np.dstack((plane, plane, plane)).astype(np.uint8)

        for value in (230, 150, 140):
            after = before.copy()
            cv2.rectangle(
                after, (220, 140), (420, 340), (value, value, value), -1
            )
            events, global_change = self.monitor._detect_changes(
                before, after, [], self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(len(events), 1, (value, [event.bbox for event in events]))
            self.assertEqual(events[0].kind, "added")
            x1, y1, width, height = events[0].bbox
            self.assertLessEqual(x1, 220)
            self.assertLessEqual(y1, 140)
            self.assertGreaterEqual(x1 + width, 420)
            self.assertGreaterEqual(y1 + height, 340)

    def test_brightness_only_shadow_is_not_a_low_contrast_object(self) -> None:
        self.config.update(
            {
                "compensate_lighting": True,
                "compensate_local_lighting": True,
                "min_change_area": 1800,
                "min_change_area_ratio": 0.0007,
                "change_threshold": 24,
                "motion_threshold": 40,
            }
        )
        y, x = np.indices((480, 640))
        plane = (200 + ((x // 24 + y // 20) % 2) * 4).astype(np.uint8)
        before = np.dstack((plane, plane, plane)).astype(np.uint8)

        hard = before.astype(np.int16)
        hard[140:341, 220:421] -= 50
        cases = [np.clip(hard, 0, 255).astype(np.uint8)]
        for sigma in (8, 20):
            shadow = np.zeros((480, 640), np.float32)
            cv2.rectangle(shadow, (220, 140), (420, 340), 1, -1)
            shadow = cv2.GaussianBlur(shadow, (0, 0), sigma)
            cases.append(
                np.clip(
                    before.astype(np.float32) - 50 * shadow[:, :, None],
                    0,
                    255,
                ).astype(np.uint8)
            )

        for case_index, after in enumerate(cases):
            events, global_change = self.monitor._detect_changes(
                before, after, [], self.config
            )
            self.assertFalse(global_change)
            self.assertEqual(
                [(event.kind, event.bbox) for event in events],
                [],
                f"shadow case {case_index}",
            )

    def test_boundary_exposure_drift_is_not_an_added_item(self) -> None:
        self.config["compensate_lighting"] = True
        before = self.textured_frame(False)
        y, x = np.indices(before.shape[:2])
        exposure = 27.0 * np.exp(-((x / 115.0) ** 2 + (y / 72.0) ** 2))
        after = np.clip(
            before.astype(np.float32) + exposure[:, :, None], 0, 255
        ).astype(np.uint8)
        events, global_change = self.monitor._detect_changes(
            before, after, [], self.config
        )
        self.assertFalse(global_change)
        self.assertEqual(events, [])

    def test_fallback_jpeg_is_always_available(self) -> None:
        image = cv2.imdecode(np.frombuffer(self.monitor.get_jpeg(), np.uint8), cv2.IMREAD_COLOR)
        self.assertIsNotNone(image)
        self.assertGreater(image.shape[0], 200)

    def test_browser_preview_quality_is_independent_from_evidence_quality(self) -> None:
        config = dict(self.config)
        config.update({"preview_jpeg_quality": 67, "jpeg_quality": 93})
        frame = self.frame(False)

        with patch.object(self.monitor, "_encode_jpeg", return_value=b"preview") as encode:
            self.monitor._publish_frame(frame, config)

        encode.assert_called_once_with(frame, 67)
        self.assertEqual(self.monitor.get_jpeg(), b"preview")


if __name__ == "__main__":
    unittest.main()
