from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from experiments.schema import (
    EpisodeRecord,
    EventRecord,
    format_iso8601,
    parse_iso8601,
    validate_episode,
    validate_event,
)


def issue_codes(issues) -> set[str]:
    return {issue.code for issue in issues}


class ExperimentSchemaTests(unittest.TestCase):
    def episode(self, **overrides) -> EpisodeRecord:
        values = {
            "run_id": "run-001",
            "episode_id": "episode-001",
            "started_at": "2026-09-15T10:00:00+09:00",
            "action_start_at": "2026-09-15T10:00:05+09:00",
            "action_end_at": "2026-09-15T10:00:06+09:00",
            "ended_at": "2026-09-15T10:01:00+09:00",
            "eligible_monitoring_seconds": 54.0,
            "expected_event_count": 1,
        }
        values.update(overrides)
        return EpisodeRecord(**values)

    def event(self, **overrides) -> EventRecord:
        values = {
            "run_id": "run-001",
            "episode_id": "episode-001",
            "event_id": "pred-001",
            "pipeline_id": "pipeline-001",
            "record_role": "prediction",
            "stage": "local",
            "event_kind": "added",
            "event_at": "2026-09-15T10:00:06.250+09:00",
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
            "frame_width": 320,
            "frame_height": 240,
            "confidence": 0.85,
        }
        values.update(overrides)
        return EventRecord(**values)

    def test_timezone_aware_timestamp_round_trip(self) -> None:
        parsed = parse_iso8601("2026-09-15T01:02:03.456Z")
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(format_iso8601(parsed), "2026-09-15T01:02:03.456000Z")

        kst = datetime(2026, 9, 15, 10, 2, 3, tzinfo=timezone(timedelta(hours=9)))
        self.assertEqual(format_iso8601(kst), "2026-09-15T01:02:03Z")

    def test_naive_and_malformed_timestamps_are_rejected(self) -> None:
        for value in ("", "not-a-date", "2026-09-15T10:00:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_iso8601(value)

    def test_valid_episode_and_incomplete_episode(self) -> None:
        self.assertEqual(validate_episode(self.episode()), [])

        incomplete = self.episode(
            ended_at="", episode_complete=False, expected_event_count=0
        )
        issues = validate_episode(incomplete)
        self.assertEqual(issue_codes(issues), {"incomplete_episode"})
        self.assertFalse(issues[0].is_error)

    def test_episode_validates_ids_order_ranges_and_digest(self) -> None:
        record = self.episode(
            run_id=" run-001",
            action_end_at="2026-09-15T09:59:00+09:00",
            eligible_monitoring_seconds=-1,
            callback_dropped_count=-1,
            observed_monitor_fps=math.inf,
            config_sha256="not-a-sha256",
        )
        codes = issue_codes(validate_episode(record))
        self.assertTrue(
            {
                "invalid_id",
                "timestamp_order",
                "out_of_range",
                "invalid_integer",
                "invalid_number",
                "invalid_sha256",
            }.issubset(codes)
        )

    def test_episode_rejects_monitoring_time_beyond_wall_duration(self) -> None:
        record = self.episode(
            eligible_monitoring_seconds=61.0,
            camera_disconnect_seconds=1.0,
        )
        codes = issue_codes(validate_episode(record))
        self.assertIn("duration_exceeds_episode", codes)
        self.assertIn("accounted_time_exceeds_episode", codes)

    def test_event_bbox_property_and_valid_record(self) -> None:
        record = self.event()
        self.assertEqual(record.bbox, (10, 20, 30, 40))
        self.assertEqual(validate_event(record), [])
        self.assertIsNone(
            self.event(bbox_x=None, bbox_y=None, bbox_w=None, bbox_h=None).bbox
        )
        missing = validate_event(
            self.event(bbox_x=None, bbox_y=None, bbox_w=None, bbox_h=None)
        )
        self.assertEqual(issue_codes(missing), {"missing_bbox"})
        self.assertFalse(missing[0].is_error)

    def test_event_validates_partial_and_out_of_frame_bbox(self) -> None:
        partial = self.event(bbox_h=None)
        self.assertIn("partial_bbox", issue_codes(validate_event(partial)))

        invalid = self.event(bbox_x=-1, bbox_w=0)
        self.assertIn("invalid_bbox", issue_codes(validate_event(invalid)))

        outside = self.event(bbox_x=300, bbox_w=30)
        self.assertIn("bbox_out_of_frame", issue_codes(validate_event(outside)))

        partial_frame = self.event(frame_height=None)
        self.assertIn("partial_frame_size", issue_codes(validate_event(partial_frame)))

        wrong_type = self.event(bbox_x="10")
        self.assertIsNone(wrong_type.bbox)
        self.assertIn("invalid_bbox", issue_codes(validate_event(wrong_type)))

    def test_event_validates_confidence_and_identifiers(self) -> None:
        record = self.event(
            event_id="bad\nidentifier", confidence=1.01, ai_confidence=math.nan
        )
        codes = issue_codes(validate_event(record))
        self.assertIn("invalid_id", codes)
        self.assertIn("out_of_range", codes)
        self.assertIn("invalid_number", codes)

    def test_role_stage_and_verify_removed_constraints(self) -> None:
        ground_truth = self.event(
            event_id="gt-001",
            record_role="ground_truth",
            stage="local",
            event_kind="verify_removed",
        )
        codes = issue_codes(validate_event(ground_truth))
        self.assertIn("role_stage_mismatch", codes)
        self.assertIn("invalid_ground_truth_kind", codes)

        final_candidate = self.event(stage="final", event_kind="verify_removed")
        self.assertIn("invalid_final_kind", issue_codes(validate_event(final_candidate)))

    def test_pipeline_timestamps_must_be_ordered(self) -> None:
        record = self.event(
            ai_request_at="2026-09-15T10:00:08+09:00",
            ai_response_at="2026-09-15T10:00:07+09:00",
        )
        self.assertIn("timestamp_order", issue_codes(validate_event(record)))


if __name__ == "__main__":
    unittest.main()
