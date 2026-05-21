from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from openai import OpenAI
from ultralytics import YOLO


SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
ASSET_DIR = SRC_DIR / "asset"
CROP_DIR = ASSET_DIR / "crops"
SNAPSHOT_PATH = ASSET_DIR / "snapshot.jpg"

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DEFAULT_BACKEND_URL = "http://localhost:8000"

MOTION_THRESHOLD = 20
MIN_MOTION_AREA = 5000
STABILIZATION_TIME = 2.0
STARTUP_GRACE_PERIOD = 3.0
IOU_THRESHOLD = 0.5
BACKEND_TIMEOUT = 1.0

FOOD_LABELS = {
    "apple",
    "banana",
    "broccoli",
    "cake",
    "carrot",
    "donut",
    "hot dog",
    "orange",
    "pizza",
    "sandwich",
}

VALUABLE_LABELS = {
    "cell phone",
    "keyboard",
    "laptop",
    "mouse",
    "remote",
    "tv",
    "watch",
}

KOREAN_LABELS = {
    "backpack": "가방",
    "book": "책",
    "bottle": "병",
    "cell phone": "휴대폰",
    "cup": "컵",
    "handbag": "가방",
    "keyboard": "키보드",
    "laptop": "노트북",
    "mouse": "마우스",
    "remote": "리모컨",
    "sports ball": "공",
    "suitcase": "캐리어",
    "umbrella": "우산",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="분실물 자동 감지 메인 프로그램")
    parser.add_argument("--camera", type=int, default=0, help="사용할 카메라 번호")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL))
    parser.add_argument("--backend-timeout", type=float, default=float(os.getenv("BACKEND_TIMEOUT", BACKEND_TIMEOUT)))
    parser.add_argument("--model", default=os.getenv("YOLO_MODEL", "yolo26s.pt"), help="YOLO 모델 파일 경로")
    parser.add_argument("--yolo-conf", type=float, default=float(os.getenv("YOLO_CONF", "0.4")))
    parser.add_argument("--initial-yolo-conf", type=float, default=float(os.getenv("INITIAL_YOLO_CONF", "0.4")))
    parser.add_argument("--motion-threshold", type=int, default=int(os.getenv("MOTION_THRESHOLD", MOTION_THRESHOLD)))
    parser.add_argument("--min-motion-area", type=int, default=int(os.getenv("MIN_MOTION_AREA", MIN_MOTION_AREA)))
    parser.add_argument("--stabilization-time", type=float, default=float(os.getenv("STABILIZATION_TIME", STABILIZATION_TIME)))
    parser.add_argument("--startup-grace", type=float, default=float(os.getenv("STARTUP_GRACE_PERIOD", STARTUP_GRACE_PERIOD)))
    parser.add_argument("--no-ai", action="store_true", help="OpenAI 호출 없이 YOLO 라벨 기반으로 저장")
    parser.add_argument("--once-image", help="카메라 대신 이미지 1장을 분석하고 종료")
    return parser.parse_args()


def setup_environment() -> OpenAI | None:
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[main] OPENAI_API_KEY가 없어 YOLO 라벨 기반 분류로 실행합니다.")
        return None
    return OpenAI(api_key=api_key)


def resolve_model_path(model_arg: str) -> Path | str:
    candidates = [Path(model_arg)] if model_arg else []
    candidates.extend([ROOT_DIR / "yolo26s.pt", ROOT_DIR / "yolov8n.pt", SRC_DIR / "yolov8n.pt"])

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return model_arg or "yolov8n.pt"


def calculate_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])

    inter_area = max(0, x_b - x_a) * max(0, y_b - y_a)
    if inter_area == 0:
        return 0.0

    box_a_area = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    box_b_area = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return inter_area / float(box_a_area + box_b_area - inter_area)


