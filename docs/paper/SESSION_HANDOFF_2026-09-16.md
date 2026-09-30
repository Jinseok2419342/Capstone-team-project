# 대화 요점 백업과 다음 AI 인계 — 2026-09-16

이 문서는 이번 대화에서 결정한 내용과 실제 작업 상태를 재구성한 인계용 요약이다. 채팅 서비스의 원본 대화 전체를 내보낸 파일은 아니다. 저장소의 `AGENTS.md`를 먼저 읽고 이 문서로 사용자 의도와 진행 과정을 보충한다.

## 사용자가 원하는 것

- 캡스톤 Re:Found를 국내 학술지 논문으로 발전시키고 싶다. 사용자는 논문 작성 경험이 많지 않아 AI가 연구 구성·작성·검증을 주도하기를 원한다.
- 우선 제목·요약·서론·이론적 배경·관련 연구, 즉 연구방법 이전의 2–4쪽을 약 5분 동안 소개해야 한다.
- 발표 대본은 필요하지 않다. 처음에는 원고 문단을 슬라이드에 배치했으나 사용자가 수정 요청했다. **최종 선호는 PDF 페이지를 그대로 캡처하여 왼쪽에 넣고, 오른쪽에는 짧은 설명 몇 개만 배치하는 것**이다. 문단을 다시 조판하는 방식으로 되돌리지 않는다.
- 기존 초안 활용, 전체 원고 개정과 앞부분 수정에 재량을 주었다. 실제 결과를 지어내도 된다는 허가는 아니다.
- 마지막 요청은 대화 백업과 불필요한 파일 정리다. 이 요청에서 실제 Pi 실험이나 애플리케이션 계측 구현을 새로 시작하지 않았다.

## 대화에서 설명하고 합의한 논문 방향

사용자는 다른 논문의 저자 이름과 그들이 한 일을 본문에 적어도 되는지 질문했다. 선행연구를 인용해 기존 접근을 설명하는 것은 정상적인 논문 작성 방식이며, 그 연구를 우리가 수행했다고 쓰는 것과 다르다고 설명했다. 실제 저자·소속 칸에 다른 논문의 저자를 넣어서는 안 된다. 현재 원고는 저자 식별정보를 넣지 않은 편집본이다.

사용자는 저사양 장치의 최적화 연구인지 단순 구현·성능 소개인지도 질문했다. 연구의 중심을 **저사양 제약 때문에 어떤 처리를 선택했는지, 어떻게 구현했는지, 그 선택의 효과와 부담을 어떻게 비교 검증할지**로 정리했다. 새로운 학습 모델, 양자화나 가지치기를 제안하는 논문은 아니다. 단순 구동 확인만으로 학술지 게재가 보장되지는 않으며 현재 게재 가능성을 확률로 단정하지 않았다.

핵심 상충 관계는 안정화 대기와 지연, 영상 보정과 추가 연산·누락, 선택적 VLM 호출과 로컬 누락, 임시 등록과 관리자 확인 부담이다. 호출 수가 적거나 처리 성공 사례가 빠르다는 사실 하나만으로 우수성을 주장하지 않는다.

## 현재 사용해야 할 파일

| 목적 | 파일 |
|---|---|
| 전체 논문 수정 원본 | `docs/paper/PAPER_DRAFT_JDCS.md` |
| 전체 논문 읽기용 PDF | `output/pdf/REFOUND_FULL_MANUSCRIPT.pdf` — 19쪽 |
| 발표 전반부 원본 | `docs/paper/briefing/RESEARCH_FRONT_MATTER.md` |
| 발표 전반부 PDF | `output/pdf/RESEARCH_FRONT_MATTER.pdf` — 4쪽 |
| **최신 발표 슬라이드** | `output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx` — 4장, 4:3 |
| 이전 재조판 발표 시안 | `output/presentation/REFOUND_EARLY_PAPER_FINAL.pptx` — 6장, 현재 선호 아님 |
| 실측 입력 항목 | `docs/paper/RESULTS_FILL_SHEET.md` |
| 쉬운 성능 측정 안내 | `docs/paper/PERFORMANCE_MEASUREMENT_START.md` |
| 엄밀한 실험 규칙 | `docs/paper/EXPERIMENT_GUIDE.md` |
| 코드 사실과 작성 인계 | `docs/paper/PAPER_AI_HANDOFF.md` |
| 원고 개정 상태 | `docs/paper/REVISION_STATUS.md` |

