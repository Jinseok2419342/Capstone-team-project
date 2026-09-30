from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.ai import ObjectClassifier


RESULT = {
    "action": "added",
    "name": "검은색 지갑",
    "description": "검은색 가죽 지갑입니다.",
    "category": "valuable",
    "estimated_value_krw": None,
    "confidence": 0.94,
}


def openai_body(**overrides) -> dict:
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(RESULT)},
        ]}],
        **overrides,
    }


def gemini_body(reason="STOP", parts=None) -> dict:
    return {"candidates": [{
        "finishReason": reason,
        "content": {"parts": parts or [{"text": json.dumps(RESULT)}]},
    }]}


class AiTransportTests(unittest.TestCase):
    """Exercise request serialization and HTTP response handling without a network."""

    def setUp(self) -> None:
        self.settings = {"provider": "auto"}
        self.classifier = ObjectClassifier(
            SimpleNamespace(openai_api_key="test-openai-key", gemini_api_key="test-gemini-key"),
            lambda: self.settings,
        )
        self.responses: list[tuple[int, dict] | Exception] = []
        self.requests: list[httpx.Request] = []
        self.timeouts = []
        real_client = httpx.Client

        def handle(request):
            self.requests.append(request)
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            status, body = response
            return httpx.Response(status, json=body, request=request)

        def client(**kwargs):
            self.timeouts.append(kwargs["timeout"])
            return real_client(transport=httpx.MockTransport(handle), **kwargs)

        patcher = patch("app.ai.httpx.Client", side_effect=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def classify(self):
        return self.classifier.classify(
            [b"crop-before", b"crop-after"],
            scene_images=[b"scene-before", b"scene-after"],
        )

    def test_openai_default_has_strict_schema_and_bounded_reasoning(self) -> None:
        self.responses.append((200, openai_body()))
        result = self.classify()
        self.assertEqual((result.provider, result.name, result.action), ("openai", RESULT["name"], "added"))
        payload = json.loads(self.requests[0].content)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertEqual(payload["max_output_tokens"], 2048)
        form = payload["text"]["format"]
        self.assertTrue(form["strict"])
        self.assertFalse(form["schema"]["additionalProperties"])
        self.assertEqual(set(form["schema"]["required"]), set(RESULT))
        content = payload["input"][0]["content"]
        self.assertEqual(len([part for part in content if part["type"] == "input_image"]), 4)
        self.assertEqual(self.requests[0].headers["authorization"], "Bearer test-openai-key")
        self.assertEqual(self.timeouts[0].connect, 8.0)
        self.assertEqual(self.timeouts[0].read, 30.0)

    def test_custom_model_is_preserved_without_forcing_reasoning_parameter(self) -> None:
        self.settings["openai_model"] = "gpt-4.1-mini"
        self.responses.append((200, openai_body()))
        self.assertEqual(self.classify().provider, "openai")
        payload = json.loads(self.requests[0].content)
        self.assertEqual(payload["model"], "gpt-4.1-mini")
        self.assertNotIn("reasoning", payload)

    def test_truncated_openai_even_with_complete_json_uses_next_provider(self) -> None:
        self.responses.extend([
            (200, openai_body(status="incomplete", incomplete_details={"reason": "max_output_tokens"})),
            (200, gemini_body()),
        ])
        result = self.classify()
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[1].url.host, "generativelanguage.googleapis.com")

    def test_forced_provider_does_not_silently_fallback(self) -> None:
        self.settings["provider"] = "openai"
        self.responses.append((200, openai_body(status="incomplete", incomplete_details={"reason": "max_output_tokens"})))
        result = self.classify()
        self.assertEqual(result.provider, "offline")
        self.assertIn("max_output_tokens", result.raw)
        self.assertEqual(len(self.requests), 1)

    def test_refusal_overrides_any_convenience_output_text(self) -> None:
        self.settings["provider"] = "openai"
        self.responses.append((200, openai_body(
            output_text=json.dumps(RESULT),
            output=[{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}],
        )))
        self.assertEqual(self.classify().provider, "offline")

    def test_gemini_schema_and_thought_separation(self) -> None:
        self.settings["provider"] = "gemini"
        self.responses.append((200, gemini_body(parts=[
            {"thought": True, "text": '{"action":"removed","confidence":1}'},
            {"text": json.dumps(RESULT)},
        ])))
        result = self.classify()
        self.assertEqual((result.provider, result.action), ("gemini", "added"))
        payload = json.loads(self.requests[0].content)
        generation = payload["generationConfig"]
        self.assertEqual(generation["responseMimeType"], "application/json")
        self.assertEqual(set(generation["responseJsonSchema"]["required"]), set(RESULT))
        self.assertEqual(generation["maxOutputTokens"], 2048)
        self.assertNotIn("temperature", generation)
        self.assertNotIn("thinkingConfig", generation)
        self.assertEqual(len([part for part in payload["contents"][0]["parts"] if "inline_data" in part]), 4)
        self.assertEqual(self.requests[0].headers["x-goog-api-key"], "test-gemini-key")
        self.assertNotIn("key=", str(self.requests[0].url))

    def test_incomplete_or_blocked_gemini_never_authorizes_action(self) -> None:
        self.settings["provider"] = "gemini"
        for reason in ("MAX_TOKENS", "SAFETY", "RECITATION", None):
            with self.subTest(reason=reason):
                self.responses.append((200, gemini_body(reason)))
                result = self.classify()
                self.assertEqual(result.provider, "offline")
                self.assertLess(result.confidence, 0.5)

    def test_missing_candidates_or_malformed_json_falls_back_to_review(self) -> None:
        self.settings["provider"] = "gemini"
        for body in ({"promptFeedback": {"blockReason": "SAFETY"}}, gemini_body(parts=[{"text": "{broken}"}])):
            with self.subTest(body=body):
                self.responses.append((200, body))
                self.assertEqual(self.classify().provider, "offline")

    def test_api_failure_and_timeout_preserve_offline_fallback_and_redact_keys(self) -> None:
        self.responses.extend([
            (401, {"error": {"message": "invalid test-openai-key"}}),
            httpx.ReadTimeout("provider timeout"),
        ])
        with self.assertLogs("app.ai", level="WARNING") as captured:
            result = self.classify()
        self.assertEqual(result.provider, "offline")
        self.assertIn("HTTP 401", result.raw)
        self.assertIn("초과", result.raw)
        self.assertNotIn("test-openai-key", result.raw + "".join(captured.output))
        self.assertEqual(len(self.requests), 2)

    def test_error_truncation_cannot_expose_a_partial_credential(self) -> None:
        request = httpx.Request("POST", "https://example.invalid")
        secret = "test-openai-key"
        json_response = httpx.Response(400, request=request, json={
            "error": {"message": "x" * 477 + secret},
        })
        text_response = httpx.Response(400, request=request, text="x" * 490 + secret)
        for error in (
            RuntimeError("x" * 490 + secret),
            httpx.HTTPStatusError("bad", request=request, response=json_response),
            httpx.HTTPStatusError("bad", request=request, response=text_response),
        ):
            with self.subTest(error=type(error).__name__):
                safe = self.classifier._safe_error(error)
                self.assertNotIn(secret[:8], safe)
                self.assertIn("[REDACTED]", safe)
                self.assertLessEqual(len(safe), 700)


if __name__ == "__main__":
    unittest.main()
