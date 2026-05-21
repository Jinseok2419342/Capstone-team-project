

## 자, 다들 빅데이터 분석 프로젝트 들으니 이미 해본겁니다.  


1. Python `3.11.9` 설치하기 (파이썬 공식 홈페이지에서 다운로드하여 설치합니다)    
[매우 중요] 설치 파일 실행 시, 첫 화면 맨 아래에 있는 `Add Python.exe to PATH` 체크박스를 무조건!! 체크하고 설치를 진행해 주세요. (체크 안 하면 나중에 명령어 실행이 안 됩니다.)  
<br><br>


2. VSCode에서 프로젝트 열기  
VSCode에서 `CAPSTONE_TEAM_PROJECT` 리포지토리 폴더를 엽니다.  
상단 메뉴의 [ 터미널 ] - [ 새 터미널 ]을 엽니다.
<br><br>


3. 가상환경(venv) 생성하기  
터미널에 `python -m venv venv`를 입력하고 엔터를 칩니다. (잠시 기다리면 venv라는 폴더가 생성됩니다.)  
<br><br>


4. 가상환경 실행(활성화)하기  
터미널에 `venv\Scripts\activate`를 입력하여 가상환경을 켭니다.<br>  
🚨 만약 빨간 글씨로 '보안 오류(스크립트를 실행할 수 없음)'가 뜬다면?  
당황하지 말고 터미널에 아래 명령어를 복사+붙여넣기  
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`  
(이후 다시 venv\Scripts\activate 입력)  
(맥(Mac) 사용자의 경우: `source venv/bin/activate` 입력)
<br><br>


5. 필수 패키지 다운로드
터미널 입력창 맨 앞에 초록색으로 (venv) 가 떴는지 확인합니다! (이게 떠 있어야 가상환경에 성공적으로 들어온 것입니다.)
가상환경에 들어왔다면, `python -m pip install -r requirements.txt`를 입력해 프로젝트에 필요한 모든 패키지를 한 번에 설치합니다.
<br><br>


6. 테스트 파일 실행해보기  
터미널에 `python src/test/basic_print.py`로 실행해보기.
<br><br>


---

## 백엔드 서버 실행 방법

7. `src/backend/` 폴더로 이동  
터미널에 `cd src/backend`를 입력합니다.
<br><br>


8. Firebase 키 확인  
`src/backend/firebase-key.json` 파일이 있는지 확인합니다.  
없으면 Firebase 콘솔에서 서비스 계정 키를 발급받아 해당 위치에 넣어주세요.
<br><br>


9. 백엔드 서버 실행  
터미널에 `uvicorn main:app --reload`를 입력합니다.  
브라우저에서 `http://localhost:8000` 에 접속했을 때 `{"message": "서버 실행 중"}` 이 뜨면 성공입니다.
<br><br>


10. 프론트엔드 대시보드 열기  
백엔드 서버가 실행 중인 상태에서 `src/frontend/index.html` 을 브라우저로 열면 대시보드가 실제 데이터와 연동됩니다.  
(VSCode의 Live Server 확장으로 열거나, 파일을 직접 브라우저에 드래그해도 됩니다.)
<br><br>


---

## AI 감지 모듈 실행 방법 (main.py)

11. 루트 폴더로 이동 확인  
터미널 경로가 프로젝트 루트(`CAPSTONE_TEAM_PROJECT`)인지 확인합니다.  
`cd src/backend`로 이동했다면 `cd ../..`으로 루트로 돌아옵니다.
<br><br>


12. `.env` 파일 확인  
프로젝트 루트에 `.env` 파일이 있는지 확인합니다.  
없으면 아래 내용으로 루트에 `.env` 파일을 직접 만들어주세요.  
```
OPENAI_API_KEY=여기에_본인_API_키_입력
```
<br>


13. 백엔드 서버가 실행 중인지 확인  
`main.py`는 감지된 물체를 백엔드(`http://localhost:8000`)로 전송합니다.  
**반드시 9번 단계의 백엔드 서버를 먼저 실행한 상태에서** 아래 명령어를 실행하세요.
<br><br>


14. AI 감지 모듈 실행  
새 터미널을 열고 가상환경을 활성화한 뒤 루트에서 아래 명령어를 입력합니다.  
```
python src/main.py
```
카메라 화면이 열리고 `✅ 초기화 완료! 이제 새로운 분실물을 감지합니다.` 메시지가 뜨면 정상 실행된 것입니다.  
종료하려면 카메라 창에서 `q`를 누릅니다.
<br><br>


> **실행 순서 요약**  
> 1. 터미널 A: `cd src/backend` → `uvicorn main:app --reload` (백엔드)  
> 2. 터미널 B: 루트에서 `python src/main.py` (AI 감지)  
> 3. 브라우저: `src/frontend/index.html` 열기 (대시보드)