전체 원고에는 참고문헌 17개, 표 13개, 수식 6개, 알고리즘 1개, SVG 구조도 4개가 있다. 전반부 문단과 인용 [1]–[8]은 전체 원고와 맞췄다. 결과 입력표의 297개 고유 항목과 원고의 항목 집합이 일치한다. `REFERENCES.bib`의 28개 항목은 후보 문헌 모음이다.

기존 26문헌·321항목 전체 초안과 전반부 원고는 `docs/paper/archive/2026-09-16-before-full-revision/`에 보존했다. 이 자료는 변경 이력이며 현재 원고를 대신하지 않는다. 그림 SVG와 PDF 페이지 PNG는 현재 생성 스크립트의 입력·원본이므로 임시 렌더링 파일과 구분하여 보존한다.

## 성능 수치 질문에 대한 답변과 다음 실행 순서

성능은 실제 행동을 정답으로 기록하고 시스템 출력과 비교해서 계산한다고 설명했다. 사용자가 297개 칸을 손으로 계산하거나 실험을 297번 해야 하는 것은 아니다. 장비 정보와 같은 확인 항목을 먼저 채우고, 여러 수치는 같은 원시 기록에서 집계한다.

역할 분담은 AI가 계측·집계 코드와 비교 실행기를 준비하고, 사용자가 실제 Pi 설치와 물품 동작 촬영에 협력하는 방식이다. 먼저 약 40건(추가·이동·제거·none 각 10건)의 예비 실험을 구성할 수 있다고 제안했다. 이는 기록과 라벨링 절차를 점검하는 개발 자료이며, 본 논문의 표본 수가 40건으로 확정되었다는 뜻은 아니다. 본 실험 규모는 파일럿의 오류·불확실성과 촬영 세션 구성을 보고 정한다.

재개하면 `AGENTS.md` 10절에 따라 종단간 영속 계측부터 시작하는 것이 자연스럽다. 다음 AI는 먼저 `app/vision.py`, `app/main.py`, `app/ai.py`, `app/store.py`, `app/config.py`와 `experiments/`의 실제 상태를 읽는다. motion 종료 추정값과 영상 정답의 `action_end_at`을 구분한다. 이후 VLM logical job/HTTP attempt/usage, drop·재연결, privacy 부팅 동기화, 공통 replay·장애 주입 실행기를 준비한다.

아직 확인하지 않은 것은 실제 Pi 접속 방법, 현재 장치 사용 가능 여부, OS·카메라·렌즈·냉각·전원·설치 정보, 기존 녹화 자료와 실험 참여 일정이다. 사용자에게 필요한 시점에 구체적으로 묻는다. 외부 API에 대한 대량 유료 실험을 이미 실행 승인한 것으로 가정하지 않는다.

## 검증과 주장 경계

