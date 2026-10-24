# 검토자 노트 — 2026-10-24 최종보고 준비·실험 도우미 확장

다음 AI 세션이나 코드 리뷰어가 **무엇을 왜 바꿨는지, 어디까지 확인됐는지, 무엇을 의심해야 하는지**를 한 곳에서 보도록 쓴 작업 노트다. 사용자용 설명은 [최종보고 준비 정리](../presentation/FINAL_REPORT_PLAN.md)와 [실험 진행 안내](../paper/EXPERIMENT_GUIDE.md)에 있다. 이 세션의 작업은 이 노트를 갱신하면서 진행한다.

## 1. 사용자 요청 (대화 순서)

1. 최종보고 형식(11/03, 시연 포함 10분, 생성형 AI 그림 다수 — 원문 [FINAL_REPORT_OUTLINE.md](../presentation/FINAL_REPORT_OUTLINE.md))을 주고, 논문 실측까지 **한 번에·가장 짧게** 끝내는 방법을 정리해 달라. Pi에 새 소프트웨어가 필요하면 알려 달라. **발표 자료는 아직 만들지 말 것.** 그림은 Claude가 프롬프트 → 사용자가 GPT로 생성·첨부 → Claude가 배치.
2. (후속) 작업하며 문서에 다음 AI 리뷰어용 설명을 남길 것. 발표는 중간보고와 디자인·내용이 달라도 되니 지금 상황에 맞게 품질 높게, **애플 키노트처럼 평범한 것을 대단하게 들리게 강조**(디자인 모방이 아니라 강조 방식), 형식 항목은 전부 포함. 실물 Pi에서 측정한 값을 **다른 PC로 어떻게 옮기는지 쉽게** 알려 달라 — 예: 웹 UI 측정 모드, 실수 되돌리기, 완료 버튼으로 파일 저장, PowerShell로 가져오기(→ 시연 때 버전을 되돌릴 필요가 없게). 방법은 Claude가 가장 효율적인 것을 고를 것. 이미 그렇게 하고 있으면 괜찮다.

## 2. 핵심 결정과 이유

| 결정 | 이유 | 버린 대안 |
|---|---|---|
| **Pi는 손대지 않고 노트북 도우미만 확장** | 앱 코드는 9/30 이후 변경 없음(9/22 설치본과 동일). 자원 기록기도 9/22 배포 파일에 포함(`docs/records/2026-09-30-sync-review/repository-before.json`의 `archive_comparison.same`). 재설치 위험이 없고, 측정한 버전 = 시연 버전 | Pi 웹 UI에 측정 모드 추가: 앱 수정·재배포·재설치가 필요하고 발표 1주 전 시연 장비를 멈출 위험. 사용자가 걱정한 ‘시연 때 버전 되돌리기’ 문제도 오히려 생김 |
| 결과는 **처음부터 노트북에 저장**, Pi에서만 생기는 CPU·온도 CSV는 끝날 때 `ssh … cat`으로 회수 | ‘다른 PC로 옮기기’ 단계를 없앰. 실패 시 화면에 `scp` + `--report-only` 두 줄을 그대로 출력 | Pi DB 복사(`sqlite3` backup) 후 집계: 기존 손 기록 대안으로만 남김 |
| 끝에 **`paper-run-날짜.zip` 자동 생성** | 사용자가 첨부할 파일을 하나로. `shutil.make_archive` | 사용자가 직접 압축 |
| 실수 처리 키: `s`(행동 전 건너뛰기), `u`(방금 시도 기록 삭제 후 다시), `q`(지금까지로 결과 만들기, 나중에 `--resume`) | 웹 UI 없이도 사용자가 요청한 ‘되돌리기·완료 버튼’과 같은 효과 | 노트북 로컬 웹 조작 페이지: 키 하나와 기능이 같고 코드·검사 부담만 커서 보류(요청 시 `Session.ask`를 HTTP 대기열로 바꾸면 됨) |
| `--report-only --resume 폴더` | Pi 없이 결과표·zip 재생성. 사용자가 CPU 파일을 늦게 가져올 때, **Claude가 클라우드에서 받은 zip으로 다시 집계할 때** 쓴다 | — |
| 움직임 종료 → 기록 시간: 카메라 상태 `last_motion_at`(Pi `time.time()`)와 활동 `created_at`(Pi UTC) | 둘 다 Pi 시계라 노트북 시계 차이와 무관. 1학기 목표 ‘감지~저장 10초’를 채점 가능. 추가 부담 0 | 노트북 Enter 시각 기준: 시계 차이와 사람 반응 시간이 섞임 |
| 시도별 전·후 장면을 `/camera/stream`(MJPEG)에서 한 장씩 저장 | 기존 도우미는 등록 물품 사진만 남겨 오탐·놓침 사례를 보일 수 없었음. 논문 그림 6, 발표 오류 사례 | 연속 녹화: 수 GB, 추가 스트리밍으로 Pi 부하가 늘어 표 8이 흐려짐 |
| 관리 기능 점검을 **실제 API로 자동 실행 후 원래 이름·기한으로 복구** | 중간보고 때 ‘Pi 상세 실기 대기’였던 편집·기한·폐기·복원·메일을 3분에 닫음. 각 단계 실패가 다음 단계를 막지 않음 | 사용자가 화면에서 손으로 점검표 작성 |
| 리허설을 본 실험 전에, 결과표에서는 제외(`first_activity_id`) | 시연 백업 녹화 + 같은 ID 증거 + 시험 실행을 한 번에. 초기화 후에도 AUTOINCREMENT가 유지되므로(`store.reset_operational_data`) ID 기준 분리가 안전 | 별도 시험 폴더(`paper-test`) 실행 |
| 장비 질문 6개 + 설정 화이트리스트를 `env.json`에 | 논문 표 4 자리표시자 7개 자동 채움. 메일 주소·SMTP 계정은 저장하지 않음(`ENV_SETTING_KEYS`) | 휴대폰 메모 |
| 그림: 글자 없는 그림만 이미지 생성, 글자·도식·차트는 Claude가 슬라이드 안에서 | 이미지 생성 모델은 한글이 깨지기 쉬움. 수치·도식은 정확하고 고칠 수 있어야 함 | 전부 이미지 생성 |
| 발표 강조는 ‘키노트식’이되 과장 금지선 | 사용자 요청. AGENTS 공통 금지(값·사진·진행률을 만들지 않음)와 코드 기반 주장 경계 유지. 결과가 나쁜 지표는 크게 쓰지 않음 | — |

