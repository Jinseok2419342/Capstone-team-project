# 세팅/실행 통합 가이드

다른 PC에서도 바로 실행할 수 있도록 설치, 환경 변수, 실행 순서를 한 파일에 모았습니다.

`localhost`는 지금 실행 중인 내 컴퓨터를 뜻합니다. 백엔드 서버와 AI 카메라 프로그램이 같은 PC에서 통신할 때 사용하는 로컬 주소입니다.

## 1. 최초 1회 설치

Python은 3.11 버전을 권장합니다. Windows에서는 설치할 때 `Add Python.exe to PATH`를 체크하세요.

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

PowerShell에서 가상환경 실행이 막히면 한 번만 실행합니다.

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 2. `.env` 설정

프로젝트 루트의 `.env` 파일을 열고 필요한 값을 채웁니다.

```env
OPENAI_API_KEY=여기에_OpenAI_API_키를_입력하세요
OPENAI_MODEL=gpt-4.1

BACKEND_URL=http://localhost:8000
BACKEND_TIMEOUT=1.0

YOLO_MODEL=yolo26s.pt
YOLO_CONF=0.35
INITIAL_YOLO_CONF=0.4

MOTION_THRESHOLD=20
MIN_MOTION_AREA=5000
STARTUP_GRACE_PERIOD=3.0
STABILIZATION_TIME=2.0

FIREBASE_CREDENTIALS=src/backend/firebase-key.json
USE_FIREBASE=auto
```

OpenAI 키가 없으면 `OPENAI_API_KEY=`를 비워두고 AI 카메라 실행 때 `--no-ai`를 붙입니다.

## 3. Firebase가 있는 경우

Firebase 서비스 계정 키를 아래 위치에 둡니다.

```text
src/backend/firebase-key.json
```

터미널 1에서 백엔드를 실행합니다.

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

터미널 2에서 AI 카메라를 실행합니다.

```powershell
venv\Scripts\activate
python src/main.py
```

OpenAI 없이 흐름만 확인하려면:

```powershell
python src/main.py --no-ai
```

## 4. Firebase가 없는 경우

Firebase 없이 로컬 JSON 파일에 저장합니다. 팀원 PC에서 빠르게 테스트할 때 이 방법을 쓰면 됩니다.

터미널 1에서 백엔드를 실행합니다.

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

터미널 2에서 AI 카메라를 실행합니다.

```powershell
venv\Scripts\activate
python src/main.py --no-ai
```

OpenAI 키가 있다면 실제 이미지 분석도 가능합니다.

```powershell
python src/main.py
```

## 5. 대시보드 열기

백엔드와 AI 카메라를 실행한 뒤 브라우저에서 아래 파일을 엽니다.

```text
src/frontend/index.html
```

목록을 전부 비우려면 대시보드의 `목록 초기화` 버튼을 누릅니다. 분실물 목록, AR 박스, 기본 이미지가 함께 사라집니다.

## 6. 실행 확인

백엔드 상태 확인:

```text
http://localhost:8000/health
```

카메라 화면 표시:

- 초록 박스: 현재 움직임
- 파란 박스: 이미 등록된 물건
- 초록 플래시: 새 물건 저장
- 회색 플래시: 새 물건은 없지만 현재 상태 갱신

카메라 창 종료는 `q`입니다.

## 7. 모델 조절

기본 모델은 `yolo26s.pt`입니다. 느리면 `.env`에서 가벼운 모델로 바꿉니다.

```env
YOLO_MODEL=yolov8n.pt
YOLO_CONF=0.35
```

작은 물건을 너무 못 잡으면:

```env
YOLO_CONF=0.25
```

배경이나 그림자를 너무 자주 잡으면:

```env
YOLO_CONF=0.45
MIN_MOTION_AREA=7000
```

## 8. 실행 순서 요약

Firebase 있음:

```text
1. src/backend/firebase-key.json 준비
2. 터미널 1: USE_FIREBASE=auto 로 백엔드 실행
3. 터미널 2: python src/main.py
4. 브라우저: src/frontend/index.html 열기
```

Firebase 없음:

```text
1. 터미널 1: USE_FIREBASE=false 로 백엔드 실행
2. 터미널 2: python src/main.py --no-ai
3. 브라우저: src/frontend/index.html 열기
```
