from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.store import Store


class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.store = Store(root / "health.sqlite3")
        self.store.initialize()
        self.store.update_settings({"provider": "gemini"})
        self.stack.enter_context(patch.object(main, "store", self.store))
        self.stack.enter_context(patch.object(main.vision, "get_status", return_value={
            "connected": False, "state": "offline", "message": "camera unavailable",
        }))
        # No lifespan: the probe must not start a camera, VLM job or scheduler.
        self.client = TestClient(main.app)
        self.stack.callback(self.client.close)

    def test_database_failure_is_503_and_recovers_on_next_probe(self) -> None:
        with patch.object(self.store, "get_settings", side_effect=sqlite3.OperationalError("sensitive path")):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertIs(response.json()["ok"], False)
        self.assertEqual(response.json()["database"], "unavailable")
        self.assertNotIn("sensitive path", response.text)
        recovered = self.client.get("/api/health")
        self.assertEqual(recovered.status_code, 200)
        self.assertIs(recovered.json()["ok"], True)
        self.assertEqual(recovered.json()["provider"]["requested"], "gemini")

    def test_live_api_without_camera_reports_both_states_truthfully(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "connected")
        self.assertIs(response.json()["camera"]["connected"], False)


if __name__ == "__main__":
    unittest.main()
