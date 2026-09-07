from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import Classification, ObjectClassifier
from .config import (
    DEFAULT_SETTINGS,
    SETTING_TYPES,
    AppConfig,
    coerce_setting,
    public_provider_state,
)
from .notifier import EmailNotifier, ExpirationScheduler
from .store import Store, classify_retention
from .vision import ChangeEvent, VisionMonitor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lost-item-admin")

UTC = timezone.utc
config = AppConfig.from_env()
config.data_dir.mkdir(parents=True, exist_ok=True)
config.capture_dir.mkdir(parents=True, exist_ok=True)

store = Store(config.db_path)
_settings_lock = threading.RLock()
_reference_cache_lock = threading.RLock()
_reference_cache: OrderedDict[str, tuple[int, bytes]] = OrderedDict()
_reference_cache_bytes = 0
_item_mutation_lock = threading.RLock()
_reset_lock = threading.Lock()

RESET_CONFIRMATION = "초기화"


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def current_settings() -> dict[str, Any]:
    with _settings_lock:
        try:
            raw = store.get_settings(DEFAULT_SETTINGS)
        except Exception:
            raw = dict(DEFAULT_SETTINGS)
        return {
            key: coerce_setting(key, raw.get(key, default))
            for key, default in DEFAULT_SETTINGS.items()
        }


def public_settings() -> dict[str, Any]:
    settings = current_settings()
    settings.update(
        {
            "hardware_profile": config.hardware_profile,
            "openai_key_configured": bool(config.openai_api_key),
            "gemini_key_configured": bool(config.gemini_api_key),
            "smtp_password_configured": bool(config.smtp_password),
        }
    )
    return settings


def cached_capture(raw_path: Any) -> bytes | None:
    global _reference_cache_bytes
    if not raw_path:
        return None
    try:
        path = Path(str(raw_path)).resolve()
        if not path.is_relative_to(config.capture_dir.resolve()) or not path.is_file():
            return None
        stat = path.stat()
        if stat.st_size > 8 * 1024 * 1024:
            return None
        cache_key = str(path)
        with _reference_cache_lock:
            cached = _reference_cache.get(cache_key)
            if cached and cached[0] == stat.st_mtime_ns:
                _reference_cache.move_to_end(cache_key)
                return cached[1]
            content = path.read_bytes()
            previous = _reference_cache.pop(cache_key, None)
            if previous:
                _reference_cache_bytes -= len(previous[1])
            if len(content) <= config.reference_cache_max_bytes:
                _reference_cache[cache_key] = (stat.st_mtime_ns, content)
                _reference_cache_bytes += len(content)
                while (
                    _reference_cache
                    and _reference_cache_bytes > config.reference_cache_max_bytes
                ):
                    _, evicted = _reference_cache.popitem(last=False)
                    _reference_cache_bytes -= len(evicted[1])
            return content
    except OSError:
        logger.debug("Could not read item comparison image", exc_info=True)
        return None


def active_items_for_vision() -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for item in store.list_items(limit=500):
        bbox = item.get("bbox") or item.get("bbox_json")
        # Presentation presets do not correspond to a physical camera object.
        if item.get("status") not in {"stored", "due"} or not bbox or item.get("provider") == "demo":
            continue
        active.append(
            {
                "id": item["id"],
                "bbox": bbox,
                "reference_jpeg": cached_capture(item.get("image_path")),
                "background_jpeg": cached_capture(item.get("background_path")),
            }
        )
    return active


def vision_event_callback(*args: Any, **kwargs: Any) -> None:
    """Accept lightweight diagnostics from the camera worker without coupling interfaces."""
    try:
        if args and isinstance(args[0], dict):
            data = args[0]
            event_type = str(data.get("type", "camera"))
            message = str(data.get("message", "카메라 상태가 변경되었습니다."))
        elif len(args) >= 2:
            event_type, message = str(args[0]), str(args[1])
        elif args:
            event_type, message = "camera", str(args[0])
        else:
            event_type, message = "camera", str(kwargs.get("message", "카메라 상태 변경"))
        if event_type in {"camera_error", "camera_connected", "baseline_reset"}:
            store.create_activity(event_type, message)
    except Exception:
        logger.debug("Could not persist camera diagnostic", exc_info=True)


classification_pool = ThreadPoolExecutor(
    max_workers=config.classifier_workers, thread_name_prefix="item-classifier"
)
classification_slots = threading.BoundedSemaphore(
    value=max(config.classifier_workers, config.classification_slots)
)
classifier = ObjectClassifier(config, current_settings)
notifier = EmailNotifier(config, current_settings)
scheduler = ExpirationScheduler(store, notifier, interval_seconds=20)


def save_capture(image: bytes | None, prefix: str = "item") -> str | None:
    if not image:
        return None
    filename = f"{prefix}-{utc_now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.jpg"
    path = (config.capture_dir / filename).resolve()
    path.write_bytes(image)
    return str(path)