def encode_image_to_base64(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def normalize_category(value: str) -> str:
    if "고가" in value:
        return "고가품"
    if "음식" in value and "비음식" not in value:
        return "음식물"
    return "비음식물"


def fallback_analysis(label: str) -> dict[str, str]:
    category = "비음식물"
    if label in FOOD_LABELS:
        category = "음식물"
    elif label in VALUABLE_LABELS:
        category = "고가품"

    return {
        "object_name": KOREAN_LABELS.get(label, label or "알 수 없음"),
        "category": category,
        "freshness": "확인 필요" if category == "음식물" else "해당 없음",
        "raw_ai_response": f"fallback_label={label}, category={category}",
    }


def parse_ai_response(text: str, fallback: dict[str, str]) -> dict[str, str]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        data = json.loads(cleaned)
        return {
            "object_name": str(data.get("object_name") or data.get("물체") or fallback["object_name"]),
            "category": normalize_category(str(data.get("category") or data.get("카테고리") or fallback["category"])),
            "freshness": str(data.get("freshness") or data.get("신선도") or fallback["freshness"]),
            "raw_ai_response": text,
        }
    except json.JSONDecodeError:
        pass

    object_name = fallback["object_name"]
    category = fallback["category"]
    freshness = fallback["freshness"]

    for line in cleaned.splitlines():
        if "물체" in line or "object" in line.lower():
            object_name = line.split(":", 1)[-1].strip(" -")
        elif "카테고리" in line or "category" in line.lower():
            category = normalize_category(line.split(":", 1)[-1].strip(" -"))
        elif "신선" in line or "fresh" in line.lower():
            freshness = line.split(":", 1)[-1].strip(" -")

    return {
        "object_name": object_name,
        "category": category,
        "freshness": freshness,
        "raw_ai_response": text,
    }


def analyze_crop(client: OpenAI | None, image_path: Path, label: str, no_ai: bool) -> dict[str, str]:
    fallback = fallback_analysis(label)
    if no_ai or client is None:
        return fallback

    prompt = (
        "이 이미지는 분실물 바구니에서 새로 발견된 물건입니다. "
        "이미지가 작거나 일부만 보이더라도 가장 가능성이 높은 물체명을 추론하세요. "
        "물체명, 카테고리, 신선도를 JSON 하나로만 답하세요. "
        "category는 반드시 음식물, 비음식물, 고가품 중 하나입니다. "
        "freshness는 음식물이 아니면 '해당 없음'으로 답하세요. "
        '예: {"object_name":"에어팟 프로","category":"고가품","freshness":"해당 없음"}'
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encode_image_to_base64(image_path)}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=220,
        )
        text = response.choices[0].message.content or ""
        analysis = parse_ai_response(text, fallback)
        print(f"   -> 분석 결과: {analysis['object_name']} / {analysis['category']}")
        return analysis
    except Exception as exc:
        print(f"   -> OpenAI 호출 실패, fallback 사용: {exc}")
        return fallback


def check_backend(backend_url: str, timeout: float) -> bool:
    try:
        response = requests.get(f"{backend_url.rstrip('/')}/health", timeout=timeout)
        response.raise_for_status()
        data = response.json()
        print(f"[main] 백엔드 연결 확인: storage={data.get('storage', 'unknown')}")
        return True
    except Exception as exc:
        print(f"[main] 백엔드 연결 안 됨: {backend_url} ({exc})")
        print("[main] 감지는 계속하지만 대시보드 저장은 건너뜁니다.")
        return False


