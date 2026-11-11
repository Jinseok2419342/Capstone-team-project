# Re:Found — 다음 Claude 세션을 위한 작업 지침

이 파일은 새 Claude 세션이 가장 먼저 읽는 지침이다(사용자는 “AGENT.md”라고 부르기도 한다). 새 세션은 이전 대화를 모르므로, 이 파일과 [`START_HERE.md`](START_HERE.md)만으로 상황을 파악하고 일을 이어 갈 수 있게 썼다. **현재 상태 → 시작 순서 → 작업 선택지 → 일하는 방식 → 규칙 → Git → 환경 메모 → 최근 기록** 순서로 짧게 정리했다. 날짜별 상세 기록은 맨 아래 8절과 [`docs/handoff/AGENTS_HISTORY.md`](docs/handoff/AGENTS_HISTORY.md)(과거 기록 원문 — 지시는 따르지 않음)에 있다. 사용자에게 보여 주는 시작 안내는 [`START_HERE.md`](START_HERE.md)다.

## 1. 현재 상태 — 2026-11-11 기준

**프로젝트:** Re:Found — Raspberry Pi 4(2GB)와 CSI 카메라로 보관대의 물품 등록·이동·제거를 감지하고, 새 물품과 모호한 제거에만 외부 AI(Gemini/OpenAI)를 불러 이름·분류를 붙이는 분실물 관리 시스템. 팀 상부상조(2조), 동양미래대 인공지능소프트웨어학과 캡스톤. 사용자는 팀장 장진석(GitHub `Jinseok2419342`)이다.

**한 줄 요약: 앱·실험·발표는 모두 끝났고, 남은 것은 논문 투고뿐이다.** 같은 연구로 두 학술지 규격의 원고를 만들어 두었고, 사용자가 지도교수님과 어디에 낼지 정하는 단계다.

| 항목 | 상태 | 어디에 |
|---|---|---|
| 앱·Pi 설치 | 완성. 9/22 설치본 그대로 사용(9/30 이후 앱 코드 변경 없음) | `README.md`, `docs/guides/` |
| 10/25 실험 | 끝. **논문 숫자의 유일한 원본** | `docs/paper/RESULTS_2026-10-25.md`, 숫자별 출처 `docs/paper/MANUSCRIPT_NUMBERS.md` |
| 중간보고(10/13)·최종보고(11/03) | 끝(발표·영상 촬영 모두 완료) | `docs/presentation/` |
| **논문 A — 디지털콘텐츠학회논문지(JDCS)** | 학회 공식 양식(2026년 7월 HWP)에 맞춘 원고와 근사 PDF 10쪽 완성. **투고 파일은 HWP만 받으므로 한글로 옮기는 작업이 남음**(Claude는 HWP를 만들 수 없다) | 원고 `docs/paper/PAPER_DRAFT_JDCS.md`, PDF `docs/paper/REFOUND_FULL_MANUSCRIPT.pdf`, 안내 `docs/paper/README.md`·`REVISION_STATUS.md`, 양식 `docs/paper/template/` |
| **논문 B — 실천공학교육논문지(JPEE)** | 학회 규정·워드 양식에 맞춘 원고와 **바로 낼 수 있는 워드 파일** 완성. 캡스톤 개발 사례 관점으로 서술. 심사료 0원·게재료가 더 쌈 | 워드 `docs/paper/REFOUND_JPEE_MANUSCRIPT.docx`, 원고 `docs/paper/jpee/PAPER_DRAFT_JPEE.md`, 비교·투고 순서 `docs/paper/jpee/README.md`, 양식 `docs/paper/jpee/template/` |

두 원고는 **같은 연구·같은 숫자**다. **두 학술지에 동시에 내면 중복 투고이므로 한 곳에만 낸다.** 한 곳에서 게재 불가가 난 뒤 다른 곳에 내는 것은 된다.

**일정:** 11/03 최종보고(끝) → 11/10 본론(지남) → **11/17 팀논문 → 11/24 최종논문 발표.** 11/24 발표 자료가 필요한지는 아직 모른다. 사용자가 요청하면 그때 만든다.

