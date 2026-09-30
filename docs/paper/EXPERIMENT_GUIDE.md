# Re:Found 논문 실험 실행 가이드

이 문서는 현재 소스 코드에서 재현 가능한 실험 데이터를 만드는 절차를 설명한다. 자동화 테스트 결과는 소프트웨어 회귀 검증이고, 아래 절차로 수집한 실제 표본만 논문의 인식 성능 수치로 사용한다.

## 1. 측정 범위

실험은 서로 다른 범위를 섞지 않고 세 층으로 나눈다.

| 층 | 입력과 실행 위치 | 측정 가능한 것 | 측정하지 못하는 것 |
|---|---|---|---|
| 안정 이미지 쌍 | 동일한 before/after 이미지를 `VisionMonitor._detect_changes()`에 입력 | 로컬 사건 검출 정확도, bbox IoU, 코어 계산 시간, 방해요인 보정 ablation | 카메라 캡처, 움직임 종료 판정, settling, callback, DB, VLM 지연 |
| 실제 녹화·실시간 episode | 전체 `VisionMonitor`와 서비스 실행 | 행동 종료부터 로컬 사건·DB·최종 확정까지 지연, 상태기계 효과, 실제 FPS와 drop | 별도 계측하지 않은 전력 |
| Raspberry Pi 자원 계측 | 실제 Pi 프로세스를 1초 간격 관찰 | CPU, RSS, load, 메모리, SoC 온도, 디스크 여유 | 전력·에너지 — 외부 콘센트 전력계 필요 |

안정 이미지 쌍 결과를 “실시간 종단간 지연”으로 쓰면 안 된다. 또한 현재 `plain` profile도 운영 코드의 Lab 색차, contour/event 판정, 조명·그림자 거부 규칙, 활성 물체 참조 로직 등을 공유하므로 **순수 grayscale absolute difference 기준선이 아니다**.

논문 원고에서는 자료를 `D_pair`(코어 ablation), `D_stream`(상태기계·ID·FP/hour·종단간), `D_vlm`(V1–V4 paired 비교), `D_fault`(통제 장애 주입)로 구분한다. 사건별 주 성능표는 `D_stream`, 단계적 방해요인 표만 `D_pair`에서 작성한다.

## 2. 원시 데이터 원칙

논문의 원시 진실 원장은 정규화된 두 CSV다.

- `episodes.csv`: 한 실험 episode의 조건, 노출 시간, 자원, 호출량
- `events.csv`: 그 episode의 정답 사건과 로컬·최종 예측 사건

`EXPERIMENT_RECORD_TEMPLATE.csv`는 사람이 한 행으로 살펴보기 위한 파생·보조 양식이다. 복수 예측, false positive, 중간 `verify_removed`를 손실 없이 보존하려면 `episodes.csv`와 `events.csv`를 우선한다.

공통 규칙은 다음과 같다.

- 시각은 timezone을 포함한 ISO 8601로 기록한다. 예: `2026-09-15T14:30:00+09:00`
- 정답은 `added`, `removed`, `moved`, `none` 중 하나다.
- `none`은 `expected_event_count=0`인 episode로 기록하고 정답 event 행은 만들지 않는다.
- `verify_removed`는 로컬 중간 후보일 뿐 정답이나 최종 사건으로 쓰지 않는다.
- 워밍업, 기준 장면 부재, 카메라 단절 시간은 `eligible_monitoring_seconds`에서 제외한다.
- 얼굴·문서·화면이 촬영된 표본은 비식별화하거나 폐기한다.
- 원시 CSV와 이미지는 수정본으로 덮어쓰지 말고 새로운 run ID와 디렉터리를 만든다.

빈 수동 기록 작업공간은 다음과 같이 만든다.

```powershell
python -m experiments init data/experiments/manual-R001
```

생성되는 `protocol.json`, `episodes.csv`, `events.csv`, `pair_manifest.csv`를 같은 실험 묶음으로 보관한다.

## 3. 안정 이미지 쌍 데이터 준비

`VISION_PAIR_MANIFEST_TEMPLATE.csv`를 별도 실험 폴더로 복사한 뒤 한 행에 한 사건을 기록한다. 이미지 경로는 manifest 파일 기준 상대 경로 또는 절대 경로를 쓸 수 있다.

