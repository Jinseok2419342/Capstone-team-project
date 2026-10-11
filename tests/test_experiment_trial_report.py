import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.store import Store
from experiments import trial_report
from experiments.trial_report import TrialSheetError


SHEET_HEADER = ["번호", "조건", "행동", "물품", "결과", "AI이름", "AI분류", "메모"]


def write_sheet(path: Path, rows, encoding="utf-8-sig"):
    with path.open("w", newline="", encoding=encoding) as handle:
        writer = csv.writer(handle)
        writer.writerow(SHEET_HEADER)
        writer.writerows(rows)


class TrialSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_confusion_metrics_and_ai_marks(self):
        rows = [
            [1, "일반", "등록", "지갑", "등록", "O", "O", ""],
            [2, "일반", "등록", "우산", "등록", "X", "O", ""],
            [3, "일반", "등록", "컵", "반응 없음", "", "", ""],
            [4, "일반", "이동", "지갑", "이동", "", "", ""],
            [5, "일반", "이동", "우산", "등록", "", "", ""],
            [6, "일반", "제거", "지갑", "제거", "", "", ""],
            [7, "일반", "제거", "우산", "확인필요", "", "", ""],
            [8, "손", "무변화", "", "반응없음", "", "", ""],
            [9, "조명", "무변화", "", "등록", "", "", ""],
            [10, "그림자", "없음", "", "없음", "", "", ""],
            ["", "", "", "", "", "", "", ""],
        ]
        sheet = self.dir / "trials.csv"
        write_sheet(sheet, rows, encoding="cp949")
        summary = trial_report.summarize_trials(trial_report.read_trials(sheet))

        self.assertEqual(summary["trials"], 10)
        self.assertEqual(summary["confusion"]["등록"]["등록"], 2)
        self.assertEqual(summary["confusion"]["이동"]["등록"], 1)
        self.assertEqual(summary["confusion"]["무변화"]["반응 없음"], 2)
        self.assertAlmostEqual(summary["accuracy"], 6 / 10)
        added = summary["per_kind"]["등록"]
        # TP 2, FP from move 1 + light 1, FN 1.
        self.assertEqual((added["tp"], added["fp"], added["fn"]), (2, 2, 1))
        self.assertAlmostEqual(added["precision"], 0.5)
        self.assertAlmostEqual(added["recall"], 2 / 3)
        self.assertEqual(summary["none_false_events"]["조명"]["false_events"], 1)
        self.assertEqual(summary["nuisance_false_events"], 1)
        self.assertAlmostEqual(summary["ai_name_accuracy"], 0.5)
        self.assertAlmostEqual(summary["ai_category_accuracy"], 1.0)
        low, high = summary["accuracy_ci95"]
        self.assertLess(low, 0.6)
        self.assertGreater(high, 0.6)

    def test_invalid_value_names_the_row(self):
        sheet = self.dir / "bad.csv"
        write_sheet(sheet, [[1, "일반", "등록", "지갑", "놓침", "", "", ""]])
        with self.assertRaisesRegex(TrialSheetError, "2행 결과"):
            trial_report.read_trials(sheet)

    def test_wilson_interval_known_value(self):
        low, high = trial_report.wilson_interval(18, 20)
        self.assertAlmostEqual(low, 0.699, places=3)
        self.assertAlmostEqual(high, 0.972, places=3)


class RunLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _activity(self, store, kind, item_id, metadata, at):
        store.create_activity(kind, kind, item_id=item_id, metadata=metadata)
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "UPDATE activities SET created_at=? WHERE id=(SELECT max(id) FROM activities)", (at,)
            )

    def test_database_counts_selective_calls_and_latency(self):
        self.db = self.dir / "lost_items.db"
        store = Store(self.db)
        store.initialize()
        item = store.create_item({
            "name": "지갑", "category": "valuable", "retention_days": 90,
            "detected_at": "2026-10-20T05:00:00+00:00", "expires_at": "2027-01-18T05:00:00+00:00",
            "source_kind": "camera",
        })
        other = store.create_item({
            "name": "우산", "category": "general", "retention_days": 60,
            "detected_at": "2026-10-20T05:01:00+00:00", "expires_at": "2026-12-19T05:01:00+00:00",
            "source_kind": "camera",
        })
        camera = {"source": "camera"}
        verify = {"source": "camera_ai_verification"}
        self._activity(store, "item_detected", item["id"], camera, "2026-10-20T05:00:00+00:00")
        self._activity(store, "item_classified", item["id"], {}, "2026-10-20T05:00:04+00:00")
        self._activity(store, "item_detected", other["id"], camera, "2026-10-20T05:01:00+00:00")
        self._activity(store, "classification_inconclusive", other["id"], {}, "2026-10-20T05:01:10+00:00")
        self._activity(store, "item_moved", item["id"], camera, "2026-10-20T05:02:00+00:00")
        self._activity(store, "item_recovered", item["id"], camera, "2026-10-20T05:03:00+00:00")
        self._activity(store, "recovery_check_inconclusive", other["id"], verify, "2026-10-20T05:04:00+00:00")
        # Inside the unattended window: one false event.
        self._activity(store, "item_moved", other["id"], camera, "2026-10-20T06:30:00+00:00")

        summary = trial_report.summarize_database(
            self.db, until=trial_report._parse_time("2026-10-20T06:00:00+00:00")
        )
        self.assertEqual(summary["detected_events"], 5)
        self.assertEqual(summary["ai_calls"], 3)
        self.assertAlmostEqual(summary["ai_call_ratio"], 3 / 5)
        self.assertEqual(summary["classification_median_s"], 7.0)
        self.assertEqual(summary["classification_max_s"], 10.0)
        self.assertAlmostEqual(summary["review_ratio"], 2 / 3)

        sheet = self.dir / "trials.csv"
        write_sheet(sheet, [[1, "일반", "등록", "지갑", "등록", "O", "O", ""]])
        health = self.dir / "health.csv"
        with health.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp_utc", "ok", "phase", "camera_connected", "fps", "processing_ms", "frame_sequence"])
            writer.writerow(["t1", 1, "monitoring", 1, "6.0", "40", "100"])
            writer.writerow(["t2", 1, "monitoring", 1, "7.0", "60", "160"])
            writer.writerow(["t3", 0, "stopped", 0, "0", "0", "160"])
        resources = self.dir / "resources.csv"
        with resources.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["process_alive", "system_cpu_percent", "rss_mib", "temperature_c"])
            writer.writerow([1, "", "150", "55.0"])
            writer.writerow([1, "40", "160", "61.5"])
        out = self.dir / "out"
        code = trial_report.main([
            "--trials", str(sheet), "--db", str(self.db), "--health", str(health),
            "--resources", str(resources), "--idle-start", "2026-10-20T06:00:00+00:00",
            "--idle-end", "2026-10-20T07:00:00+00:00", "--output-dir", str(out),
        ])
        self.assertEqual(code, 0)
        result = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(result["idle"]["false_events"], 1)
        self.assertEqual(result["database"]["detected_events"], 5)
        self.assertEqual(result["health"]["frames_processed"], 60)
        self.assertAlmostEqual(result["health"]["fps"]["mean"], 6.5)
        markdown = (out / "paper_tables.md").read_text(encoding="utf-8")
        self.assertIn("[[AI_CALL_RATIO]]` = 60.0", markdown)
        self.assertIn("[[TEMP_MAX]]` = 61.5", markdown)
        self.assertIn("[[IDLE_FP]]` = 1", markdown)
        self.assertIn("| 등록(1) | 1 | 0 | 0 | 0 | 0 |", markdown)


if __name__ == "__main__":
    unittest.main()
