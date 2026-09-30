from __future__ import annotations

import os
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load a small, dependency-free subset of .env syntax."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(ROOT_DIR / ".env")


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _float(value: Any, default: float) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    data_dir: Path
    db_path: Path
    capture_dir: Path
    host: str
    port: int
    reload: bool
    hardware_profile: str
    classifier_workers: int
    classification_slots: int
    reference_cache_max_bytes: int
    openai_api_key: str
    gemini_api_key: str
    smtp_password: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        data_dir = Path(os.getenv("DATA_DIR", str(ROOT_DIR / "data"))).resolve()
        hardware_profile = os.getenv("HARDWARE_PROFILE", "desktop").strip().lower()
        is_raspberry_pi = hardware_profile in {"pi", "raspberry-pi", "raspberry_pi"}
        return cls(
            root_dir=ROOT_DIR,
            data_dir=data_dir,
            db_path=Path(os.getenv("DB_PATH", str(data_dir / "lost_items.db"))).resolve(),
            capture_dir=Path(os.getenv("CAPTURE_DIR", str(data_dir / "captures"))).resolve(),
            host=os.getenv("HOST", "127.0.0.1"),
            port=_int(os.getenv("PORT"), 8000),
            reload=_bool(os.getenv("RELOAD"), False),
            hardware_profile="raspberry-pi" if is_raspberry_pi else "desktop",
            classifier_workers=max(
                1, min(4, _int(os.getenv("CLASSIFIER_WORKERS"), 1 if is_raspberry_pi else 2))
            ),
            classification_slots=max(
                1, min(16, _int(os.getenv("CLASSIFICATION_SLOTS"), 4 if is_raspberry_pi else 8))
            ),
            reference_cache_max_bytes=max(
                8, min(256, _int(os.getenv("REFERENCE_CACHE_MAX_MB"), 32 if is_raspberry_pi else 64))
            )
            * 1024
            * 1024,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
        )


DEFAULT_SETTINGS: dict[str, Any] = {
    "provider": "auto",
    "openai_model": "gpt-5.6-luna",
    "gemini_model": "gemini-3.5-flash-lite",
    "ai_min_confidence": 0.5,
    "valuable_value_threshold_krw": 100000,
    "camera_index": 0,
    "camera_backend": "auto",
    "camera_width": 1280,
    "camera_height": 720,
    "camera_fps": 20,
    "monitor_fps": 12.0,
    "accumulated_check_fps": 4.0,
    "preview_stream_fps": 8.0,
    "preview_jpeg_quality": 84,
    "preview_max_width": 1280,
    "camera_mains_frequency_hz": 0,
    "jpeg_quality": 88,
    "stabilization_analysis_width": 480,
    "motion_threshold": 20,
    "motion_min_ratio": 0.001,
    "motion_min_area": 420,
    "change_threshold": 24,
    "min_change_area": 1800,
    "max_change_ratio": 0.42,
    "settle_seconds": 3.0,
    "stable_seconds": 1.2,
    "camera_retry_seconds": 5.0,
    "alert_lead_days": 7,
    "admin_email": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "",
    "smtp_use_tls": True,
    "privacy_mode": False,
    "site_name": "AI 분실물 보관소",
}

# Raspberry Pi 4 keeps high-resolution, quality-88 evidence crops for AI, but
# processes fewer frames, sends a lighter browser preview, and uses smaller
# alignment working images. This profile is enabled with
# HARDWARE_PROFILE=raspberry-pi and leaves desktop defaults intact.
if os.getenv("HARDWARE_PROFILE", "desktop").strip().lower() in {
    "pi",
    "raspberry-pi",
    "raspberry_pi",
}:
    DEFAULT_SETTINGS.update(
        {
            "camera_backend": "picamera2",
            "camera_fps": 10.0,
            "monitor_fps": 7.0,
            "accumulated_check_fps": 2.0,
            "preview_stream_fps": 5.0,
            "preview_jpeg_quality": 78,
            "preview_max_width": 800,
            "stabilization_analysis_width": 360,
        }
    )


SETTING_TYPES: dict[str, type] = {
    "provider": str,
    "openai_model": str,
    "gemini_model": str,
    "ai_min_confidence": float,
    "valuable_value_threshold_krw": int,
    "camera_index": int,
    "camera_backend": str,
    "camera_width": int,
    "camera_height": int,
    "camera_fps": float,
    "monitor_fps": float,
    "accumulated_check_fps": float,
    "preview_stream_fps": float,
    "preview_jpeg_quality": int,
    "preview_max_width": int,
    "camera_mains_frequency_hz": int,
    "jpeg_quality": int,
    "stabilization_analysis_width": int,
    "motion_threshold": int,
    "motion_min_ratio": float,
    "motion_min_area": int,
    "change_threshold": int,
    "min_change_area": int,
    "max_change_ratio": float,
    "settle_seconds": float,
    "stable_seconds": float,
    "camera_retry_seconds": float,
    "alert_lead_days": int,
    "admin_email": str,
    "smtp_host": str,
    "smtp_port": int,
    "smtp_username": str,
    "smtp_use_tls": bool,
    "privacy_mode": bool,
    "site_name": str,
}


def coerce_setting(key: str, value: Any) -> Any:
    target = SETTING_TYPES.get(key, str)
    if target is bool:
        return _bool(value)
    if target is int:
        return _int(value, int(DEFAULT_SETTINGS.get(key, 0)))
    if target is float:
        return _float(value, float(DEFAULT_SETTINGS.get(key, 0.0)))
    return str(value)


def validate_setting(key: str, value: Any) -> Any:
    """Parse an administrator input without silently replacing bad values."""
    target = SETTING_TYPES[key]
    if target is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (str, int)) and str(value).strip().lower() in {
            "1", "true", "yes", "on", "y", "0", "false", "no", "off", "n"
        }:
            return _bool(value)
        raise ValueError(f"{key}: 켜짐/꺼짐 값을 확인해 주세요.")
    if target in {int, float}:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"{key}: 숫자를 입력해 주세요.")
        try:
            number = float(value)
            if not math.isfinite(number) or (target is int and not number.is_integer()):
                raise ValueError
            return target(number)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{key}: 유효한 {'정수' if target is int else '숫자'}를 입력해 주세요.") from exc
    if not isinstance(value, str) or len(value) > 300 or "\n" in value or "\r" in value:
        raise ValueError(f"{key}: 300자 이내의 한 줄 문자열을 입력해 주세요.")
    value = value.strip()
    if key in {"site_name", "openai_model", "gemini_model"} and not value:
        raise ValueError(f"{key}: 빈 값은 사용할 수 없습니다.")
    return value


def public_provider_state(config: AppConfig, settings: dict[str, Any]) -> dict[str, Any]:
    requested = settings.get("provider", "auto")
    openai_ready = bool(config.openai_api_key)
    gemini_ready = bool(config.gemini_api_key)
    if requested == "openai" and openai_ready:
        active = "openai"
    elif requested == "gemini" and gemini_ready:
        active = "gemini"
    elif requested == "auto":
        active = "openai" if openai_ready else "gemini" if gemini_ready else "offline"
    else:
        active = "offline"
    return {
        "requested": requested,
        "active": active,
        "openai_configured": openai_ready,
        "gemini_configured": gemini_ready,
        "model": settings.get(
            "openai_model" if active == "openai" else "gemini_model", "로컬 폴백"
        )
        if active != "offline"
        else "로컬 폴백",
    }
