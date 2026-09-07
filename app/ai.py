from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

import httpx

from .config import AppConfig


logger = logging.getLogger(__name__)


@dataclass
class Classification:
    name: str
    description: str
    category: str
    confidence: float
    provider: str
    action: str = "added"
    estimated_value_krw: int | None = None
    raw: str = ""

    @property
    def retention_days(self) -> int:
        return {"valuable": 90, "general": 60, "food": 1}.get(self.category, 60)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"retention_days": self.retention_days}


SYSTEM_PROMPT = """당신은 고정 카메라로 촬영한 학교 분실물 보관소의 물품 분류 담당자입니다.
이미지는 각각의 직전에 붙은 한국어 라벨 순서대로 해석하세요. 입력에는 다음 두 증거 묶음이 포함될 수 있습니다.
- 전체 장면 변화 전/후: 물건이 실제로 추가 또는 제거됐는지와 주변 맥락을 판정합니다. 주황색 사각형이 있으면 분석 후보 영역 표시일 뿐 물체의 일부가 아닙니다.
- 후보 영역 crop 변화 전/후: 후보 물건의 종류, 색상과 특징을 판정합니다.
항상 전체 장면에서 변화 방향을 먼저 확인하고 crop으로 물건을 식별하세요. 전체 장면과 crop의 결론이 충돌하면 uncertain입니다.
카메라의 미세 흔들림, 노출·그림자 변화, 이미 있던 물건의 위치가 몇 픽셀 달라진 것만으로는 added가 아닙니다.
변화 후에 실제 새 물건의 윤곽과 특징이 분명히 나타난 경우에만 added로 판단하세요.
사람, 손, 바닥, 책상, 가구, 빛과 그림자는 물건으로 분류하지 마세요.
후보 영역 밖에 원래부터 있던 물건을 새 물건으로 잘못 식별하지 마세요.
두 이미지가 거의 같거나 새 물건을 확정할 수 없으면 반드시 uncertain으로 답하세요.
제공된 이미지가 한 장뿐인 예외적인 경우에도 확실하지 않으면 uncertain으로 답하세요.
반드시 다음 JSON 객체만 답하세요:
{"action":"added|removed|uncertain", "name":"짧은 한국어 물건명", "description":"색상·재질·특징을 포함한 한 문장", "category":"valuable|general|food", "estimated_value_krw":숫자또는null, "confidence":0부터1}
변화 후 이미지에 물건이 새로 생긴 경우에만 action을 added로 하세요. 전 이미지의 물건이 사라졌다면 removed, 방향을 판단할 수 없으면 uncertain입니다.
category 기준: 음식·음료·부패 가능 내용물은 food, 휴대전화·노트북·태블릿·카메라·지갑·귀금속·고가 전자기기는 valuable, 나머지는 general입니다.
브랜드나 소유자를 근거 없이 단정하지 마세요. 확실하지 않으면 포괄적인 이름과 낮은 confidence를 사용하세요."""


