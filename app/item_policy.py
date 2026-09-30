"""Decisions shared by observation ingestion and the administration API.

An AI answer describes evidence; it cannot delete that evidence. Review state
is independent of the item's storage lifecycle and the model that supplied it.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .ai import Classification


def review_status(item: Mapping[str, Any]) -> str:
    """Read explicit state, allowing older integrations during migration."""
    state = item.get("review_status")
    if state in {"pending", "needs_review", "confirmed", "dismissed"}:
        return str(state)
    provider = str(item.get("provider") or "")
    if provider == "pending":
        return "pending"
    if provider == "offline" or provider.endswith("_review"):
        return "needs_review"
    return "confirmed"


def classification_review_reason(result: Classification, minimum: float) -> str | None:
    """None accepts an addition; every other outcome remains reviewable."""
    try:
        confidence = float(result.confidence)
        minimum = float(minimum)
    except (TypeError, ValueError, OverflowError):
        return "invalid_confidence"
    if isinstance(result.confidence, bool) or not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return "invalid_confidence"
    if not math.isfinite(minimum):
        minimum = 0.5
    if result.provider == "offline":
        return "offline"
    if result.action == "removed":
        return "ai_rejected"
    if result.action != "added":
        return "ai_uncertain"
    if confidence < max(0.0, min(1.0, minimum)):
        return "low_confidence"
    return None


def observation_is_current(item: Mapping[str, Any] | None, revision: int | None) -> bool:
    if not item or item.get("status") not in {"stored", "due"}:
        return False
    if review_status(item) == "dismissed":
        return False
    return revision is None or item.get("tracking_revision", 0) == revision
