# 실행 가이드

이 가이드는 다른 PC에서도 프로젝트를 실행할 수 있도록 정리한 최소 실행 절차입니다.

`localhost`는 지금 실행 중인 내 컴퓨터를 뜻합니다. 백엔드 서버, AI 카메라 프로그램, 대시보드가 같은 PC에서 서로 통신할 때 사용합니다.

## 1. 최초 1회 준비

프로젝트 폴더에서 터미널을 열고 실행합니다.

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

프로젝트 루트에 `yolov8n.pt`가 있어야 합니다.

```text
Capstone-team-project/
├── yolov8n.pt
├── RUN_GUIDE.md
└── src/
```

## 2. `.env` 설정

`.env` 파일을 열어 필요한 값만 채웁니다.

```env
OPENAI_API_KEY=여기에_OpenAI_API_키를_입력하세요
OPENAI_MODEL=gpt-4.1
BACKEND_URL=http://localhost:8000
YOLO_MODEL=yolo26s.pt
YOLO_CONF=0.35
INITIAL_YOLO_CONF=0.4
MOTION_THRESHOLD=20
MIN_MOTION_AREA=5000
FIREBASE_CREDENTIALS=src/backend/firebase-key.json
USE_FIREBASE=auto
STARTUP_GRACE_PERIOD=3.0
STABILIZATION_TIME=2.0
BACKEND_TIMEOUT=1.0
```

OpenAI 키가 없으면 `OPENAI_API_KEY=`를 비워두고 실행할 때 `--no-ai`를 붙이면 됩니다.

처음 실행 후 `Initializing Background...`가 뜨는 동안에는 카메라 앞을 비워둡니다. 이 시간이 기존 YOLO 물체를 기억하는 시간입니다.

현재 감지 방식은 단순합니다. 움직임이 멈추면 전체 화면을 YOLO로 분석하고, 시작 시 기억한 박스와 겹치지 않는 박스만 새 분실물로 저장합니다.

`YOLO_MODEL`은 기본 `yolo26s.pt`를 권장합니다. 너무 느리면 `yolov8n.pt` 또는 `yolo26n.pt`로 낮춥니다. OpenAI 비전 분석은 `OPENAI_MODEL=gpt-4.1`을 기본으로 둡니다.

## 3. 실행 방법 A: Firebase 키가 있는 경우

Firebase 서비스 계정 키를 아래 위치에 둡니다.

```text
src/backend/firebase-key.json
```

### 터미널 1: 백엔드 실행

Windows:

```powershell
venv\Scripts\activate
$env:USE_FIREBASE="auto"
python -m uvicorn src.backend.main:app --host localhost --port 8000 --reload
```

macOS / Linux:

```bash
source venv/bin/activate
USE_FIREBASE=auto python -m uvicorn src.backend.main:app --host localhost --port 8000 --reload
```

브라우저에서 확인:

```text
http://localhost:8000/health
```

`storage`가 `firebase`면 성공입니다.

### 터미널 2: AI 카메라 실행

OpenAI까지 사용하는 실제 실행:

```powershell
venv\Scripts\activate
python src/main.py --skip-initial-scan
```

OpenAI 없이 카메라, YOLO, Firebase 저장 흐름만 확인:

```powershell
venv\Scripts\activate
python src/main.py --no-ai --skip-initial-scan
```

카메라 창 종료는 `q`입니다.

## 4. 실행 방법 B: Firebase 키가 없는 경우

Firebase 없이 로컬 JSON 파일에 저장합니다. 팀원 PC에서 빠르게 테스트할 때 이 방법을 쓰면 됩니다.

### 터미널 1: 백엔드 실행

Windows:

```powershell
venv\Scripts\activate
$env:USE_FIREBASE="false"
python -m uvicorn src.backend.main:app --host localhost --port 8000 --reload
```

macOS / Linux:

```bash
source venv/bin/activate
USE_FIREBASE=false python -m uvicorn src.backend.main:app --host localhost --port 8000 --reload
```

브라우저에서 확인:

```text
http://localhost:8000/health
```

`storage`가 `local`이면 성공입니다.

### 터미널 2: AI 카메라 실행

OpenAI 없이 전체 데모:

```powershell
venv\Scripts\activate
python src/main.py --no-ai --skip-initial-scan
```

OpenAI 키가 있다면 실제 이미지 분석도 가능합니다.

```powershell
venv\Scripts\activate
python src/main.py --skip-initial-scan
```

## 5. 대시보드 열기

백엔드와 AI 카메라를 실행한 뒤 브라우저에서 아래 파일을 엽니다.

```text
src/frontend/index.html
```

물건을 카메라 앞에 놓고 손을 빼면 감지 후 대시보드에 표시됩니다.

카메라 화면 표시:

- 초록 박스: 현재 움직임
- 노란 박스: OpenCV가 잡은 새 물체 후보 (`SHOW_CANDIDATES=true`일 때만 표시)
- 파란 박스: 분석/저장된 물체

목록을 전부 비우려면 대시보드의 `목록 초기화` 버튼을 누릅니다. 누르면 분실물 목록과 AR 마스킹이 함께 사라집니다.

## 6. 실행 순서 요약

Firebase 있음:

```text
1. src/backend/firebase-key.json 준비
2. 터미널 1: USE_FIREBASE=auto 로 백엔드 실행
3. 터미널 2: python src/main.py --skip-initial-scan
4. 브라우저: src/frontend/index.html 열기
```

Firebase 없음:

```text
1. 터미널 1: USE_FIREBASE=false 로 백엔드 실행
2. 터미널 2: python src/main.py --no-ai --skip-initial-scan
3. 브라우저: src/frontend/index.html 열기
```