class ObjectClassifier:
    def __init__(self, config: AppConfig, settings_getter: Callable[[], dict[str, Any]]):
        self.config = config
        self.settings_getter = settings_getter

    def classify(
        self,
        images: Iterable[bytes | None],
        *,
        scene_images: Iterable[bytes | None] | None = None,
    ) -> Classification:
        """Classify a visual change using crop and optional full-scene evidence.

        ``images`` remains the backwards-compatible crop pair in
        ``before, after`` order.  ``scene_images`` optionally supplies a
        downscaled full-frame pair in the same order.  At most two images from
        each group are sent, bounding both request size and vision-token cost.
        """

        encoded = self._encode_pair(images)
        encoded_scenes = self._encode_pair(scene_images or ())
        if not any(encoded) and not any(encoded_scenes):
            return self._offline("분석할 이미지가 없습니다.")

        settings = self.settings_getter()
        requested = str(settings.get("provider", "auto"))
        attempts: list[str] = []
        if requested in {"auto", "openai"} and self.config.openai_api_key:
            attempts.append("openai")
        if requested in {"auto", "gemini"} and self.config.gemini_api_key:
            attempts.append("gemini")

        errors: list[str] = []
        for provider in attempts:
            try:
                if provider == "openai":
                    return self._openai(
                        encoded,
                        str(settings.get("openai_model", "gpt-5.6-luna")),
                        encoded_scenes,
                    )
                return self._gemini(
                    encoded,
                    str(settings.get("gemini_model", "gemini-3.5-flash-lite")),
                    encoded_scenes,
                )
            except Exception as exc:  # API failures must never stop camera monitoring
                safe_error = self._safe_error(exc)
                logger.warning("%s classification failed: %s", provider, safe_error)
                errors.append(f"{provider}: {safe_error}")
        reason = "; ".join(errors) if errors else "API 키가 설정되지 않았습니다."
        return self._offline(reason)

    @staticmethod
    def _encode_pair(images: Iterable[bytes | None]) -> list[str | None]:
        values = list(images)[-2:]
        return [
            base64.b64encode(image).decode("ascii") if image else None
            for image in values
        ]

    @staticmethod
    def _labeled_evidence(
        images: list[str | None], group: str
    ) -> list[tuple[str, str]]:
        """Preserve before/after meaning even if one side failed to encode."""
        if len(images) >= 2:
            labels = (
                f"{group} · 변화 전 (BEFORE)",
                f"{group} · 변화 후 (AFTER)",
            )
        else:
            labels = (f"{group} · 단일 이미지 (전후 위치 불명)",)
        return [
            (label, image)
            for label, image in zip(labels, images)
            if image
        ]

    @classmethod
    def _openai_content(
        cls,
        images: list[str | None],
        scene_images: list[str | None] | None = None,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": SYSTEM_PROMPT}
        ]
        groups = (
            ("전체 장면", scene_images or [], "low"),
            ("후보 영역 crop", images, "high"),
        )
        for group, group_images, detail in groups:
            for label, image in cls._labeled_evidence(group_images[-2:], group):
                content.append({"type": "input_text", "text": f"[{label}]"})
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image}",
                        "detail": detail,
                    }
                )
        return content

    def _openai(
        self,
        images: list[str | None],
        model: str,
        scene_images: list[str | None] | None = None,
    ) -> Classification:
        content = self._openai_content(images, scene_images)
        payload = {
            "model": model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": 450,
        }
        timeout = httpx.Timeout(30.0, connect=8.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        text = body.get("output_text") or self._extract_openai_text(body)
        return self._normalize(text, "openai")

    @staticmethod
    def _extract_openai_text(body: dict[str, Any]) -> str:
        chunks: list[str] = []
        for output in body.get("output", []):
            for part in output.get("content", []):
                if part.get("type") in {"output_text", "text"} and part.get("text"):
                    chunks.append(str(part["text"]))
        return "\n".join(chunks)

    @classmethod
    def _gemini_parts(
        cls,
        images: list[str | None],
        scene_images: list[str | None] | None = None,
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"text": SYSTEM_PROMPT}]
        groups = (
            ("전체 장면", scene_images or []),
            ("후보 영역 crop", images),
        )
        for group, group_images in groups:
            for label, image in cls._labeled_evidence(group_images[-2:], group):
                parts.append({"text": f"[{label}]"})
                parts.append(
                    {"inline_data": {"mime_type": "image/jpeg", "data": image}}
                )
        return parts

    def _gemini(
        self,
        images: list[str | None],
        model: str,
        scene_images: list[str | None] | None = None,
    ) -> Classification:
        parts = self._gemini_parts(images, scene_images)
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 450,
                "responseMimeType": "application/json",
            },
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        timeout = httpx.Timeout(30.0, connect=8.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={"x-goog-api-key": self.config.gemini_api_key},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        candidates = body.get("candidates", [])
        text = ""
        if candidates:
            text = "".join(
                str(part.get("text", ""))
                for part in candidates[0].get("content", {}).get("parts", [])
            )
        return self._normalize(text, "gemini")

    def _normalize(self, raw: str, provider: str) -> Classification:
        if not raw:
            raise ValueError("AI 응답에 텍스트가 없습니다.")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I | re.S)
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise ValueError("AI 응답에서 JSON 객체를 찾지 못했습니다.")
        data = json.loads(match.group(0))
        category = str(data.get("category", "general")).lower()
        if category not in {"valuable", "general", "food"}:
            category = "general"
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.65))))
        except (TypeError, ValueError):
            confidence = 0.65
        estimated = data.get("estimated_value_krw")
        try:
            estimated = int(estimated) if estimated is not None else None
        except (TypeError, ValueError):
            estimated = None
        try:
            threshold = int(self.settings_getter().get("valuable_value_threshold_krw", 100000))
        except (TypeError, ValueError):
            threshold = 100000
        if category == "general" and estimated is not None and estimated >= max(1, threshold):
            category = "valuable"
        # Missing polarity is not enough evidence to persist a detected item.
        # Offline fallback explicitly opts into ``added`` so camera events are
        # still retained when no remote model is available.
        action = str(data.get("action", "uncertain")).strip().lower()
        if action not in {"added", "removed", "uncertain"}:
            action = "uncertain"
        if action == "uncertain":
            confidence = min(confidence, 0.45)
        return Classification(
            name=str(data.get("name") or "확인 필요한 물건")[:80],
            description=str(data.get("description") or "사진을 확인해 주세요.")[:300],
            category=category,
            confidence=confidence,
            provider=provider,
            action=action,
            estimated_value_krw=estimated,
            raw=raw[:4000],
        )

    def _safe_error(self, exc: Exception) -> str:
        """Return a useful API error while guaranteeing credentials are absent."""
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            try:
                detail = exc.response.json()
                if isinstance(detail, dict):
                    detail = detail.get("error", detail)
                message = json.dumps(detail, ensure_ascii=False)[:500]
            except Exception:
                message = exc.response.text[:500]
            value = f"HTTP {status}: {message}"
        elif isinstance(exc, httpx.TimeoutException):
            value = "API 응답 시간이 초과되었습니다."
        elif isinstance(exc, httpx.RequestError):
            value = f"API 연결 실패: {exc.__class__.__name__}"
        else:
            value = f"{exc.__class__.__name__}: {str(exc)[:500]}"
        for secret in (self.config.openai_api_key, self.config.gemini_api_key):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(
            r"(?i)((?:api[_-]?key|key)=)([^&\s\"']+)",
            r"\1[REDACTED]",
            value,
        )
        return value[:700]

    @staticmethod
    def _offline(reason: str) -> Classification:
        return Classification(
            name="새 분실물",
            description="AI 연결 전 임시 등록되었습니다. 관리자 화면에서 이름과 분류를 수정해 주세요.",
            category="general",
            confidence=0.25,
            provider="offline",
            action="added",
            raw=reason[:1000],
        )
