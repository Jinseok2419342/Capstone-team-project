from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from experiments.vision_pairs import (
    PAIR_MANIFEST_FIELDS,
    PairTrial,
    detect_stable_pair,
    parse_bbox,
    read_pair_manifest,
)


class VisionPairExperimentTests(unittest.TestCase):
    def test_bbox_parser_accepts_supported_formats_and_rejects_bad_sizes(self) -> None:
        self.assertEqual(parse_bbox("1;2;30;40"), (1, 2, 30, 40))
        self.assertEqual(parse_bbox("[1, 2, 30, 40]"), (1, 2, 30, 40))
        self.assertIsNone(parse_bbox(""))
        with self.assertRaisesRegex(ValueError, "positive"):
            parse_bbox("1;2;0;40")

    def test_manifest_preserves_korean_notes_and_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAIR_MANIFEST_FIELDS)
                writer.writeheader()
                row = {
                    "trial_id": "T001",
                    "before_image": "before.jpg",
                    "after_image": "after.jpg",
                    "event_ground_truth": "added",
                    "bbox_ground_truth": "10;10;20;20",
                    "notes": "조명, 그림자\n두 줄",
                }
                writer.writerow(row)
            trials = read_pair_manifest(path)
            self.assertEqual(trials[0].notes, "조명, 그림자\n두 줄")

            with path.open("a", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAIR_MANIFEST_FIELDS)
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "duplicate trial_id"):
                read_pair_manifest(path)

    def test_manifest_requires_positive_bbox_and_rejects_bbox_for_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.csv"
            for kind, bbox, expected in (
                ("added", "", "requires bbox_ground_truth"),
                ("none", "1;2;3;4", "must not have bbox_ground_truth"),
            ):
                with path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=PAIR_MANIFEST_FIELDS)
                    writer.writeheader()
                    writer.writerow(
                        {
                            "trial_id": "T001",
                            "before_image": "before.jpg",
                            "after_image": "after.jpg",
                            "event_ground_truth": kind,
                            "bbox_ground_truth": bbox,
                        }
                    )
                with self.assertRaisesRegex(ValueError, expected):
                    read_pair_manifest(path)

    def test_full_profile_detects_synthetic_addition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = np.full((240, 320, 3), 205, dtype=np.uint8)
            after = before.copy()
            cv2.rectangle(after, (110, 80), (200, 170), (25, 45, 75), -1)
            self.assertTrue(cv2.imwrite(str(root / "before.jpg"), before))
            self.assertTrue(cv2.imwrite(str(root / "after.jpg"), after))
            trial = PairTrial(
                trial_id="T001",
                before_image="before.jpg",
                after_image="after.jpg",
                event_ground_truth="added",
                bbox_ground_truth=(110, 80, 91, 91),
            )
            result = detect_stable_pair(
                trial,
                manifest_dir=root,
                profile="full",
                config_overrides={"min_change_area": 500},
            )
            self.assertFalse(result.global_change_suppressed)
            self.assertEqual([event.kind for event in result.events], ["added"])
            self.assertGreater(result.detection_latency_ms, 0.0)
            self.assertIn('"kind":"added"', result.as_row()["predicted_events_json"])

    def test_removal_uses_active_reference_and_background_crops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = np.full((240, 320, 3), 205, dtype=np.uint8)
            present = empty.copy()
            cv2.rectangle(present, (100, 70), (209, 179), (25, 45, 75), -1)
            cv2.line(present, (110, 80), (195, 165), (130, 150, 170), 4)
            self.assertTrue(cv2.imwrite(str(root / "present.jpg"), present))
            self.assertTrue(cv2.imwrite(str(root / "empty.jpg"), empty))
            trial = PairTrial(
                trial_id="T002",
                before_image="present.jpg",
                after_image="empty.jpg",
                event_ground_truth="removed",
                bbox_ground_truth=(95, 65, 120, 120),
                active_item_id="51",
                active_bbox=(95, 65, 120, 120),
            )
            result = detect_stable_pair(
                trial,
                manifest_dir=root,
                profile="full",
                config_overrides={"min_change_area": 500},
            )
            self.assertEqual(
                [(event.kind, event.matched_item_id) for event in result.events],
                [("removed", "51")],
            )


if __name__ == "__main__":
    unittest.main()