**정해진 것(다시 묻거나 바꾸자고 하지 않는다):**
- **발표 덱은 고치지 않는다(10/26).** 덱의 AI 호출 "81건·75%·절감 25%"는 그대로 둔다. 정확한 값은 80건·74.1%·절감 25.9%이고 논문은 80건을 쓴다. 질의에서 물으면 "정확히는 80건, 74.1%"라고 답한다.
- **논문에 생성형 AI 사용 고지는 넣지 않는다(10/26).** 심사에서 요구하면 그때 반영한다.
- **논문 내용은 실험 측정값을 빼고는 바꿔도 된다(11/11).** 인용 문헌·서술·구성·언어는 투고처에 맞게 고칠 수 있다. 측정값과 실험 사실은 그대로 둔다.
- **JDCS 원고는 10쪽 이내(11/11).**
- **커밋 작성자는 사용자 계정(11/11 재확인).** 6절 참고.

**사용자가 답하거나 해야 할 것(아직 안 됨):**
1. **어느 학술지에 낼지**(JDCS 또는 JPEE)와 **저자 정보**(저자·순서·소속·교신저자·약력) — 지도교수님(강환수 교수님)과 정할 일. 교수님께 보낼 메시지 초안은 `docs/paper/REVISION_STATUS.md` 4절, 두 학술지 비교표는 `docs/paper/jpee/README.md` 1절에 있다.
2. **참고문헌 [3]의 학술대회 개최 장소**(양형준·최규상, 2025 한국정보기술학회 하계종합학술대회, 6/12–14) — 두 원고 모두 비어 있다. DBpia 페이지에도 없었다. 사용자가 논문 PDF 등에서 확인해 알려 주면 넣는다. 추측해서 넣지 않는다.
3. 투고 실행 — JPEE면 회원 가입 → KCI 유사도 검사 → 온라인 투고(`docs/paper/jpee/README.md` 4절). JDCS면 HWP 이식 → 투고(`docs/paper/REVISION_STATUS.md` 3절).
4. (선택) Pi 남은 시험: 핫스팟 자동 연결, 정상 종료 후 전원 재인가, 랜선 없이 영상과 AI가 돌아오는지.

## 2. 새 세션 시작 순서

사용자는 보통 “AGENT.md, START_HERE.md 읽고 시작하자”처럼 말한다. **`AGENT.md`는 이 파일 `AGENTS.md`를 뜻한다.** 이 파일과 `START_HERE.md`만 읽으면 시작할 수 있게 써 두었다.

1. **최신인지 확인한다.** `git fetch origin` 후 `git log --oneline -5 origin/main`과 `git branch -r`을 본다.
   - 2026-11-11 기준 모든 작업이 `main`에 들어 있다. 확인 방법: `main`에 `docs/paper/jpee/` 폴더가 있으면 된다.
   - 다른 `origin/claude/…` 브랜치에 `main`에 없는 내용이 있으면(`git diff --stat origin/main <브랜치>`로 확인) 사용자에게 알리고 `main` 반영 여부를 묻는다. 내용 차이가 없으면 옛 브랜치이니 무시한다(커밋 해시만 달라 “앞서 있다”고 보일 수 있다).
2. **사용자가 고른 작업을 확인한다.**
   - 작업을 말했으면 3절 표의 ‘먼저 읽을 것 → 첫 행동’대로 바로 시작한다.
   - “읽고 시작하자”, “계속하자”처럼 대상이 없으면: 1절을 3–5줄로 요약(끝난 것 / 남은 것 = 논문 투고 / 사용자가 정할 것)하고, 3절 선택지를 한 줄씩 보여 주고 고르게 한다. 이미 정해진 것(1절)은 다시 묻지 않는다.
   - 사용자가 교수님 답(투고처·저자 정보)을 가져오면 3절 ①의 해당 갈래로 바로 이어 간다.
3. **환경 준비는 필요할 때만 한다(7절).** 논문 PDF·워드를 다시 만들 때는 한국어 글꼴 설치, 학회 사이트를 읽을 때는 네트워크 환경 확인, 앱 코드를 바꿀 때만 테스트 환경이다.

