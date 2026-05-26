from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from .email_notify import send_status_email, smtp_configured

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:  # pragma: no cover - lets the demo run without Firebase deps.
    firebase_admin = None
    credentials = None
    firestore = None


BACKEND_DIR = Path(__file__).resolve().parent
SRC_DIR = BACKEND_DIR.parent
ROOT_DIR = SRC_DIR.parent
ASSET_DIR = SRC_DIR / "asset"
SNAPSHOT_PATH = ASSET_DIR / "snapshot.jpg"
LOCAL_DB_PATH = ASSET_DIR / "local_items.json"

load_dotenv(ROOT_DIR / ".env")

CATEGORY_DISPOSE_DAYS = {
    "음식물": 1,
    "비음식물": 30,
    "고가품": 180,
}

app = FastAPI(title="Lost & Found AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BBox(BaseModel):
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


class LostItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object_name: str = Field(default="알 수 없음")
    category: str = Field(default="비음식물")
    image_url: str = Field(default="")
    full_image_url: str = Field(default="")
    yolo_confidence: float = Field(default=0.0)
    freshness: str = Field(default="")
    camera_id: str = Field(default="cam0")
    raw_ai_response: str = Field(default="")
    bbox: BBox = Field(default_factory=BBox)
    detected_at: datetime | None = None


class LocalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, items: list[dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)

    def add(self, data: dict[str, Any]) -> str:
        items = self._read()
        next_id = str(max([int(item.get("id", 0)) for item in items] or [0]) + 1)
        stored = {"id": next_id, **_jsonable(data)}
        items.append(stored)
        self._write(items)
        return next_id

    def list(self) -> list[dict[str, Any]]:
        return self._read()

    def mark_processed(self, item_id: str) -> bool:
        items = self._read()
        found = False
        for item in items:
            if str(item.get("id")) == str(item_id):
                item["status"] = "processed"
                item["processed_at"] = _now().isoformat()
                found = True
                break
        if found:
            self._write(items)
        return found

    def clear(self) -> int:
        count = len(self._read())
        self._write([])
        return count


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_jsonable(inner) for inner in value]
    return value


def _find_firebase_key() -> Path | None:
    env_path = os.getenv("FIREBASE_CREDENTIALS")
    candidates = [
        Path(env_path) if env_path else None,
        BACKEND_DIR / "firebase-key.json",
        ROOT_DIR / "firebase-key.json",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def _init_firestore():
    if os.getenv("USE_FIREBASE", "auto").lower() in {"0", "false", "no", "off"}:
        print("[backend] USE_FIREBASE=false. Using local JSON store.")
        return None

    if firebase_admin is None:
        return None

    key_path = _find_firebase_key()
    if key_path is None:
        print("[backend] Firebase key not found. Using local JSON store.")
        return None

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(key_path))
            firebase_admin.initialize_app(cred)
        print(f"[backend] Firebase enabled: {key_path}")
        return firestore.client()
    except Exception as exc:
        print(f"[backend] Firebase init failed. Using local JSON store. ({exc})")
        return None


db = _init_firestore()
local_store = LocalStore(LOCAL_DB_PATH)


def _storage_mode() -> str:
    return "firebase" if db is not None else "local"


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _to_public_asset_url(value: str | None) -> str:
    if not value:
        return ""
    value = str(value)
    if value.startswith(("http://", "https://", "/assets/")):
        return value

    path = Path(value)
    if not path.is_absolute():
        path = (ROOT_DIR / value).resolve()
    else:
        path = path.resolve()

    try:
        relative = path.relative_to(ASSET_DIR.resolve())
    except ValueError:
        return value

    return "/assets/" + relative.as_posix()


def _build_storage_data(item: LostItem) -> dict[str, Any]:
    found_at = item.detected_at or _now()
    if found_at.tzinfo is None:
        found_at = found_at.replace(tzinfo=timezone.utc)

    category = item.category if item.category in CATEGORY_DISPOSE_DAYS else "비음식물"
    dispose_days = CATEGORY_DISPOSE_DAYS[category]

    return {
        "object_name": item.object_name,
        "category": category,
        "dispose_days": dispose_days,
        "found_at": found_at,
        "dispose_at": found_at + timedelta(days=dispose_days),
        "status": "stored",
        "image_url": item.image_url,
        "full_image_url": item.full_image_url,
        "bbox": item.bbox.model_dump(),
        "yolo_confidence": item.yolo_confidence,
        "freshness": item.freshness,
        "camera_id": item.camera_id,
        "raw_ai_response": item.raw_ai_response,
        "notified": False,
    }


