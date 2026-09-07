from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.store import Store


class OperationalResetApiTests(unittest.TestCase):
    """The reset route is exercised only against disposable files."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.project_dir = root / "project"
        self.data_dir = self.project_dir / "data"
        self.capture_dir = self.data_dir / "captures"
        self.db_path = self.data_dir / "test.sqlite3"
        self.project_dir.mkdir(parents=True)
        self.capture_dir.mkdir(parents=True)
        self.env_file = self.project_dir / ".env"
        self.env_file.write_text("OPENAI_API_KEY=keep-me\n", encoding="utf-8")

        self.store = Store(self.db_path)
        self.original_store = main.store
        self.original_scheduler_store = main.scheduler.store
        self.original_config = main.config
        main.store = self.store
        main.scheduler.store = self.store
        main.config = replace(
            self.original_config,
            root_dir=self.project_dir,
            data_dir=self.data_dir,
            db_path=self.db_path,
            capture_dir=self.capture_dir,
        )

        self.patchers = [
            patch.object(main.vision, "start"),
            patch.object(main.vision, "stop"),
            patch.object(main.vision, "rebaseline"),
            patch.object(main.scheduler, "start"),
            patch.object(main.scheduler, "stop"),
        ]
        (
            self.vision_start,
            self.vision_stop,
            self.vision_rebaseline,
            self.scheduler_start,
            self.scheduler_stop,
        ) = [patcher.start() for patcher in self.patchers]
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        try:
            self.client_context.__exit__(None, None, None)
        finally:
            for patcher in reversed(self.patchers):
                patcher.stop()
            main.store = self.original_store
            main.scheduler.store = self.original_scheduler_store
            main.config = self.original_config
            self.temp_dir.cleanup()

    def test_reset_requires_exact_confirmation_and_keeps_recoverable_backup(self) -> None:
        self.store.update_settings(
            {"motion_threshold": 41, "reset_test_setting": "preserve"}
        )
        image_path = self.capture_dir / "item-test.jpg"
        nested_path = self.capture_dir / "nested" / "background-test.jpg"
        nested_path.parent.mkdir()
        image_path.write_bytes(b"item-image")
        nested_path.write_bytes(b"background-image")
        item = self.store.create_item(
            {
                "name": "Reset API item",
                "category": "general",
                "image_path": str(image_path),
                "background_path": str(nested_path),
            }
        )
        self.store.create_activity(
            "reset_test", "activity before reset", item_id=item["id"]
        )
        self.store.create_notification(
            "reset_test",
            item_id=item["id"],
            scheduled_for=item["expires_at"],
        )

        item_response = self.client.get(f"/api/items/{item['id']}")
        self.assertEqual(item_response.status_code, 200)
        old_image_url = item_response.json()["image_url"]
        self.assertEqual(
            old_image_url,
            f"/api/items/{item['id']}/image?v={item['updated_at']}",
        )
        old_image_response = self.client.get(old_image_url)
        self.assertEqual(old_image_response.content, b"item-image")
        self.assertIn("no-store", old_image_response.headers["cache-control"])
        self.assertEqual(old_image_response.headers["pragma"], "no-cache")

        before_counts = {
            "items": len(self.store.list_items()),
            "activities": len(self.store.list_activities()),
            "notifications": len(self.store.list_notifications()),
            "settings_preserved": len(self.store.get_settings()),
        }
        rejected = self.client.post(
            "/api/maintenance/reset", json={"confirmation": "초기화 "}
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIsNotNone(self.store.get_item(item["id"]))
        self.assertFalse((self.data_dir / "reset-backups").exists())
        self.vision_stop.assert_not_called()

        response = self.client.post(
            "/api/maintenance/reset", json={"confirmation": "초기화"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIs(payload["ok"], True)
        self.assertEqual(payload["removed"], before_counts)
        self.assertEqual(payload["capture_files"], 2)

        self.assertEqual(self.store.list_items(), [])
        self.assertEqual(self.store.list_activities(), [])
        self.assertEqual(self.store.list_notifications(), [])
        self.assertEqual(
            self.store.get_settings()["reset_test_setting"], "preserve"
        )
        self.assertEqual(list(self.capture_dir.iterdir()), [])
        self.assertEqual(
            self.env_file.read_text(encoding="utf-8"),
            "OPENAI_API_KEY=keep-me\n",
        )

        backup_dir = self.data_dir / payload["backup_directory"]
        backup_store = Store(backup_dir / "database.sqlite3")
        self.assertEqual(
            backup_store.get_item(item["id"])["name"], "Reset API item"
        )
        self.assertEqual(
            (backup_dir / "captures" / image_path.name).read_bytes(), b"item-image"
        )
        self.assertEqual(
            (backup_dir / "captures" / "nested" / nested_path.name).read_bytes(),
            b"background-image",
        )
        manifest = json.loads(
            (backup_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["state"], "complete")
        self.assertEqual(manifest["removed"], before_counts)

        # A new item cannot inherit the reset item's id or image URL. Even a
        # browser retaining the old URL receives 404 instead of a new image.
        fresh_path = self.capture_dir / "fresh-item.jpg"
        fresh_path.write_bytes(b"fresh-image")
        fresh_item = self.store.create_item(
            {
                "name": "First item after reset",
                "category": "food",
                "image_path": str(fresh_path),
            }
        )
        self.assertGreater(fresh_item["id"], item["id"])
        fresh_response = self.client.get(f"/api/items/{fresh_item['id']}")
        fresh_image_url = fresh_response.json()["image_url"]
        self.assertNotEqual(fresh_image_url, old_image_url)
        self.assertEqual(self.client.get(old_image_url).status_code, 404)
        fresh_image_response = self.client.get(fresh_image_url)
        self.assertEqual(fresh_image_response.content, b"fresh-image")
        self.assertIn("no-store", fresh_image_response.headers["cache-control"])

        self.vision_stop.assert_called_once_with()
        self.scheduler_stop.assert_called_once_with()
        self.vision_rebaseline.assert_called_once_with()
        # One start comes from app lifespan, the second resumes after reset.
        self.assertEqual(self.vision_start.call_count, 2)
        self.assertEqual(self.scheduler_start.call_count, 2)


if __name__ == "__main__":
    unittest.main()
