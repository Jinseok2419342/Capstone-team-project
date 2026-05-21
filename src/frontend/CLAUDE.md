# Frontend — CLAUDE.md

> **이 폴더의 담당자: 고지호 (20241505)**
> 새로운 AI Agent가 작업을 시작하기 전에 이 문서를 반드시 읽으세요.

---

## 절대 규칙 (작업 범위)

- **이 Agent는 `src/frontend/` 안에서만 작업한다.**
- `src/backend/`, `src/ai/`, `src/main/`, `requirements.txt`, `src/main.py` 등 프론트엔드 외 파일은 읽기만 허용하고 **절대 수정하지 않는다.**
- 프로젝트 루트의 `.gitignore`, `README.md`, `LICENSE` 도 수정 금지.
- 백엔드 API 스펙 변경이 필요하다고 판단되면 **코드를 직접 바꾸지 말고 담당자에게 요청 사항을 텍스트로 남긴다.**

---

## 프로젝트 한 줄 요약

라즈베리파이 엣지 카메라로 분실물을 감지(YOLOv8) → AI가 분류(Gemini + Gemma) →
FastAPI 백엔드가 AWS RDS에 저장 → **이 대시보드가 관리자에게 시각화**.

---

## 현재 구현 상태 (2026-05-12 기준)

| 항목 | 상태 |
|------|------|
| 대시보드 HTML/CSS 골격 | 완료 |
| 요약 카드 (카테고리별 건수) | 완료 |
| 분실물 목록 테이블 | 완료 |
| 카테고리 필터 | 완료 |
| D-Day 계산 및 색상 | 완료 |
| Canvas AR 마스킹 렌더러 | 완료 |
| 30초 자동 갱신 | 완료 |
| **백엔드 API 실제 연동** | **미완료 — Mock 데이터로 동작 중** |
| **카메라 스냅샷 실시간 연동** | **미완료** |

---

## 파일 구조

```
src/frontend/
├── CLAUDE.md          ← 이 파일
├── README.md          ← 한 줄 설명
├── index.html         ← 대시보드 단일 페이지 (SPA 아님, 순수 HTML)
├── css/
│   └── style.css      ← 전체 스타일 (외부 CSS 프레임워크 없음)
└── js/
    ├── api.js         ← 백엔드 호출 함수 + 개발용 Mock 데이터
    ├── ar_mask.js     ← Canvas API AR 마스킹 렌더러
    └── dashboard.js   ← 대시보드 메인 로직 (테이블·카드·갱신)
```

### 스크립트 로드 순서 (index.html 하단 고정)

```html
<script src="js/api.js"></script>      <!-- 1. API 함수 및 Mock 데이터 정의 -->
<script src="js/ar_mask.js"></script>  <!-- 2. renderARMasks() 정의 -->
<script src="js/dashboard.js"></script><!-- 3. 위 두 파일의 함수를 호출 -->
```

**순서를 바꾸면 `getMockItems is not defined` 등의 오류가 발생한다. 절대 변경하지 말 것.**

---

## 백엔드 API 계약

백엔드 팀(김지훈·권기원)이 구현 예정인 FastAPI 엔드포인트.
아직 서버가 없으므로 `USE_MOCK = true` 상태로 개발 중.

### GET `/items`

```json
[
  {
    "id": 1,
    "name": "에어팟 프로",
    "category": "고가품",
    "detected_at": "2026-05-12T10:30:00",
    "expires_at": "2026-11-12T10:30:00",
    "image_path": "/assets/crops/item_001.jpg",
    "bbox": { "x": 50, "y": 40, "width": 120, "height": 90 }
  }
]
```

- `category` 값은 반드시 `"음식물"` / `"비음식물"` / `"고가품"` 세 가지 중 하나.
- `bbox` 좌표는 **원본 이미지(640×480) 기준 픽셀값**. 다른 해상도로 들어오면 `ar_mask.js`의 `naturalW` / `naturalH` 기본값을 함께 수정해야 한다.
- `image_path`가 빈 문자열이면 테이블에서 `-` 로 표시됨 (정상 동작).

### GET `/items?category=음식물`

카테고리 필터 쿼리. `"all"` 이면 쿼리스트링 없이 전체 조회.

### GET `/snapshot`