def _format_item(item_id: str, data: dict[str, Any]) -> dict[str, Any]:
    found_at = _parse_datetime(data.get("found_at"))
    dispose_at = _parse_datetime(data.get("dispose_at"))
    bbox = data.get("bbox") or {}

    return {
        "id": str(item_id),
        "name": data.get("object_name", ""),
        "category": data.get("category", ""),
        "detected_at": found_at.isoformat() if found_at else None,
        "expires_at": dispose_at.isoformat() if dispose_at else None,
        "status": data.get("status", "stored"),
        "image_path": _to_public_asset_url(data.get("image_url", "")),
        "full_image_path": _to_public_asset_url(data.get("full_image_url", "")),
        "bbox": {
            "x": int(bbox.get("x", 0)),
            "y": int(bbox.get("y", 0)),
            "width": int(bbox.get("w", bbox.get("width", 0))),
            "height": int(bbox.get("h", bbox.get("height", 0))),
        },
    }


@app.get("/")
def home():
    return {"message": "서버 실행 중", "storage": _storage_mode()}


@app.get("/health")
def health():
    return {
        "ok": True,
        "storage": _storage_mode(),
        "snapshot_exists": SNAPSHOT_PATH.is_file(),
    }


@app.post("/save")
def save_item(item: LostItem):
    data = _build_storage_data(item)

    if db is not None:
        _, ref = db.collection("lost_items").add(data)
        item_id = ref.id
    else:
        item_id = local_store.add(data)

    return {"message": "저장 완료", "id": item_id, "storage": _storage_mode()}


def _list_public_items(
    category: str | None = None,
    include_processed: bool = False,
) -> list[dict[str, Any]]:
    if db is not None:
        docs = db.collection("lost_items").stream()
        raw_items = [(doc.id, doc.to_dict()) for doc in docs]
    else:
        raw_items = [(str(item.get("id")), item) for item in local_store.list()]

    result = []
    for item_id, data in raw_items:
        item = _format_item(item_id, data)
        if category and item["category"] != category:
            continue
        if not include_processed and item["status"] == "processed":
            continue
        result.append(item)

    result.sort(key=lambda row: row.get("detected_at") or "", reverse=True)
    return result


@app.get("/items")
def get_items(
    category: str | None = Query(default=None),
    include_processed: bool = Query(default=False),
):
    return _list_public_items(category=category, include_processed=include_processed)


@app.post("/notify/status-email")
def notify_status_email():
    if not smtp_configured():
        raise HTTPException(
            status_code=503,
            detail="이메일 설정이 완료되지 않았습니다. .env에 SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ADMIN_EMAIL을 설정하세요.",
        )

    items = _list_public_items()
    try:
        recipient = send_status_email(items)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail=f"이메일 전송 실패: {exc}") from exc

    return {
        "message": "관리자에게 현황 이메일을 보냈습니다.",
        "recipient": recipient,
        "item_count": len(items),
    }


@app.post("/items/{item_id}/process")
def process_item(item_id: str):
    if db is not None:
        ref = db.collection("lost_items").document(item_id)
        snapshot = ref.get()
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
        ref.update({"status": "processed", "processed_at": _now()})
        return {"message": "처리 완료", "id": item_id}

    if not local_store.mark_processed(item_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return {"message": "처리 완료", "id": item_id}


@app.delete("/items")
def clear_items():
    if db is not None:
        docs = list(db.collection("lost_items").stream())
        batch = db.batch()
        for index, doc in enumerate(docs, start=1):
            batch.delete(doc.reference)
            if index % 450 == 0:
                batch.commit()
                batch = db.batch()
        batch.commit()
        return {"message": "초기화 완료", "deleted": len(docs), "storage": _storage_mode()}

    count = local_store.clear()
    return {"message": "초기화 완료", "deleted": count, "storage": _storage_mode()}


@app.get("/snapshot")
def get_snapshot():
    if SNAPSHOT_PATH.is_file():
        return FileResponse(
            SNAPSHOT_PATH,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(status_code=404, content={"error": "스냅샷 없음"})


@app.get("/assets/{asset_path:path}")
def get_asset(asset_path: str):
    requested = (ASSET_DIR / asset_path).resolve()
    try:
        requested.relative_to(ASSET_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="허용되지 않은 경로입니다.")

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(requested, headers={"Cache-Control": "no-store"})
