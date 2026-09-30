from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from experiments.pair_runner import build_pair_dataset, canonical_json_sha256
from experiments.vision_pairs import PairTrial


class PairDatasetRunnerTests(unittest.TestCase):
    def test_hash_is_order_independent_for_mapping_keys(self) -> None:
        self.assertEqual(
            canonical_json_sha256({"b": 2, "a": 1}),
            canonical_json_sha256({"a": 1, "b": 2}),
        )

    def test_builds_separate_profile_runs_and_preserves_all_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = np.full((240, 320, 3), 205, dtype=np.uint8)
            after = before.copy()
            cv2.rectangle(after, (110, 80), (200, 170), (25, 45, 75), -1)
            self.assertTrue(cv2.imwrite(str(root / "before.jpg"), before))
            self.assertTrue(cv2.imwrite(str(root / "after.jpg"), after))
            dataset = build_pair_dataset(
                [
                    PairTrial(
                        trial_id="T001",
                        before_image="before.jpg",
                        after_image="after.jpg",
                        event_ground_truth="added",
                        bbox_ground_truth=(100, 70, 111, 111),
                        scenario="added_normal",
                    )
                ],
                manifest_dir=root,
                run_id="R001",
                profiles=["plain", "full"],
                protocol_version="P1",
                config_overrides={"min_change_area": 500},
                device="test",
            )
            self.assertEqual(len(dataset.episodes), 2)
            self.assertEqual(
                [record.run_id for record in dataset.episodes],
                ["R001__plain", "R001__full"],
            )
            self.assertEqual(
                sum(record.record_role == "ground_truth" for record in dataset.events),
                2,
            )
            self.assertEqual(
                sum(record.record_role == "prediction" for record in dataset.events),
                2,
            )
            self.assertEqual(len(dataset.trial_rows), 2)
            self.assertEqual(len(dataset.episodes[0].config_sha256), 64)
            self.assertIsNone(dataset.episodes[0].cpu_avg_pct)
            self.assertIsNone(dataset.episodes[0].cpu_peak_pct)
            self.assertGreaterEqual(dataset.trial_rows[0]["process_cpu_ms"], 0.0)

    def test_none_trial_has_no_ground_truth_event_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = np.full((120, 160, 3), 205, dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(root / "a.jpg"), frame))
            self.assertTrue(cv2.imwrite(str(root / "b.jpg"), frame))
            dataset = build_pair_dataset(
                [
                    PairTrial(
                        trial_id="N001",
                        before_image="a.jpg",
                        after_image="b.jpg",
                        event_ground_truth="none",
                        source_segment_seconds=30.0,
                    )
                ],
                manifest_dir=root,
                run_id="R002",
                profiles=["full"],
                protocol_version="P1",
            )
            self.assertEqual(dataset.episodes[0].expected_event_count, 0)
            self.assertEqual(dataset.episodes[0].eligible_monitoring_seconds, 0.0)
            self.assertEqual(dataset.events, ())

    def test_rejects_profile_switch_overrides(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile-controlled"):
            build_pair_dataset(
                [
                    PairTrial(
                        trial_id="N001",
                        before_image="unused-a.jpg",
                        after_image="unused-b.jpg",
                        event_ground_truth="none",
                    )
                ],
                manifest_dir=Path("."),
                run_id="R003",
                profiles=["plain"],
                protocol_version="P1",
                config_overrides={"stabilize_camera": True},
            )


if __name__ == "__main__":
    unittest.main()