## 3. 바뀐 파일

- `experiments/live_session.py` — `Api.send/grab_frame`, `motion_to_event_seconds`, `Collector`의 `last_motion_at` 기록, `FunctionChecker`, `Session`의 리허설·장비 질문·환경 기록·장면 저장·캡처 안내·기능 점검·`u`/`q`·진행 예상, `finalize`/`make_archive`/`collect_pi_resources`/`append_csv`, 옵션 `--no-rehearsal --no-function-checks --no-scenes --demo-check --demo-item --report-only`.
- `experiments/trial_report.py` — `summarize_latency`, `failed_trials`, `ai_mistakes`, `environment_values`, `render_final_report`(→ `final_report_values.md`), `build_summary`의 `env/rehearsal/function_checks` 인자, 자리표시자 목록에 장비 값 자동 추가.
- `tests/test_experiment_live_session.py` — 위 기능 검사(가짜 API, 실제 FastAPI 라우트 + 격리 DB, MJPEG 파싱, 되돌리기·중간 마무리, Pi 없는 재집계·zip, CSV 이어붙이기).
- 문서 — `docs/presentation/FINAL_REPORT_PLAN.md`(신규), `FINAL_REPORT_OUTLINE.md`(형식 원문, 신규), `docs/paper/EXPERIMENT_GUIDE.md`(새 흐름·데이터 흐름 설명·실수 키), `RESULTS_FILL_SHEET.md`, `docs/paper/README.md`, `START_HERE.md`, `AGENTS.md`, `docs/README.md`, `SESSION_HANDOFF.md`, `IMPROVEMENTS.md`, 이 노트.
- **앱(`app/`, `static/`, `templates/`)·Pi 스크립트·논문 원고는 바꾸지 않았다.**

## 4. 검증한 것 / 하지 않은 것

