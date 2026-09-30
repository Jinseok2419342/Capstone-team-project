from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from experiments.csvio import (
    CsvFormatError,
    DuplicateRecordError,
    append_episode,
    append_events,
    read_episodes,
    read_events,
    validate_dataset,
)
from experiments.schema import (
    EPISODE_CSV_FIELDS,
    EpisodeRecord,
    EventRecord,
    RecordValidationError,
)


def issue_codes(issues) -> set[str]:
    return {issue.code for issue in issues}


class ExperimentCsvIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.episodes_path = self.root / "records" / "episodes.csv"
        self.events_path = self.root / "records" / "events.csv"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def episode(self, **overrides) -> EpisodeRecord:
        values = {
            "run_id": "run-001",
            "episode_id": "episode-001",
            "started_at": "2026-09-15T01:00:00Z",
            "ended_at": "2026-09-15T01:01:00Z",
            "eligible_monitoring_seconds": 60.0,
            "expected_event_count": 1,
            "scenario": "책상, 실내",
            "notes": "첫 줄, 쉼표 포함\n둘째 줄",
        }
        values.update(overrides)
        return EpisodeRecord(**values)

    def event(self, **overrides) -> EventRecord:
        values = {
            "run_id": "run-001",
            "episode_id": "episode-001",
            "event_id": "gt-001",
            "record_role": "ground_truth",
            "stage": "ground_truth",
            "event_kind": "added",
            "event_at": "2026-09-15T01:00:05Z",
            "object_id": "object-001",
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
            "frame_width": 320,
            "frame_height": 240,
            "object_name": "검정색, 지갑",
            "notes": "한글\n메모",
        }
        values.update(overrides)
        return EventRecord(**values)

    def test_utf8_sig_csv_round_trip_with_korean_commas_and_newlines(self) -> None:
        episode = self.episode()
        event = self.event()
        append_episode(self.episodes_path, episode)
        append_events(self.events_path, [event], episodes_path=self.episodes_path)

        self.assertEqual(read_episodes(self.episodes_path), [episode])
        self.assertEqual(read_events(self.events_path), [event])
        self.assertTrue(self.episodes_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue(self.events_path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_repeated_append_emits_one_bom_and_one_header(self) -> None:
        append_episode(self.episodes_path, self.episode(expected_event_count=0))
        append_episode(
            self.episodes_path,
            self.episode(episode_id="episode-002", expected_event_count=0),
        )

        payload = self.episodes_path.read_bytes()
        self.assertEqual(payload.count(b"\xef\xbb\xbf"), 1)
        with self.episodes_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(tuple(rows[0]), EPISODE_CSV_FIELDS)
        self.assertEqual(len(rows), 3)

    def test_append_rejects_incompatible_existing_header_without_mutation(self) -> None:
        self.episodes_path.parent.mkdir(parents=True)
        self.episodes_path.write_text("wrong,header\n1,2\n", encoding="utf-8-sig")
        before = self.episodes_path.read_bytes()

        with self.assertRaises(CsvFormatError):
            append_episode(self.episodes_path, self.episode())
        self.assertEqual(self.episodes_path.read_bytes(), before)

    def test_append_rejects_invalid_and_duplicate_records(self) -> None:
        with self.assertRaises(RecordValidationError):
            append_episode(
                self.episodes_path,
                self.episode(run_id="", expected_event_count=0),
            )
        self.assertFalse(self.episodes_path.exists())

        episode = self.episode(expected_event_count=0)
        append_episode(self.episodes_path, episode)
        with self.assertRaises(DuplicateRecordError):
            append_episode(self.episodes_path, episode)

    def test_event_batch_is_validated_before_any_rows_are_written(self) -> None:
        valid = self.event(event_id="pred-001", record_role="prediction", stage="local")
        invalid = self.event(
            event_id="pred-002",
            record_role="prediction",
            stage="local",
            confidence=2.0,
        )
        with self.assertRaises(RecordValidationError):
            append_events(self.events_path, [valid, invalid])
        self.assertFalse(self.events_path.exists())

        with self.assertRaises(DuplicateRecordError):
            append_events(self.events_path, [valid, valid])
        self.assertFalse(self.events_path.exists())

    def test_event_append_can_reject_an_unknown_episode(self) -> None:
        append_episode(self.episodes_path, self.episode(expected_event_count=0))
        orphan = self.event(episode_id="missing-episode")
        with self.assertRaisesRegex(ValueError, "unknown episodes"):
            append_events(
                self.events_path, [orphan], episodes_path=self.episodes_path
            )
        self.assertFalse(self.events_path.exists())

    def test_duplicate_event_is_rejected_on_later_append(self) -> None:
        event = self.event()
        append_events(self.events_path, [event])
        with self.assertRaises(DuplicateRecordError):
            append_events(self.events_path, [event])

    def test_read_rejects_invalid_numeric_and_missing_columns(self) -> None:
        append_episode(
            self.episodes_path, self.episode(expected_event_count=0)
        )
        text = self.episodes_path.read_text(encoding="utf-8-sig")
        self.episodes_path.write_text(
            text.replace(",60.0,true,", ",not-a-number,true,"),
            encoding="utf-8-sig",
            newline="",
        )
        with self.assertRaises(CsvFormatError):
            read_episodes(self.episodes_path)

        self.events_path.write_text("run_id,event_id\nrun-001,event-001\n", encoding="utf-8-sig")
        with self.assertRaises(CsvFormatError):
            read_events(self.events_path)

    def test_validate_dataset_reports_duplicates_orphans_and_gt_count(self) -> None:
        episode = self.episode(expected_event_count=1)
        duplicate_episode = self.episode(expected_event_count=1)
        ground_truth = self.event()
        duplicate_event = self.event()
        orphan = self.event(episode_id="missing", event_id="gt-orphan")

        codes = issue_codes(
            validate_dataset(
                [episode, duplicate_episode],
                [ground_truth, duplicate_event, orphan],
            )
        )
        self.assertIn("duplicate_episode_id", codes)
        self.assertIn("duplicate_event_id", codes)
        self.assertIn("orphan_event", codes)
        self.assertIn("ground_truth_count_mismatch", codes)

    def test_validate_dataset_rejects_pipeline_time_before_action_end(self) -> None:
        episode = self.episode(
            action_end_at="2026-09-15T01:00:10Z",
            expected_event_count=1,
        )
        truth = self.event(event_at="2026-09-15T01:00:10Z")
        prediction = self.event(
            event_id="pred-001",
            record_role="prediction",
            stage="final",
            event_at="2026-09-15T01:00:11Z",
            provisional_db_at="2026-09-15T01:00:09Z",
        )
        codes = issue_codes(validate_dataset([episode], [truth, prediction]))
        self.assertIn("timestamp_before_episode_window", codes)


if __name__ == "__main__":
    unittest.main()
