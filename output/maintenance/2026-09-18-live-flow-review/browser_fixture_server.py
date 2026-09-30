"""Local browser regression fixture. Run directly; never a deployment entrypoint.

The real FastAPI routes/SQLite/classification/scheduler services run against a
fresh directory under this file's output directory. All imagery and observations
are synthetic. Camera, VLM and SMTP transports cannot contact real equipment or
services. No application source or operational .env/data files are changed.
"""

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
REVIEW_DIR = Path(__file__).resolve().parent


def build_fixture():
    if "app.main" in sys.modules or "app.config" in sys.modules:
        raise RuntimeError("Run this isolated fixture in a fresh Python process.")
    if not REVIEW_DIR.is_relative_to((ROOT / "output").resolve()):
        raise RuntimeError("Fixture data must remain under the workspace output directory.")
    fixture_dir = Path(tempfile.mkdtemp(prefix="browser-fixture-", dir=REVIEW_DIR)).resolve()
    data_dir = fixture_dir / "data"
    capture_dir = data_dir / "captures"
    capture_dir.mkdir(parents=True)
    # Override inherited credentials before app.config is imported. These are
    # explicit fake strings; SMTP and VLM implementations below never network.
    os.environ.update({
        "DATA_DIR": str(data_dir), "DB_PATH": str(data_dir / "fixture.sqlite3"),
        "CAPTURE_DIR": str(capture_dir), "HOST": "127.0.0.1", "PORT": "8765",
        "RELOAD": "false", "HARDWARE_PROFILE": "desktop",
        "CLASSIFIER_WORKERS": "2", "CLASSIFICATION_SLOTS": "4",
        "OPENAI_API_KEY": "synthetic-fixture-key-not-valid",
        "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
        "SMTP_PASSWORD": "synthetic-fixture-password-not-valid",
    })
    sys.path.insert(0, str(ROOT))
    actual_read_text = Path.read_text
    operational_dotenv = (ROOT / ".env").resolve()

    def without_operational_dotenv(path, *args, **kwargs):
        if path.resolve() == operational_dotenv:
            return ""
        return actual_read_text(path, *args, **kwargs)

    with patch.object(Path, "read_text", without_operational_dotenv):
        from app import main
        from app.ai import Classification
        from app.notifier import EmailNotifier, ExpirationScheduler
        from app.vision import ChangeEvent, VisionStatus

    import cv2
    import numpy as np
    from dataclasses import asdict
    from fastapi import HTTPException
    from pydantic import BaseModel, Field

    fixture_lock = threading.RLock()
    mail_calls = []
    classification_calls = []
    classifier_jobs = {}

    def encode(frame):
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise RuntimeError("Could not encode synthetic fixture image")
        return jpeg.tobytes()

    def scene(label="SYNTHETIC TEST", bbox=None):
        frame = np.full((360, 640, 3), (221, 218, 210), np.uint8)
        cv2.putText(frame, "SYNTHETIC TEST - NO LIVE CAMERA", (25, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (30, 65, 90), 2)
        for x in range(40, 640, 60):
            cv2.line(frame, (x, 55), (x, 345), (200, 199, 196), 1)
        if bbox:
            x, y, width, height = bbox
            cv2.rectangle(frame, (x, y), (x + width - 1, y + height - 1), (65, 80, 105), -1)
            cv2.line(frame, (x + 8, y + 8), (x + width - 10, y + height - 10), (155, 175, 210), 4)
            cv2.putText(frame, str(label)[:15], (x + 5, y + height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (245, 245, 245), 1)
        return frame

    class SyntheticVision:
        def __init__(self):
            self.privacy = False
            self.sequence = 0
            self.last_baseline = time.time()
            self.preview = encode(scene(bbox=(205, 125, 170, 135)))
            privacy_frame = np.full((360, 640, 3), (42, 42, 42), np.uint8)
            cv2.putText(privacy_frame, "SYNTHETIC TEST - PRIVACY ON", (45, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
            self.privacy_preview = encode(privacy_frame)

        def get_jpeg(self):
            self.sequence += 1
            return self.privacy_preview if self.privacy else self.preview

        def get_status(self):
            status = asdict(VisionStatus())
            status.update(
                running=True, camera_connected=True, using_fallback=False,
                privacy_enabled=self.privacy, phase="privacy" if self.privacy else "monitoring",
                baseline_ready=not self.privacy, inventory_connected=True,
                frame_width=640, frame_height=360, preview_width=640, preview_height=360,
                fps=7.0, processing_ms=2.0, frame_sequence=self.sequence,
                last_frame_at=time.time(), last_baseline_at=self.last_baseline,
                camera_diagnostics={"backend": "synthetic_test", "fixture": True},
            )
            return status

        def set_privacy(self, enabled):
            self.privacy = bool(enabled)

        def rebaseline(self, *, reconcile_items=False):
            self.last_baseline = time.time()

        def start(self):
            pass

        def stop(self, timeout=None):
            return True

    class SyntheticClassifier:
        def classify(self, images, *, scene_images=None):
            evidence = next((image for image in reversed(images) if image), b"")
            key = hashlib.sha256(evidence).hexdigest()
            with fixture_lock:
                job = dict(classifier_jobs.get(key, {"name": "합성 테스트 물품", "delay_seconds": 0, "category": "general"}))
                call = {"name": job["name"], "delay_seconds": job["delay_seconds"],
                        "started_at": time.time(), "finished_at": None}
                classification_calls.append(call)
            threading.Event().wait(float(job["delay_seconds"]))
            with fixture_lock:
                call["finished_at"] = time.time()
            return Classification(
                job["name"], "브라우저 검증용 합성 AI 응답입니다. 실제 외부 모델 호출이 없습니다.",
                job["category"], 0.97, "openai", action="added", raw="synthetic fixture response",
            )

    class SyntheticSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            return 250, b"synthetic fixture"

        def starttls(self, **kwargs):
            return 220, b"synthetic fixture"

        def login(self, *args):
            return 235, b"synthetic fixture"

        def send_message(self, message):
            with fixture_lock:
                mail_calls.append({"to": str(message["To"]), "subject": str(message["Subject"]),
                                   "sent_at": time.time(), "synthetic": True})
            return {}

    # Keep these replacements active for the lifetime of this fixture process.
    import app.notifier as notifier_module
    notifier_module.smtplib.SMTP = SyntheticSMTP
    notifier_module.smtplib.SMTP_SSL = SyntheticSMTP
    main.vision = SyntheticVision()
    main.classifier = SyntheticClassifier()
    main.store.initialize()
    main.store.update_settings({
        "site_name": "합성 브라우저 검증 · 운영 데이터 아님",
        "provider": "openai", "privacy_mode": False,
        "camera_width": 640, "camera_height": 360, "preview_stream_fps": 5.0,
        "admin_email": "fixture-admin@example.test", "smtp_host": "fixture.example.test",
        "smtp_port": 587, "smtp_username": "fixture-sender@example.test", "smtp_use_tls": True,
    })
    main.notifier = EmailNotifier(main.config, main.current_settings)
    main.scheduler = ExpirationScheduler(main.store, main.notifier)
    now = datetime.now(timezone.utc)
    seed_ids = {"all": [], "expired": [], "needs_review": [], "recovered": [], "disposed": [], "dismissed": []}
    for index in range(56):
        bbox = (120 + index % 4 * 25, 115 + index % 3 * 15, 130, 100)
        frame = scene(f"FIXTURE {index + 1:02d}", bbox)
        blank = scene()
        x, y, width, height = bbox
        crop = encode(frame[y:y + height, x:x + width])
        background = encode(blank[y:y + height, x:x + width])
        expired = index < 4
        needs_review = index in {0, 4, 8, 12, 16}
        status = "recovered" if index == 53 else "disposed" if index == 54 else "stored"
        review = "dismissed" if index == 55 else "needs_review" if needs_review else "confirmed"
        detected = now - timedelta(days=100 - index) if expired else now - timedelta(hours=56 - index)
        expires = now - timedelta(days=4 - index) if expired else now + timedelta(days=index - 3 if index < 9 else 30)
        item = main.store.create_item({
            "name": f"오래된 만료 물품 {index + 1:02d}" if expired else f"검증 물품 {index + 1:02d}",
            "description": "브라우저 회귀검증용 합성 자료입니다. 실제 카메라 관측이 아닙니다.",
            "category": ("valuable", "general", "food")[index % 3],
            "detected_at": detected, "expires_at": expires, "status": status,
            "review_status": review, "review_reason": "synthetic_fixture" if review != "confirmed" else None,
            "provider": "offline_review" if needs_review else "openai", "source_kind": "camera",
            "source_event_id": f"synthetic-seed-{index + 1}", "bbox": list(bbox), "confidence": 0.96,
            "image_path": main.save_capture(crop), "background_path": main.save_capture(background, "background"),
        })
        seed_ids["all"].append(item["id"])
        for group, belongs in (("expired", expired), ("needs_review", needs_review),
                               ("recovered", status == "recovered"), ("disposed", status == "disposed"),
                               ("dismissed", review == "dismissed")):
            if belongs:
                seed_ids[group].append(item["id"])

    class ObservationRequest(BaseModel):
        name: str = Field(default="브라우저 자동 분석", min_length=1, max_length=80)
        delay_seconds: float = Field(default=0, ge=0, le=30)
        category: Literal["valuable", "general", "food"] = "general"

    class MoveRequest(BaseModel):
        dx: int = Field(default=30, ge=-300, le=300)
        dy: int = Field(default=0, ge=-200, le=200)

    def event_for(bbox, label, *, kind="added", item=None):
        blank = scene()
        present = scene(label, bbox)
        x, y, width, height = bbox
        before_scene = present if kind == "removed" else blank
        after_scene = blank if kind == "removed" else present
        before = encode(before_scene[y:y + height, x:x + width])
        after = encode(after_scene[y:y + height, x:x + width])
        if kind == "moved" and item and item.get("bbox"):
            before_scene = scene(f"BEFORE {item['id']}", item["bbox"])
        return ChangeEvent(
            kind=kind, bbox=tuple(bbox), before_jpeg=before, after_jpeg=after, crop_jpeg=after,
            confidence=0.96, scene_before_jpeg=encode(before_scene), scene_after_jpeg=encode(after_scene),
            matched_item_id=item["id"] if item else None,
            expected_revision=item["tracking_revision"] if item else None,
        )

    @main.app.post("/__test__/observation")
    def observation(request: ObservationRequest):
        label = f"JOB {time.time_ns() % 100000000:08d}"
        event = event_for((210, 130, 160, 125), label)
        with fixture_lock:
            classifier_jobs[hashlib.sha256(event.after_jpeg).hexdigest()] = request.model_dump()
        if not main.handle_vision_change(event):
            raise HTTPException(503, "Synthetic observation could not be persisted")
        main.vision.preview = event.scene_after_jpeg
        item = main.store.get_item_by_source_event(event.event_id)
        return {**main.item_for_api(item), "synthetic": True}

    @main.app.post("/__test__/move/{item_id}")
    def move(item_id: int, request: MoveRequest = MoveRequest()):
        item = main.store.get_item(item_id)
        if not item:
            raise HTTPException(404, "Fixture item not found")
        x, y, width, height = item["bbox"] or [210, 130, 160, 125]
        bbox = (max(0, min(640 - width, x + request.dx)), max(55, min(360 - height, y + request.dy)), width, height)
        event = event_for(bbox, f"MOVED {item_id}", kind="moved", item=item)
        if not main.handle_vision_change(event):
            raise HTTPException(503, "Synthetic move could not be persisted")
        main.vision.preview = event.scene_after_jpeg
        return {**main.item_for_api(main.store.get_item(item_id)), "synthetic": True}

    @main.app.post("/__test__/remove/{item_id}")
    def remove(item_id: int):
        item = main.store.get_item(item_id)
        if not item:
            raise HTTPException(404, "Fixture item not found")
        event = event_for(item["bbox"] or [210, 130, 160, 125], f"REMOVED {item_id}", kind="removed", item=item)
        if not main.handle_vision_change(event):
            raise HTTPException(503, "Synthetic removal could not be persisted")
        main.vision.preview = event.scene_after_jpeg
        return {**main.item_for_api(main.store.get_item(item_id)), "synthetic": True}

    @main.app.get("/__test__/state")
    def state():
        items = main.store.list_items(limit=1000)
        with fixture_lock:
            return {
                "synthetic": True, "fixture_dir": str(fixture_dir), "db_path": str(main.config.db_path),
                "capture_dir": str(main.config.capture_dir), "seed_ids": seed_ids,
                "item_count": len(items), "visible_count": main.store.list_items_page()["total"],
                "stats": main.store.item_stats(), "pending_ids": [item["id"] for item in items if item["review_status"] == "pending"],
                "mail_count": len(mail_calls), "mail_calls": list(mail_calls),
                "classification_calls": [dict(call) for call in classification_calls],
                "items": [{key: item[key] for key in ("id", "name", "status", "review_status", "tracking_revision", "bbox")}
                          for item in items],
            }

    return main.app, state


if __name__ == "__main__":
    import uvicorn
    app, fixture_state = build_fixture()
    print(json.dumps({"url": "http://127.0.0.1:8765", **fixture_state()}, ensure_ascii=False), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8765, lifespan="off", access_log=False)