## 3. 작업 선택지

| 선택지 | 먼저 읽을 것 | 첫 행동 |
|---|---|---|
| ① **논문 투고 준비** | `docs/paper/README.md` → `docs/paper/jpee/README.md`(두 학술지 비교·JPEE 투고 순서) → `docs/paper/REVISION_STATUS.md`(JDCS 규격 대조·HWP 이식·투고 전 확인) | 투고처가 정해졌는지 먼저 묻는다(정해졌으면 묻지 않는다). **JPEE로 가면:** 워드 파일은 완성이다. 저자 정보는 투고 화면에 입력하므로 원고에 넣지 않는다. 사용자가 투고 단계(`jpee/README.md` 4절)를 진행하도록 한 단계씩 쉽게 안내하고, 화면 문구를 붙여 주면 그에 맞춰 돕는다. 원고를 고치면 `jpee/PAPER_DRAFT_JPEE.md` 수정 → `python docs/paper/jpee/build_jpee_docx.py` → LibreOffice로 PDF 변환해 눈으로 확인 → `jpee/REFOUND_JPEE_PREVIEW.pdf` 교체. **JDCS로 가면:** HWP 이식은 사용자가 한글에서 한다. `REVISION_STATUS.md` 3절 순서대로 안내하고, 붙여 넣을 문단·표를 그때그때 준다. 원고를 고치면 `make_figures.py` → `build_manuscript.py`로 PDF를 다시 만들고 10쪽 이내인지 이미지로 확인한다. **두 원고의 숫자는 항상 같게 유지한다.** 새 실험은 심사위원이 요청할 때만 한다. |
| ①-2 심사 결과 대응 | 위와 같음 + 사용자가 붙여 준 심사 의견 | 의견별로 원고를 고치고 ‘심사 의견 답변서’를 쓴다. JDCS 답변서 양식은 학회 자료실 ‘주요양식’에 있다(`dcs.or.kr`). 측정하지 않은 것을 요구받으면 만들지 말고 한계로 답하거나 사용자에게 추가 실험 여부를 묻는다. |
| ② 발표 자료(필요할 때만) | `docs/presentation/final/README.md` | 최종보고 덱은 고치지 않는다(1절). 11/24 최종논문 발표 등으로 새 자료가 필요하면 사용자 요청을 받아 새로 만든다. 기존 덱 아티팩트(`https://claude.ai/artifact/DsBPmugyoDJ7YLKdYD5G9B`)를 참고할 때는 `Artifact` 도구로 다시 읽는다. |
| ③ Pi 시연·실기 확인 | `START_HERE.md` ‘확정한 시연 실행·종료 순서’ → `docs/guides/WINDOWS_HOTSPOT_GUIDE.md` → `docs/guides/PI_ACCEPTANCE_CHECKLIST.md` | 실행 7단계·종료 4단계는 바꾸지 않는다. 결과는 사용자가 붙여 준 출력·보고로만 기록한다. |
| ④ Pi API 키 교체·제공자 전환 | `docs/guides/PI_API_KEY_CHANGE.md` | 키 값은 사용자가 Pi에서 직접 넣는다. 10/25 실험은 Gemini 3.5 Flash-Lite(`gemini-3.5-flash-lite`)로 했다. |
| ⑤ PC 자체 앱 실행 | `START_HERE.md` ‘PC 실행 환경 다시 준비하기’ | 처음이면 `setup.ps1` → `start.ps1`. |

## 4. 사용자와 일하는 방식

- 한국어로, **짧고 쉽게** 설명한다. 사용자는 논문 투고가 처음이다. 사용자가 할 일은 **초보자에게 말하듯** 어디를 눌러 무엇을 하는지까지 단계별로 쓴다(11/11 요청). 사용자는 복잡한 절차를 싫어한다(10/25: “쉽게 하자고 뭐이리 복잡해”). 사용자가 할 일은 단계 수를 최소로 하고 명령은 그대로 붙여 넣을 수 있게 준다.
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

