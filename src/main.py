# Python Ver 3.11.9
# 꼭 가상환경 설치 후 가상환경 실행 한 다음 requirements.txt로 PIP 다운 받고, 작업, 실행.

'''
Setting_Guide.md 확인
'''

import cv2
import time
import os
import re
import base64
import requests
from datetime import datetime
from ultralytics import YOLO
from dotenv import load_dotenv
from openai import OpenAI

# ==========================================
# [1. 디렉토리 경로 동적 설정]
# ==========================================
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
ASSET_DIR = os.path.join(SRC_DIR, "asset")
CROP_DIR = os.path.join(ASSET_DIR, "crops")
os.makedirs(CROP_DIR, exist_ok=True)

# ==========================================
# [2. 환경 변수 및 API 초기화]
# ==========================================
env_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print(f"🚨 에러: .env 파일을 찾을 수 없거나 OPENAI_API_KEY가 없습니다!\n확인 경로: {env_path}")
    exit()

client = OpenAI(api_key=OPENAI_API_KEY)

# ==========================================
# [3. AI 모델 및 동작 파라미터 설정]
# ==========================================
MOTION_THRESHOLD = 20
MIN_MOTION_AREA = 5000
STABILIZATION_TIME = 2.0
STARTUP_GRACE_PERIOD = 3.0 # 시작 후 배경을 학습하고 초기 상태를 기억할 시간(초)
IOU_THRESHOLD = 0.5        # 기존 물체와 50% 이상 겹치면 같은 물체로 간주

BACKEND_URL = "http://localhost:8000"
CAMERA_ID   = "cam_01"

# GPT 응답에서 카테고리 키워드를 3개 중 하나로 정규화
CATEGORY_KEYWORDS = {
    "고가품": "고가품",
    "비음식물": "비음식물",
    "음식물": "음식물",
}

def parse_gpt_response(text):
    """GPT 응답 텍스트에서 object_name, category, freshness를 추출합니다."""
    object_name = "알 수 없음"
    category    = "비음식물"
    freshness   = "해당없음"

    for line in text.splitlines():
        line = line.strip()
        # "1. 물체: 에어팟 프로" 또는 "물체: 에어팟 프로" 형태 모두 처리
        if re.search(r"물체\s*[:：]", line):
            object_name = re.sub(r".*물체\s*[:：]\s*", "", line).strip()
        elif re.search(r"카테고리\s*[:：]", line):
            raw = re.sub(r".*카테고리\s*[:：]\s*", "", line).strip()
            for keyword, value in CATEGORY_KEYWORDS.items():
                if keyword in raw:
                    category = value
                    break
        elif re.search(r"신선도\s*[:：]|신선\s*여부\s*[:：]", line):
            freshness = re.sub(r".*[:：]\s*", "", line).strip()

    return object_name, category, freshness


def send_to_backend(object_name, category, freshness, raw_ai_response,
                    crop_path, full_image_path, bbox, confidence):
    """파싱된 결과를 백엔드 /save 엔드포인트로 전송합니다."""
    x1, y1, x2, y2 = bbox
    payload = {
        "object_name":    object_name,
        "category":       category,
        "image_url":      crop_path,
        "full_image_url": full_image_path,
        "yolo_confidence": round(float(confidence), 4),
        "freshness":      freshness,
        "camera_id":      CAMERA_ID,
        "raw_ai_response": raw_ai_response,
        "bbox": {
            "x": x1,
            "y": y1,
            "w": x2 - x1,
            "h": y2 - y1,
        },
    }
    try:
        res = requests.post(f"{BACKEND_URL}/save", json=payload, timeout=10)
        if res.status_code == 200:
            print(f"   -> ✅ 백엔드 저장 완료: {object_name} / {category}")
        else:
            print(f"   -> ⚠️  백엔드 응답 오류: {res.status_code} {res.text}")
    except requests.exceptions.ConnectionError:
        print(f"   -> 🚨 백엔드 연결 실패 (서버가 실행 중인지 확인하세요: {BACKEND_URL})")

print("Loading Local AI Model (YOLOv8n)...")
model = YOLO('yolov8n.pt') 
print("YOLO Model Loaded.")


