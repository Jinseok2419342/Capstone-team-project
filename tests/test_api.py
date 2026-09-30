from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.ai import Classification
from app.store import Store
from app.vision import ChangeEvent


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ApiIntegrationTests(unittest.TestCase):
    """Exercise the real FastAPI routes against an isolated SQLite database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp_dir.name) / "api-test.sqlite3")

        # Route functions resolve these globals at request time.  The scheduler
        # also holds its own store reference, so both are replaced before the
        # application lifespan starts.
        cls.original_store = main.store
        cls.original_scheduler_store = main.scheduler.store
        main.store = cls.store
        main.scheduler.store = cls.store

        cls.patchers = [
            patch.object(main.vision, "start"),
            patch.object(main.vision, "stop"),
            patch.object(main.vision, "get_jpeg", return_value=b""),
            patch.object(
                main.vision,
                "get_status",
                return_value={
                    "state": "test",
                    "connected": False,
                    "message": "camera disabled in tests",
                },
            ),
            patch.object(main.vision, "set_privacy"),
            patch.object(main.vision, "rebaseline"),
            patch.object(main.scheduler, "start"),
            patch.object(main.scheduler, "stop"),
        ]
        (
            cls.vision_start,
            cls.vision_stop,
            cls.vision_get_jpeg,
            cls.vision_get_status,
            cls.vision_set_privacy,
            cls.vision_rebaseline,
            cls.scheduler_start,
            cls.scheduler_stop,
        ) = [patcher.start() for patcher in cls.patchers]

        # A single lifespan is intentional: app.main's process-wide classifier
        # executor is shut down when the lifespan exits.
        cls.client_context = TestClient(main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.client_context.__exit__(None, None, None)
        finally:
            for patcher in reversed(cls.patchers):
                patcher.stop()
            main.store = cls.original_store
            main.scheduler.store = cls.original_scheduler_store
            cls.temp_dir.cleanup()

    def create_demo_phone(self) -> dict:
        response = self.client.post("/api/demo/items", json={"preset": "phone"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_health_and_dashboard_contract(self) -> None:
        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        health = health_response.json()
        self.assertIs(health["ok"], True)
        self.assertEqual(health["database"], "connected")
        self.assertEqual(health["camera"]["state"], "test")
        self.assertIn(health["hardware_profile"], {"desktop", "raspberry-pi"})
        self.assertIn("active", health["provider"])
        parse_datetime(health["time"])

        dashboard_response = self.client.get("/api/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard = dashboard_response.json()
        self.assertEqual(
            set(dashboard["stats"]), {"active", "due_soon", "expired", "recovered", "review_needed"}
        )
        self.assertIsInstance(dashboard["items"], list)
        self.assertIsInstance(dashboard["activities"], list)
        self.assertIsInstance(dashboard["notifications"], list)
        self.assertEqual(dashboard["camera"]["state"], "test")
        self.assertTrue(
            any(activity["type"] == "system_started" for activity in dashboard["activities"])
        )
        self.vision_start.assert_called_once_with()
        self.scheduler_start.assert_called_once_with()

    def test_uncertain_ai_result_is_kept_for_review(self) -> None:
        event = ChangeEvent(
            kind="added",
            bbox=(0, 20, 45, 80),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.61,
        )
        provisional = main.create_provisional_item(event)
        uncertain = Classification(
            name="식별 불가 물체",
            description="전후 이미지가 거의 같습니다.",
            category="general",
            confidence=0.2,
            provider="openai",
            action="uncertain",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=uncertain):
            main.classify_existing_item(provisional["id"], event)

        reviewed = self.store.get_item(provisional["id"])
        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed["status"], "stored")
        self.assertEqual(reviewed["provider"], "openai_review")
        self.assertEqual(reviewed["name"], "확인 필요한 새 물품")
        inconclusive = [
            activity
            for activity in self.store.list_activities(limit=50)
            if activity["type"] == "classification_inconclusive"
            and activity.get("item_id") == provisional["id"]
        ]
        self.assertTrue(inconclusive)
        self.assertEqual(inconclusive[0]["metadata"]["action"], "uncertain")
        self.assertIs(inconclusive[0]["metadata"]["review_required"], True)

    def test_late_ai_result_preserves_quickly_recovered_item(self) -> None:
        event = ChangeEvent(
            kind="added",
            bbox=(120, 90, 160, 110),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.74,
        )
        provisional = main.create_provisional_item(event)
        self.store.mark_recovered(provisional["id"])
        late_result = Classification(
            name="확인 필요한 물건",
            description="분석 전에 화면에서 사라졌습니다.",
            category="general",
            confidence=0.25,
            provider="openai",
            action="removed",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=late_result):
            main.classify_existing_item(provisional["id"], event)

        preserved = self.store.get_item(provisional["id"])
        self.assertIsNotNone(preserved)
        self.assertEqual(preserved["status"], "recovered")
        self.assertEqual(preserved["provider"], "openai_review")
        self.assertNotEqual(preserved["name"], "분석 중인 새 물품")

    def test_low_confidence_remote_addition_is_kept_for_review(self) -> None:
        event = ChangeEvent(
            kind="added",
            bbox=(35, 35, 70, 70),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.68,
        )
        provisional = main.create_provisional_item(event)
        weak_addition = Classification(
            name="희미한 물체",
            description="새 물체일 가능성이 낮습니다.",
            category="general",
            confidence=0.2,
            provider="openai",
            action="added",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=weak_addition):
            main.classify_existing_item(provisional["id"], event)
        reviewed = self.store.get_item(provisional["id"])
        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed["provider"], "openai_review")
        self.assertEqual(reviewed["name"], "희미한 물체")

    def test_low_confidence_remote_removal_is_kept_for_review(self) -> None:
        event = ChangeEvent(
            kind="added",
            bbox=(70, 60, 90, 80),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.7,
        )
        provisional = main.create_provisional_item(event)
        weak_removal = Classification(
            name="확인 필요한 물건",
            description="제거 변화일 가능성이 있지만 확실하지 않습니다.",
            category="general",
            confidence=0.55,
            provider="openai",
            action="removed",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=weak_removal):
            main.classify_existing_item(provisional["id"], event)

        reviewed = self.store.get_item(provisional["id"])
        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed["status"], "stored")
        self.assertEqual(reviewed["provider"], "openai_review")

    def test_strong_remote_rejection_preserves_reviewable_evidence(self) -> None:
        """A model's polarity decision cannot erase a camera observation."""

        with tempfile.TemporaryDirectory() as capture_temp_dir:
            capture_dir = Path(capture_temp_dir)
            isolated_config = replace(main.config, capture_dir=capture_dir)
            event = ChangeEvent(
                kind="added",
                bbox=(85, 45, 150, 95),
                crop_jpeg=b"candidate-after",
                before_jpeg=b"candidate-before",
                after_jpeg=b"candidate-after",
                confidence=0.79,
                scene_before_jpeg=b"scene-before",
                scene_after_jpeg=b"scene-after",
            )

            with patch.object(main, "config", isolated_config):
                provisional = main.create_provisional_item(event)
                image_path = Path(provisional["image_path"])
                background_path = Path(provisional["background_path"])
                self.assertEqual(
                    {path.resolve() for path in capture_dir.iterdir()},
                    {image_path.resolve(), background_path.resolve()},
                )

                removed = Classification(
                    name="Existing object removed",
                    description="The object is present before and absent after.",
                    category="general",
                    confidence=0.87,
                    provider="openai",
                    action="removed",
                )
                self.assertTrue(main.classification_slots.acquire(blocking=False))
                with patch.object(
                    main.classifier, "classify", return_value=removed
                ) as classify:
                    main.classify_existing_item(provisional["id"], event)

                classify.assert_called_once_with(
                    [b"candidate-before", b"candidate-after"],
                    scene_images=[b"scene-before", b"scene-after"],
                )
                preserved = self.store.get_item(provisional["id"])
                self.assertEqual(preserved["review_status"], "needs_review")
                self.assertEqual(preserved["review_reason"], "ai_rejected")
                self.assertEqual(image_path.read_bytes(), b"candidate-after")
                self.assertEqual(background_path.read_bytes(), b"candidate-before")
                self.assertEqual(len(list(capture_dir.iterdir())), 2)

        ignored = [
            activity
            for activity in self.store.list_activities(limit=100)
            if activity["type"] == "classification_inconclusive"
            and activity["metadata"].get("reason") == "ai_rejected"
            and activity["metadata"].get("confidence") == 0.87
        ]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["item_id"], provisional["id"])

    def test_offline_addition_is_explicitly_kept_for_review(self) -> None:
        event = ChangeEvent(
            kind="added",
            bbox=(45, 70, 100, 65),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.66,
        )
        provisional = main.create_provisional_item(event)
        offline = Classification(
            name="새 분실물",
            description="AI 연결 전 임시 등록되었습니다.",
            category="general",
            confidence=0.25,
            provider="offline",
            action="added",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=offline):
            main.classify_existing_item(provisional["id"], event)

        reviewed = self.store.get_item(provisional["id"])
        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed["provider"], "offline_review")
        self.assertEqual(reviewed["name"], "확인 필요한 새 물품")

    def test_ai_verified_removal_marks_item_recovered(self) -> None:
        item = self.store.create_item(
            {
                "name": "검은색 이어폰 케이스",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[40,40,90,70]",
                "confidence": 0.82,
            }
        )
        event = ChangeEvent(
            kind="verify_removed",
            bbox=(40, 40, 90, 70),
            crop_jpeg=b"crop-before",
            before_jpeg=b"crop-before",
            after_jpeg=b"crop-after",
            confidence=0.75,
            matched_item_id=item["id"],
            scene_before_jpeg=b"scene-before",
            scene_after_jpeg=b"scene-after",
        )
        result = Classification(
            name="검은색 이어폰 케이스",
            description="전에는 있었지만 이후 장면에서 사라졌습니다.",
            category="general",
            confidence=0.88,
            provider="openai",
            action="removed",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=result) as classify:
            main.verify_removed_item(item["id"], event)

        recovered = self.store.get_item(item["id"])
        self.assertEqual(recovered["status"], "recovered")
        classify.assert_called_once_with(
            [b"crop-before", b"crop-after"],
            scene_images=[b"scene-before", b"scene-after"],
        )

    def test_stale_ai_removal_does_not_recover_item_moved_during_call(self) -> None:
        item = self.store.create_item(
            {
                "name": "회색 리모컨",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[40,40,90,70]",
                "confidence": 0.82,
            }
        )
        verification = ChangeEvent(
            kind="verify_removed",
            bbox=(40, 40, 90, 70),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.75,
            matched_item_id=item["id"],
        )
        removed = Classification(
            name="회색 리모컨",
            description="이전 위치에서 사라졌습니다.",
            category="general",
            confidence=0.9,
            provider="openai",
            action="removed",
        )

        def move_then_return(*_args, **_kwargs):
            main.handle_vision_change(
                ChangeEvent(
                    kind="moved",
                    bbox=(220, 180, 90, 70),
                    crop_jpeg=None,
                    before_jpeg=None,
                    after_jpeg=None,
                    confidence=0.9,
                    matched_item_id=item["id"],
                )
            )
            return removed

        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", side_effect=move_then_return):
            main.verify_removed_item(item["id"], verification)

        current = self.store.get_item(item["id"])
        self.assertEqual(current["status"], "stored")
        self.assertEqual(current["bbox"], [220, 180, 90, 70])

    def test_uncertain_recovery_check_remains_persistently_visible(self) -> None:
        item = self.store.create_item(
            {
                "name": "파란색 볼펜",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[80,80,120,50]",
                "confidence": 0.8,
            }
        )
        event = ChangeEvent(
            kind="verify_removed",
            bbox=(80, 80, 120, 50),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.72,
            matched_item_id=item["id"],
        )
        uncertain = Classification(
            name="파란색 볼펜",
            description="가림 또는 제거인지 확실하지 않습니다.",
            category="general",
            confidence=0.35,
            provider="openai",
            action="uncertain",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=uncertain):
            main.verify_removed_item(item["id"], event)

        self.assertEqual(self.store.get_item(item["id"])["status"], "stored")
        activities = self.store.list_activities(limit=100)
        self.assertTrue(
            any(
                row["type"] == "recovery_check_inconclusive"
                and row.get("item_id") == item["id"]
                for row in activities
            )
        )

    def test_queued_removal_check_is_dropped_if_item_moved_before_worker(self) -> None:
        item = self.store.create_item(
            {
                "name": "흰색 충전기",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[55,55,100,75]",
                "confidence": 0.82,
            }
        )
        expected_signature = main.item_tracking_signature(item)
        event = ChangeEvent(
            kind="verify_removed",
            bbox=(55, 55, 100, 75),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.75,
            matched_item_id=item["id"],
        )
        main.handle_vision_change(
            ChangeEvent(
                kind="moved",
                bbox=(260, 190, 100, 75),
                crop_jpeg=None,
                before_jpeg=None,
                after_jpeg=None,
                confidence=0.9,
                matched_item_id=item["id"],
            )
        )

        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify") as classify:
            main.verify_removed_item(
                item["id"], event, expected_signature
            )

        current = self.store.get_item(item["id"])
        self.assertEqual(current["status"], "stored")
        self.assertEqual(current["bbox"], [260, 190, 100, 75])
        classify.assert_not_called()

    def test_moved_event_updates_bbox_without_creating_duplicate(self) -> None:
        item = self.store.create_item(
            {
                "name": "검은색 리모컨",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[100,100,80,55]",
                "confidence": 0.8,
            }
        )
        before_ids = {row["id"] for row in self.store.list_items(limit=500)}
        main.handle_vision_change(
            ChangeEvent(
                kind="moved",  # type: ignore[arg-type]
                bbox=(145, 105, 80, 55),
                crop_jpeg=None,
                before_jpeg=None,
                after_jpeg=None,
                confidence=0.86,
                matched_item_id=item["id"],
            )
        )

        moved = self.store.get_item(item["id"])
        after_ids = {row["id"] for row in self.store.list_items(limit=500)}
        self.assertEqual(before_ids, after_ids)
        self.assertEqual(moved["bbox"], [145, 105, 80, 55])
        self.assertEqual(moved["status"], "stored")
        self.assertEqual(moved["name"], "검은색 리모컨")
        activities = self.store.list_activities(limit=50)
        self.assertTrue(any(row["type"] == "item_moved" for row in activities))

    def test_duplicate_camera_removal_is_idempotent(self) -> None:
        item = self.store.create_item(
            {
                "name": "카메라 회수 테스트",
                "category": "general",
                "status": "stored",
                "provider": "openai",
                "bbox_json": "[120,80,70,50]",
            }
        )
        event = ChangeEvent(
            kind="removed",
            bbox=(120, 80, 70, 50),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.92,
            matched_item_id=item["id"],
        )

        main.handle_vision_change(event)
        main.handle_vision_change(event)

        recovered = self.store.get_item(item["id"])
        self.assertEqual(recovered["status"], "recovered")
        activities = [
            activity
            for activity in self.store.list_activities(100)
            if activity["item_id"] == item["id"]
            and activity["type"] == "item_recovered"
        ]
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["metadata"], {"source": "camera"})

    def test_moved_pending_item_survives_late_uncertain_ai_result(self) -> None:
        original_event = ChangeEvent(
            kind="added",
            bbox=(80, 80, 60, 45),
            crop_jpeg=None,
            before_jpeg=None,
            after_jpeg=None,
            confidence=0.7,
        )
        provisional = main.create_provisional_item(original_event)
        main.handle_vision_change(
            ChangeEvent(
                kind="moved",
                bbox=(115, 85, 60, 45),
                crop_jpeg=None,
                before_jpeg=None,
                after_jpeg=None,
                confidence=0.82,
                matched_item_id=provisional["id"],
            )
        )
        uncertain = Classification(
            name="확인 필요한 물건",
            description="첫 이미지 쌍만으로는 불확실합니다.",
            category="food",
            confidence=0.3,
            provider="openai",
            action="uncertain",
        )
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=uncertain):
            main.classify_existing_item(provisional["id"], original_event)

        preserved = self.store.get_item(provisional["id"])
        self.assertIsNotNone(preserved)
        self.assertEqual(preserved["status"], "stored")
        self.assertEqual(preserved["bbox"], [115, 85, 60, 45])
        self.assertEqual(preserved["provider"], "openai_review")
        self.assertEqual(preserved["category"], "general")
        self.assertEqual(preserved["retention_days"], 60)
        self.assertEqual(preserved["expires_at"], provisional["expires_at"])

    def _assert_late_rejection_preserves_reconfirmed_item(self, *, queued: bool) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture_dir = Path(directory)
            with patch.object(main, "config", replace(main.config, capture_dir=capture_dir)):
                event = ChangeEvent(
                    kind="added", bbox=(80, 80, 60, 45), crop_jpeg=b"original crop",
                    before_jpeg=b"original background", after_jpeg=b"original after",
                    confidence=0.7,
                )
                provisional = main.create_provisional_item(event)
                initial_signature = main.item_tracking_signature(provisional)
                reconfirmed: dict = {}
                rejection = Classification(
                    name="확인 필요한 물건", description="이전 증거를 제거로 판정했습니다.",
                    category="food", confidence=0.95, provider="openai", action="removed",
                )

                def move_away_and_back() -> None:
                    for index, bbox in enumerate(((160, 90, 60, 45), event.bbox)):
                        main.handle_vision_change(
                            ChangeEvent(
                                kind="moved", bbox=bbox,
                                crop_jpeg=f"new crop {index}".encode(),
                                before_jpeg=f"new background {index}".encode(),
                                after_jpeg=f"new after {index}".encode(),
                                confidence=0.9, matched_item_id=provisional["id"],
                            )
                        )
                    reconfirmed.update(self.store.get_item(provisional["id"]))
                    self.assertEqual(reconfirmed["bbox"], list(event.bbox))
                    self.assertNotEqual(main.item_tracking_signature(reconfirmed), initial_signature)

                def respond_after_movement(*_args, **_kwargs) -> Classification:
                    if not queued:
                        move_away_and_back()
                    return rejection

                if queued:
                    move_away_and_back()
                self.assertTrue(main.classification_slots.acquire(blocking=False))
                with patch.object(main.classifier, "classify", side_effect=respond_after_movement):
                    if queued:
                        main.classify_existing_item(provisional["id"], event, initial_signature)
                    else:
                        main.classify_existing_item(provisional["id"], event)

                preserved = self.store.get_item(provisional["id"])
                self.assertIsNotNone(preserved)
                self.assertEqual(preserved["status"], "stored")
                self.assertEqual(preserved["provider"], "openai_review")
                self.assertEqual(preserved["bbox"], list(event.bbox))
                self.assertEqual(preserved["category"], "general")
                self.assertEqual(preserved["expires_at"], provisional["expires_at"])
                for field in ("image_path", "background_path"):
                    self.assertEqual(preserved[field], reconfirmed[field])
                    self.assertTrue(Path(preserved[field]).is_file())
                self.assertEqual(Path(preserved["image_path"]).read_bytes(), b"new crop 1")
                self.assertEqual(Path(preserved["background_path"]).read_bytes(), b"new background 1")

    def test_late_rejection_after_move_back_preserves_item_and_current_captures(self) -> None:
        self._assert_late_rejection_preserves_reconfirmed_item(queued=False)

    def test_queued_addition_uses_original_signature_after_move_back(self) -> None:
        self._assert_late_rejection_preserves_reconfirmed_item(queued=True)

    def test_demo_phone_edit_recover_restore_and_extend(self) -> None:
        phone = self.create_demo_phone()
        item_id = phone["id"]
        self.assertEqual(phone["category"], "valuable")
        self.assertEqual(phone["retention_days"], 90)
        self.assertEqual(phone["provider"], "demo")
        self.assertIsNone(phone["bbox"])
        self.assertEqual(phone["source_kind"], "demo")
        self.assertIsNone(phone["image_url"])
        self.assertEqual(
            parse_datetime(phone["expires_at"]) - parse_datetime(phone["detected_at"]),
            timedelta(days=90),
        )
        self.assertNotIn(phone["id"], [item["id"] for item in main.active_items_for_vision()])

        edited_response = self.client.patch(
            f"/api/items/{item_id}",
            json={"name": "Capstone Phone", "description": "edited in API test"},
        )
        self.assertEqual(edited_response.status_code, 200, edited_response.text)
        edited = edited_response.json()
        self.assertEqual(edited["name"], "Capstone Phone")
        self.assertEqual(edited["description"], "edited in API test")

        search_response = self.client.get("/api/items", params={"q": "Capstone"})
        self.assertEqual(search_response.status_code, 200)
        self.assertIn(item_id, [item["id"] for item in search_response.json()["items"]])

        recovered_response = self.client.post(f"/api/items/{item_id}/recover")
        self.assertEqual(recovered_response.status_code, 200)
        recovered = recovered_response.json()
        self.assertEqual(recovered["status"], "recovered")
        self.assertIsNotNone(recovered["recovered_at"])

        restored_response = self.client.post(f"/api/items/{item_id}/restore")
        self.assertEqual(restored_response.status_code, 200)
        restored = restored_response.json()
        self.assertEqual(restored["status"], "stored")
        self.assertIsNone(restored["recovered_at"])

        previous_expiry = parse_datetime(restored["expires_at"])
        extended_response = self.client.post(
            f"/api/items/{item_id}/extend", json={"days": 5}
        )
        self.assertEqual(extended_response.status_code, 200, extended_response.text)
        extended = extended_response.json()
        self.assertEqual(
            parse_datetime(extended["expires_at"]),
            previous_expiry + timedelta(days=5),
        )
        self.assertEqual(extended["retention_days"], 95)

        same_category_edit = self.client.patch(
            f"/api/items/{item_id}",
            json={
                "name": "Capstone Phone v2",
                "category": "valuable",
                "expires_at": extended["expires_at"],
            },
        )
        self.assertEqual(same_category_edit.status_code, 200)
        self.assertEqual(same_category_edit.json()["retention_days"], 95)

        disposed_response = self.client.post(f"/api/items/{item_id}/dispose")
        self.assertEqual(disposed_response.status_code, 200)
        self.assertEqual(disposed_response.json()["status"], "disposed")
        restored_from_disposal = self.client.post(f"/api/items/{item_id}/restore")
        self.assertEqual(restored_from_disposal.status_code, 200)
        self.assertEqual(restored_from_disposal.json()["status"], "stored")

        detail_response = self.client.get(f"/api/items/{item_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["name"], "Capstone Phone v2")

    def test_demo_recovery_is_idempotent(self) -> None:
        phone = self.create_demo_phone()
        payload = {"item_id": phone["id"]}

        first = self.client.post("/api/demo/recover", json=payload)
        repeated = self.client.post("/api/demo/recover", json=payload)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["status"], "recovered")
        recovered_activities = [
            activity
            for activity in self.store.list_activities(100)
            if activity["item_id"] == phone["id"]
            and activity["type"] == "item_recovered"
        ]
        self.assertEqual(len(recovered_activities), 1)
        self.assertEqual(recovered_activities[0]["metadata"], {"source": "demo"})

    def test_manual_item_actions_are_idempotent_and_conflicts_refresh_contract(self) -> None:
        item = self.store.create_item(
            {"name": "수동 상태 테스트", "category": "general", "status": "stored"}
        )
        item_id = item["id"]

        first_recover = self.client.post(f"/api/items/{item_id}/recover")
        repeated_recover = self.client.post(f"/api/items/{item_id}/recover")
        self.assertEqual(first_recover.status_code, 200, first_recover.text)
        self.assertEqual(repeated_recover.status_code, 200, repeated_recover.text)
        self.assertEqual(repeated_recover.json()["status"], "recovered")

        dispose_conflict = self.client.post(f"/api/items/{item_id}/dispose")
        self.assertEqual(dispose_conflict.status_code, 409, dispose_conflict.text)
        detail = dispose_conflict.json()["detail"]
        self.assertEqual(detail["code"], "status_conflict")
        self.assertEqual(detail["action"], "dispose")
        self.assertEqual(detail["current_status"], "recovered")
        self.assertEqual(detail["item"]["id"], item_id)
        self.assertEqual(detail["item"]["status"], "recovered")
        self.assertTrue(detail["message"])

        first_restore = self.client.post(f"/api/items/{item_id}/restore")
        repeated_restore = self.client.post(f"/api/items/{item_id}/restore")
        self.assertEqual(first_restore.status_code, 200, first_restore.text)
        self.assertEqual(repeated_restore.status_code, 200, repeated_restore.text)
        self.assertEqual(repeated_restore.json()["status"], "stored")

        activities = [
            activity
            for activity in self.store.list_activities(100)
            if activity["item_id"] == item_id
        ]
        self.assertEqual(
            sorted(activity["type"] for activity in activities),
            ["item_recovered", "item_restored"],
        )

        due_item = self.store.create_item(
            {"name": "기한 만료 테스트", "category": "food", "status": "due"}
        )
        first_dispose = self.client.post(f"/api/items/{due_item['id']}/dispose")
        repeated_dispose = self.client.post(f"/api/items/{due_item['id']}/dispose")
        self.assertEqual(first_dispose.status_code, 200, first_dispose.text)
        self.assertEqual(repeated_dispose.status_code, 200, repeated_dispose.text)
        self.assertEqual(repeated_dispose.json()["status"], "disposed")
        recover_conflict = self.client.post(f"/api/items/{due_item['id']}/recover")
        self.assertEqual(recover_conflict.status_code, 409, recover_conflict.text)
        self.assertEqual(recover_conflict.json()["detail"]["current_status"], "disposed")

        for action in ("recover", "dispose", "restore"):
            missing = self.client.post(f"/api/items/999999/{action}")
            self.assertEqual(missing.status_code, 404, missing.text)

    def test_lifecycle_activity_failure_rolls_back_api_state(self) -> None:
        item = self.store.create_item(
            {"name": "API 원자성 테스트", "category": "general", "status": "stored"}
        )
        with closing(sqlite3.connect(self.store.db_path)) as connection:
            connection.executescript(
                """
                CREATE TRIGGER fail_api_lifecycle_activity
                BEFORE INSERT ON activities
                WHEN NEW.type = 'item_recovered'
                BEGIN
                    SELECT RAISE(ABORT, 'forced API lifecycle activity failure');
                END;
                """
            )
            connection.commit()

        try:
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.post(f"/api/items/{item['id']}/recover")
        finally:
            with closing(sqlite3.connect(self.store.db_path)) as connection:
                connection.execute("DROP TRIGGER fail_api_lifecycle_activity")
                connection.commit()

        unchanged = self.store.get_item(item["id"])
        self.assertEqual(unchanged["status"], "stored")
        self.assertIsNone(unchanged["recovered_at"])
        self.assertFalse(
            any(
                activity["item_id"] == item["id"]
                for activity in self.store.list_activities(100)
            )
        )

    def test_settings_update_and_camera_rebaseline(self) -> None:
        self.vision_set_privacy.reset_mock()
        self.vision_rebaseline.reset_mock()

        response = self.client.put(
            "/api/settings",
            json={
                "provider": "offline",
                "camera_backend": "picamera2",
                "camera_fps": 10,
                "monitor_fps": 7,
                "accumulated_check_fps": 2,
                "preview_stream_fps": 5,
                "preview_jpeg_quality": 78,
                "jpeg_quality": 88,
                "stabilization_analysis_width": 360,
                "motion_threshold": 33,
                "privacy_mode": True,
                "site_name": "Capstone Test Site",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        settings = response.json()["settings"]
        self.assertEqual(settings["provider"], "offline")
        self.assertEqual(settings["camera_backend"], "picamera2")
        self.assertEqual(settings["camera_fps"], 10)
        self.assertEqual(settings["monitor_fps"], 7)
        self.assertEqual(settings["accumulated_check_fps"], 2)
        self.assertEqual(settings["preview_stream_fps"], 5)
        self.assertEqual(settings["preview_jpeg_quality"], 78)
        self.assertEqual(settings["jpeg_quality"], 88)
        self.assertEqual(settings["stabilization_analysis_width"], 360)
        self.assertEqual(settings["motion_threshold"], 33)
        self.assertIs(settings["privacy_mode"], True)
        self.assertEqual(settings["site_name"], "Capstone Test Site")
        self.vision_set_privacy.assert_called_once_with(True)
        self.vision_rebaseline.assert_called_once_with()

        fetched = self.client.get("/api/settings")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["settings"]["motion_threshold"], 33)

        self.vision_rebaseline.reset_mock()
        baseline_response = self.client.post("/api/camera/rebaseline")
        self.assertEqual(baseline_response.status_code, 200)
        self.assertIs(baseline_response.json()["ok"], True)
        self.assertEqual(baseline_response.json()["camera"]["state"], "test")
        self.vision_rebaseline.assert_called_once_with(reconcile_items=True)

    def test_invalid_inputs_are_rejected_without_external_calls(self) -> None:
        unknown_demo = self.client.post(
            "/api/demo/items", json={"preset": "does-not-exist"}
        )
        self.assertEqual(unknown_demo.status_code, 400)

        invalid_status = self.client.get("/api/items", params={"status": "missing"})
        self.assertEqual(invalid_status.status_code, 400)

        missing_item = self.client.get("/api/items/999999")
        self.assertEqual(missing_item.status_code, 404)

        phone = self.create_demo_phone()
        item_id = phone["id"]
        invalid_category = self.client.patch(
            f"/api/items/{item_id}", json={"category": "electronics"}
        )
        self.assertEqual(invalid_category.status_code, 400)
        invalid_expiry = self.client.patch(
            f"/api/items/{item_id}", json={"expires_at": "not-a-date"}
        )
        self.assertEqual(invalid_expiry.status_code, 400)
        empty_name = self.client.patch(f"/api/items/{item_id}", json={"name": ""})
        self.assertEqual(empty_name.status_code, 422)
        invalid_extension = self.client.post(
            f"/api/items/{item_id}/extend", json={"days": 0}
        )
        self.assertEqual(invalid_extension.status_code, 422)

        no_known_settings = self.client.put(
            "/api/settings", json={"not_a_setting": "value"}
        )
        self.assertEqual(no_known_settings.status_code, 400)
        invalid_provider = self.client.put(
            "/api/settings", json={"provider": "untrusted-remote"}
        )
        self.assertEqual(invalid_provider.status_code, 400)
        invalid_threshold = self.client.put(
            "/api/settings", json={"motion_threshold": 101}
        )
        self.assertEqual(invalid_threshold.status_code, 400)
        invalid_camera_backend = self.client.put(
            "/api/settings", json={"camera_backend": "unknown-camera"}
        )
        self.assertEqual(invalid_camera_backend.status_code, 400)
        invalid_preview_fps = self.client.put(
            "/api/settings", json={"preview_stream_fps": 30}
        )
        self.assertEqual(invalid_preview_fps.status_code, 400)
        for invalid in ({"preview_max_width": 100}, {"camera_mains_frequency_hz": 59}):
            with self.subTest(invalid=invalid):
                previous = self.store.get_settings()
                response = self.client.put("/api/settings", json=invalid)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.store.get_settings(), previous)

        # Deterministic demo presets never read the camera or call external services.
        self.vision_get_jpeg.assert_not_called()

    def test_camera_preview_and_flicker_settings_persist(self) -> None:
        previous = main.current_settings()
        try:
            response = self.client.put("/api/settings", json={
                "camera_mains_frequency_hz": 60, "preview_max_width": 800,
            })
            self.assertEqual(response.status_code, 200, response.text)
            settings = self.client.get("/api/settings").json()["settings"]
            self.assertEqual(settings["camera_mains_frequency_hz"], 60)
            self.assertEqual(settings["preview_max_width"], 800)
            self.assertEqual(settings["camera_width"], previous["camera_width"])
            self.assertEqual(settings["jpeg_quality"], previous["jpeg_quality"])
        finally:
            self.store.update_settings({key: previous[key] for key in (
                "camera_mains_frequency_hz", "preview_max_width",
            )})


if __name__ == "__main__":
    unittest.main()