def remove_managed_captures(paths: list[str | None]) -> None:
    """Delete only files inside the configured capture directory."""
    global _reference_cache_bytes
    capture_root = config.capture_dir.resolve()
    for raw_path in paths:
        if not raw_path:
            continue
        try:
            path = Path(str(raw_path)).resolve()
            if not path.is_relative_to(capture_root):
                continue
            path.unlink(missing_ok=True)
            with _reference_cache_lock:
                removed = _reference_cache.pop(str(path), None)
                if removed:
                    _reference_cache_bytes -= len(removed[1])
        except OSError:
            logger.debug("Could not remove managed capture", exc_info=True)


def backup_and_reset_operational_data() -> dict[str, Any]:
    """Back up and clear runtime data without touching settings or ``.env``.

    The caller must stop camera callbacks first and hold
    ``_item_mutation_lock``.  Database backup uses SQLite's online backup API,
    so committed WAL pages are included in the snapshot.
    """

    global _reference_cache_bytes
    data_root = config.data_dir.resolve()
    capture_root = config.capture_dir.resolve()
    project_root = config.root_dir.resolve()
    database_path = Path(store.db_path).expanduser().resolve()
    backup_root = (data_root / "reset-backups").resolve()

    # A bad CAPTURE_DIR must never turn an administrator reset into a broad
    # recursive deletion.  The database and backup tree must also remain
    # outside the directory being cleared.
    filesystem_root = Path(capture_root.anchor).resolve()
    protected = {filesystem_root, data_root, project_root, Path.home().resolve()}
    if (
        capture_root in protected
        or data_root.is_relative_to(capture_root)
        or database_path.is_relative_to(capture_root)
        or backup_root.is_relative_to(capture_root)
    ):
        raise RuntimeError("unsafe capture directory; reset refused")

    data_root.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now().strftime("%Y%m%dT%H%M%S.%fZ")
    snapshot_dir = backup_root / timestamp
    snapshot_dir.mkdir(parents=False, exist_ok=False)

    manifest_path = snapshot_dir / "manifest.json"
    database_backup = snapshot_dir / "database.sqlite3"
    captures_backup = snapshot_dir / "captures"
    manifest: dict[str, Any] = {
        "created_at": iso(utc_now()),
        "state": "preparing",
        "database": database_backup.name,
        "captures": captures_backup.name,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    try:
        store.backup_to(database_backup)
        if capture_root.exists():
            shutil.copytree(
                capture_root,
                captures_backup,
                symlinks=True,
                dirs_exist_ok=False,
            )
        else:
            captures_backup.mkdir()

        capture_files = sum(
            1
            for path in captures_backup.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        manifest.update(
            {
                "state": "backup_complete",
                "capture_files": capture_files,
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        removed = store.reset_operational_data()
        capture_root.mkdir(parents=True, exist_ok=True)
        for entry in capture_root.iterdir():
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

        with _reference_cache_lock:
            _reference_cache.clear()
            _reference_cache_bytes = 0
        manifest.update({"state": "complete", "removed": removed})
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "removed": removed,
            "capture_files": capture_files,
            "backup_directory": str(Path("reset-backups") / timestamp),
        }
    except Exception as exc:
        manifest.update(
            {
                "state": "failed",
                "error_type": type(exc).__name__,
            }
        )
        try:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
        raise


def discard_provisional_item(item: dict[str, Any]) -> None:
    """Remove a rejected provisional row and only its managed capture files."""
    store.delete_item(int(item["id"]))
    remove_managed_captures(
        [item.get("image_path"), item.get("background_path")]
    )


def create_provisional_item(event: ChangeEvent) -> dict[str, Any]:
    """Persist the observation before any remote call so quick removals remain trackable."""
    detected_at = utc_now()
    image_path = save_capture(event.crop_jpeg or event.after_jpeg)
    background_path = save_capture(event.before_jpeg, prefix="background")
    item = store.create_item(
        {
            "name": "분석 중인 새 물품",
            "description": "이미지는 안전하게 등록되었으며 AI가 물품 종류를 확인하고 있습니다.",
            "category": "general",
            "retention_days": 60,
            "detected_at": iso(detected_at),
            "expires_at": iso(detected_at + timedelta(days=60)),
            "status": "stored",
            "bbox_json": json.dumps(list(event.bbox)),
            "confidence": event.confidence,
            "image_path": image_path,
            "background_path": background_path,
            "provider": "pending",
            "ai_raw": "classification pending",
        }
    )
    store.create_activity(
        "item_detected",
        "새 물품을 감지해 우선 등록했습니다. AI 분석을 시작합니다.",
        item_id=item["id"],
        metadata={"source": "camera"},
    )
    return item


def classification_is_confirmed_addition(result: Classification) -> bool:
    if result.action != "added":
        return False
    # When APIs are unavailable the local fallback intentionally preserves the
    # observation for manual review rather than presenting it as AI-confirmed.
    if result.provider == "offline":
        return False
    try:
        minimum = float(current_settings().get("ai_min_confidence", 0.5))
    except (TypeError, ValueError):
        minimum = 0.5
    return float(result.confidence) >= max(0.0, min(1.0, minimum))


def classification_is_confirmed_rejection(result: Classification) -> bool:
    """Only a strong remote polarity decision may cancel a provisional row."""

    if result.provider == "offline" or result.action != "removed":
        return False
    try:
        configured = float(current_settings().get("ai_min_confidence", 0.5))
    except (TypeError, ValueError):
        configured = 0.5
    return float(result.confidence) >= max(0.7, min(1.0, configured))


def classify_existing_item(item_id: int, event: ChangeEvent) -> None:
    try:
        result = classifier.classify(
            [event.before_jpeg, event.after_jpeg],
            scene_images=[event.scene_before_jpeg, event.scene_after_jpeg],
        )
        with _item_mutation_lock:
            existing = store.get_item(item_id)
            if not existing:
                return
            if existing.get("provider") != "pending":
                store.create_activity(
                    "classification_skipped",
                    "AI 분석 중 관리자가 물품을 수정해 관리자 입력을 유지했습니다.",
                    item_id=item_id,
                )
                return
            confirmed_addition = classification_is_confirmed_addition(result)
            if not confirmed_addition:
                original_bbox = [int(value) for value in event.bbox]
                current_bbox = existing.get("bbox") or existing.get("bbox_json")
                if isinstance(current_bbox, str):
                    try:
                        current_bbox = json.loads(current_bbox)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        current_bbox = None
                visually_reconfirmed = (
                    isinstance(current_bbox, (list, tuple))
                    and len(current_bbox) == 4
                    and [int(value) for value in current_bbox] != original_bbox
                )
                if (
                    existing.get("status") not in {"stored", "due"}
                    or visually_reconfirmed
                ):
                    fallback_name = (
                        result.name
                        if result.name and result.name not in {"확인 필요한 물건", "새 분실물"}
                        else (
                            "이동이 확인된 미확인 물품"
                            if visually_reconfirmed
                            else "빠르게 회수된 미확인 물품"
                        )
                    )
                    store.update_item(
                        item_id,
                        {
                            "name": fallback_name,
                            "description": result.description,
                            "category": result.category,
                            "confidence": result.confidence,
                            "provider": result.provider,
                            "ai_raw": result.raw,
                        },
                    )
                    store.create_activity(
                        "classification_inconclusive",
                        (
                            "AI 분석 중 동일 물품의 이동이 다시 확인되어 등록을 유지했습니다."
                            if visually_reconfirmed
                            else "물품이 AI 분석 전에 처리되어 기존 회수·폐기 기록을 유지했습니다."
                        ),
                        item_id=item_id,
                        metadata={
                            "provider": result.provider,
                            "action": result.action,
                        },
                    )
                    return
                if classification_is_confirmed_rejection(result):
                    discard_provisional_item(existing)
                    message = "AI 비교 결과 기존 장면의 물건이 사라진 것으로 판단해 새 등록을 취소했습니다."
                    store.create_activity(
                        "change_ignored",
                        message,
                        metadata={
                            "provider": result.provider,
                            "action": result.action,
                            "confidence": result.confidence,
                            "reason": result.action,
                        },
                    )
                    return

                # A stable local change is real evidence even when a remote
                # model is unsure. Deleting the provisional row here is
                # unrecoverable because the vision baseline already contains
                # the new object, so it will not trigger a second addition.
                # Keep it tracked and make the uncertainty explicit instead.
                suggested_name = str(result.name or "").strip()
                if not suggested_name or suggested_name in {
                    "확인 필요한 물건",
                    "새 분실물",
                    "식별 불가 물체",
                }:
                    suggested_name = "확인 필요한 새 물품"
                reason_text = (
                    "AI가 새 물건으로 보았지만 확신도가 기준보다 낮습니다."
                    if result.action == "added"
                    else (
                        "AI가 제거 변화로 보았지만 등록을 취소할 만큼 확실하지 않습니다."
                        if result.action == "removed"
                        else "AI가 전후 장면만으로 물품 종류를 확정하지 못했습니다."
                    )
                )
                store.update_item(
                    item_id,
                    {
                        "name": suggested_name,
                        "description": f"{reason_text} 관리자 확인 전까지 추적을 계속합니다.",
                        "confidence": result.confidence,
                        "provider": f"{result.provider}_review",
                        "ai_raw": result.raw,
                    },
                )
                store.create_activity(
                    "classification_inconclusive",
                    "AI 판정이 불확실해 물품을 확인 필요 상태로 유지했습니다.",
                    item_id=item_id,
                    metadata={
                        "provider": result.provider,
                        "action": result.action,
                        "confidence": result.confidence,
                        "reason": (
                            "low_confidence"
                            if result.action == "added"
                            else result.action
                        ),
                        "review_required": True,
                    },
                )
                return
            detected_at = parse_dt(existing.get("detected_at")) or utc_now()
            item = store.update_item(
                item_id,
                {
                    "name": result.name,
                    "description": result.description,
                    "category": result.category,
                    "retention_days": result.retention_days,
                    "expires_at": iso(detected_at + timedelta(days=result.retention_days)),
                    "confidence": result.confidence,
                    "provider": result.provider,
                    "ai_raw": result.raw,
                },
            )
        if not item:
            return
        store.create_activity(
            "item_classified",
            f"{item['name']} 분석을 마쳐 {item['retention_days']}일 보관 정책을 적용했습니다.",
            item_id=item["id"],
            metadata={"category": item["category"], "provider": result.provider},
        )
    except Exception as exc:
        logger.exception("Failed to register detected item")
        try:
            with _item_mutation_lock:
                existing = store.get_item(item_id)
                if existing and existing.get("provider") == "pending":
                    store.update_item(
                        item_id,
                        {
                            "name": "확인 필요한 새 물품",
                            "description": "AI 분석 중 오류가 발생했지만 감지 기록과 추적은 유지됩니다.",
                            "provider": "offline_review",
                            "ai_raw": f"classification error: {type(exc).__name__}",
                        },
                    )
                    store.create_activity(
                        "classification_inconclusive",
                        "AI 분석 오류로 물품을 확인 필요 상태로 유지했습니다.",
                        item_id=item_id,
                        metadata={
                            "reason": "classifier_error",
                            "review_required": True,
                        },
                    )
            store.create_activity("system_error", f"감지 물품 등록 실패: {str(exc)[:160]}")
        except Exception:
            pass
    finally:
        classification_slots.release()


def item_tracking_signature(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        tuple(item.get("bbox") or ()),
        item.get("image_path"),
        item.get("background_path"),
        item.get("updated_at"),
    )


def verify_removed_item(
    item_id: int,
    event: ChangeEvent,
    expected_signature: tuple[Any, ...] | None = None,
) -> None:
    """Use full-scene evidence only when local removal evidence is ambiguous."""
    try:
        with _item_mutation_lock:
            initial = store.get_item(item_id)
            if not initial or initial.get("status") not in {"stored", "due"}:
                return
            initial_signature = item_tracking_signature(initial)
            if (
                expected_signature is not None
                and initial_signature != expected_signature
            ):
                return
        result = classifier.classify(
            [event.before_jpeg, event.after_jpeg],
            scene_images=[event.scene_before_jpeg, event.scene_after_jpeg],
        )
        try:
            minimum = float(current_settings().get("ai_min_confidence", 0.5))
        except (TypeError, ValueError):
            minimum = 0.5
        confirmed = (
            result.provider != "offline"
            and result.action == "removed"
            and float(result.confidence) >= max(0.0, min(1.0, minimum))
        )
        with _item_mutation_lock:
            existing = store.get_item(item_id)
            if not existing or existing.get("status") not in {"stored", "due"}:
                return
            current_signature = item_tracking_signature(existing)
            # The model inspected an older scene. A move, administrator edit,
            # or new reference capture makes that answer stale and it must not
            # recover the now-current item.
            if current_signature != initial_signature:
                return
            if confirmed:
                store.apply_item_action(
                    item_id,
                    "recover",
                    activity_type="item_recovered",
                    activity_message=(
                        "{name}이(가) 전체 장면 AI 비교에서 사라진 것으로 "
                        "확인되어 자동 회수 처리되었습니다."
                    ),
                    activity_metadata={
                        "source": "camera_ai_verification",
                        "provider": result.provider,
                        "confidence": result.confidence,
                    },
                )
                return
        store.create_activity(
            "recovery_check_inconclusive",
            f"{existing['name']}의 화면 변화를 확인했지만 회수로 확정하지 않아 추적을 유지했습니다.",
            item_id=item_id,
            metadata={
                "source": "camera_ai_verification",
                "provider": result.provider,
                "action": result.action,
                "confidence": result.confidence,
                "bbox": list(event.bbox),
                "review_required": result.provider == "offline",
            },
        )
    except Exception as exc:
        logger.exception("Failed to verify ambiguous removal")
        try:
            store.create_activity(
                "recovery_check_inconclusive",
                "회수 AI 재검증 중 오류가 발생해 물품 추적을 유지했습니다.",
                item_id=item_id,
                metadata={
                    "source": "camera_ai_verification",
                    "reason": "classifier_error",
                    "bbox": list(event.bbox),
                    "review_required": True,
                },
            )
            store.create_activity(
                "system_error",
                f"회수 재검증 실패: {str(exc)[:160]}",
                item_id=item_id,
            )
        except Exception:
            pass
    finally:
        classification_slots.release()


def handle_vision_change(event: ChangeEvent) -> None:
    if event.kind == "added":
        try:
            item = create_provisional_item(event)
        except Exception as exc:
            logger.exception("Failed to persist provisional detected item")
            try:
                store.create_activity("system_error", f"감지 물품 임시 등록 실패: {str(exc)[:160]}")
            except Exception:
                pass
            return
        if classification_slots.acquire(blocking=False):
            classification_pool.submit(classify_existing_item, item["id"], event)
        else:
            store.update_item(
                item["id"],
                {
                    "name": "확인 필요한 새 물품",
                    "description": "분석 대기열이 가득 차 임시 등록되었습니다. 관리자 화면에서 확인해 주세요.",
                    "provider": "offline",
                    "ai_raw": "classification queue full",
                },
            )
            store.create_activity(
                "classification_deferred",
                "AI 분석 대기열이 가득 차 물품을 임시 등록했습니다.",
                item_id=item["id"],
            )
        return
    if event.kind == "verify_removed" and event.matched_item_id is not None:
        item_id = int(event.matched_item_id)
        with _item_mutation_lock:
            expected_item = store.get_item(item_id)
            expected_signature = (
                item_tracking_signature(expected_item)
                if expected_item
                and expected_item.get("status") in {"stored", "due"}
                else None
            )
        if expected_signature is None:
            return
        if classification_slots.acquire(blocking=False):
            classification_pool.submit(
                verify_removed_item,
                item_id,
                event,
                expected_signature,
            )
        else:
            try:
                store.create_activity(
                    "recovery_check_deferred",
                    "회수 여부 AI 재검증 대기열이 가득 차 로컬 추적을 유지했습니다.",
                    item_id=item_id,
                )
            except Exception:
                logger.debug("Could not record deferred removal verification", exc_info=True)
        return
    if event.kind == "moved" and event.matched_item_id is not None:
        new_image_path: str | None = None
        new_background_path: str | None = None
        try:
            with _item_mutation_lock:
                existing = store.get_item(int(event.matched_item_id))
                if not existing or existing.get("status") not in {"stored", "due"}:
                    return
                new_image_path = save_capture(
                    event.crop_jpeg or event.after_jpeg,
                    prefix="item-moved",
                )
                new_background_path = save_capture(
                    event.before_jpeg,
                    prefix="background-moved",
                )
                updates: dict[str, Any] = {
                    "bbox_json": json.dumps(list(event.bbox)),
                    "confidence": max(
                        float(existing.get("confidence") or 0.0),
                        float(event.confidence),
                    ),
                }
                if new_image_path:
                    updates["image_path"] = new_image_path
                if new_background_path:
                    updates["background_path"] = new_background_path
                item = store.update_item(existing["id"], updates)
                if not item:
                    raise RuntimeError("Moved item disappeared during update")
        except Exception:
            remove_managed_captures([new_image_path, new_background_path])
            logger.exception("Failed to update moved item location")
            return

        remove_managed_captures(
            [
                existing.get("image_path") if new_image_path else None,
                existing.get("background_path") if new_background_path else None,
            ]
        )
        try:
            store.create_activity(
                "item_moved",
                f"{item['name']}의 위치 변화를 감지해 추적 영역을 갱신했습니다.",
                item_id=item["id"],
                metadata={"source": "camera", "bbox": list(event.bbox)},
            )
        except Exception:
            logger.exception("Failed to record moved item activity")
        return
    if event.kind == "removed" and event.matched_item_id is not None:
        try:
            with _item_mutation_lock:
                store.apply_item_action(
                    int(event.matched_item_id),
                    "recover",
                    activity_type="item_recovered",
                    activity_message="{name}이(가) 장면에서 사라져 자동 회수 처리되었습니다.",
                    activity_metadata={"source": "camera"},
                )
        except Exception:
            logger.exception("Failed to mark removed item as recovered")


vision = VisionMonitor(
    config_getter=current_settings,
    change_callback=handle_vision_change,
    active_items_getter=active_items_for_vision,
    event_callback=vision_event_callback,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    store.create_activity("system_started", "분실물 감지 시스템을 시작했습니다.")
    scheduler.start()
    vision.start()
    try:
        yield
    finally:
        vision.stop()
        scheduler.stop()
        classification_pool.shutdown(wait=False, cancel_futures=True)


app = FastAPI(
    title="AI 분실물 보관 시스템",
    version="1.0.0",
    description="고정 웹캠 기반 분실물 감지·분류·보관 기한 관리 API",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=config.root_dir / "static"), name="static")


class ItemEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    category: str | None = None
    expires_at: str | None = None


class ExtendRequest(BaseModel):
    days: int = Field(ge=1, le=365)


class DemoRequest(BaseModel):
    preset: str = "phone"


class ResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=20)


def item_for_api(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item)
    if item.get("image_path"):
        image_version = item.get("updated_at") or item.get("created_at") or "1"
        result["image_url"] = (
            f"/api/items/{item['id']}/image?v={image_version}"
        )
    else:
        result["image_url"] = None
    result.pop("image_path", None)
    result.pop("background_path", None)
    result.pop("ai_raw", None)
    if isinstance(result.get("bbox_json"), str):
        try:
            result["bbox"] = json.loads(result["bbox_json"])
        except (json.JSONDecodeError, TypeError):
            result["bbox"] = None
    result.pop("bbox_json", None)
    return result


def item_action_response(result: dict[str, Any]) -> dict[str, Any]:
    """Map Store lifecycle outcomes to the stable HTTP item contract."""

    outcome = result.get("outcome")
    item = result.get("item")
    if outcome == "not_found" or not item:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    if outcome == "conflict":
        action = str(result.get("action") or "")
        messages = {
            "recover": "이미 폐기 처리된 물품입니다. 먼저 보관 목록으로 복원해 주세요.",
            "dispose": "이미 회수 처리된 물품입니다. 먼저 보관 목록으로 복원해 주세요.",
            "restore": "현재 상태에서는 물품을 복원할 수 없습니다.",
        }
        raise HTTPException(
            409,
            detail={
                "code": "status_conflict",
                "message": messages.get(action, "물품 상태가 이미 변경되었습니다."),
                "action": action,
                "current_status": item.get("status"),
                "item": item_for_api(item),
            },
        )
    return item_for_api(item)


def dashboard_payload() -> dict[str, Any]:
    items = store.list_items(limit=500)
    now = utc_now()
    lead = timedelta(days=int(current_settings().get("alert_lead_days", 7)))
    stored = [item for item in items if item.get("status") == "stored"]
    due_soon = [
        item
        for item in stored
        if (expiry := parse_dt(item.get("expires_at"))) is not None and now <= expiry <= now + lead
    ]
    stats = {
        "active": len(stored),
        "due_soon": len(due_soon),
        "expired": sum(item.get("status") == "due" for item in items),
        "recovered": sum(item.get("status") == "recovered" for item in items),
    }
    return {
        "stats": stats,
        "items": [item_for_api(item) for item in items[:100]],
        "activities": store.list_activities(limit=30),
        "notifications": store.list_notifications(limit=30),
        "camera": vision.get_status(),
        "provider": public_provider_state(config, current_settings()),
        "server_time": iso(now),
    }


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.root_dir / "templates" / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    status = vision.get_status()
    return {
        "ok": True,
        "version": "1.0.0",
        "hardware_profile": config.hardware_profile,
        "database": "connected",
        "camera": status,
        "provider": public_provider_state(config, current_settings()),
        "time": iso(utc_now()),
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return dashboard_payload()


@app.get("/api/items")
def list_items(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    if status == "all":
        status = None
    if status and status not in {"stored", "due", "recovered", "disposed"}:
        raise HTTPException(400, "지원하지 않는 상태입니다.")
    items = store.list_items(status=status, q=q, limit=500)
    return {"items": [item_for_api(item) for item in items], "total": len(items)}


@app.get("/api/items/{item_id}")
def get_item(item_id: int) -> dict[str, Any]:
    item = store.get_item(item_id)
    if not item:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    return item_for_api(item)


@app.get("/api/items/{item_id}/image", include_in_schema=False)
def item_image(item_id: int) -> FileResponse:
    item = store.get_item(item_id)
    if not item or not item.get("image_path"):
        raise HTTPException(404, "저장된 이미지가 없습니다.")
    path = Path(str(item["image_path"])).resolve()
    if not path.is_relative_to(config.capture_dir.resolve()) or not path.is_file():
        raise HTTPException(404, "저장된 이미지를 찾을 수 없습니다.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, private, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.patch("/api/items/{item_id}")
def edit_item(item_id: int, edit: ItemEdit) -> dict[str, Any]:
    with _item_mutation_lock:
        existing = store.get_item(item_id)
        if not existing:
            raise HTTPException(404, "물품을 찾을 수 없습니다.")
        updates = {key: value for key, value in edit.model_dump(exclude_none=True).items()}
        if "category" in updates:
            category = updates["category"]
            if category not in {"valuable", "general", "food"}:
                raise HTTPException(400, "분류는 valuable, general, food 중 하나여야 합니다.")
            if category != existing.get("category"):
                days = classify_retention(category)
                updates["retention_days"] = days
                if "expires_at" not in updates:
                    detected = parse_dt(existing.get("detected_at")) or utc_now()
                    updates["expires_at"] = iso(detected + timedelta(days=days))
        if "expires_at" in updates and not parse_dt(updates["expires_at"]):
            raise HTTPException(400, "기한 날짜 형식이 올바르지 않습니다.")
        if existing.get("status") in {"stored", "due"}:
            effective_expiry = parse_dt(updates.get("expires_at", existing.get("expires_at")))
            if effective_expiry:
                updates["status"] = "due" if effective_expiry <= utc_now() else "stored"
        if existing.get("provider") == "pending":
            updates["provider"] = "manual"
            updates["ai_raw"] = "manual edit while classification was pending"
        item = store.update_item(item_id, updates)
    store.create_activity("item_edited", f"{item['name']} 정보를 수정했습니다.", item_id=item_id)
    return item_for_api(item)


@app.post("/api/items/{item_id}/recover")
def recover_item(item_id: int) -> dict[str, Any]:
    with _item_mutation_lock:
        result = store.apply_item_action(
            item_id,
            "recover",
            activity_type="item_recovered",
            activity_message="{name}을(를) 수동 회수 처리했습니다.",
        )
    return item_action_response(result)


@app.post("/api/items/{item_id}/dispose")
def dispose_item(item_id: int) -> dict[str, Any]:
    with _item_mutation_lock:
        result = store.apply_item_action(
            item_id,
            "dispose",
            activity_type="item_disposed",
            activity_message="{name}을(를) 폐기 처리했습니다.",
        )
    return item_action_response(result)


@app.post("/api/items/{item_id}/restore")
def restore_item(item_id: int) -> dict[str, Any]:
    with _item_mutation_lock:
        result = store.apply_item_action(
            item_id,
            "restore",
            activity_type="item_restored",
            activity_message="{name}을(를) 보관 목록으로 되돌렸습니다.",
        )
    return item_action_response(result)


@app.post("/api/items/{item_id}/extend")
def extend_item(item_id: int, request: ExtendRequest) -> dict[str, Any]:
    item = store.extend_item(item_id, request.days)
    if not item:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    store.create_activity(
        "item_extended",
        f"{item['name']}의 보관 기한을 {request.days}일 연장했습니다.",
        item_id=item_id,
    )
    return item_for_api(item)


DEMO_PRESETS: dict[str, dict[str, Any]] = {
    "phone": {
        "name": "검은색 스마트폰",
        "description": "검은색 케이스를 장착한 스마트폰입니다.",
        "category": "valuable",
        "confidence": 0.98,
        "bbox": [430, 265, 240, 250],
    },
    "sandwich": {
        "name": "포장 샌드위치",
        "description": "투명 포장 안에 든 신선식품 샌드위치입니다.",
        "category": "food",
        "confidence": 0.97,
        "bbox": [525, 300, 280, 190],
    },
    "umbrella": {
        "name": "남색 접이식 우산",
        "description": "손잡이 끈이 달린 남색 접이식 우산입니다.",
        "category": "general",
        "confidence": 0.96,
        "bbox": [370, 315, 430, 130],
    },
    "wallet": {
        "name": "갈색 카드지갑",
        "description": "가죽 질감의 얇은 갈색 카드지갑입니다.",
        "category": "valuable",
        "confidence": 0.94,
        "bbox": [490, 330, 230, 145],
    },
}


@app.post("/api/demo/items")
def create_demo_item(request: DemoRequest) -> dict[str, Any]:
    preset = DEMO_PRESETS.get(request.preset)
    if not preset:
        raise HTTPException(400, "지원하지 않는 시연 물품입니다.")
    detected = utc_now()
    days = classify_retention(preset["category"])
    item = store.create_item(
        {
            "name": preset["name"],
            "description": preset["description"],
            "category": preset["category"],
            "retention_days": days,
            "detected_at": iso(detected),
            "expires_at": iso(detected + timedelta(days=days)),
            "status": "stored",
            "bbox_json": json.dumps(preset["bbox"]),
            "confidence": preset["confidence"],
            "image_path": None,
            "provider": "demo",
            "ai_raw": "built-in deterministic presentation preset",
        }
    )
    store.create_activity(
        "item_detected",
        f"시연: {item['name']}을(를) 감지해 {days}일 보관으로 등록했습니다.",
        item_id=item["id"],
        metadata={"source": "demo"},
    )
    return item_for_api(item)


@app.post("/api/demo/recover")
def recover_demo_item(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    item_id = (payload or {}).get("item_id")
    if item_id is None:
        active = [item for item in store.list_items(limit=100) if item.get("status") in {"stored", "due"}]
        if not active:
            raise HTTPException(404, "회수할 보관 물품이 없습니다.")
        item_id = active[0]["id"]
    with _item_mutation_lock:
        result = store.apply_item_action(
            int(item_id),
            "recover",
            activity_type="item_recovered",
            activity_message="시연: {name}이(가) 사라져 자동 회수 처리되었습니다.",
            activity_metadata={"source": "demo"},
        )
    return item_action_response(result)


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {"settings": public_settings(), "provider": public_provider_state(config, current_settings())}


@app.put("/api/settings")
def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(SETTING_TYPES)
    updates = {key: coerce_setting(key, value) for key, value in payload.items() if key in allowed}
    if not updates:
        raise HTTPException(400, "저장할 수 있는 설정이 없습니다.")
    if updates.get("provider") not in {None, "auto", "openai", "gemini", "offline"}:
        raise HTTPException(400, "AI 공급자 설정이 올바르지 않습니다.")
    if updates.get("camera_backend") not in {
        None,
        "auto",
        "picamera2",
        "any",
        "v4l2",
        "dshow",
        "msmf",
        "avfoundation",
        "ffmpeg",
        "gstreamer",
    }:
        raise HTTPException(400, "카메라 백엔드 설정이 올바르지 않습니다.")
    ranges = {
        "camera_index": (-1, 20),
        "camera_width": (160, 3840),
        "camera_height": (120, 2160),
        "camera_fps": (1, 60),
        "monitor_fps": (1, 30),
        "accumulated_check_fps": (1, 30),
        "preview_stream_fps": (1, 15),
        "preview_jpeg_quality": (45, 95),
        "jpeg_quality": (45, 95),
        "stabilization_analysis_width": (160, 1280),
        "motion_threshold": (2, 100),
        "motion_min_ratio": (0.0, 0.25),
        "motion_min_area": (1, 500000),
        "change_threshold": (2, 120),
        "min_change_area": (100, 500000),
        "max_change_ratio": (0.01, 1.0),
        "settle_seconds": (0.5, 30),
        "stable_seconds": (0.2, 15),
        "smtp_port": (1, 65535),
        "alert_lead_days": (0, 90),
        "ai_min_confidence": (0.0, 1.0),
        "valuable_value_threshold_krw": (10000, 1000000000),
    }
    for key, (minimum, maximum) in ranges.items():
        if key in updates and not minimum <= updates[key] <= maximum:
            raise HTTPException(400, f"{key} 값은 {minimum}~{maximum} 범위여야 합니다.")
    with _settings_lock:
        store.update_settings(updates)
    if "privacy_mode" in updates:
        vision.set_privacy(bool(current_settings().get("privacy_mode", False)))
    vision_keys = {
        "camera_index",
        "camera_backend",
        "camera_width",
        "camera_height",
        "camera_fps",
        "monitor_fps",
        "accumulated_check_fps",
        "jpeg_quality",
        "stabilization_analysis_width",
        "motion_threshold",
        "motion_min_ratio",
        "motion_min_area",
        "change_threshold",
        "min_change_area",
        "max_change_ratio",
        "settle_seconds",
        "stable_seconds",
    }
    if vision_keys.intersection(updates):
        vision.rebaseline()
    store.create_activity("settings_updated", "관리자 설정을 변경했습니다.")
    return {"settings": public_settings(), "provider": public_provider_state(config, current_settings())}


@app.post("/api/settings/test-email")
def test_email() -> dict[str, Any]:
    if not notifier.configured():
        raise HTTPException(400, "관리자 메일, SMTP 계정과 .env의 SMTP_PASSWORD를 먼저 설정해 주세요.")
    test_item = {
        "id": "TEST",
        "name": "테스트 분실물",
        "expires_at": iso(utc_now()),
    }
    sent, error = notifier.send_due(test_item)
    if not sent:
        raise HTTPException(502, f"메일 발송 실패: {error}")
    store.create_activity("email_sent", "관리자 테스트 메일을 발송했습니다.")
    return {"ok": True, "message": "테스트 메일을 발송했습니다."}


@app.post("/api/camera/rebaseline")
def rebaseline_camera() -> dict[str, Any]:
    vision.rebaseline(reconcile_items=True)
    store.create_activity("baseline_reset", "관리자가 기준 장면을 다시 설정했습니다.")
    return {"ok": True, "message": "다음 안정 장면을 새 기준으로 사용합니다.", "camera": vision.get_status()}


@app.post("/api/maintenance/check-expirations")
def check_expirations() -> dict[str, Any]:
    expired = scheduler.run_once()
    return {"ok": True, "processed": len(expired)}


@app.post("/api/maintenance/reset")
def reset_operational_data(request: ResetRequest) -> dict[str, Any]:
    if request.confirmation != RESET_CONFIRMATION:
        raise HTTPException(400, "확인 문구가 일치하지 않아 초기화를 취소했습니다.")
    if not _reset_lock.acquire(blocking=False):
        raise HTTPException(409, "다른 초기화 작업이 이미 진행 중입니다.")

    try:
        # Stopping the producer first drains camera callbacks. Pending remote
        # classifications become harmless because their item rows no longer
        # exist when they return.
        vision.stop()
        scheduler.stop()
        try:
            with _item_mutation_lock:
                with store.maintenance_window():
                    result = backup_and_reset_operational_data()
            vision.rebaseline()
        except Exception as exc:
            logger.exception("Operational data reset failed")
            raise HTTPException(
                500,
                "초기화 중 오류가 발생했습니다. 생성된 백업은 삭제하지 않았습니다.",
            ) from exc
        finally:
            scheduler.start()
            vision.start()
    finally:
        _reset_lock.release()

    return {
        "ok": True,
        "message": "운영 데이터를 초기화했습니다. 설정과 API 키는 유지됩니다.",
        **result,
    }


@app.get("/camera/stream", include_in_schema=False)
def camera_stream() -> StreamingResponse:
    def frames() -> Generator[bytes, None, None]:
        stream_fps = float(current_settings().get("preview_stream_fps", 8.0))
        frame_delay = 1.0 / max(1.0, min(15.0, stream_fps))
        while True:
            frame = vision.get_jpeg()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n" + frame + b"\r\n"
            time.sleep(frame_delay)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