| 열 | 입력 방법 |
|---|---|
| `trial_id` | 중복 없는 ID. 예: `classroom-led-shadow-001` |
| `scenario` | 장소·배치 조건. 예: `classroom_table` |
| `lighting` | 예: `led_fixed`, `daylight_mixed`, `exposure_shift` |
| `nuisance` | 예: `none`, `shadow`, `micro_jitter`, `focus`, `occlusion` |
| `before_image`, `after_image` | 안정된 전·후 이미지 경로 |
| `event_ground_truth` | `added`, `removed`, `moved`, `none` |
| `bbox_ground_truth` | 사건 영역 `x;y;width;height`; 양성 사건은 반드시 라벨링 |
| `active_item_id` | moved/removed 대상의 기존 ID |
| `active_bbox` | before 화면의 기존 bbox `x;y;width;height` |
| `active_reference_image` | 선택: 등록 당시 물체 crop |
| `active_background_image` | 선택: 등록 전 빈 배경 crop |
| `source_segment_seconds` | 선택: 이미지 쌍을 추출한 원본 구간 길이. 출처 메타데이터이며 FP/hour 분모로 쓰지 않음 |
| `notes` | 촬영 반복, 예외, 라벨 판단 근거 |

`moved`와 `removed`는 `active_item_id`와 `active_bbox`가 필요하다. 참조 crop을 생략하면 runner가 before/after에서 `active_bbox`를 잘라 사용하므로, after의 이전 위치가 실제 빈 배경인 표본에만 생략한다.
`moved`의 `bbox_ground_truth`는 이동 후 새 위치로 통일하고, 이동 전 위치는 `active_bbox`에 기록한다.

권장 파일 구조 예시는 다음과 같다.

```text
data/experiments/source-R001/
├── pair_manifest.csv
└── images/
    ├── 001-before.jpg
    ├── 001-after.jpg
    └── ...
```

## 4. 코어 ablation 실행

현재 구현된 누적 profile은 다음 순서다.

| profile | 정합 | 전역 노출 보정 | 지속 경계 jitter 억제 | 국소 조명 보정 |
|---|---:|---:|---:|---:|
| `plain` | X | X | X | X |
| `aligned` | O | X | X | X |
| `aligned_global` | O | O | X | X |
| `aligned_global_jitter` | O | O | O | X |
| `full` | O | O | O | O |

모든 profile은 같은 입력 픽셀과 같은 contour/event 로직을 사용한다. 따라서 이는 고정된 순서의 “단계적 방해요인 방어 코어 ablation”이며 각 요소의 독립 인과효과를 뜻하지 않는다. 순수 absolute difference, 상태기계 제거와 OpenCV MOG2는 같은 `D_stream` replay에서 별도 필수 baseline으로 구현·측정한다. 세 baseline은 공통 FPS·warm-up·후보 병합 시간창·활성 물품 event adapter를 사용하고, B0/B1의 참조 갱신 규칙과 MOG2의 history·varThreshold·background ratio·learning rate를 개발 세트에서 고정해 run metadata에 남긴다. 이 adapter가 정의되지 않으면 added/moved/removed Macro-F1을 직접 비교하지 않는다.

```powershell
python -m experiments run-pairs `
  --manifest data/experiments/source-R001/pair_manifest.csv `
  --output-dir data/experiments/result-R001 `
  --run-id R001 `
  --profiles plain,aligned,aligned_global,aligned_global_jitter,full `
  --device "Raspberry Pi 4 Model B 2GB" `
  --camera-model "카메라 모델 입력" `
  --operator "실험자 코드"