- 정량 현장 결과는 없다. 결과 장은 입력 틀이며 초록·결론도 실측 전 문장이다. PDF는 편집용 단일단이고 최종 JDCS HWP 투고본은 아니다.
- PDF 19쪽·4쪽과 최신 PPTX 4장을 렌더링해 시각 검사했다. 최신 PPTX의 네 이미지가 PDF에서 생성한 PNG와 바이트 단위로 일치함을 확인했다. 오른쪽 설명은 편집 가능하고 왼쪽 원문은 이미지다.
- 이전 6장 시안도 구조·원문 일치를 검사했으나 사용자 선호에 따라 대체되었다. 해당 검사 기록을 최신 4장 검사로 오인하지 않는다.
- PowerPoint 앱 자체에서 저장·재열기한 검증은 하지 않았다. Artifact Tool의 구조 검사·재가져오기와 렌더링 검사다.
- 인계 문서에 있던 136개 테스트 통과는 과거 기록이다. 이전 확인에서 시스템 Python 환경에 fastapi/cv2/httpx 등이 없어 테스트 import 실패가 있었으므로 현재 환경에서 무조건 통과한다고 말하지 않는다. 실행환경을 확인해 필요한 프로젝트 의존성을 갖춘 뒤 재실행한다.
- 이번 원고·발표·백업 작업에서 애플리케이션 실행 코드를 바꾸지 않았다. 실제 인식 정확도·지연·자원·비용·전력 결과도 생성하지 않았다.

## 생성·검사 도구 인계

- 전체 PDF·SVG: `docs/paper/manuscript/build_manuscript.py`
- 전반부 PDF·옆 설명 HTML: `docs/paper/briefing/build_front_matter.py`
- 최신 PPTX: `docs/paper/briefing/build_pdf_capture_slides.mjs`
- 최신 PPTX 입력 PNG: `docs/paper/briefing/pdf_pages/page-1.png`–`page-4.png` (PDF에서 200 dpi 렌더링)
- 전체·전반부 원고와 이전 6장 시안 일치 검사: `docs/paper/manuscript/validate_artifacts.py` (최신 4장 검사로 오인하지 않는다)
- 최신 4장 검사 기록: `docs/paper/briefing/PDF_CAPTURE_SLIDES_CHECK.json` 및 `docs/paper/validation/PDF_CAPTURE_SLIDES.validation.json`
- **주의:** `manuscript/revise_manuscript.py`는 보관된 초안으로부터 과거 개정을 재현한다. 수동 수정이나 실측 입력 후 실행하면 새 편집을 덮어쓰므로 사용하지 않는다.

이 세션의 Windows 번들 런타임은 `C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime`이다. Python은 `dependencies/python/python.exe`, Node는 `dependencies/node/bin/node.exe`, Poppler는 `dependencies/native/poppler/Library/bin/pdftoppm.exe`에 있었다. 새 환경에서는 사용 가능한 런타임부터 확인한다. PDF는 ReportLab과 맑은 고딕·Cambria, PPTX는 Artifact Tool로 만들었다. LibreOffice는 이 환경에 없었다.

PPTX 생성 시 최종 출력과 검증 보고서는 기존 파일과 다른 경로를 사용해야 한다. `RUNTIME_NODE_MODULES`와 `RUNTIME_NODE`를 지정한다. 폰트·수식 기호·한글 줄바꿈은 최종 렌더링으로 확인한다. 사용자가 PDF 캡처를 요청했으므로 표를 굳이 네이티브 표로 재작성하지 않는다.

## 정리 정책

이번 사용자 요청으로 `tmp` 아래 작업용 렌더링·중간 PPTX·레이아웃 덤프, pytest/Python 캐시를 정리한다. 최종 검증 영수증은 `docs/paper/validation/`으로 보존한다. `tmp/paper-revision/node_modules`는 외부 런타임에 대한 junction이므로 연결만 제거하고 외부 대상은 삭제하지 않는다. 소스 코드, 실제 캡처 데이터, 최신 산출물, 재생성 입력과 유의미한 보관본은 유지한다. 실제 삭제 내역은 `docs/paper/validation/CLEANUP_2026-09-16.json`에 기록한다.

## 다음 AI에게 전달할 짧은 지시

> AGENTS.md와 docs/paper/SESSION_HANDOFF_2026-09-16.md를 먼저 읽고 현재 코드를 확인해 이어서 작업해줘. 최신 발표본은 PDF 캡처 4장이고 대본은 필요 없어. 논문은 아직 실측 전이다. 계속 진행할 때는 종단간 자동 계측부터 준비하고, 실제 측정 없이 성능값을 채우지 마.