# ==========================================
# [4. 핵심 기능 함수 (IoU 및 API)]
# ==========================================

def calculate_iou(boxA, boxB):
    """두 바운딩 박스가 겹치는 비율(IoU)을 계산하여 같은 물체인지 판단합니다."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0: return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_with_openai(image_path, full_image_path="", bbox=None, confidence=0.0):
    print(f"   -> 🤖 OpenAI에 '새로운 물건' 분석 요청 중... ({os.path.basename(image_path)})")
    base64_image = encode_image_to_base64(image_path)

    prompt_text = (
        "이 이미지는 분실물 바구니에서 새로 발견된 물건입니다. "
        "다음 세 가지를 분석해서 정확히 답변해 주세요:\n"
        "1. 물체: (예: 에어팟 프로, 먹다 남은 빵, 충전기)\n"
        "2. 카테고리: (음식물 / 비음식물 / 고가품 중 택 1)\n"
        "   - 음식물: 먹을 수 있는 식품류\n"
        "   - 고가품: 스마트폰, 지갑, 이어폰, 시계 등 고가 전자기기·귀중품\n"
        "   - 비음식물: 그 외 나머지\n"
        "3. 신선도: (음식물인 경우만 신선/의심/부패 중 택 1, 아니면 해당없음)"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            max_tokens=150
        )
        result_text = response.choices[0].message.content.strip()
        print("\n================ [ AI 분석 결과 ] ================")
        print(result_text)
        print("==================================================\n")

        object_name, category, freshness = parse_gpt_response(result_text)
        send_to_backend(
            object_name     = object_name,
            category        = category,
            freshness       = freshness,
            raw_ai_response = result_text,
            crop_path       = image_path,
            full_image_path = full_image_path,
            bbox            = bbox if bbox else (0, 0, 0, 0),
            confidence      = confidence,
        )
        return result_text
    except Exception as e:
        print(f"   -> 🚨 OpenAI API 호출 실패: {e}")
        return None

def perform_object_detection_and_crop(frame, timestamp, known_boxes, is_initial_scan=False):
    """YOLO를 실행하고, 기존 물체(known_boxes)와 겹치지 않는 '새 물체'만 처리합니다."""
    if is_initial_scan:
        print(f"\n[초기화] 기존 배경 및 물체 학습 중...")
    else:
        print(f"\n[AI 분석 시작] 안정화된 화면 분석 중... (Timestamp: {timestamp})")

    # 전체 프레임을 full_image로 저장 (AR 마스킹용)
    full_image_path = ""
    if not is_initial_scan:
        full_image_path = os.path.join(ASSET_DIR, f"full_{timestamp}.jpg")
        cv2.imwrite(full_image_path, frame)

    start_time = time.time()
    results = model.predict(frame, conf=0.4, verbose=False)

    current_boxes = [] # 방금 화면에서 찾은 모든 물체들의 위치
    new_object_count = 0

    for result in results:
        for i, box in enumerate(result.boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            current_box = (x1, y1, x2, y2)
            current_boxes.append(current_box) # 현재 상태로 등록

            # 초기 스캔일 경우, 화면의 박스들만 기억하고 API 전송은 생략
            if is_initial_scan:
                continue

            # --- [새 물체 필터링 (IoU)] ---
            is_new = True
            for known_box in known_boxes:
                # 기존 박스와 50% 이상 겹치면 원래 있던 물체로 간주
                if calculate_iou(current_box, known_box) > IOU_THRESHOLD:
                    is_new = False
                    break

            if is_new: # 완전히 새로운 물체일 때만!
                cropped_img = frame[y1:y2, x1:x2]
                if cropped_img.size == 0: continue

                crop_filename = os.path.join(CROP_DIR, f"crop_{timestamp}_{i}.jpg")
                cv2.imwrite(crop_filename, cropped_img)
                new_object_count += 1
                print(f"   -> ✨ [NEW] 객체 크롭 완료: {crop_filename}")
                analyze_with_openai(
                    image_path      = crop_filename,
                    full_image_path = full_image_path,
                    bbox            = (x1, y1, x2, y2),
                    confidence      = confidence,
                )
            else:
                # 디버깅용 (실제 운영시엔 주석처리해도 됨)
                print("   -> ♻️ [기존 물체] 무시됨 (API 호출 안함)")

    end_time = time.time()
    if not is_initial_scan:
        print(f"[프로세스 완료] 새로운 물체 {new_object_count}개 처리. 소요시간: {end_time - start_time:.2f}초")
        
    # 현재 화면의 박스 리스트를 반환하여 known_boxes를 최신 상태로 업데이트
    return current_boxes, new_object_count

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("에러: 카메라를 열 수 없습니다.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_frame = None
    is_motion_detected = False
    motion_stop_time = 0
    is_waiting_for_stabilization = False
    
    # 객체 추적 상태 변수
    known_boxes = [] 
    startup_time = time.time()
    is_initialized = False

    print("\n------------------------------------------------")
    print("분실물 관리 시스템 실행 중 (객체 추적 기능 활성화)")
    print("------------------------------------------------\n")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        display_frame = frame.copy()
        h, w, _ = frame.shape

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_frame is None:
            prev_frame = gray
            continue

        # 1. 초기 배경 학습 및 기준점 설정 (시작 후 3초간)
        elapsed_time = time.time() - startup_time
        if not is_initialized:
            if elapsed_time < STARTUP_GRACE_PERIOD:
                cv2.putText(display_frame, f"Initializing Background... {int(STARTUP_GRACE_PERIOD - elapsed_time)}s", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imshow("Lost & Found AI", display_frame)
                prev_frame = gray
                cv2.waitKey(1)
                continue
            else:
                # 3초가 지난 시점의 화면을 '초기 상태'로 저장
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                known_boxes, _ = perform_object_detection_and_crop(frame, timestamp, known_boxes, is_initial_scan=True)
                is_initialized = True
                print("\n✅ 초기화 완료! 이제 새로운 분실물을 감지합니다.")

        # 2. 모션 감지 로직
        frame_delta = cv2.absdiff(prev_frame, gray)
        _, thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        is_motion_now = False
        
        for contour in contours:
            if cv2.contourArea(contour) < MIN_MOTION_AREA: continue
            (x, y, w_box, h_box) = cv2.boundingRect(contour)
            cv2.rectangle(display_frame, (x, y), (x + w_box, y + h_box), (0, 255, 0), 2)
            is_motion_now = True

        # 3. 상태 관리 (안정화)
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
                status_text = f"Stabilizing ({wait_time:.1f}s / {STABILIZATION_TIME}s)"
                status_color = (255, 255, 0)

                # 지정 시간 안정화 완료 시 분석 트리거
                if wait_time >= STABILIZATION_TIME:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # 새로운 박스 찾기 및 known_boxes 최신화
                    known_boxes, new_count = perform_object_detection_and_crop(frame, timestamp, known_boxes)
                    
                    is_motion_detected = False
                    is_waiting_for_stabilization = False
                    status_text = "Status: AI Analyzed!"
                    status_color = (0, 255, 0)
                    
                    # 화면 피드백 (새로운 물체가 있을때만 초록색 번쩍임)
                    flash_color = (0, 255, 0) if new_count > 0 else (200, 200, 200)
                    flash_text = "NEW ITEM CAPTURED!" if new_count > 0 else "UPDATED STATE"
                    cv2.rectangle(display_frame, (0,0), (w,h), flash_color, -1)
                    cv2.putText(display_frame, flash_text, (w//2-200, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 4)
                    cv2.imshow("Lost & Found AI", display_frame)
                    cv2.waitKey(500) 
            else:
                status_text = f"Status: Monitoring (Known Items: {len(known_boxes)})"
                status_color = (255, 255, 255)

        # 기존 물체(known_boxes) 위치를 화면에 파란색 점선(약식)으로 시각화
        for (kx1, ky1, kx2, ky2) in known_boxes:
            cv2.rectangle(display_frame, (kx1, ky1), (kx2, ky2), (255, 100, 0), 1)

        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.imshow("Lost & Found AI", display_frame)
        prev_frame = gray

        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()