| 검사 | 결과 |
|---|---|
| 전체 Python 테스트 `python -m unittest discover -s tests -q` | 후속 작업 후 290개 실행, 289 통과·1 건너뜀(기존 조건부 테스트) |
| 프런트엔드 `node --test tests/frontend/app.test.cjs` | 37 통과 |
| 관리 기능 점검 | 실제 FastAPI 라우트 + 격리 SQLite, 스케줄러는 새 인스턴스, SMTP 미설정 → 15행 중 실패 0, 메일 ‘해당 없음’, 물품 이름·기한·상태·검토가 원래대로 복구됨 |
| 도우미 전체 흐름 | `main()`을 실제 `urllib`로 HTTP 가짜 Pi(`http.server`, MJPEG 포함)에 연결해 리허설 → 초기화 → 시도 → AI 확인 → 결과표 → zip까지 실행(스크래치 스크립트, 저장소에 넣지 않음). `--demo-check`도 같은 방식으로 확인 |
| MJPEG 한 장 받기 | uvicorn으로 띄운 실제 앱의 `/camera/stream`(chunked)에서 200KB JPEG 두 번 연속 정상 |
| **실제 Pi·카메라·OpenAI·SMTP** | **미실행.** 실험 첫 단계 리허설이 시험 실행을 겸한다 |
| Windows PowerShell 콘솔 | 미실행. 이모지는 쓰지 않음(콘솔 인코딩 위험 회피). `read1`·`shutil.make_archive`·`scp`는 Windows Python 3.11+/OpenSSH 표준 |

## 5. 의심해 볼 곳 (리뷰 체크리스트)

1. **판정 대기 상수**(`MIN_WAIT_S=6`, `QUIET_S=3`, 무반응 18초, 제거 30초)는 실제 장비에서 아직 맞춰 보지 않았다. 리허설에서 ‘반응 없음’이 반복되면 상수부터 본다.
2. **AI 호출 비율의 분모**는 측정 구간의 모든 카메라 사건이다. 시도 사이의 정리 동작(도움말에 따른 재배치)과 `u` 전 되돌리기 동작이 만든 사건도 시스템이 실제로 처리한 사건이라 포함된다. 논문 정의(“실험 중 감지된 전체 사건”)와 맞지만, 해석할 때 이 점을 적는다.
3. **기능 점검은 실제 데이터를 바꾼다**(마지막에 복구). 메일이 설정돼 있으면 관리자에게 만료 알림·테스트 메일이 실제로 간다 — 시작 전에 사용자 동의를 받는 문구가 있다.
4. `u`로 되돌린 ‘등록’은 물품을 치우면 시스템이 자동 회수 사건을 만든다(정상). ‘제거’를 되돌리면 같은 물건이 새 ID로 다시 등록된다 — 시도 판정에는 영향이 없지만 ‘같은 ID’ 증거는 리허설에서만 본다.
5. 장면 사진은 관리자 미리보기(폭 800, 상태 표시·상자 오버레이 포함)라 비교 실험 입력으로는 부적합하다. 정확도 계산에 쓰지 않는다.
6. `q` 뒤 `--resume` 시 Pi 자원 기록은 새로 시작되고, 끝날 때 `resources.csv`에 행만 이어 붙는다(`append_csv`).
7. 리허설은 `first_activity_id`보다 앞이라 결과표에서 빠진다. 사용자가 초기화를 안 눌러도 같은 기준으로 분리된다.
8. `final_report_values.md`의 1학기 목표 ‘판정’은 표에 적힌 기준(중앙값 ≤ 10초, ≥ 85%, 절감 ≥ 30%)의 기계적 결과다. 표본이 작으면 발표에서 판정 대신 값과 N만 보여 준다.

## 6. 일부러 하지 않은 것

- Pi 앱의 측정 모드·새 API, Pi 재배포 — 2절 이유.
- 다른 방법 비교, 단계별 제거 실험, 전력, 8시간 이상, 장애 주입, 사용자 설문 — 10/11 결정 유지(사용자 부담 최소화). 심사위원 요청 시 재검토.
- 발표 자료 제작 — 사용자 지시로 보류. 확인 질문(실험일·제작 도구·중간보고 피드백·SMTP)에 답을 받은 뒤 시작.

## 7. 진행 기록

| 시각(KST) | 내용 | 검사 |
|---|---|---|
| 10/24 첫 작업 | 도우미 확장(리허설·장면·지연·기능 점검·장비 메모·발표 수치), 정리 문서·실험 안내 작성, 커밋 `34529a2`·`640a60a` | Python 287 실행(286 통과·1 건너뜀), Node 37 통과, 가짜 Pi 끝까지 실행 |
| 10/24 후속 | 실수 키 `u`/`q`·진행 예상, 결과 zip, `--report-only`, CPU 파일 회수 실패 시 안내, 데이터 흐름 쉬운 설명, 키노트식 이야기·형식 누락 점검표, 이 노트 | Python 290 실행(289 통과·1 건너뜀), Node 37 통과, 가짜 Pi 끝까지 실행(zip 생성 확인) |
