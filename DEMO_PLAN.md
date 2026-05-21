# 분실물 관리 AI 시스템 — 실행 가이드

> 웹캠 앞에 물건을 올려놓으면 자동으로 감지 → AI 분류 → 대시보드에 표시됩니다.

---

## 시스템 구조

```
웹캠
  → src/main.py        (모션 감지 + YOLOv8 탐지 + GPT-4o 분류)
  → src/backend/       (FastAPI 서버 — Firebase에 저장)
  → src/frontend/      (브라우저 대시보드 — 30초 자동 갱신)
```

---

## 사전 준비

### 필요한 것

| 항목 | 비고 |
|------|------|
| Python 3.11.9 | 다른 버전은 패키지 호환 문제 발생 가능 |
| 웹캠 | USB 카메라 또는 내장 카메라 |
| `firebase-key.json` | 팀원에게 받아 `src/backend/` 폴더에 넣기 |
| `.env` 파일 | 아래 **4-1단계** 참고 (`.env.example` 복사 후 키 입력) |

### 최초 1회 설정

**1. Python 설치**
- [python.org](https://www.python.org/downloads/release/python-3119/) 에서 Python 3.11.9 다운로드
- 설치 첫 화면에서 **"Add Python.exe to PATH" 반드시 체크** 후 설치

**2. 프로젝트 폴더에서 터미널 열기**
- VSCode에서 프로젝트 폴더 열기 → 상단 메뉴 [터미널] → [새 터미널]

**3. 가상환경 생성 및 활성화**
```powershell
python -m venv venv
venv\Scripts\activate
```

> 맥(Mac): `source venv/bin/activate`

> 보안 오류가 뜨면 먼저 아래 명령 실행 후 다시 시도:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**4-1. `.env` 파일 생성**

프로젝트 루트의 `.env.example` 파일을 복사해서 `.env`로 만든 뒤, API 키를 입력합니다.

```powershell
copy .env.example .env
```

> 맥(Mac): `cp .env.example .env`

`.env` 파일을 열어 `OPENAI_API_KEY=` 뒤에 팀원에게 받은 키를 붙여넣기 하세요.

**4-2. 패키지 설치**
```powershell
python -m pip install -r requirements.txt
```

> 터미널 앞에 `(venv)` 가 표시된 상태에서 실행해야 합니다.

---

## 실행 방법 (터미널 2개 사용)

### 터미널 1 — 백엔드 서버 실행

```powershell
venv\Scripts\activate
cd src\backend
uvicorn main:app --reload --port 8000
```

`Started server process` 메시지가 뜨면 성공.  
백엔드 주소: `http://localhost:8000`

### 터미널 2 — AI 카메라 실행

```powershell
venv\Scripts\activate
python src/main.py
```

카메라 창이 열리고 `Initializing Background... 3s` 가 표시되면 정상 실행.  
초기화 완료 후 웹캠 앞에 물건을 올려놓으면 자동 감지됩니다.

> **종료**: 카메라 창에서 `q` 키

### 브라우저 — 대시보드 열기

`src/frontend/index.html` 을 브라우저로 열면 됩니다.

**방법 1 (VSCode)**: `index.html` 파일 우클릭 → "Live Server로 열기"  
**방법 2 (직접)**: 파일 탐색기에서 `index.html` 더블클릭

> 방법 2(file://)로 열었을 때 데이터가 안 보이면 Live Server를 사용하세요.

---

## 동작 흐름

```
1. 카메라 앞에 물건을 올려놓는다
2. 모션 감지 → 2초 안정화 대기
3. YOLOv8이 물체 위치 탐지
4. GPT-4o가 물체명 + 카테고리(음식물/비음식물/고가품) + 신선도 분석
5. 백엔드(/save)로 전송 → Firebase 저장
6. 대시보드에 30초 내 자동 표시
```

---

## 카테고리별 보관 기간

| 카테고리 | 보관 기간 |
|---------|---------|
| 음식물 | 1일 |
| 비음식물 | 30일 |
| 고가품 | 180일 (6개월) |

---

## 파일 구조

```
Capstone-team-project/
├── .env                    ← OPENAI_API_KEY (팀원에게 받기, git 비공개)
├── requirements.txt        ← 패키지 목록
├── yolov8n.pt             ← YOLO 모델 파일
├── src/
│   ├── main.py            ← AI 메인 (카메라 + YOLO + GPT-4o)
│   ├── backend/
│   │   ├── main.py        ← FastAPI 서버
│   │   └── firebase-key.json  ← Firebase 인증 (팀원에게 받기, git 비공개)
│   ├── frontend/
│   │   ├── index.html     ← 대시보드
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── api.js
│   │       ├── ar_mask.js
│   │       └── dashboard.js
│   └── test/
│       ├── clear_dummy.py ← Firebase 데이터 전체 삭제
│       └── insert_dummy.py
```

---

## 테스트 유틸리티

### Firebase 데이터 전체 삭제 (`clear_dummy.py`)

데모 후 Firebase `lost_items` 컬렉션을 초기화할 때 사용합니다.

```powershell
venv\Scripts\activate
python src/test/clear_dummy.py
```

> **주의**: 실행하면 Firebase의 모든 분실물 데이터가 삭제됩니다. 되돌릴 수 없으니 신중히 사용하세요.

---

## 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| `OPENAI_API_KEY` 오류 | `.env` 파일 없음 | `.env.example` 복사해서 `.env` 만들고 키 입력 (4-1단계 참고) |
| `firebase-key.json` 오류 | 파일 없음 | 팀원에게 받아 `src/backend/` 에 넣기 |
| 카메라를 열 수 없습니다 | 웹캠 미연결 또는 다른 앱 사용 중 | 웹캠 연결 확인, 다른 앱 종료 |
| 데이터가 대시보드에 안 보임 | 백엔드 서버 미실행 | 터미널 1(백엔드)이 실행 중인지 확인 |
| 보안 오류 (스크립트 실행 불가) | PowerShell 실행 정책 | 위 설정 명령어 실행 후 재시도 |

---

## git에 올라가지 않는 파일 (공유 금지)

```
.env                    ← API 키 포함
src/backend/firebase-key.json   ← Firebase 인증 정보
src/asset/              ← 카메라 캡처 이미지
src/Setting_Guide.md    ← 내부 설정 문서
venv/                   ← 가상환경 (각자 생성)
```

이 파일들은 팀원에게 **직접 공유(카카오톡, 이메일 등)** 해야 합니다.
