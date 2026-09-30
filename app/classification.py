"""Apply remote descriptions without giving a model ownership of inventory.

The camera commits an observation first. This service can confirm its metadata
or request review, but cannot erase observations, pictures, or lifecycle history.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .ai import ObjectClassifier
from .item_policy import classification_review_reason, review_status
from .store import Store
from .vision import ChangeEvent


logger = logging.getLogger(__name__)

REVIEW_MESSAGES = {
    "offline": "외부 AI를 사용할 수 없어 이름과 분류를 확인해야 합니다.",
    "ai_rejected": "AI는 제거 변화로 판단했습니다. 사진을 확인한 뒤 실제 물품인지 결정해 주세요.",
    "ai_uncertain": "AI가 전후 장면으로 물품을 확정하지 못했습니다.",
    "low_confidence": "AI의 물품 판정 확신도가 기준보다 낮습니다.",
    "invalid_confidence": "AI 응답의 확신도를 검증할 수 없습니다.",
}


class ClassificationProcessor:
    def __init__(
        self, store: Store, classifier: ObjectClassifier,
        settings_getter: Callable[[], dict[str, Any]], mutation_lock: Any,
        signature_getter: Callable[[dict[str, Any]], tuple[Any, ...]],
    ) -> None:
        self.store = store
        self.classifier = classifier
        self.settings_getter = settings_getter
        self.mutation_lock = mutation_lock
        self.signature_getter = signature_getter

    def process(
        self, item_id: int, event: ChangeEvent,
        expected_signature: tuple[Any, ...] | None = None,
    ) -> None:
        try:
            with self.mutation_lock:
                initial = self.store.get_item(item_id)
                if not initial or review_status(initial) != "pending":
                    return
                signature = expected_signature or self.signature_getter(initial)
            result = self.classifier.classify(
                [event.before_jpeg, event.after_jpeg],
                scene_images=[event.scene_before_jpeg, event.scene_after_jpeg],
            )
            reason = classification_review_reason(
                result, self.settings_getter().get("ai_min_confidence", 0.5),
            )
            try:
                confidence = float(result.confidence)
            except (TypeError, ValueError, OverflowError):
                confidence = 0.0
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                confidence = 0.0
            with self.mutation_lock:
                current = self.store.get_item(item_id)
                if not current or review_status(current) != "pending":
                    return
                updates: dict[str, Any] = {
                    "confidence": confidence,
                    "ai_raw": result.raw,
                    "review_status": "confirmed" if reason is None else "needs_review",
                    "review_reason": reason,
                    # Keep the legacy provider representation for older clients.
                    # All workflow decisions use the independent review state.
                    "provider": result.provider if reason is None else f"{result.provider}_review",
                }
                if reason is None:
                    detected = datetime.fromisoformat(str(current["detected_at"]).replace("Z", "+00:00"))
                    expiry = detected + timedelta(days=result.retention_days)
                    updates.update(
                        name=result.name, description=result.description,
                        category=result.category, retention_days=result.retention_days,
                        expires_at=expiry,
                    )
                    if current.get("status") in {"stored", "due"}:
                        updates["status"] = "due" if expiry <= datetime.now(timezone.utc) else "stored"
                    activity_type = "item_classified"
                    message = "{name} 분석을 마쳐 보관 정책을 적용했습니다."
                else:
                    name = str(result.name or "").strip()
                    if not name or name in {"확인 필요한 물건", "새 분실물", "식별 불가 물체"}:
                        name = "확인 필요한 새 물품"
                    changed = self.signature_getter(current) != signature
                    updates.update(
                        name=name,
                        description=REVIEW_MESSAGES[reason] + (
                            " 이동·처리 기록과 사진은 보존됩니다." if changed
                            else " 확인 전까지 감지 기록과 추적을 유지합니다."
                        ),
                    )
                    activity_type = "classification_inconclusive"
                    message = "AI 판정을 자동 확정하지 않고 감지 기록과 사진을 보존했습니다."
                self.store.update_item(
                    item_id, updates, activity_type=activity_type,
                    activity_message=message,
                    activity_metadata={
                        "provider": result.provider, "action": result.action,
                        "confidence": confidence, "reason": reason,
                        "review_required": reason is not None,
                    },
                )
        except Exception:
            logger.exception("Could not classify observation %s", item_id)
            try:
                with self.mutation_lock:
                    current = self.store.get_item(item_id)
                    if current and review_status(current) == "pending":
                        self.store.update_item(
                            item_id,
                            {
                                "name": "확인 필요한 새 물품",
                                "description": "AI 분석 오류가 발생했습니다. 감지 기록과 사진은 보존됩니다.",
                                "provider": "offline_review",
                                "review_status": "needs_review",
                                "review_reason": "classifier_error",
                            },
                            activity_type="classification_inconclusive",
                            activity_message="AI 분석 오류로 관리자 확인이 필요합니다.",
                            activity_metadata={"reason": "classifier_error", "review_required": True},
                        )
            except Exception:
                logger.exception("Could not persist classification failure for %s", item_id)
