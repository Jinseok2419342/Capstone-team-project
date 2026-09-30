from __future__ import annotations

import unittest

from experiments.matching import bbox_iou, match_events
from experiments.schema import EpisodeRecord, EventRecord


def _episode(
    episode_id: str,
    *,
    expected: int,
    eligible_seconds: float = 20.0,
) -> EpisodeRecord:
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
    *,
    role: str,
    kind: str,
    second: int,
    bbox: tuple[int, int, int, int] = (0, 0, 10, 10),
    stage: str | None = None,
    object_id: str = "",
    matched_item_id: str = "",
) -> EventRecord:
    x, y, width, height = bbox
    return EventRecord(
        run_id="R1",
        episode_id=episode_id,
        event_id=event_id,
        record_role=role,  # type: ignore[arg-type]
        stage=stage or ("ground_truth" if role == "ground_truth" else "final"),  # type: ignore[arg-type]
        event_kind=kind,  # type: ignore[arg-type]
        event_at=f"2026-09-15T00:00:{second:02d}+09:00",
        object_id=object_id,
        matched_item_id=matched_item_id,
        bbox_x=x,
        bbox_y=y,
        bbox_w=width,
        bbox_h=height,
        frame_width=100,
        frame_height=100,
    )


class ExperimentMatchingTests(unittest.TestCase):
    def test_incomplete_episode_cannot_be_scored(self) -> None:
        episode = EpisodeRecord(
            run_id="R1",
            episode_id="OPEN",
            started_at="2026-09-15T00:00:00+09:00",
            ended_at="",
            eligible_monitoring_seconds=0.0,
            episode_complete=False,
        )
        with self.assertRaisesRegex(ValueError, "incomplete"):
            match_events([episode], [])

    def test_bbox_iou_uses_xywh_and_rejects_invalid_boxes(self) -> None:
        self.assertAlmostEqual(bbox_iou((0, 0, 10, 10), (5, 0, 10, 10)), 1 / 3)
        self.assertEqual(bbox_iou((0, 0, 0, 10), (0, 0, 10, 10)), 0.0)
        self.assertEqual(bbox_iou(None, (0, 0, 10, 10)), 0.0)

    def test_first_duplicate_is_tp_and_local_verification_is_ignored(self) -> None:
        episode = _episode("E1", expected=1)
        truth = _event("E1", "T1", role="ground_truth", kind="added", second=10)
        first = _event(
            "E1", "P1", role="prediction", kind="added", second=11, bbox=(5, 0, 10, 10)
        )
        later = _event("E1", "P2", role="prediction", kind="added", second=12)
        verification = _event(
            "E1",
            "P0",
            role="prediction",
            kind="verify_removed",
            second=11,
            stage="local",
        )

        result = match_events(
            [episode],
            [truth, later, verification, first],
            iou_threshold=0.3,
            allowed_window_seconds=5,
        )

        self.assertEqual(result.matches[0].prediction.event_id, "P1")
        self.assertEqual([event.event_id for event in result.false_positives], ["P2"])
        self.assertEqual([event.event_id for event in result.duplicate_predictions], ["P2"])
        self.assertEqual([event.event_id for event in result.ignored_predictions], ["P0"])

    def test_assignment_maximizes_cardinality_instead_of_greedy_iou(self) -> None:
        episode = _episode("E2", expected=2)
        truth_a = _event("E2", "T1", role="ground_truth", kind="added", second=10)
        truth_b = _event(
            "E2", "T2", role="ground_truth", kind="added", second=10, bbox=(8, 0, 10, 10)
        )
        overlaps_both = _event(
            "E2", "P1", role="prediction", kind="added", second=11, bbox=(4, 0, 10, 10)
        )
        only_a = _event("E2", "P2", role="prediction", kind="added", second=12)

        result = match_events(
            [episode],
            [truth_a, truth_b, overlaps_both, only_a],
            allowed_window_seconds=5,
        )

        pairs = {
            match.ground_truth.event_id: match.prediction.event_id for match in result.matches
        }
        self.assertEqual(pairs, {"T1": "P2", "T2": "P1"})
        self.assertFalse(result.false_positives)
        self.assertFalse(result.false_negatives)

    def test_kind_time_and_iou_are_hard_matching_gates(self) -> None:
        episode = _episode("E3", expected=1)
        truth = _event("E3", "T1", role="ground_truth", kind="removed", second=10)
        before_window = _event(
            "E3", "P1", role="prediction", kind="removed", second=9
        )
        wrong_kind = _event("E3", "P2", role="prediction", kind="added", second=11)
        wrong_box = _event(
            "E3", "P3", role="prediction", kind="removed", second=12, bbox=(50, 50, 10, 10)
        )

        result = match_events(
            [episode],
            [truth, before_window, wrong_kind, wrong_box],
            allowed_window_seconds=5,
        )

        self.assertFalse(result.matches)
        self.assertEqual(len(result.false_positives), 3)
        self.assertEqual([event.event_id for event in result.false_negatives], ["T1"])

    def test_moved_identity_failure_does_not_erase_detection_tp(self) -> None:
        episode = _episode("E4", expected=1)
        truth = _event(
            "E4", "T1", role="ground_truth", kind="moved", second=10, object_id="O1"
        )
        prediction = _event(
            "E4", "P1", role="prediction", kind="moved", second=11, object_id="O2"
        )

        result = match_events([episode], [truth, prediction])

        self.assertEqual(len(result.matches), 1)
        self.assertFalse(result.matches[0].id_preserved)
        self.assertTrue(result.matches[0].duplicate_id_created)

    def test_none_episode_counts_final_events_but_not_verify_removed(self) -> None:
        episode = _episode("E5", expected=0, eligible_seconds=1800)
        false_event = _event("E5", "P1", role="prediction", kind="added", second=11)
        verification = _event(
            "E5",
            "P2",
            role="prediction",
            kind="verify_removed",
            second=12,
            stage="local",
        )

        result = match_events([episode], [false_event, verification])

        self.assertTrue(result.episodes[0].is_none_episode)
        self.assertEqual([event.event_id for event in result.false_positives], ["P1"])
        self.assertEqual([event.event_id for event in result.ignored_predictions], ["P2"])

    def test_prediction_stage_keeps_local_and_final_scores_separate(self) -> None:
        episode = _episode("E7", expected=1)
        truth = _event("E7", "T1", role="ground_truth", kind="added", second=10)
        local = _event(
            "E7", "P1", role="prediction", kind="added", second=11, stage="local"
        )
        final = _event(
            "E7", "P2", role="prediction", kind="added", second=12, stage="final"
        )
        verification = _event(
            "E7",
            "P3",
            role="prediction",
            kind="verify_removed",
            second=13,
            stage="local",
        )

        final_result = match_events([episode], [truth, local, final, verification])
        local_result = match_events(
            [episode],
            [truth, local, final, verification],
            prediction_stage="local",
        )

        self.assertEqual(final_result.prediction_stage, "final")
        self.assertEqual(final_result.matches[0].prediction.event_id, "P2")
        self.assertEqual(local_result.prediction_stage, "local")
        self.assertEqual(local_result.matches[0].prediction.event_id, "P1")
        self.assertEqual(
            {event.event_id for event in local_result.ignored_predictions},
            {"P2", "P3"},
        )

    def test_declared_truth_count_is_checked_before_scoring(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected_event_count"):
            match_events([_episode("E6", expected=1)], [])


if __name__ == "__main__":
    unittest.main()
