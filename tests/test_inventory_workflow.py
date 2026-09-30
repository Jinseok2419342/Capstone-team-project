from __future__ import annotations

import tempfile
import threading
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.ai import Classification
from app.item_policy import classification_review_reason
from app.store import Store
from app.vision import ChangeEvent


class InventoryWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.captures = self.root / "captures"
        self.captures.mkdir()
        self.store = Store(self.root / "isolated.sqlite3")
        self.store.initialize()
        self.stack.enter_context(patch.object(main, "store", self.store))
        self.stack.enter_context(patch.object(main, "config", replace(
            main.config, capture_dir=self.captures, db_path=self.store.db_path,
        )))
        self.stack.enter_context(patch.object(main, "classification_slots", threading.BoundedSemaphore(1)))
        self.stack.enter_context(patch.object(main.vision, "get_status", return_value={}))
        self.client = TestClient(main.app)
        # Do not run lifespan: these tests must not start cameras, SMTP, or AI.
        self.stack.callback(self.client.close)
        self.event = ChangeEvent(
            kind="added", bbox=(10, 20, 60, 80), confidence=0.9,
            crop_jpeg=b"crop", before_jpeg=b"before", after_jpeg=b"after",
        )

    def classify(self, item: dict, result: Classification) -> None:
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=result):
            main.classify_existing_item(item["id"], self.event)

    def test_observation_retry_has_one_id_and_one_evidence_pair(self) -> None:
        first = main.create_provisional_item(self.event)
        second = main.create_provisional_item(self.event)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list_items()), 1)
        self.assertEqual(len(list(self.captures.iterdir())), 2)

    def test_failed_local_commit_is_nacked_without_orphaned_captures(self) -> None:
        with patch.object(self.store, "create_item", side_effect=OSError("disk unavailable")):
            with self.assertLogs("lost-item-admin", level="ERROR"):
                self.assertFalse(main.handle_vision_change(self.event))
        self.assertEqual(list(self.captures.iterdir()), [])
        self.assertEqual(self.store.list_items(), [])
        with patch.object(main, "submit_classification", return_value=False):
            self.assertTrue(main.handle_vision_change(self.event))
        self.assertEqual(len(self.store.list_items()), 1)

    def test_dismiss_preserves_evidence_and_restore_requires_review(self) -> None:
        item = main.create_provisional_item(self.event)
        item_id = item["id"]
        dismissed = self.client.post(f"/api/items/{item_id}/dismiss")
        self.assertEqual(dismissed.status_code, 200)
        self.assertEqual(dismissed.json()["review_status"], "dismissed")
        self.assertEqual(self.client.get("/api/items").json()["total"], 0)
        self.assertEqual(self.client.get("/api/items?status=dismissed").json()["total"], 1)
        self.assertEqual(main.active_items_for_vision(), [])
        self.assertTrue(Path(item["image_path"]).is_file())
        self.assertTrue(Path(item["background_path"]).is_file())
        for action in ("recover", "dispose", "extend"):
            response = self.client.post(f"/api/items/{item_id}/{action}", json={"days": 7})
            self.assertEqual(response.status_code, 409)
        result = Classification("AI overwrite", "", "food", 0.99, "test", action="added")
        self.classify(item, result)
        self.assertEqual(self.store.get_item(item_id)["review_status"], "dismissed")
        restored = self.client.post(f"/api/items/{item_id}/restore").json()
        self.assertEqual(restored["id"], item_id)
        self.assertEqual(restored["review_status"], "needs_review")
        self.assertGreater(restored["tracking_revision"], item["tracking_revision"])
        self.assertEqual(len(main.active_items_for_vision()), 1)

    def test_expiry_edit_does_not_silently_confirm_a_review(self) -> None:
        item = self.store.create_item({"name": "Unknown", "provider": "offline_review"})
        expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        response = self.client.patch(f"/api/items/{item['id']}", json={"expires_at": expiry})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["review_status"], "needs_review")
        confirmed = self.client.patch(f"/api/items/{item['id']}", json={"confirm_review": True})
        self.assertEqual(confirmed.json()["review_status"], "confirmed")
        self.assertEqual(confirmed.json()["provider"], "manual")

    def test_stale_edit_returns_latest_without_overwriting_it(self) -> None:
        item = self.store.create_item({"name": "Before"})
        current = self.store.update_item(item["id"], {"name": "AI result"})
        response = self.client.patch(f"/api/items/{item['id']}", json={
            "name": "Old form", "expected_updated_at": item["updated_at"],
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "edit_conflict")
        self.assertEqual(response.json()["detail"]["item"]["name"], "AI result")
        self.assertEqual(self.store.get_item(item["id"])["updated_at"], current["updated_at"])

    def test_stale_camera_callback_does_not_undo_manual_restore(self) -> None:
        for kind in ("removed", "moved", "verify_removed"):
            with self.subTest(kind=kind):
                item = self.store.create_item({"name": kind, "bbox": [10, 20, 60, 80]})
                old_event = replace(self.event, kind=kind, matched_item_id=item["id"],
                                    expected_revision=item["tracking_revision"])
                self.store.apply_item_action(item["id"], "recover")
                restored = self.store.apply_item_action(item["id"], "restore")["item"]
                with patch.object(main, "submit_classification") as submit:
                    self.assertTrue(main.handle_vision_change(old_event))
                    submit.assert_not_called()
                self.assertEqual(self.store.get_item(item["id"]), restored)

    def test_uncertain_removal_creates_an_actionable_review(self) -> None:
        item = self.store.create_item({"name": "Umbrella", "provider": "test", "bbox": [10, 20, 60, 80]})
        event = replace(self.event, kind="verify_removed", matched_item_id=item["id"], expected_revision=0)
        result = Classification("Umbrella", "", "general", 0.2, "test", action="uncertain")
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", return_value=result):
            main.verify_removed_item(item["id"], event)
        current = self.store.get_item(item["id"])
        self.assertEqual(current["status"], "stored")
        self.assertEqual(current["review_reason"], "removal_uncertain")
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["stats"]["review_needed"], 1)
        self.assertEqual(dashboard["review_items"][0]["id"], item["id"])

    def test_failed_removal_review_commit_is_nacked_for_retry(self) -> None:
        item = self.store.create_item({"name": "Umbrella", "bbox": [10, 20, 60, 80]})
        event = replace(self.event, kind="verify_removed", matched_item_id=item["id"], expected_revision=0)
        with patch.object(main, "submit_classification", return_value=False):
            with patch.object(self.store, "update_item", side_effect=OSError("disk unavailable")):
                self.assertFalse(main.handle_vision_change(event))
            self.assertTrue(main.handle_vision_change(event))
        self.assertEqual(self.store.get_item(item["id"])["review_reason"], "removal_queue_full")

    def test_metadata_changes_during_removal_check_do_not_erase_observation(self) -> None:
        item = self.store.create_item({"name": "Umbrella", "bbox": [10, 20, 60, 80]})
        event = replace(self.event, kind="verify_removed", matched_item_id=item["id"], expected_revision=0)
        def describe_then_remove(*args, **kwargs):
            self.store.update_item(item["id"], {"name": "Blue umbrella", "category": "general"})
            return Classification("Umbrella", "", "general", 0.9, "test", action="removed")
        self.assertTrue(main.classification_slots.acquire(blocking=False))
        with patch.object(main.classifier, "classify", side_effect=describe_then_remove):
            main.verify_removed_item(item["id"], event, main.item_tracking_signature(item))
        current = self.store.get_item(item["id"])
        self.assertEqual(current["name"], "Blue umbrella")
        self.assertEqual(current["status"], "recovered")

    def test_invalid_model_confidence_never_confirms_inventory(self) -> None:
        for confidence in (float("nan"), float("inf"), -1, 2, None, True):
            with self.subTest(confidence=confidence):
                result = Classification("Unknown", "", "general", confidence, "test")
                self.assertEqual(classification_review_reason(result, 0.5), "invalid_confidence")

    def test_http_pagination_counts_all_matches_and_validates_parameters(self) -> None:
        for name in ("C", "A", "B", "D"):
            self.store.create_item({"name": name, "category": "food"})
        self.store.create_item({"name": "Other", "category": "general"})
        first = self.client.get("/api/items?category=food&sort=name&limit=2").json()
        second = self.client.get("/api/items?category=food&sort=name&limit=2&offset=2").json()
        self.assertEqual(first["total"], 4)
        self.assertEqual([i["name"] for i in first["items"]], ["A", "B"])
        self.assertEqual([i["name"] for i in second["items"]], ["C", "D"])
        for query in ("limit=0", "limit=101", "offset=-1", "sort=sql", "review=unknown", "category=unknown"):
            self.assertIn(self.client.get(f"/api/items?{query}").status_code, {400, 422})

    def test_demo_recovery_never_operates_on_real_inventory(self) -> None:
        actual = self.store.create_item({"name": "Real umbrella", "source_kind": "camera", "bbox": [1, 2, 30, 40]})
        self.assertEqual(self.client.post("/api/demo/recover", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/demo/recover", json={"item_id": actual["id"]}).status_code, 409)
        demo = self.client.post("/api/demo/items", json={"preset": "phone"}).json()
        changed = self.client.patch(f"/api/items/{demo['id']}", json={"name": "Edited demo"}).json()
        self.assertEqual(changed["source_kind"], "demo")
        self.assertEqual([item["id"] for item in main.active_items_for_vision()], [actual["id"]])
        self.assertIsNone(changed["bbox"])
        recovered = self.client.post("/api/demo/recover", json={})
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["id"], demo["id"])
        self.assertEqual(self.store.get_item(actual["id"])["status"], "stored")


if __name__ == "__main__":
    unittest.main()
