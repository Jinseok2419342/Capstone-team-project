from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import glob
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# asset 폴더 정적 서빙 (백엔드 실행 위치 기준 ../asset)
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "asset")
ASSET_DIR = os.path.normpath(ASSET_DIR)
if os.path.isdir(ASSET_DIR):
    app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")

# Firebase 연결
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class LostItem(BaseModel):
    object_name: str
    category: str
    image_url: str
    full_image_url: str
    yolo_confidence: float
    freshness: str
    camera_id: str
    raw_ai_response: str
    bbox: BBox


@app.get("/")
def home():
    return {"message": "서버 실행 중"}


@app.post("/save")
def save_item(item: LostItem):

    dispose_days_map = {
        "음식물": 1,
        "비음식물": 30,
        "고가품": 180
    }

    dispose_days = dispose_days_map.get(
        item.category,
        30
    )

    data = {
        "object_name": item.object_name,
        "category": item.category,
        "dispose_days": dispose_days,
        "found_at": datetime.now(timezone.utc),
        "dispose_at": datetime.now(timezone.utc) + timedelta(days=dispose_days),
        "status": "stored",
        "image_url": item.image_url,
        "full_image_url": item.full_image_url,
        "bbox": item.bbox.dict(),
        "yolo_confidence": item.yolo_confidence,
        "freshness": item.freshness,
        "camera_id": item.camera_id,
        "raw_ai_response": item.raw_ai_response,
        "notified": False
    }

    db.collection("lost_items").add(data)

    return {"message": "저장 완료"}


@app.get("/snapshot")
def get_snapshot():
    # asset 폴더에서 가장 최신 full_*.jpg 반환
    pattern = os.path.join(ASSET_DIR, "full_*.jpg")
    files = sorted(glob.glob(pattern))
    if files:
        return FileResponse(files[-1], media_type="image/jpeg")
    return JSONResponse(status_code=404, content={"error": "스냅샷 없음"})


@app.get("/items")
def get_items(category: str = Query(default=None)):

    query = db.collection("lost_items")
    if category:
        query = query.where("category", "==", category)
    docs = query.stream()

    result = []

    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id
        if hasattr(item.get("found_at"), "isoformat"):
            dt = item["found_at"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            item["found_at"] = dt.isoformat()
        if hasattr(item.get("dispose_at"), "isoformat"):
            dt = item["dispose_at"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            item["dispose_at"] = dt.isoformat()
        result.append(item)

    return result