현재 카메라 스냅샷 이미지를 반환. JPEG 또는 PNG.
AR 마스킹 뷰어의 배경 이미지로 사용됨.

---

## 백엔드 연동 전환 방법

백엔드 서버가 준비되면 **두 곳만** 수정하면 된다.

**1. `js/api.js` — 서버 주소 변경**
```js
// 변경 전
const API_BASE = 'http://localhost:8000';

// 변경 후 (실제 서버 주소로)
const API_BASE = 'http://실제서버IP:8000';
```

**2. `js/dashboard.js` — Mock 모드 해제**
```js
// 변경 전
const USE_MOCK = true;

// 변경 후
const USE_MOCK = false;
```

---

## AR 마스킹 렌더러 (`ar_mask.js`) 핵심 규칙

| D-Day 조건 | 채우기 색 | 테두리 색 | 의미 |
|-----------|----------|----------|------|
| D-Day < 0 (초과) | `rgba(220,50,50,0.45)` | 빨간색 | 즉시 폐기 필요 |
| 0 ≤ D-Day ≤ 3 | `rgba(230,140,0,0.4)` | 주황색 | 폐기 임박 |
| D-Day > 3 | `rgba(39,174,96,0.35)` | 초록색 | 정상 보관 중 |

- `renderARMasks(items, naturalW, naturalH)` 를 직접 호출해 다시 그릴 수 있다.
- 창 크기 변경 시 자동으로 재렌더링됨 (`resize` 이벤트 등록되어 있음).
- 현재 items 데이터는 `window._arItems` 에 캐싱됨.

---

## 주의사항 / 알려진 구조적 특이점

1. **`calcDday` 함수가 `ar_mask.js`와 `dashboard.js` 양쪽에 선언되어 있다.**
   전역 스크립트 방식이라 중복 선언이 허용되지만, 로직을 수정할 때는 **두 파일 모두** 동일하게 바꿔야 한다.
   향후 공통 유틸 파일(`js/utils.js`)로 분리하는 것이 좋다.

2. **외부 라이브러리 없음.** jQuery, Bootstrap, React 등 일절 사용하지 않는다.
   팀 합의 기술 스택이 Vanilla JS이므로, 새 라이브러리 도입은 팀원과 협의 후 결정.

3. **CORS 주의.** `index.html`을 `file://` 로 열면 `fetch()`가 CORS 오류 없이 작동하지 않을 수 있다.
   Mock 모드(`USE_MOCK = true`)에서는 fetch를 호출하지 않으므로 로컬 파일 열기로도 동작함.
   실제 연동 시에는 백엔드에서 `Access-Control-Allow-Origin` 헤더 허용 필요 (백엔드 팀에 요청).

4. **`bbox` 좌표 기준.** AR 마스킹의 bbox는 원본 카메라 이미지(기본 640×480) 기준이다.
   백엔드가 다른 해상도로 좌표를 내려주면 `ar_mask.js:30`의 `naturalW`, `naturalH` 기본값을 맞춰서 수정한다.

5. **자동 갱신 주기.** `dashboard.js:3`의 `AUTO_REFRESH_MS = 30000` (30초).
   너무 빠르게 줄이면 백엔드/API 비용 부담이 생기므로 함부로 줄이지 말 것.

---

## 앞으로 해야 할 작업 (우선순위 순)

- [ ] 백엔드 `/items` API 연동 (`USE_MOCK = false` 전환)
- [ ] 카메라 스냅샷(`/snapshot`) 실시간 연동
- [ ] 분실물 클릭 시 상세 모달(이미지 크게 보기 등)
- [ ] 폐기 처리 버튼 (백엔드 `DELETE /items/{id}` 또는 상태 변경 API 필요)
- [ ] 반응형 모바일 레이아웃 보완

---

## 팀 구성 (참고용 — 연락처)

| 이름 | 역할 | GitHub |
|------|------|--------|
| 장진석 | PM / Full-Stack | Jinseok2419342/2026-Capstone-SDL |
| 김지훈 | Backend · AI | seusik1122/ai-capstone |
| 권기원 | Backend | giwon1115/3-1-ai |
| **고지호** | **Frontend (이 폴더 담당)** | jiho050718/2026-QA-Capstone |