**논문 형식(학회 공식 양식, 2026년 7월 수정본)** — 원고를 고칠 때 깨지 않는다. 전체 대조표는 `docs/paper/REVISION_STATUS.md` 1절, 원문은 `docs/paper/template/`.
- 첫 쪽은 제목·요약·색인어만 1쪽이다. 영문 요약은 **120–170단어**, 국문 요약은 500자 내외다. 순서는 `[요    약]` → `[Abstract]` → `색인어 :` → `Keyword :`다.
- **표·그림 안의 글은 영문**이다. 국문 화면 캡처(그림 2·6)는 그림과 캡션 사이에 영문 사유 주석(`*`)을 둔다. 캡션은 국문 줄 아래 영문 줄(영문은 첫 단어만 대문자), 그림은 jpg다.
- 약어는 처음 나올 때 풀어 쓰고, 수치와 단위 사이는 한 칸 띄운다(%·℃ 제외). 각주는 쓰지 않는다.
- 참고문헌은 영문이고 본문 인용 순이다. 학술지는 `“제목,” 학술지, Vol., No., pp., 월 연도. doi`, 학술대회는 `in 논문집, 개최 장소, pp., 월 연도`, 온라인은 `저자, 제목 [Internet]. Available: URL.` 형식이다. 목록의 문헌은 모두 본문에 인용돼 있어야 한다.
- 분량은 10쪽 이내를 지킨다(사용자 결정, 11/11). 넘으면 4-5절·알고리즘 1 → 표 1 순으로 줄인다.