```

동일 출력 디렉터리를 덮어쓰지 않도록 명령이 거부한다. 설정을 바꿀 때는 JSON 객체를 만들어 `--config-json settings.json`으로 전달한다. 이 파일로 네 ablation 핵심 스위치를 덮어쓰려 하면 profile 이름과 실제 구성이 달라지는 것을 막기 위해 실행이 거부된다. 실제 실행 설정과 detector 소스 hash는 결과에 함께 보존되며, 논문에는 profile 이름뿐 아니라 `configs/*.json`과 hash를 보관한다.

결과 파일은 다음과 같다.

- `episodes.csv`, `events.csv`: 분석 가능한 원시 기록
- `pair_trials.csv`: 각 표본의 모든 예측과 코어 시간
- `configs/*.json`: profile별 실제 설정
- `run_metadata.json`: manifest hash와 측정 범위
- `summary-local.json`, `summary-local-overall.csv`, `summary-local-by-kind.csv`: 논문 표의 출발 지표

각 profile은 내부적으로 `R001__plain`, `R001__aligned`처럼 별도 run으로 기록된다.
`pair_trials.csv`의 `process_cpu_ms`와 `process_cpu_percent`는 단일 `_detect_changes()` 호출의 보조 값일 뿐 장시간 자원 평균·최대가 아니다. 그래서 이 값은 `episodes.csv`의 `cpu_avg_pct`, `cpu_peak_pct`에 복사하지 않으며, 논문의 Pi 자원 표는 제6절의 별도 1초 계측으로 작성한다.

## 5. 검증과 재집계

수동 또는 자동 수집 CSV를 먼저 검증한다.

```powershell
python -m experiments validate `
  --episodes data/experiments/result-R001/episodes.csv `
  --events data/experiments/result-R001/events.csv
```

로컬 예측은 다음처럼 집계한다.

```powershell
python -m experiments summarize `
  --episodes data/experiments/result-R001/episodes.csv `
  --events data/experiments/result-R001/events.csv `
  --output-dir data/experiments/summary-R001-local `
  --stage local
```

VLM 이후 최종 사건이 기록된 종단간 데이터는 `--stage final`을 사용한다. 정답과 예측은 episode 안에서 사건 종류, bbox IoU, 시간 창을 이용해 일대일 최적 매칭한다. 매칭 수를 먼저 최대화하고, 중복 후보가 있으면 자격을 만족한 더 이른 예측, 그다음 높은 IoU 순으로 선택한다. 기본 IoU 임계값은 0.30이며, protocol에서 다른 값을 정했다면 `--iou`를 명시한다. 시간 창을 제한하려면 `--window-seconds`를 사용하고 그 값을 결과에 함께 쓴다. 창을 생략하면 `action_end_at`부터 `ended_at`까지이다. `action_end_at`은 물품 또는 조작하는 손의 마지막 물리적 접촉이 끝나고 물품이 최종 상태에 머물기 시작한 첫 frame으로 라벨링한다. 수집 중 `episode_complete=false`인 행은 검증 경고와 함께 보관할 수 있지만 `ended_at`을 채워 완료하기 전에는 집계가 거부된다. 종단간 실험에서는 fallback 기준시각을 쓰지 않도록 `action_end_at`을 필수로 채운다.

CLI는 사건 종류별·micro·macro precision/recall/F1, precision/recall Wilson 구간, 무사건 표본 오탐 발생률, FP/hour, IoU, ID 보존율과 각 지연의 표본 수·p50·p95를 출력한다. recording session을 주 cluster로 고정한 10,000회 bootstrap CI, IoU 0.50 민감도, FP/hour의 Poisson exact 및 run-block CI, McNemar·Holm 결과는 별도 고정 분석 script로 산출한다. 동일 물품은 development와 final 사이에 걸치지 않게 group split하고 item-cluster 분석은 민감도 결과로만 사용한다.

해석 경계는 다음과 같다.

- 안정 이미지 쌍에서는 `none` 표본 중 하나 이상의 오탐이 난 비율을 주지표로 쓴다. FP/hour는 실제 연속 무사건 감시에서 워밍업·단절을 제외한 wall-clock 초를 기록한 경우에만 운영 수치로 쓴다.
- FP/hour의 분자는 `none` episode에서 선택 stage가 만든 `added/removed/moved` 오탐만이다. 양성 episode의 여분 예측은 precision에는 포함되지만 이 분자에는 포함되지 않는다.
- 지연 분포는 IoU와 종류가 일치해 성공적으로 TP 매칭된 사건에 조건부다. recall, 각 분포의 `count`, timestamp 결측률을 함께 보고한다.
- `--stage final`의 `selected_event_latency_ms`는 선택된 final 행의 `event_at` 기준이다. DB, AI, 최종 확정은 각각 명시적인 `provisional_db`, `ai_round_trip`, `final_commit` 열을 사용한다.
- `duplicate_prediction_count`는 같은 정답에 대한 여분 검출 수이지 중복 DB ID 수가 아니다.
- `ignored_prediction_count`는 `verify_removed`뿐 아니라 집계에서 선택하지 않은 반대 stage 행도 포함한다.
- macro 평균은 support가 없는 종류도 포함해 `added`, `removed`, `moved` 세 종류를 고정 평균한다. 비교 run마다 세 종류 표본을 모두 포함하고 종류별 support를 함께 제시한다.
- 현재 duplicate-ID 생성률은 ID 평가가 가능한 matched-moved TP 중 예측에 상이한 새 `object_id`가 명시된 조건부 비율이다. 안정 이미지 쌍 runner는 예측 `object_id`를 만들지 않으므로 이 값으로 “중복 없음”을 주장할 수 없다.
- `moved`를 `added`로 오판해 새 DB 행을 만든 사례는 moved FN과 added FP로 반영된다. 전체 moved 사건 기준 실제 DB 중복률로도 세려면 실시간 원장에 `created_new_id`와 생성 ID를 명시해 별도 운영지표를 고정한다.

## 6. Raspberry Pi 자원 기록

Pi에 배포한 뒤 Re:Found 서비스와 동시에 실행한다. `/opt/refound/data`의 권한을 가진 설치 당시 일반 사용자로 실행하며, 먼저 `systemctl is-active refound.service`가 `active`인지 확인한다.

```bash
/opt/refound/.venv/bin/python \
  /opt/refound/scripts/experiments/monitor_pi_resources.py \
  --service refound.service \
  --output /opt/refound/data/experiments/R001-resources.csv \
  --disk-path /opt/refound/data \
  --trial-id R001 \
  --duration 7200
```

기본 간격은 1초이고, 파일은 새 경로에만 생성된다. 첫 CPU 표본은 이전 누적값이 없어 비어 있을 수 있다. 첫 행의 `pid`, `process_alive`, `rss_mib`가 채워졌는지 즉시 확인한다. 프로세스 CPU는 한 코어 기준이라 멀티코어 사용 시 100%를 넘을 수 있으며, 별도의 device-normalized 열을 함께 기록한다. `process_cpu_percent`와 `rss_mib`는 Re:Found 주 프로세스 지표이고, system CPU·load·가용 메모리·디스크는 계측기와 OS까지 포함한 장치 전체 지표이므로 논문 표를 분리한다. 온도는 Pi의 `/sys/class/thermal`이 보고한 thermal-zone 값일 때만 채워지며 보정된 절대 접합온도로 표현하지 않는다.

전력은 이 스크립트가 추정하지 않는다. 같은 시간대의 외부 AC 전력계 또는 USB 전력계에서 W와 Wh를 기록하고 시계를 UTC로 동기화한다. AC 콘센트 측정과 USB/DC 입력 측정은 전원 어댑터 손실 포함 범위가 달라 서로 직접 비교하지 않는다. 측정 지점, 포함 주변장치, 계측기 모델·정확도·샘플링률과 idle 보정 여부를 논문에 쓴다.

## 7. 최소 파일럿과 본 실험

처음부터 300건을 촬영하지 말고 아래 파일럿으로 protocol을 고정한다.

1. 물품 5종, added/removed/moved 각 5회
2. 무사건 방해요인 none/조명/그림자/미세진동/초점 각 10회 또는 동등한 유효 감시 시간
3. 두 명이 독립적으로 20%를 라벨링해 bbox와 사건 종류 기준을 점검
4. 다섯 profile을 실행하고 누락 열, 매칭 오류, global suppression 사례를 검토
5. protocol과 임계값을 고정한 뒤 본 실험을 별도 run으로 시작

본 실험 중 결과를 보고 임계값을 바꾸면 해당 데이터는 개발 세트로 분리한다. 최종 평가 세트의 설정은 한 번만 실행하고, 실패 표본도 제외하지 않은 채 사유와 함께 보존한다.

## 8. 아직 추가해야 하는 계측

현재 도구는 안정 이미지 쌍과 Pi 자원 원장을 제공한다. 논문의 전체 주장을 위해 다음 구현·수집이 남아 있다.

- 실제 `VisionMonitor`의 motion 시작, action 종료, stable 확정, local callback timestamp
- 임시 DB 저장과 최종 commit timestamp, 논리 VLM 작업 ID, 공급자별 HTTP 시도·성공 여부, 모델 ID, prompt hash, 업로드 byte, 입력·출력 token과 비용
- capture read 실패, scheduler skip, change callback drop, diagnostic callback drop을 분리한 누적 counter와 카메라 reconnect 시간
- 순수 grayscale absolute difference, 상태기계 제거형, OpenCV MOG2, 제안 전체 시스템을 동일 스트림에서 비교하는 replay runner
- DB 저장 실패·VLM timeout·프로세스 재시작을 재현하는 통제된 fault-injection runner
- 동일 사건에 대한 1장/2장/4장 멀티모달 증거 ablation
- 실행 중 privacy 전환 전 queue 작업의 잔류 여부와 재시작 시 저장 privacy 설정을 VisionMonitor에 재적용하는 부팅 동기화
- 2시간 파일럿 후 8시간·24시간 장시간 안정성 실험

이 값이 생기기 전에는 “실시간”, “호출량 감소”, “저전력”, “높은 정확도”를 수치나 단정으로 쓰지 않는다.
