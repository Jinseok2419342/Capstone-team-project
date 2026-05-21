"""
테스트용 더미 데이터를 백엔드 /save API를 통해 Firebase에 삽입합니다.
실행 전 백엔드 서버(uvicorn)가 켜져 있어야 합니다.

실행 방법:
  python src/test/insert_dummy.py
"""

import requests

BACKEND_URL = "http://localhost:8000"

DUMMY_ITEMS = [
    {
        "object_name": "에어팟 프로",
        "category": "고가품",
        "image_url": "",
        "full_image_url": "",
        "yolo_confidence": 0.92,
        "freshness": "해당없음",
        "camera_id": "cam_test",
        "raw_ai_response": "1. 물체: 에어팟 프로\n2. 카테고리: 고가품\n3. 신선도: 해당없음",
        "bbox": {"x": 50, "y": 40, "w": 120, "h": 90},
    },
    {
        "object_name": "바나나",
        "category": "음식물",
        "image_url": "",
        "full_image_url": "",
        "yolo_confidence": 0.85,
        "freshness": "신선",
        "camera_id": "cam_test",
        "raw_ai_response": "1. 물체: 바나나\n2. 카테고리: 음식물\n3. 신선도: 신선",
        "bbox": {"x": 200, "y": 80, "w": 100, "h": 80},
    },
    {
        "object_name": "우산",
        "category": "비음식물",
        "image_url": "",
        "full_image_url": "",
        "yolo_confidence": 0.78,
        "freshness": "해당없음",
        "camera_id": "cam_test",
        "raw_ai_response": "1. 물체: 우산\n2. 카테고리: 비음식물\n3. 신선도: 해당없음",
        "bbox": {"x": 320, "y": 60, "w": 80, "h": 140},
    },
    {
        "object_name": "지갑",
        "category": "고가품",
        "image_url": "",
        "full_image_url": "",
        "yolo_confidence": 0.88,
        "freshness": "해당없음",
        "camera_id": "cam_test",
        "raw_ai_response": "1. 물체: 지갑\n2. 카테고리: 고가품\n3. 신선도: 해당없음",
        "bbox": {"x": 420, "y": 100, "w": 90, "h": 70},
    },
    {
        "object_name": "먹다 남은 빵",
        "category": "음식물",
        "image_url": "",
        "full_image_url": "",
        "yolo_confidence": 0.71,
        "freshness": "의심",
        "camera_id": "cam_test",
        "raw_ai_response": "1. 물체: 먹다 남은 빵\n2. 카테고리: 음식물\n3. 신선도: 의심",
        "bbox": {"x": 100, "y": 200, "w": 110, "h": 85},
    },
]

def main():
    print(f"백엔드 서버: {BACKEND_URL}")
    print(f"삽입할 항목 수: {len(DUMMY_ITEMS)}개\n")

    for item in DUMMY_ITEMS:
        try:
            res = requests.post(f"{BACKEND_URL}/save", json=item, timeout=10)
            if res.status_code == 200:
                print(f"  ✅ 저장 완료: {item['object_name']} ({item['category']})")
            else:
                print(f"  ❌ 저장 실패: {item['object_name']} — {res.status_code} {res.text}")
        except requests.exceptions.ConnectionError:
            print("  🚨 백엔드 연결 실패! uvicorn 서버가 실행 중인지 확인하세요.")
            break

    print("\n완료! 브라우저에서 대시보드를 새로고침하세요.")

if __name__ == "__main__":
    main()
