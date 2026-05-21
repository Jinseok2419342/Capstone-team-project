from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import os
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


SNAPSHOT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "asset", "snapshot.jpg")
)

@app.get("/snapshot")
def get_snapshot():
    if os.path.isfile(SNAPSHOT_PATH):
        return FileResponse(
            SNAPSHOT_PATH,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(status_code=404, content={"error": "스냅샷 없음"})


@app.get("/items")
def get_items(category: str = Query(default=None)):

    docs = db.collection("lost_items").stream()

    result = []

    for doc in docs:
        d = doc.to_dict()
        item = {
            "id": doc.id,
            "name": d.get("object_name", ""),
            "category": d.get("category", ""),
            "detected_at": d.get("found_at").isoformat() if d.get("found_at") else None,
            "expires_at": d.get("dispose_at").isoformat() if d.get("dispose_at") else None,
            "image_path": d.get("image_url", ""),
            "bbox": {
                "x": d.get("bbox", {}).get("x", 0),
                "y": d.get("bbox", {}).get("y", 0),
                "width": d.get("bbox", {}).get("w", 0),
                "height": d.get("bbox", {}).get("h", 0),
            },
        }
        if category and item["category"] != category:
            continue
        result.append(item)

    return result