def send_to_backend(
    backend_url: str,
    analysis: dict[str, str],
    crop_path: Path,
    bbox: tuple[int, int, int, int],
    confidence: float,
    timeout: float,
) -> str | None:
    x1, y1, x2, y2 = bbox
    payload = {
        "object_name": analysis["object_name"],
        "category": analysis["category"],
        "image_url": str(crop_path),
        "full_image_url": str(SNAPSHOT_PATH) if SNAPSHOT_PATH.exists() else "",
        "yolo_confidence": confidence,
        "freshness": analysis["freshness"],
        "camera_id": "cam0",
        "raw_ai_response": analysis["raw_ai_response"],
        "bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = requests.post(f"{backend_url.rstrip('/')}/save", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        print(f"   -> 백엔드 저장 완료: {data}")
        item_id = data.get("id")
        return str(item_id) if item_id is not None else None
    except Exception as exc:
        print(f"   -> 백엔드 전송 실패: {exc}")
        return None


def mark_backend_processed(backend_url: str, item_id: str | None, timeout: float) -> bool:
    if not item_id:
        return False
    try:
        response = requests.post(f"{backend_url.rstrip('/')}/items/{item_id}/process", timeout=timeout)
        response.raise_for_status()
        print(f"   -> 회수 처리 완료: id={item_id}")
        return True
    except Exception as exc:
        print(f"   -> 회수 처리 실패: id={item_id} ({exc})")
        return False


def predict_boxes(model: YOLO, frame: Any, conf: float) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    results = model.predict(frame, conf=conf, verbose=False)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            class_id = int(box.cls[0]) if box.cls is not None else -1
            label = result.names.get(class_id, str(class_id))
            confidence = float(box.conf[0]) if box.conf is not None else 0.0
            detections.append({"box": (x1, y1, x2, y2), "label": label, "confidence": confidence})
    return detections


def perform_object_detection_and_crop(
    frame: Any,
    timestamp: str,
    known_items: list[dict[str, Any]],
    model: YOLO,
    client: OpenAI | None,
    args: argparse.Namespace,
    backend_available: bool,
    is_initial_scan: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    if is_initial_scan:
        print("\n[초기화] 현재 화면의 기존 YOLO 물체를 기억합니다.")
    else:
        print(f"\n[AI 분석 시작] 안정화된 전체 화면 분석 중... (Timestamp: {timestamp})")

    conf = args.initial_yolo_conf if is_initial_scan else args.yolo_conf
    detections = predict_boxes(model, frame, conf)

    if is_initial_scan:
        return [
            {
                "box": detection["box"],
                "id": None,
                "label": detection["label"],
                "missing_count": 0,
            }
            for detection in detections
        ], 0

    next_items: list[dict[str, Any]] = []
    new_count = 0

    for known in known_items:
        matching_detection = None
        for detection in detections:
            if calculate_iou(known["box"], detection["box"]) > IOU_THRESHOLD:
                matching_detection = detection
                break

        if matching_detection:
            known["box"] = matching_detection["box"]
            known["missing_count"] = 0
            next_items.append(known)
            continue

        print(f"   -> 회수된 물체로 처리: {known.get('label', 'unknown')} id={known.get('id')}")
        if backend_available:
            mark_backend_processed(args.backend_url, known.get("id"), args.backend_timeout)

    for index, detection in enumerate(detections):
        current_box = detection["box"]
        is_new = not any(calculate_iou(current_box, item["box"]) > IOU_THRESHOLD for item in next_items)
        if not is_new:
            print(f"   -> 기존 물체 무시: {detection['label']} ({detection['confidence']:.2f})")
            continue

        x1, y1, x2, y2 = current_box
        cropped = frame[y1:y2, x1:x2]
        if cropped.size == 0:
            continue

        crop_path = CROP_DIR / f"crop_{timestamp}_{index}.jpg"
        cv2.imwrite(str(crop_path), cropped)
        new_count += 1
        print(f"   -> [NEW] 객체 크롭 완료: {crop_path}")

        analysis = analyze_crop(client, crop_path, detection["label"], args.no_ai)
        item_id = None
        if backend_available:
            item_id = send_to_backend(args.backend_url, analysis, crop_path, current_box, detection["confidence"], args.backend_timeout)
        else:
            print("   -> 백엔드 미연결: 저장 건너뜀")

        next_items.append(
            {
                "box": current_box,
                "id": item_id,
                "label": analysis["object_name"],
                "missing_count": 0,
            }
        )

    print(f"[프로세스 완료] 새로운 물체 {new_count}개 처리")
    return next_items, new_count


def run_once_image(args: argparse.Namespace, model: YOLO, client: OpenAI | None) -> None:
    image = cv2.imread(args.once_image)
    if image is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {args.once_image}")

    CROP_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(SNAPSHOT_PATH), image)
    perform_object_detection_and_crop(
        image,
        datetime.now().strftime("%Y%m%d_%H%M%S"),
        [],
        model,
        client,
        args,
        check_backend(args.backend_url, args.backend_timeout),
        is_initial_scan=False,
    )


def run_camera(args: argparse.Namespace, model: YOLO, client: OpenAI | None) -> None:
    CROP_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"카메라를 열 수 없습니다. camera={args.camera}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    prev_frame = None
    is_motion_detected = False
    motion_stop_time = 0.0
    is_waiting_for_stabilization = False
    known_items: list[dict[str, Any]] = []
    startup_time = time.time()
    is_initialized = False
    backend_available = check_backend(args.backend_url, args.backend_timeout)

    print("\n------------------------------------------------")
    print("분실물 관리 시스템 실행 중 (단순 YOLO 전체 프레임 모드)")
    print("------------------------------------------------")
    print(
        f"model={args.model}, conf={args.yolo_conf}, camera={args.camera}, "
        f"ai={'off' if args.no_ai or client is None else 'on'}"
    )
    print("종료: 카메라 창에서 q\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display_frame = frame.copy()
        height, width, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_frame is None:
            prev_frame = gray
            continue

        elapsed_time = time.time() - startup_time
        if not is_initialized:
            if elapsed_time < args.startup_grace:
                cv2.putText(
                    display_frame,
                    f"Initializing Background... {int(args.startup_grace - elapsed_time)}s",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )
                cv2.imshow("Lost & Found AI", display_frame)
                prev_frame = gray
                cv2.waitKey(1)
                continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            known_items, _ = perform_object_detection_and_crop(
                frame,
                timestamp,
                known_items,
                model,
                client,
                args,
                backend_available,
                is_initial_scan=True,
            )
            is_initialized = True
            print("\n초기화 완료! 이제 새로운 분실물을 감지합니다.")

        frame_delta = cv2.absdiff(prev_frame, gray)
        _, thresh = cv2.threshold(frame_delta, args.motion_threshold, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        is_motion_now = False
        for contour in contours:
            if cv2.contourArea(contour) < args.min_motion_area:
                continue
            x, y, w_box, h_box = cv2.boundingRect(contour)
            cv2.rectangle(display_frame, (x, y), (x + w_box, y + h_box), (0, 255, 0), 2)
            is_motion_now = True

        if is_motion_now:
            is_motion_detected = True
            is_waiting_for_stabilization = False
            status_text = "Status: Motion Detected"
            status_color = (0, 0, 255)
        else:
            if is_motion_detected and not is_waiting_for_stabilization:
                motion_stop_time = time.time()
                is_waiting_for_stabilization = True
                status_text = "Status: Stabilizing..."
                status_color = (255, 255, 0)
            elif is_waiting_for_stabilization:
                wait_time = time.time() - motion_stop_time
                status_text = f"Stabilizing ({wait_time:.1f}s / {args.stabilization_time}s)"
                status_color = (255, 255, 0)

                if wait_time >= args.stabilization_time:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    cv2.imwrite(str(SNAPSHOT_PATH), frame)
                    known_items, new_count = perform_object_detection_and_crop(
                        frame,
                        timestamp,
                        known_items,
                        model,
                        client,
                        args,
                        backend_available,
                    )

                    is_motion_detected = False
                    is_waiting_for_stabilization = False
                    status_text = "Status: AI Analyzed"
                    status_color = (0, 255, 0)

                    flash_color = (0, 255, 0) if new_count > 0 else (200, 200, 200)
                    flash_text = "NEW ITEM CAPTURED" if new_count > 0 else "UPDATED STATE"
                    cv2.rectangle(display_frame, (0, 0), (width, height), flash_color, -1)
                    cv2.putText(
                        display_frame,
                        flash_text,
                        (max(10, width // 2 - 220), height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.3,
                        (0, 0, 0),
                        3,
                    )
                    cv2.imshow("Lost & Found AI", display_frame)
                    cv2.waitKey(500)
            else:
                status_text = f"Status: Monitoring (Known Items: {len(known_items)})"
                status_color = (255, 255, 255)

        for item in known_items:
            x1, y1, x2, y2 = item["box"]
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 100, 0), 1)

        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.imshow("Lost & Found AI", display_frame)
        prev_frame = gray

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    client = setup_environment()
    model_path = resolve_model_path(args.model)

    print(f"[main] YOLO 모델 로딩: {model_path}")
    model = YOLO(str(model_path))
    print("[main] YOLO 모델 로딩 완료")
    print("[main] 첫 감지 지연을 줄이기 위해 YOLO 워밍업 중...")
    warmup_frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    model.predict(warmup_frame, conf=0.25, verbose=False)
    print("[main] YOLO 워밍업 완료")

    if args.once_image:
        run_once_image(args, model, client)
    else:
        run_camera(args, model, client)


if __name__ == "__main__":
    main()
