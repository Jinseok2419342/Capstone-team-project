from __future__ import annotations

import unittest

from experiments.matching import match_events
from experiments.metrics import (
    bootstrap_interval,
    compute_detection_metrics,
    mcnemar_exact,
    percentile,
    precision_recall_f1,
    wilson_interval,
)
from experiments.schema import EpisodeRecord, EventRecord


def _episode(episode_id: str, expected: int, eligible_seconds: float = 20.0) -> EpisodeRecord:
    return EpisodeRecord(
        run_id="R1",
        episode_id=episode_id,
        started_at="2026-09-15T00:00:00+09:00",
        action_end_at="2026-09-15T00:00:10+09:00",
        ended_at="2026-09-15T00:00:30+09:00",
        eligible_monitoring_seconds=eligible_seconds,
        expected_event_count=expected,
    )


def _event(
    episode_id: str,
    event_id: str,
    role: str,
    kind: str,
    second: int,
    *,
    object_id: str = "",
    matched_item_id: str = "",
    provisional_db_at: str = "",
    ai_request_at: str = "",
    ai_response_at: str = "",
    final_commit_at: str = "",
) -> EventRecord:
    return EventRecord(
        run_id="R1",
        episode_id=episode_id,
        event_id=event_id,
        record_role=role,  # type: ignore[arg-type]
        stage="ground_truth" if role == "ground_truth" else "final",
        event_kind=kind,  # type: ignore[arg-type]
        event_at=f"2026-09-15T00:00:{second:02d}+09:00",
        object_id=object_id,
        matched_item_id=matched_item_id,
        bbox_x=0,
        bbox_y=0,
        bbox_w=10,
        bbox_h=10,
        frame_width=100,
        frame_height=100,
        provisional_db_at=provisional_db_at,
        ai_request_at=ai_request_at,
        ai_response_at=ai_response_at,
        final_commit_at=final_commit_at,
    )


class ExperimentMetricsTests(unittest.TestCase):
    def test_core_detection_identity_false_rate_and_latency_metrics(self) -> None:
        episodes = [
            _episode("E1", 1),
            _episode("E2", 1),
            _episode("E3", 1),
            _episode("E4", 0, eligible_seconds=1800.0),
        ]
        events = [
            _event("E1", "T1", "ground_truth", "added", 10),
            _event(
                "E1",
                "P1",
                "prediction",
                "added",
                11,
                provisional_db_at="2026-09-15T00:00:12+09:00",
                ai_request_at="2026-09-15T00:00:12+09:00",
                ai_response_at="2026-09-15T00:00:14+09:00",
                final_commit_at="2026-09-15T00:00:15+09:00",
            ),
            _event("E2", "T1", "ground_truth", "removed", 10),
            _event(
                "E3", "T1", "ground_truth", "moved", 10, object_id="OBJECT-1"
            ),
            _event(
                "E3", "P1", "prediction", "moved", 13, object_id="NEW-OBJECT"
            ),
            _event("E4", "P1", "prediction", "added", 11),
            _event("E4", "P2", "prediction", "removed", 12),
        ]

        result = match_events(episodes, events, allowed_window_seconds=5)
        metrics = compute_detection_metrics(result)

        self.assertEqual(metrics.iou_threshold, 0.3)
        self.assertEqual(metrics.allowed_window_seconds, 5)

        added = metrics.by_kind["added"]
        self.assertEqual((added.true_positives, added.false_positives, added.false_negatives), (1, 1, 0))
        self.assertAlmostEqual(added.precision, 0.5)
        self.assertAlmostEqual(added.recall, 1.0)
        self.assertAlmostEqual(added.f1, 2 / 3)
        self.assertEqual(
            (
                metrics.by_kind["removed"].true_positives,
                metrics.by_kind["removed"].false_positives,
                metrics.by_kind["removed"].false_negatives,
            ),
            (0, 1, 1),
        )
        self.assertAlmostEqual(metrics.macro_f1, 5 / 9)
        self.assertAlmostEqual(metrics.micro_f1, 4 / 7)
        self.assertEqual(metrics.ground_truth_event_count, 3)
        self.assertEqual(metrics.scored_prediction_count, 4)
        self.assertEqual(metrics.final_prediction_count, 4)
        self.assertEqual(metrics.false_event_count, 2)
        self.assertEqual(metrics.none_episode_count, 1)
        self.assertEqual(metrics.none_episode_false_trigger_count, 1)
        self.assertEqual(metrics.none_episode_false_trigger_rate, 1.0)
        self.assertIsNotNone(metrics.none_episode_false_trigger_interval)
        self.assertAlmostEqual(metrics.none_monitoring_hours, 0.5)
        self.assertAlmostEqual(metrics.false_events_per_hour or 0.0, 4.0)
        self.assertEqual(metrics.moved_identity_scorable_count, 1)
        self.assertEqual(metrics.moved_id_preserved_count, 0)
        self.assertEqual(metrics.moved_id_preservation_rate, 0.0)
        self.assertEqual(metrics.duplicate_id_created_count, 1)
        self.assertEqual(metrics.bbox_iou.mean, 1.0)
        self.assertEqual(metrics.local_event_latency_ms.p50, 2000.0)
        self.assertEqual(metrics.local_event_latency_ms.p95, 2900.0)
        self.assertEqual(metrics.provisional_db_latency_ms.p50, 2000.0)
        self.assertEqual(metrics.ai_round_trip_latency_ms.p50, 2000.0)
        self.assertEqual(metrics.final_commit_latency_ms.p50, 5000.0)

    def test_zero_denominators_are_explicit_and_not_nan(self) -> None:
        episode = _episode("E0", 0, eligible_seconds=0.0)
        metrics = compute_detection_metrics(match_events([episode], []))

        self.assertEqual(precision_recall_f1(0, 0, 0), (0.0, 0.0, 0.0))
        self.assertIsNone(metrics.by_kind["added"].precision_interval)
        self.assertIsNone(metrics.false_events_per_hour)
        self.assertEqual(metrics.none_episode_false_trigger_rate, 0.0)
        self.assertIsNone(metrics.bbox_iou.mean)

    def test_wilson_percentile_mcnemar_and_bootstrap_helpers(self) -> None:
        interval = wilson_interval(5, 10)
        assert interval is not None
        self.assertAlmostEqual(interval.lower, 0.2366, places=4)
        self.assertAlmostEqual(interval.upper, 0.7634, places=4)
        self.assertEqual(percentile([1.0, 2.0, 3.0], 95), 2.9)

        paired = mcnemar_exact([False] * 4, [True] * 4)
        self.assertEqual(paired.first_only_correct, 0)
        self.assertEqual(paired.second_only_correct, 4)
        self.assertEqual(paired.exact_p_value, 0.125)

        bootstrapped = bootstrap_interval([2.0, 2.0, 2.0], resamples=100, seed=7)
        self.assertEqual((bootstrapped.lower, bootstrapped.upper), (2.0, 2.0))


if __name__ == "__main__":
    unittest.main()
