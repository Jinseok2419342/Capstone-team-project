from __future__ import annotations

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.ai import ObjectClassifier
from app.notifier import ExpirationScheduler
from app.store import Store


class _Config:
    openai_api_key = ""
    gemini_api_key = ""


class _SecretConfig:
    openai_api_key = "openai-secret-value"
    gemini_api_key = "gemini-secret-value"


class _SuccessfulNotifier:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def send_due(self, item: dict) -> tuple[bool, str | None]:
        self.items.append(item)
        return True, None


class _FlakyNotifier:
    def __init__(self) -> None:
        self.calls = 0

    def send_due(self, item: dict) -> tuple[bool, str | None]:
        self.calls += 1
        if self.calls == 1:
            return False, "temporary SMTP failure"
        return True, None


class _SlowNotifier(_SuccessfulNotifier):
    def send_due(self, item: dict) -> tuple[bool, str | None]:
        self.items.append(item)
        time.sleep(0.08)
        return True, None


class ServiceTests(unittest.TestCase):
    def test_ai_hybrid_evidence_is_labeled_and_cost_bounded(self) -> None:
        classifier = ObjectClassifier(
            _Config(), lambda: {"provider": "auto"}
        )  # type: ignore[arg-type]

        # Only the latest before/after pair from each group is retained.
        crops = classifier._encode_pair([b"old", b"crop-before", b"crop-after"])
        scenes = classifier._encode_pair([b"scene-before", b"scene-after"])
        content = classifier._openai_content(crops, scenes)

        image_parts = [part for part in content if part["type"] == "input_image"]
        label_parts = [
            part["text"]
            for part in content[1:]
            if part["type"] == "input_text"
        ]
        self.assertEqual(len(image_parts), 4)
        self.assertEqual(
            [part["detail"] for part in image_parts],
            ["low", "low", "high", "high"],
        )
        self.assertEqual(
            label_parts,
            [
                "[전체 장면 · 변화 전 (BEFORE)]",
                "[전체 장면 · 변화 후 (AFTER)]",
                "[후보 영역 crop · 변화 전 (BEFORE)]",
                "[후보 영역 crop · 변화 후 (AFTER)]",
            ],
        )

        # Gemini receives the same chronological text/image interleaving.
        gemini_parts = classifier._gemini_parts(crops, scenes)
        self.assertEqual(len(gemini_parts), 9)
        self.assertEqual(gemini_parts[1]["text"], label_parts[0])
        self.assertEqual(
            gemini_parts[2]["inline_data"]["data"],
            image_parts[0]["image_url"].split(",", 1)[1],
        )

    def test_ai_evidence_preserves_missing_before_position(self) -> None:
        classifier = ObjectClassifier(
            _Config(), lambda: {"provider": "auto"}
        )  # type: ignore[arg-type]
        encoded = classifier._encode_pair([None, b"after"])
        content = classifier._openai_content(encoded)
        labels = [
            part["text"]
            for part in content
            if part["type"] == "input_text" and part["text"].startswith("[")
        ]
        self.assertEqual(labels, ["[후보 영역 crop · 변화 후 (AFTER)]"])

    def test_ai_json_normalization_and_retention(self) -> None:
        classifier = ObjectClassifier(_Config(), lambda: {"provider": "auto"})  # type: ignore[arg-type]
        result = classifier._normalize(
            """```json
            {"action":"added","name":"검은색 스마트폰","description":"검은 케이스","category":"valuable",
             "estimated_value_krw":850000,"confidence":1.4}
            ```""",
            "test",
        )
        self.assertEqual(result.name, "검은색 스마트폰")
        self.assertEqual(result.category, "valuable")
        self.assertEqual(result.retention_days, 90)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.action, "added")

        invalid_category = classifier._normalize(
            '{"name":"물건","description":"설명","category":"other","confidence":"bad"}',
            "test",
        )
        self.assertEqual(invalid_category.category, "general")
        self.assertEqual(invalid_category.retention_days, 60)
        self.assertEqual(invalid_category.action, "uncertain")
        self.assertLessEqual(invalid_category.confidence, 0.45)

        price_promoted = classifier._normalize(
            '{"action":"added","name":"고가 장비","description":"장비",'
            '"category":"general","estimated_value_krw":200000,"confidence":0.8}',
            "test",
        )
        self.assertEqual(price_promoted.category, "valuable")

    def test_api_error_text_redacts_credentials(self) -> None:
        import httpx

        classifier = ObjectClassifier(
            _SecretConfig(), lambda: {"valuable_value_threshold_krw": 100000}
        )  # type: ignore[arg-type]
        request = httpx.Request(
            "POST", "https://example.invalid/generate?key=gemini-secret-value"
        )
        response = httpx.Response(
            400,
            json={"error": {"message": "bad key gemini-secret-value"}},
            request=request,
        )
        error = classifier._safe_error(
            httpx.HTTPStatusError("failed", request=request, response=response)
        )
        self.assertNotIn("gemini-secret-value", error)
        self.assertIn("[REDACTED]", error)

    def test_ai_offline_fallback_never_drops_detection(self) -> None:
        classifier = ObjectClassifier(_Config(), lambda: {"provider": "auto"})  # type: ignore[arg-type]
        result = classifier.classify([b"not-an-image"])
        self.assertEqual(result.provider, "offline")
        self.assertEqual(result.category, "general")
        self.assertIn("임시 등록", result.description)

    def test_expiration_scheduler_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "scheduler.db")
            store.initialize()
            now = datetime.now(timezone.utc)
            item = store.create_item(
                {
                    "name": "샌드위치",
                    "category": "food",
                    "detected_at": now - timedelta(days=2),
                    "expires_at": now - timedelta(minutes=1),
                }
            )
            notifier = _SuccessfulNotifier()
            scheduler = ExpirationScheduler(store, notifier, interval_seconds=999)

            changed = scheduler.run_once()
            self.assertEqual([entry["id"] for entry in changed], [item["id"]])
            self.assertEqual(store.get_item(item["id"])["status"], "due")
            self.assertEqual(store.list_notifications()[0]["status"], "sent")
            self.assertEqual(len(notifier.items), 1)

    def test_scheduler_retries_failed_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "retry.db")
            store.initialize()
            now = datetime.now(timezone.utc)
            store.create_item(
                {
                    "name": "도시락",
                    "category": "food",
                    "detected_at": now - timedelta(days=2),
                    "expires_at": now - timedelta(minutes=1),
                }
            )
            notifier = _FlakyNotifier()
            scheduler = ExpirationScheduler(
                store, notifier, interval_seconds=999, retry_after_seconds=0.01
            )
            scheduler.run_once()
            self.assertEqual(notifier.calls, 1)
            self.assertEqual(store.list_notifications()[0]["status"], "failed")
            time.sleep(0.02)
            scheduler.run_once()
            self.assertEqual(notifier.calls, 2)
            self.assertEqual(store.list_notifications()[0]["status"], "sent")

    def test_scheduler_lock_prevents_concurrent_duplicate_email(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "concurrent-scheduler.db")
            store.initialize()
            now = datetime.now(timezone.utc)
            store.create_item(
                {
                    "name": "음료",
                    "category": "food",
                    "detected_at": now - timedelta(days=2),
                    "expires_at": now - timedelta(minutes=1),
                }
            )
            notifier = _SlowNotifier()
            scheduler = ExpirationScheduler(store, notifier, interval_seconds=999)
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: scheduler.run_once(), range(2)))
            self.assertEqual(len(notifier.items), 1)
            self.assertEqual(len(store.list_notifications()), 1)

            self.assertEqual(scheduler.run_once(), [])
            self.assertEqual(len(store.list_notifications()), 1)
            self.assertEqual(len(notifier.items), 1)


if __name__ == "__main__":
    unittest.main()
