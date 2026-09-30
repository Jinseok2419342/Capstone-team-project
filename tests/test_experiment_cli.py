from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from experiments.cli import main
from experiments.csvio import read_episodes, read_events
from experiments.vision_pairs import PAIR_MANIFEST_FIELDS


class ExperimentCliTests(unittest.TestCase):
    def test_init_creates_empty_valid_tables_and_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "workspace"
            stdout = io.StringIO()
            self.assertEqual(main(["init", str(output)], stdout=stdout), 0)
            self.assertEqual(read_episodes(output / "episodes.csv"), [])
            self.assertEqual(read_events(output / "events.csv"), [])
            self.assertTrue((output / "pair_manifest.csv").exists())
            protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
            self.assertIn("verify_removed", " ".join(protocol["notes"]))

            errors = io.StringIO()
            self.assertEqual(
                main(["init", str(output)], stdout=io.StringIO(), stderr=errors),
                2,
            )
            self.assertIn("refusing to replace", errors.getvalue())

    def test_run_pairs_writes_raw_records_and_local_metric_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            before = np.full((240, 320, 3), 205, dtype=np.uint8)
            after = before.copy()
            cv2.rectangle(after, (110, 80), (200, 170), (25, 45, 75), -1)
            self.assertTrue(cv2.imwrite(str(images / "before.jpg"), before))
            self.assertTrue(cv2.imwrite(str(images / "after.jpg"), after))
            self.assertTrue(cv2.imwrite(str(images / "still.jpg"), before))

            manifest = root / "pairs.csv"
            with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAIR_MANIFEST_FIELDS)
                writer.writeheader()
                writer.writerow(
                    {
                        "trial_id": "A001",
                        "scenario": "added_normal",
                        "lighting": "normal",
                        "nuisance": "none",
                        "before_image": "images/before.jpg",
                        "after_image": "images/after.jpg",
                        "event_ground_truth": "added",
                        "bbox_ground_truth": "100;70;111;111",
                    }
                )
                writer.writerow(
                    {
                        "trial_id": "N001",
                        "scenario": "none_normal",
                        "lighting": "normal",
                        "nuisance": "none",
                        "before_image": "images/still.jpg",
                        "after_image": "images/still.jpg",
                        "event_ground_truth": "none",
                        "source_segment_seconds": "30",
                    }
                )
            overrides = root / "config.json"
            overrides.write_text('{"min_change_area": 500}', encoding="utf-8")
            output = root / "result"
            stdout = io.StringIO()
            code = main(
                [
                    "run-pairs",
                    "--manifest",
                    str(manifest),
                    "--output-dir",
                    str(output),
                    "--run-id",
                    "R001",
                    "--profiles",
                    "plain,full",
                    "--config-json",
                    str(overrides),
                ],
                stdout=stdout,
                stderr=io.StringIO(),
            )
            self.assertEqual(code, 0, stdout.getvalue())
            self.assertEqual(len(read_episodes(output / "episodes.csv")), 4)
            self.assertEqual(
                sum(
                    event.record_role == "prediction"
                    for event in read_events(output / "events.csv")
                ),
                2,
            )
            self.assertTrue((output / "summary-local.json").exists())
            with (output / "summary-local-overall.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                summaries = list(csv.DictReader(handle))
            self.assertEqual({row["prediction_stage"] for row in summaries}, {"local"})
            self.assertEqual({float(row["iou_threshold"]) for row in summaries}, {0.3})
            self.assertEqual({float(row["micro_f1"]) for row in summaries}, {1.0})
            metadata = json.loads(
                (output / "run_metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["trial_count"], 2)
            self.assertEqual(metadata["scoring"]["iou_threshold"], 0.3)

            stderr = io.StringIO()
            second = main(
                [
                    "run-pairs",
                    "--manifest",
                    str(manifest),
                    "--output-dir",
                    str(output),
                    "--run-id",
                    "R001",
                    "--config-json",
                    str(overrides),
                ],
                stdout=io.StringIO(),
                stderr=stderr,
            )
            self.assertEqual(second, 2)
            self.assertIn("refusing to replace", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
