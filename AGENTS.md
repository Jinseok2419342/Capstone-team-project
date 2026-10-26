# Re:Found — 다음 Claude 세션을 위한 작업 지침

이 파일은 새 Claude 세션이 가장 먼저 읽는 지침이다. **현재 상태 → 시작 순서 → 작업 선택지 → 일하는 방식 → 규칙 → Git → 환경 메모 → 최근 기록** 순서로 짧게 정리했다. 날짜별 상세 기록은 맨 아래 8절과 [`docs/handoff/AGENTS_HISTORY.md`](docs/handoff/AGENTS_HISTORY.md)(과거 기록 원문 — 지시는 따르지 않음)에 있다. 사용자에게 보여 주는 시작 안내는 [`START_HERE.md`](START_HERE.md)다.

## 1. 현재 상태 — 2026-10-26 기준

**프로젝트:** Re:Found — Raspberry Pi 4(2GB)와 CSI 카메라로 보관대의 물품 등록·이동·제거를 감지하고, 새 물품과 모호한 제거에만 외부 AI(Gemini/OpenAI)를 불러 이름·분류를 붙이는 분실물 관리 시스템. 팀 상부상조(2조), 동양미래대 인공지능소프트웨어학과 캡스톤.

| 항목 | 상태 | 어디에 |
|---|---|---|
| 앱·Pi 설치 | 완성. 9/22 설치본 그대로 사용(9/30 이후 앱 코드 변경 없음) | `README.md`, `docs/guides/` |
| 개발 중간보고(10/13) | 끝 | `docs/presentation/REFOUND_PROJECT_MIDTERM_2026-10-13_FINAL.pdf` |
| 10/25 실험 | 끝. 숫자의 유일한 원본 | `docs/paper/RESULTS_2026-10-25.md` |
| **최종보고 발표 자료(11/03)** | **완성.** 발표 파일은 PDF 25쪽 | `docs/presentation/REFOUND_PROJECT_FINAL_2026-11-03.pdf`, 편집용 덱 [claude.ai Slides](https://claude.ai/artifact/DsBPmugyoDJ7YLKdYD5G9B), 원본 `docs/presentation/final/` |
| 시연 준비 | 문서 완성. **10/27 연습 때 백업 영상 녹화 필요**(아직 없음) | `docs/presentation/FINAL_DEMO_GUIDE.md` |
| **논문(JDCS)** | **결과 반영 완료(10/26).** JDCS 형식 점검·수정 후 2단 근사 PDF 9쪽, 빈칸 없음. 남은 일은 HWP 이식과 투고 전 확인 | `docs/paper/README.md`, `docs/paper/REVISION_STATUS.md` |

**일정:** 10/27 최종보고 연습 → 11/03 최종보고 → 11/10 본론 → 11/17 팀논문 → 11/24 최종논문 발표.

**정해진 것:** **발표 덱은 고치지 않는다(사용자 결정, 10/26).** 덱 20장·부록 B의 AI 호출 "81건·75%·절감 25%"는 그대로 둔다. 원본 재계산 값은 80건·74.1%·절감 25.9%이고 논문은 80건을 쓴다. 결론(목표 30% 미달)은 같다. 다시 묻거나 덱 수정을 제안하지 않는다. 발표 질의에서 물으면 "정확히는 80건, 74.1%"라고 답하면 된다.

**사용자가 답하거나 해야 할 것(아직 안 됨):**

1. 논문 투고 전 확인 5가지(`docs/paper/REVISION_STATUS.md` 4절):
   - 성공 기준 문장이 실제로 기록한 기준과 같은지
   - 본 실험 때 다른 물품이 함께 놓여 있었는지
   - 참고문헌 1·3번의 발행 월과 3번의 공식 영문 제목
   - 학회의 생성형 AI 사용 고지 규정
   - 최종본의 저자 정보
2. 10/27 연습 때 백업 영상 녹화.
3. Pi 남은 시험(선택): 핫스팟 자동 연결, 정상 종료 후 전원 재인가, 랜선 없이 영상과 AI가 돌아오는지.

## 2. 새 세션 시작 순서

1. **이 파일이 최신인지 확인한다.** `git fetch origin` 후 `git log --oneline -5 origin/main`과 `git branch -r`을 본다. 이전 세션의 작업 브랜치(`origin/claude/…`)에 `main`보다 새 커밋이 있으면 사용자에게 알리고 `main` 반영 여부를 묻는다. 1절 날짜보다 새 작업이 있으면 그쪽 `AGENTS.md`가 기준이다.
   - 2026-10-26 기준: 10/26 작업(논문 결과 반영, 최종보고 PDF, 이 지침)은 [PR #20](https://github.com/Jinseok2419342/Capstone-team-project/pull/20)으로 `main`에 반영했다.
   - 확인 방법: `docs/paper/MANUSCRIPT_NUMBERS.md`가 있으면 그 작업이 들어 있는 것이다.
   - `origin/claude/quirky-dirac-tqqjzj`와 `origin/claude/quirky-dirac-tqqjzj-main`은 내용이 모두 `main`에 들어간 옛 작업 브랜치다(커밋 해시만 달라 “앞서 있다”고 보일 수 있음). 무시한다. 비교할 때는 커밋 수 대신 `git diff --stat origin/main <브랜치>`로 내용 차이를 본다.
2. **사용자가 고른 작업을 확인한다.** 작업을 말했으면 3절 표의 ‘먼저 읽을 것 → 첫 행동’대로 바로 시작한다. “START_HERE.md, AGENTS.md 보고 시작하자”, “계속하자”처럼 대상이 없으면 1절을 3–5줄로 요약(끝난 것·남은 일정·사용자가 할 일)한 뒤 3절 선택지를 한 줄씩 보여 주고 고르게 한다. 정해진 일정, Pi 설치·연결 방식, 논문 범위는 다시 묻지 않는다.
3. 코드를 바꿀 때만 테스트 환경을 준비한다(7절). 문서·논문만 고칠 때는 필요 없다.

## 3. 작업 선택지

| 선택지 | 먼저 읽을 것 | 첫 행동 |
|---|---|---|
| ① **논문 마무리·투고** | `docs/paper/README.md` → `docs/paper/REVISION_STATUS.md`(1절 형식 점검표, 3절 HWP 이식, 4절 투고 전 확인) → `docs/paper/MANUSCRIPT_NUMBERS.md` | 원고 `docs/paper/PAPER_DRAFT_JDCS.md`는 완성본이다. 사용자가 4절에 답하면 원고를 고친다. 수정 후 `python docs/paper/manuscript/make_photo_figures.py` → `python docs/paper/manuscript/build_manuscript.py`로 PDF를 다시 만들고 쪽수·글자 깨짐을 이미지로 확인한다. HWP 이식은 3절 순서대로 돕는다. 새 실험(다른 방법과의 비교 등)은 심사위원이 요청할 때만 한다. |
| ② **최종보고 연습·발표** | `docs/presentation/FINAL_DEMO_GUIDE.md` → `docs/presentation/final/README.md` | 10/27 연습을 지원한다(시간 확인, 백업 영상 녹화 안내). 덱 수정 요청이 오면 덱 아티팩트를 `Artifact` 도구로 읽고 고친 뒤 `docs/presentation/final/deck/project/`도 같은 내용으로 갱신한다. 덱 수정 규칙은 `final/README.md`에 있다(padding ≤ 256px, 모든 글 `white-space:nowrap` + `<br>`, 목록 대신 점 + 글, 글은 칸 폭 90% 이내). 사용자가 PDF를 다시 내려받아 주면 `REFOUND_PROJECT_FINAL_2026-11-03.pdf`를 교체한다. |
| ③ **Pi 시연·실기 확인** | `START_HERE.md` ‘확정한 시연 실행·종료 순서’ → `docs/guides/WINDOWS_HOTSPOT_GUIDE.md`(2–5절, 8절 남은 시험) → `docs/guides/PI_ACCEPTANCE_CHECKLIST.md` | 시연 실행 안내인지, 남은 시험인지 확인한다. 실행 7단계·종료 4단계는 바꾸지 않는다. 결과는 사용자가 붙여 준 출력·보고로만 실기 확인표에 적는다. |
| ④ **Pi API 키 교체·제공자 전환** | `docs/guides/PI_API_KEY_CHANGE.md` | 안내 순서대로 진행한다(Pi `.env` 수정 → 서비스 재시작 → 웹에서 제공자 선택 → 실물 확인). 키 값은 사용자가 Pi에서 직접 넣는다. 10/25 실험은 Gemini 3.5 Flash-Lite(`gemini-3.5-flash-lite`)로 했다. |
| ⑤ **PC 자체 앱 실행** | `START_HERE.md` ‘PC 실행 환경 다시 준비하기’ | 처음이면 `setup.ps1` → `start.ps1`. |

## 4. 사용자와 일하는 방식

- 한국어로, **짧고 쉽게** 설명한다. 사용자는 복잡한 절차를 싫어한다(10/25: “쉽게 하자고 뭐이리 복잡해”). 사용자가 할 일은 단계 수를 최소로 하고 명령은 그대로 붙여 넣을 수 있게 준다.
- 끝나면 **무엇을 했는지 표로** 정리해 보여 준다.
- 안전하고 합리적인 범위에서는 먼저 진행하고 결과로 보고한다. 이미 정한 것을 반복해서 묻지 않는다.
- 사용자 판단이 필요한 것(투고 전 확인, `main` 반영 등)은 마지막에 짧게 묻는다.
- 품질을 중요하게 본다. 발표·논문은 실제로 겹침·줄바꿈·넘침을 렌더링으로 확인한 뒤 끝났다고 말한다.

## 5. 반드시 지킬 규칙

**금지**
- 실험값·사진·AI 응답·진행률을 만들어 넣지 않는다. 숫자는 `docs/paper/RESULTS_2026-10-25.md`(와 그 근거 `MANUSCRIPT_NUMBERS.md`)에 있는 값만 쓴다. 측정하지 않은 것(CPU·온도·무변화 오탐률·다른 방법과의 비교)은 ‘없음’으로 둔다.
- API 키·비밀번호·초대 링크를 채팅이나 문서에 받거나 적지 않는다.
- Claude는 Pi에 직접 접속할 수 없다. Pi·노트북 명령은 사용자가 실행하고 출력을 붙여 준다.
- **팀 역할:** 기획·설계·개발·구현은 장진석(팀장)이 전담했다. 권기원(팀원)은 발표 자료 점검·편집과 시연 준비 지원만 했다(최종 덱 표기: ‘발표 자료 점검 · 시연 준비 지원’). 발표·논문·문서에 권기원의 개발·구현 참여를 쓰지 않는다.
- 논문에는 GPT 생성 그림(`docs/presentation/final/images/img-0*.png`)을 쓰지 않는다. 실제 캡처·사진만 쓴다.
- 분류 정답(실험 전 사용자 기준: 지갑 = 귀중품, 음료 = 음식, 나머지 = 일반)은 결과를 본 뒤 바꾸지 않는다. 결과에서 일부를 빼는 조정도 하지 않는다.

**실험 결과 해석의 경계**
- 본 실험(손 기록)은 계획 300회, 실제 시도 280회다(줄이어폰은 등록되지 않아 이동·제거 20회는 시도 불가). 성공률 분모는 줄이어폰 제외 270회다.
- 처리 시간, 처리 속도, AI 호출 수는 본 실험 전 **보조 구간**(도우미 38회, 약 43분)의 Pi 기록에서 계산했다. 도우미의 자동 판정(57.9%)과 `paper_tables.md`는 쓰지 않는다(앞 시도의 늦은 처리와 재배치가 판정에 섞였기 때문).
- 무변화(손·조명·그림자)는 횟수를 세지 않았다. 따라서 ‘관찰한 범위에서 잘못된 기록 없음’까지만 쓴다. 무인 1시간은 0건이다.
- 자동화 테스트 통과는 소프트웨어 회귀 검사일 뿐이며 현장 인식 정확도가 아니다.
- 실험 원본 zip(`paper-run-20261025-1512.zip`)은 사용자가 보관하고 있고 저장소에는 없다. 다시 계산해야 하면 사용자에게 첨부를 요청한다.

**코드 기반 주장 경계 (논문·발표 문장에 적용)**
- 로컬 장치는 움직임이 끝나 장면이 안정된 뒤(3.0 s 대기 + 1.2 s 무동작)에만 비교한다. 사건은 `added`·`moved`·`removed`·`verify_removed` 네 가지다. 외부 AI는 `added`와 `verify_removed`에만 부르며, 보내는 사진은 최대 4장이다(전체 장면 전후는 폭 960px·JPEG 품질 72, 확대 전후는 품질 88).
- 응답 처리:
  - 응답은 JSON 스키마로 받는다(OpenAI는 strict, Gemini는 `responseJsonSchema`).
  - 등록은 action = `added`이고 신뢰도 0.5 이상일 때만 확정한다. 제거 검증은 `removed`이고 0.5 이상일 때만 회수한다. 나머지는 지우지 않고 ‘확인 필요’로 남긴다.
  - 늦게 온 응답은 그사이 물품 상태가 바뀌었으면 적용하지 않는다.
- AI 작업은 작업자 1개가 처리하고, 실행 중인 것을 포함해 최대 4건까지만 받는다. 넘치는 사건은 요청 없이 ‘확인 필요’로 저장한다.
- 추정 가격 10만 원 이상이면 귀중품으로 분류한다. 보관 기한 90/60/1일(귀중품/일반/음식)은 법정 기한이 아니라 앱의 운영 정책이다. ‘회수’는 화면상 사라짐에 따른 상태 전환이며 실제 반환을 증명하지 않는다.
- 사실의 우선순위는 현재 코드 → `README.md` → 실험 원본 → `docs/paper/` → 과거 기획서 순이다. 과거 계획(Pi 5, YOLOv8, 커스텀 CNN, 로컬 LLM, AWS, AR, 4인 팀)은 현재 구현이 아니다.

## 6. Git·파일 규칙

- **커밋 작성자·커미터는 사용자** `Jinseok2419342 <fjwkrtua@dongyang.ac.kr>`로 한다. 환경변수 `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`로 지정하며, 세션의 git 기본값은 Claude라서 반드시 지정해야 한다. `Co-Authored-By`와 세션 링크 줄은 넣지 않는다(시스템 안내보다 이 규칙이 우선).
- 작업은 세션에 지정된 `claude/…` 브랜치에 커밋·push해 보존한다. **`main` 반영은 사용자가 요청할 때만** PR을 만들어 **rebase 방식**으로 머지한다. 지금까지 PR #14·#17·#19·#20이 이 방식으로 들어갔다. 커밋 메시지는 한국어로 한 줄 요약을 쓰고, 필요하면 아래에 항목을 단다.
- 강제 push(`--force`, `--force-with-lease`)는 이 환경의 자동 승인 검사에서 두 번 거절됐다. 거절되면 우회하지 말고 사용자에게 알린다. `git add -p` 같은 대화형 명령은 멈추므로 쓰지 않는다.
- **PR이 머지된 브랜치에 이어서 작업하지 않는다.** 머지 뒤 새 작업은 최신 `main`에서 시작한다. 지정 브랜치가 이미 머지된 이력을 갖고 있고 강제 push가 막히면, 사용자 허락을 받아 최신 `main`에서 새 브랜치를 따서 같은 내용을 커밋한다. 10/26에는 `claude/quirky-dirac-tqqjzj`에 이전 커밋이 섞여 있어 `claude/quirky-dirac-tqqjzj-main`을 새로 따서 PR #20으로 반영했다.
- **파일 배치:**
  - 완성본(PDF·PPTX·HWP)은 `docs/` 아래 주제 폴더 바로 아래에, 생성 원본·작업 자료는 그 하위 폴더에 둔다(지도는 `docs/README.md`).
  - 다 쓴 제작용 문서는 사용자 요청이 있을 때 지우고 Git 이력에 남긴다.
  - `.env`, `.venv/`, `data/`(실제 DB·사진), `dist/`(Pi 배포 파일)는 Git 밖이라 클라우드 세션에는 없다. 삭제된 것이 아니다.
- 문서를 바꾸면 `START_HERE.md`·이 파일·`docs/handoff/SESSION_HANDOFF.md` 맨 위·관련 README를 함께 갱신하고 상대 링크를 점검한다.

## 7. 환경 메모 (클라우드 세션)

- **테스트:** `python3 -m venv <scratch>/venv` → `<scratch>/venv/bin/pip install -r requirements-dev.txt` → `python -m unittest discover -s tests -q`. 현재 290개 실행, 289개 통과, 1개 건너뜀. Node 검사는 `node --test tests/frontend/app.test.cjs`(37개 통과)다. 폴더(`tests/frontend/`)를 지정하면 잘못 실행된다.
- **논문 PDF 빌드:** 시스템 Python에 `reportlab`·`pypdf`·Pillow가 있다.
  - 한국어 명조 글꼴이 없으면 나눔명조를 설치한다: scratchpad에서 `npm pack @expo-google-fonts/nanum-myeongjo@0.4.1`으로 받아 풀고, TTF를 `/usr/share/fonts/truetype/nanum/`에 복사한다(저장소에 글꼴을 넣지 않는다).
  - 빌드 순서는 `make_photo_figures.py`(그림 2·5·6) → `build_manuscript.py`다.
  - 도식 SVG(그림 1·3·4)는 `--figures-only`일 때만 다시 쓴다.
  - 결과 확인은 `pdftoppm -r 70 -png`로 렌더링해 본다.
- **네트워크:** PyPI·npm은 된다. 학회(dcs.or.kr)·KCI·DBpia·koreascience는 프록시 정책으로 막혀 있고 `WebFetch`도 안 된다. `WebSearch`는 되며, 검색 요약으로 JDCS 게재 논문 형식(`Ⅰ. 서 론`, `1-1`)을 확인했다.
- **Pi:** 시연은 Windows 노트북의 `ReFoundLaptop` 핫스팟 → Pi → 같은 노트북 PowerShell의 SSH 터널(`ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local`) → `http://127.0.0.1:18000`으로 한다. 이름 오류가 나면 핫스팟 연결 장치 목록에서 Pi IP를 확인해 `@` 뒤만 바꾼다(`192.168.137.243`은 고정값이 아님). 종료 순서는 `sudo shutdown -h now` → ACT 점멸이 끝난 뒤 전원 분리 → 핫스팟 끄기다.
  - Pi 환경(9/22): Debian 13, 커널 6.18, Python 3.13.5, OpenCV 4.10, Picamera2 0.3.37, FastAPI 0.141, OV5647.
  - 대시보드의 **시연 초기화**는 모든 물품·기록·사진을 백업 없이 지운다(설정·키는 유지).
  - Tailscale(`https://refound-pi-1.tail7a1a61.ts.net/`)은 설치돼 있지만 지금은 쓰지 않는다.
- **덱(claude.ai Slides 아티팩트):** 읽기·수정은 `Artifact` 도구로 한다. 사용자가 편집한 최신본이 아티팩트에 있을 수 있으므로 고치기 전에 반드시 다시 읽는다.

## 8. 최근 작업 기록 (최신순, 요약)

- **10/26 논문 결과 반영:**
  - JDCS 형식을 점검해 세 가지를 고쳤다: 장 번호(`1.` → `Ⅰ. 서 론`), 참고문헌(발행 월 추가, 국문 3번 → 영문 + `(in Korean)`), 방법-실험 불일치(실제 손 기록 방식으로 재작성).
  - 표 5–8을 새로 만들었고, 그림 2·5·6은 실제 사진으로 넣었다. 결과는 9쪽이다.
  - 보조 구간을 다시 계산해 AI 실제 요청이 80건임을 찾았다. 줄이어폰이 보조 구간에서 1회 검출됐지만 AI가 ‘제거’로 판단한 기록도 찾아 반영했다.
  - `RESULTS_FILL_SHEET.md`는 지우고 `MANUSCRIPT_NUMBERS.md`를 추가했다. 최종보고 PDF도 저장했다.
  - AGENTS 과거 기록은 `docs/handoff/AGENTS_HISTORY.md`로 옮겼다. 사용자 승인으로 [PR #20](https://github.com/Jinseok2419342/Capstone-team-project/pull/20)을 통해 `main`에 rebase 반영했다.
- **10/26 최종보고 완성 정리:**
  - 사용자가 덱 세부 수정을 마쳤다.
  - 제작용 문서를 삭제했다: `FINAL_REPORT_PLAN.md`, `FINAL_REPORT_OUTLINE.md`, `IMPROVEMENTS.md`, `REVIEW_NOTES_2026-10-24.md`, `final/preview/`.
  - 10/24–26 작업 전체를 [PR #19](https://github.com/Jinseok2419342/Capstone-team-project/pull/19)로 `main`에 rebase 반영했다.
- **10/25 실험:**
  - 손 기록 결과: 9종 270회 중 244회(90.4%) — 등록 84/90, 이동 73/90, 제거 87/90. AI 이름·분류는 80/84(95.2%).
  - 시간: 손 뗀 뒤 기록까지 4.7초, AI 이름까지 7.8초(중앙값).
  - 실패 유형: 줄이어폰 0/10, 눕힌 머그컵 이동 2/10.
  - 도우미는 38회에서 중단했다. Windows에서 Pi 비밀번호 단계에 멈춰 `--no-pi`로 우회했다. 다시 실험할 때의 주의점은 `docs/paper/EXPERIMENT_GUIDE.md` 맨 위에 있다.
- **10/24:** 최종보고 계획과 실험 도우미를 확장했다(시연 리허설, 장면 저장, 관리 기능 점검, `final_report_values.md`, `u`·`q`·`--resume`·`--report-only`). Pi 쪽 변경은 없다.
- **10/12–13 중간보고:** 사용자가 Canva로 완성했다(PDF 28쪽, 편집 원본은 사용자 Canva). 중간보고 제작 파일은 커밋 `d7cd505` 이력에만 있다.
- **10/11 논문 축소 개정:** 9월의 큰 실험 계획(D_pair 등 4개 자료군, B0–B2 비교, 297개 항목, 통계 검정)을 폐기했다. 이전 원고는 커밋 `55d59a9`에 있다.
- **9/30 이전:**
  - 9/18 앱 안정성·영상·구조 개선: 사건 반영 확인 후 기준 갱신, review_status, 시연 데이터 격리, 미리보기 분리, deadline 기반 프레임 선택.
  - 9/22 새 SD 설치와 시연 초기화 버튼.
  - 9/29–30 Windows 핫스팟 + SSH 시연 확정.
  - 상세는 `docs/handoff/AGENTS_HISTORY.md`, `docs/development/`, `docs/records/`에 있다.