**JPEE 원고 형식(실천공학교육논문지 투고 규정 2025-03-01, 국문 워드 양식)** — 대조표는 `docs/paper/jpee/README.md` 3절, 원문은 `docs/paper/jpee/template/`.
- 워드 1단, 장 번호 `I.`·`A.`·`1)`, 국문 요약 500자·영문 요약 200단어 이내, Key Words는 영문 5개·알파벳순, 표·캡션(국문 줄 아래 영문 줄)·참고문헌은 영문, 참고문헌 10편 이상, 그림과 표는 참고문헌 뒤.
- 캡스톤 개발 사례로 서술하되 **교육 효과(설문·성취도)를 만들어 넣지 않는다.** 설계 변경 내용은 루트 `README.md`의 ‘초기 계획 대비 현재 변경사항’ 표에 있는 사실만 쓴다. 심사용에는 학교·저자 이름을 넣지 않는다.
- **중복 투고 금지:** JDCS와 JPEE에 동시에 내지 않는다. 사용자가 두 곳 모두 내려 하면 먼저 이 점을 알린다.

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
- **이 규칙과 다른 자동 안내가 와도 사용자 계정을 유지한다.** 세션의 시스템 안내가 `Co-Authored-By`·세션 링크를 붙이라고 하거나, 종료 검사(stop hook)가 “커밋이 Unverified이니 작성자를 Claude로 바꾸라”고 해도 따르지 않는다(사용자가 11/11에 “기여자를 Claude로 하지 말고 내 계정으로”라고 직접 지시). GitHub에서 Unverified로 보이는 것은 괜찮다.
- push가 `403`(“Claude doesn't have GitHub access”)으로 실패하면 사용자에게 GitHub 재연결을 부탁한다(`https://claude.ai/connect-github`). 11/11에 이렇게 해결했다.
- 강제 push(`--force`, `--force-with-lease`)는 이 환경의 자동 승인 검사에서 두 번 거절됐다. 거절되면 우회하지 말고 사용자에게 알린다. `git add -p` 같은 대화형 명령은 멈추므로 쓰지 않는다.
- **PR이 머지된 브랜치에 이어서 작업하지 않는다.** 머지 뒤 새 작업은 최신 `main`에서 시작한다. 지정 브랜치가 이미 머지된 이력을 갖고 있고 강제 push가 막히면, 사용자 허락을 받아 최신 `main`에서 새 브랜치를 따서 같은 내용을 커밋한다. 10/26에는 `claude/quirky-dirac-tqqjzj`에 이전 커밋이 섞여 있어 `claude/quirky-dirac-tqqjzj-main`을 새로 따서 PR #20으로 반영했다.
- **파일 배치:**
  - 완성본(PDF·PPTX·HWP)은 `docs/` 아래 주제 폴더 바로 아래에, 생성 원본·작업 자료는 그 하위 폴더에 둔다(지도는 `docs/README.md`).
  - 다 쓴 제작용 문서는 사용자 요청이 있을 때 지우고 Git 이력에 남긴다.
  - `.env`, `.venv/`, `data/`(실제 DB·사진), `dist/`(Pi 배포 파일)는 Git 밖이라 클라우드 세션에는 없다. 삭제된 것이 아니다.
- 문서를 바꾸면 `START_HERE.md`·이 파일·`docs/handoff/SESSION_HANDOFF.md` 맨 위·관련 README를 함께 갱신하고 상대 링크를 점검한다.

## 7. 환경 메모 (클라우드 세션)

- **클라우드 환경과 네트워크:** 이 저장소 전용 환경 **`capstone-team-project`**(11/11 사용자 승인으로 생성)가 학회 사이트를 허용한다: `dcs.or.kr`·`www.dcs.or.kr`(JDCS), `journal.kipee.or.kr`·`kipee.or.kr`·`d2j16w31g89z0j.cloudfront.net`(JPEE와 양식 파일), `www.dbpia.co.kr`, `journal.kci.go.kr`. 사용자의 `Default` 환경은 이 사이트들을 막는다.
  - 학회 사이트를 읽어야 하는데 막히면 `get_environment`로 지금 환경을 보고, `Default`이면 `switch_environment`로 `capstone-team-project`로 옮긴다(사용자 승인 창이 뜬다). 새 사이트가 필요하면 `update_environment`로 그 주소만 추가 요청한다.
  - 사이트는 `curl`로 받는다. `WebFetch`는 이 환경에서 동작하지 않는다. `journal.dcs.or.kr`는 허용돼 있어도 연결이 끊긴다. JPEE 사이트의 검색 기능은 자동 접근을 막으므로 호별 목차 페이지(`/digital-library/publication?volume=N&number=M`)를 읽는다. `www.kci.go.kr`·`koreascience`는 막혀 있다. `WebSearch`는 된다. PyPI·npm·apt는 된다.
- **한국어 글꼴(논문 PDF·워드 미리보기에 필요):** 클라우드 세션에는 없다. scratchpad에서 `npm pack @expo-google-fonts/nanum-myeongjo@0.4.1`과 `npm pack @expo-google-fonts/nanum-gothic`으로 받아 풀고, TTF를 `/usr/share/fonts/truetype/nanum/`에 복사한 뒤 `fc-cache -f`. 저장소에 글꼴을 넣지 않는다.
- **JDCS PDF 빌드:** 시스템 Python의 `reportlab`·`pypdf`·Pillow로 `python docs/paper/manuscript/make_figures.py` → `python docs/paper/manuscript/build_manuscript.py`. 확인은 `pdftoppm -r 75 -png`로 렌더링해 본다. 쪽수·요약 단어 수·그림과 표의 위치는 `manuscript/PDF_BUILD_REPORT.json`에 나온다.
- **JPEE 워드 빌드:** `python docs/paper/manuscript/make_figures.py --width 2040 --out docs/paper/jpee/figures`(그림을 바꿨을 때만) → `python docs/paper/jpee/build_jpee_docx.py`. `python-docx`는 시스템 Python에 있다. 미리보기는 `soffice --headless --convert-to pdf`로 만든다. 수식이 보이려면 `apt-get install -y --no-install-recommends libreoffice-math`가 필요하다(먼저 `apt-get update`).
- **HWP 읽기:** 양식 안내문은 `docs/paper/template/JDCS_TEMPLATE_2026-07.txt`에 텍스트로 있다. 설정값까지 보려면 scratchpad venv에 `pip install pyhwp six lxml` 후 `hwp5txt`·`hwp5proc xml`. HWP 파일을 새로 만들거나 고치는 것은 할 수 없다.
- **앱 테스트(코드를 바꿀 때만):** `python3 -m venv <scratch>/venv` → `<scratch>/venv/bin/pip install -r requirements-dev.txt` → `python -m unittest discover -s tests -q`(290개 실행, 289개 통과, 1개 건너뜀). Node 검사는 `node --test tests/frontend/app.test.cjs`(37개 통과). 폴더를 지정하면 잘못 실행된다.
- **Pi:** Claude는 직접 접속할 수 없다. 시연은 Windows 노트북의 `ReFoundLaptop` 핫스팟 → Pi → 같은 노트북 PowerShell의 SSH 터널(`ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local`) → `http://127.0.0.1:18000`. 이름 오류가 나면 핫스팟 연결 장치 목록에서 Pi IP를 확인해 `@` 뒤만 바꾼다. 종료는 `sudo shutdown -h now` → ACT 점멸이 끝난 뒤 전원 분리 → 핫스팟 끄기.
  - Pi 환경(9/22): Debian 13, 커널 6.18, Python 3.13.5, OpenCV 4.10, Picamera2 0.3.37, FastAPI 0.141, OV5647.
  - 대시보드의 **시연 초기화**는 모든 물품·기록·사진을 백업 없이 지운다(설정·키는 유지). Tailscale은 설치돼 있지만 쓰지 않는다.

## 8. 최근 작업 기록 (최신순, 요약)

- **11/11 논문 공식 양식 반영:**
  - 사용자가 “남은 것은 논문뿐, 공식 규격에 맞게 보충하자”고 했다. 학회 사이트 접속을 승인받아 투고 규정과 양식(2026년 7월 수정 HWP)을 처음으로 직접 읽었다. 양식·규정은 `docs/paper/template/`에 저장했다.
  - 고친 것: 영문 요약 208 → 168단어, 요약·색인어 순서와 라벨, 표 8개·알고리즘·도식 3개 영문화, 두 줄 캡션, 그림 6장 jpg, 단위 띄어쓰기, 약어 풀어쓰기, 참고문헌 형식(학술대회 개최 장소, 저자 모두 표기, 온라인 형식).
  - 근사 PDF 생성기를 공식 용지(210 × 280 mm)·첫 쪽 단독·양식의 글꼴 크기와 간격으로 다시 맞췄다. 결과는 10쪽(마지막 쪽 4분의 1 사용). 단을 넘는 문단에서 띄어쓰기가 사라지던 오류도 고쳤다.
  - 숫자와 실험 내용은 바꾸지 않았다. 남은 것: 저자 정보, 참고문헌 [3] 개최 장소, HWP 이식.
- **11/11 두 번째 투고처(JPEE) 원고:**
  - 사용자가 다른 학술지 규격도 하나 더 만들자고 했다(내용은 측정값을 빼고 바꿔도 됨, 비용·절차 고려). 실천공학교육논문지의 규정·양식·비용을 학회 사이트에서 확인하고 그 규격의 원고와 **제출용 워드 파일**을 만들었다.
  - JDCS 원고와 다른 점: 캡스톤 개발 사례 관점, 설계 변경 표와 시사점 절 추가, JPEE 게재 논문 3편 인용(참고문헌 21편), 장 번호 I.·A., 그림과 표는 뒤에 모음, 그림 폭 2040 px.
  - 푸시: 11/11 첫 push는 GitHub 권한 오류(403)로 실패했고, 사용자가 GitHub를 다시 연결한 뒤 성공했다. 자동 검사가 커밋 작성자를 Claude로 바꾸라고 요구했지만 사용자 지시대로 사용자 계정을 유지했다(GitHub에는 Unverified로 보인다).
- **11/11 인계 정리와 `main` 반영:** 사용자 요청으로 이 파일과 `START_HERE.md`를 새 세션이 사전 지식 없이 시작할 수 있게 다시 정리했다(1–3절, 7절). 11/11 작업 전체(브랜치 `claude/gracious-ramanujan-bfolt8`)를 PR로 `main`에 rebase 반영했다.

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
