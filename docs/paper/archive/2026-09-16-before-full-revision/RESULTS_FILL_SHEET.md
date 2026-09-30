# Re:Found 논문 실측값 입력표

이 문서는 PAPER_DRAFT_JDCS.md의 이중 대괄호 placeholder를 실제 실험 결과로 교체하기 위한 단일 체크리스트다. 다른 AI에 초안을 전달할 때 반드시 함께 제공한다.

## 1. 사용 원칙

1. 이중 대괄호 항목은 추정값, 기대값 또는 발표용 예시로 채우지 않는다.
2. 수치마다 원본 CSV, 실행 run_id, 설정 JSON과 소스 hash를 남긴다.
3. 최종 평가 결과를 본 뒤 threshold를 바꾸면 해당 데이터는 개발 세트로 이동한다.
4. 안정 이미지 쌍의 core 처리시간을 종단간 지연으로 표현하지 않는다.
5. 안정 이미지 쌍에서 false events/hour를 계산하지 않는다. 연속 none 감시의 유효 wall-clock 시간만 분모로 쓴다.
6. 지연은 matched TP에 조건부이므로 recall, count와 timestamp 결측률을 함께 적는다.
7. 실제 결과가 가설과 다르면 논문의 주장과 결론을 결과에 맞게 바꾼다.

## 2. 투고 가능 상태를 위한 최소 우선순위

### P0 — 반드시 있어야 하는 값

- 사건별 added/removed/moved support, precision, recall, F1 및 IoU
- none episode 오작동률
- 실제 연속 none 감시시간과 false events/hour
- 다섯 nuisance-defense profile의 paired ablation
- 같은 \(D_{stream}\) replay에서 순수 absdiff, 상태기계 제거, OpenCV MOG2와 전체 pipeline 비교
- Raspberry Pi의 실제 처리 FPS, local 지연, CPU, RSS와 온도
- 평가 장비, 카메라, OS, 냉각, 네트워크와 실행 설정
- 실패 사례 수와 대표 영상

### P1 — 논문의 선택적 VLM 기여를 주장하려면 필요한 값

- 전체 episode 대비 실제 VLM 호출 수와 호출률
- 1장/2장/2장 scene/4장 증거 구성별 action·category·물품 의미 성능
- 요청 byte, AI round trip, provider/model/date, 사용량 또는 비용
- API 실패 시 provisional 레코드 보존률

### P2 — 외적 타당도와 모듈 독립효과를 강화하는 값

- full에서 한 요소씩 제거하는 leave-one-out
- 8시간 이상 장시간 실행과 camera reconnect/callback drop 원장
- 외부 전력계에 의한 idle/monitor/event 전력
- 복수 장소·조도·설치 각도 반복 평가

P1이 없으면 제목과 본문의 “선택적 멀티모달 추론”은 구현 설명 수준으로만 남고 실험적 기여로 주장하기 어렵다. P0의 사건 성능, 공통 replay baseline과 Pi 자원 측정이 없으면 학술지 투고용 결과 논문으로 제출하지 않는다.

## 3. 논문 기본정보

| Placeholder | 입력할 값 | 확인 방법 |
|---|---|---|
| [[AUTHOR_ORDER_AND_CORRESPONDING]] | 저자 순서, 교신저자, 이메일 | 팀과 지도교수 확인 |
| [[EQUIP_OS_KERNEL]] | Raspberry Pi OS 버전, 32/64 bit, kernel | os-release와 uname 기록 |
| [[EQUIP_CAMERA_LENS]] | CSI 카메라 모듈과 렌즈 | 실제 부품 라벨·구매내역 |
| [[EQUIP_CAMERA_GEOMETRY]] | 카메라–보관대 거리, 높이, 각도 | 줄자·각도계 및 설치 사진 |
| [[EQUIP_STORAGE]] | microSD/SSD 모델과 용량 | 장치 기록 |
| [[EQUIP_COOLING]] | 방열판, 팬, 케이스 | 설치 사진 |
| [[EQUIP_POWER_AND_METER]] | 전원과 계측 위치·기기·정확도 | 외부 계측기 설명서 |
| [[EQUIP_OPENCV_PYTHON]] | OpenCV와 Python 버전 | 실행환경 freeze |
| [[VLM_PROVIDER_MODEL_DATE]] | provider, 정확한 model ID, 실행 일시 | 각 요청 원장 |
| [[NETWORK_CONDITION]] | Wi-Fi/Tailscale, uplink/downlink, RTT | 실험 protocol |

## 4. 데이터셋 및 라벨 품질

- \(D_{pair}\): 안정 전후 영상쌍. detector core와 단계적 ablation 전용
- \(D_{stream}\): 연속 replay/실시간 episode. 상태기계, ID, Table 7, FP/hour와 종단간 지연
- \(D_{vlm}\): 동일 사건 증거의 V1–V4 paired 비교
- \(D_{fault}\): network, timeout, malformed JSON, queue 포화, stale response 장애 주입

moved의 정답 bbox는 이동 후 위치로 라벨링하고 이동 전 active_bbox와 active_item_id를 별도로 보관한다. Table 5와 Table 7의 결과는 \(D_{stream}\)을 원천으로 하며, \(D_{pair}\) 결과를 종단간 성능으로 옮겨 쓰지 않는다.

| Placeholder | 입력할 값 | 권장 원천 |
|---|---|---|
| [[OBJECT_TYPE_COUNT]] | 서로 다른 물품 종류 수 | item inventory |
| [[SITE_COUNT]] | 독립 설치 장소 수 | protocol |
| [[CAPTURE_DAY_COUNT]] | 촬영 일수 | capture log |
| [[N_DEV_ADDED]], [[N_DEV_REMOVED]], [[N_DEV_MOVED]], [[N_DEV_NONE]], [[N_DEV_TOTAL]] | 개발 episode 수 | 개발 episodes.csv |
| [[N_TEST_ADDED]], [[N_TEST_REMOVED]], [[N_TEST_MOVED]], [[N_TEST_NONE]], [[N_EVAL_EPISODES]] | 고정된 최종 평가 episode 수 | 평가 episodes.csv |
| [[N_PAIR_EVAL]] | 모든 profile에 공통으로 사용한 최종 \(D_{pair}\) 영상쌍 수 | pair manifest |
| [[N_VLM_ACTION]], [[N_VLM_GT_ADDED]], [[N_VLM_GT_REMOVED]] | decisive action 전체와 종류별 \(D_{vlm}\) 표본 수 | VLM manifest |
| [[N_VLM_RETAIN]] | verify_removed 경로의 non-removal/retain 표본 수 | VLM manifest |
| [[VLM_REPEATS_PER_CASE]] | 같은 사례·증거 구성의 반복 호출 수 | VLM protocol |
| [[N_GT_AMBIGUOUS_REMOVAL]] | 결과를 보지 않고 두 라벨러가 사전 기준으로 지정한 모호 제거 수 | annotation log |
| [[DOUBLE_LABEL_RATIO]] | 이중 라벨링 비율 | annotation log |
| [[LABEL_KAPPA]] | 사건 종류 Cohen’s κ | 라벨러 원본 |
| [[LABEL_BBOX_IOU]] | 라벨러 bbox 평균/중앙 IoU | 라벨러 원본 |
| [[NONE_MONITORING_HOURS]] | 워밍업·중단 제외 유효 시간 | continuous none log |

권장 분할은 물품과 촬영 반복이 development와 final evaluation에 중복되어 과대평가되지 않게 group 단위로 수행한다. 본 연구는 학습 모델이 없지만 threshold 조정도 개발 과정이므로 최종 평가 분리는 필요하다.

## 5. 로컬 사건 결과

### 5-1. 사건별 값

다음 placeholder는 experiments summarize의 summary 파일과 원시 episodes.csv/events.csv를 함께 보며 입력한다.

| 그룹 | Placeholder |
|---|---|
| Support | [[SUPPORT_ADDED]], [[SUPPORT_REMOVED]], [[SUPPORT_MOVED]], [[SUPPORT_TOTAL_POSITIVE]] |
| Precision | [[P_ADDED_CI]], [[P_REMOVED_CI]], [[P_MOVED_CI]], [[P_MICRO_CI]], [[P_MACRO]] |
| Recall | [[R_ADDED_CI]], [[R_REMOVED_CI]], [[R_MOVED_CI]], [[R_MICRO_CI]], [[R_MACRO]] |
| F1 | [[F1_ADDED]], [[F1_REMOVED]], [[F1_MOVED]], [[F1_MICRO]], [[LOCAL_MACRO_F1]], [[LOCAL_MACRO_F1_CI]] |
| IoU | [[IOU_ADDED_P50]], [[IOU_REMOVED_P50]], [[IOU_MOVED_P50]], [[IOU_ALL_P50]], [[IOU50_MACRO_F1_CI]] |
| 해석 | [[BEST_EVENT_KIND]], [[BEST_EVENT_F1]], [[WORST_EVENT_KIND]], [[WORST_EVENT_F1]], [[RESULT_EVENT_INTERPRETATION]] |

### 5-2. ID 및 none 조건

| Placeholder | 정의 |
|---|---|
| [[MOVED_ID_RETENTION_CI]] | scorable matched moved TP 중 기존 object_id 유지 비율과 95% CI |
| [[MOVED_ID_SCORABLE_N]] | 정답·예측 item_id가 모두 있어 ID 평가가 가능한 matched moved TP 수 |
| [[MOVED_ID_COVERAGE]] | MOVED_ID_SCORABLE_N / 전체 GT-moved |
| [[MOVED_ID_ASSIGNMENT_ERROR_CI]] | scorable matched moved TP 중 다른 object_id가 할당된 비율 |
| [[MOVED_DUPLICATE_ID_RATE_CI]] | 전체 GT-moved 중 added 오분류 등을 포함해 기존 ID 외 새 DB 행이 생성된 비율 |
| [[REMOVAL_CANDIDATE_RECALL_CI]] | GT-removed 중 removed 또는 verify_removed 후보가 위치·시간 조건을 만족한 비율 |
| [[REMOVAL_VERIFY_REFERRAL_RATE_CI]] | 제거 후보 중 verify_removed로 보낸 비율 |
| [[NONE_EPISODE_TRIGGER_RATE_CI]] | none episode 중 하나 이상의 added/removed/moved를 낸 비율 |
| [[NONE_VERIFY_REFERRAL_RATE_CI]] | none episode 중 verify_removed/VLM referral이 발생한 비율 |
| [[NONE_FALSE_EVENT_COUNT]] | 연속 none 감시에서 발생한 물품 오탐 수 |
| [[FALSE_EVENTS_PER_HOUR]] | NONE_FALSE_EVENT_COUNT / NONE_MONITORING_HOURS |
| [[FALSE_EVENTS_PER_HOUR_POISSON_CI]] | FP/hour의 Poisson exact 95% CI |
| [[FALSE_EVENTS_PER_HOUR_BLOCK_CI]] | 연속 run을 block으로 둔 bootstrap 95% CI |
| [[MOST_COMMON_FALSE_TRIGGER]] | 실패 taxonomy에서 가장 많은 오탐 원인 |

안정 이미지 pair runner는 예측 object_id와 DB 행을 만들지 않으므로 ID 관련 값을 채울 수 없다. 반드시 실제 \(D_{stream}\) VisionMonitor→DB 실행 원장이 필요하다. 로컬 확정 사건 지표에서는 verify_removed를 예측 removed로 세지 않고 referral로 따로 기록하며, VLM 이후 final removed는 final stage에서 다시 채점한다.

표 7의 F1과 IoU placeholder에는 점추정치와 recording-session cluster bootstrap 95% CI를 함께 입력한다. `LOCAL_MACRO_F1`은 점추정치, `LOCAL_MACRO_F1_CI`는 그 구간이다. `IOU50_MACRO_F1_CI`에는 IoU 0.50 민감도 분석의 Macro-F1 점추정치와 95% CI를 함께 넣는다. Precision·recall의 `_CI` 값과 `P_MACRO`, `R_MACRO`도 점추정치와 해당 구간을 함께 표기한다.

## 6. Nuisance-defense ablation

현재 구현된 도구로 바로 실행할 수 있는 부분이다.

    python -m experiments run-pairs --manifest data/experiments/source-R001/pair_manifest.csv --output-dir data/experiments/result-R001 --run-id R001 --profiles plain,aligned,aligned_global,aligned_global_jitter,full --device "Raspberry Pi 4 Model B 2GB" --camera-model "실제 모델" --operator "실험자 코드"

| profile | F1 | none rate | core latency | full과 paired 비교 |
|---|---|---|---|---|
| plain | [[ABL_PLAIN_F1]] | [[ABL_PLAIN_NONE_RATE]] | [[ABL_PLAIN_LATENCY]] | [[ABL_PLAIN_P_ADJ]] |
| aligned | [[ABL_ALIGNED_F1]] | [[ABL_ALIGNED_NONE_RATE]] | [[ABL_ALIGNED_LATENCY]] | [[ABL_ALIGNED_P_ADJ]] |
| aligned_global | [[ABL_GLOBAL_F1]] | [[ABL_GLOBAL_NONE_RATE]] | [[ABL_GLOBAL_LATENCY]] | [[ABL_GLOBAL_P_ADJ]] |
| aligned_global_jitter | [[ABL_JITTER_F1]] | [[ABL_JITTER_NONE_RATE]] | [[ABL_JITTER_LATENCY]] | [[ABL_JITTER_P_ADJ]] |
| full | [[ABL_FULL_F1]] | [[ABL_FULL_NONE_RATE]] | [[ABL_FULL_LATENCY]] | 기준 |

추가 입력:

- [[ABL_F1_DELTA]] = full − plain
- [[ABL_NONE_DELTA]] = full − plain
- [[RESULT_ABLATION_INTERPRETATION]] = nuisance별 교차표에 근거한 해석
- pure absdiff 상태: [[IMPLEMENT_AND_RUN_PURE_ABSDIFF]]
- no-state-machine replay 상태: [[IMPLEMENT_AND_RUN_NO_STATE_MACHINE]]
- MOG2 공통 replay 상태: [[IMPLEMENT_AND_RUN_MOG2]]
- 공통 warm-up: [[BASELINE_WARMUP_SECONDS]]초
- 후보→사건 adapter: [[BASELINE_EVENT_ADAPTER_PROTOCOL]]
- B0·B1 참조 갱신: [[B0_B1_REFERENCE_UPDATE_RULE]]
- B2 MOG2 설정: [[B2_MOG2_PARAMETERS]]

plain은 순수 absdiff가 아니다. 논문 결과표와 그림 캡션에도 “단계적 nuisance-defense core ablation”이라고 쓰고 각 요소의 독립효과로 해석하지 않는다. 현재 CLI summary는 McNemar p-value, Holm 보정, cluster bootstrap CI와 latency CI를 자동 표에 쓰지 않는다. experiments의 helper 또는 별도 고정 분석 script로 산출하고 분석 code·seed·cluster 단위를 보관한다.

공통 \(D_{stream}\) baseline 결과:

| 구성 | Macro-F1 | none rate | FP/hour | local p95 |
|---|---|---|---|---|
| B0 absdiff | [[B0_MACRO_F1]] | [[B0_NONE_RATE]] | [[B0_FP_HOUR]] | [[B0_LOCAL_P95]] |
| B1 no state machine | [[B1_MACRO_F1]] | [[B1_NONE_RATE]] | [[B1_FP_HOUR]] | [[B1_LOCAL_P95]] |
| B2 MOG2 | [[B2_MACRO_F1]] | [[B2_NONE_RATE]] | [[B2_FP_HOUR]] | [[B2_LOCAL_P95]] |
| 해석 | [[RESULT_BASELINE_INTERPRETATION]] | — | — | — |

baseline의 FP/hour 셀은 point estimate와 Poisson exact 95% CI를 함께 쓰고, run-block bootstrap 결과는 본문 또는 보조자료에 둔다. candidate mask만 비교하는 binary change-detection 실험이라면 added/moved/removed Macro-F1 표를 사용하지 말고 별도 결과로 명시한다.

통계 산출 조건:

- recording session을 주 cluster로 한 10,000회 bootstrap: P/R/F1, Macro-F1, IoU, latency와 profile 차이
- 동일 물품은 development/final 사이에 걸치지 않게 group split하고, item-cluster 결과는 sensitivity로만 사용
- 고정 seed: [[BOOTSTRAP_SEED]]
- IoU 0.30 주 결과와 0.50 민감도 분석
- FP/hour: Poisson exact CI와 run-block bootstrap
- McNemar: F1이 아니라 episode 전체 정답 여부의 paired endpoint
- V1–V4: 같은 사건 paired 비교, 호출 순서 무작위화

## 7. 방해요인 및 실패 사례

각 범주의 N, FP, FN과 대표 파일 ID를 한 원장에 기록한다.

| 범주 | 결과 placeholder | 실패표 placeholder |
|---|---|---|
| 노출 | [[NUIS_EXPOSURE_N]], [[NUIS_EXPOSURE_FP]], [[NUIS_EXPOSURE_FN]], [[NUIS_EXPOSURE_RATE]] | [[FAIL_EXPOSURE_N]], [[FAIL_EXPOSURE_FP]], [[FAIL_EXPOSURE_FN]], [[FAIL_EXPOSURE_NOTE]] |
| 그림자·반사 | [[NUIS_SHADOW_N]], [[NUIS_SHADOW_FP]], [[NUIS_SHADOW_FN]], [[NUIS_SHADOW_RATE]] | [[FAIL_SHADOW_N]], [[FAIL_SHADOW_FP]], [[FAIL_SHADOW_FN]], [[FAIL_SHADOW_NOTE]] |
| jitter | [[NUIS_JITTER_N]], [[NUIS_JITTER_FP]], [[NUIS_JITTER_FN]], [[NUIS_JITTER_RATE]] | [[FAIL_JITTER_N]], [[FAIL_JITTER_FP]], [[FAIL_JITTER_FN]], [[FAIL_JITTER_NOTE]] |
| 초점 | [[NUIS_FOCUS_N]], [[NUIS_FOCUS_FP]], [[NUIS_FOCUS_FN]], [[NUIS_FOCUS_RATE]] | jitter와 결합한 실패표와 별도 원장을 모두 보존 |
| 가림 | [[NUIS_OCCLUSION_N]], [[NUIS_OCCLUSION_FP]], [[NUIS_OCCLUSION_FN]], [[NUIS_OCCLUSION_RATE]] | [[FAIL_OCCLUSION_N]], [[FAIL_OCCLUSION_FP]], [[FAIL_OCCLUSION_FN]], [[FAIL_OCCLUSION_NOTE]] |
| 정상 none | [[NUIS_NONE_N]], [[NUIS_NONE_FP]], [[NUIS_NONE_RATE]] | 해당 시 기록 |
| 소형·저대비 | — | [[FAIL_SMALL_N]], [[FAIL_SMALL_FP]], [[FAIL_SMALL_FN]], [[FAIL_SMALL_NOTE]] |
| settling | — | [[FAIL_SETTLING_N]], [[FAIL_SETTLING_FP]], [[FAIL_SETTLING_FN]], [[FAIL_SETTLING_NOTE]] |
| 사건 혼동 | — | [[FAIL_KIND_N]], [[FAIL_KIND_FP]], [[FAIL_KIND_FN]], [[FAIL_KIND_NOTE]] |
| ID | — | [[FAIL_ID_N]], [[FAIL_ID_ERROR]], [[FAIL_ID_NOTE]] |
| 시스템 | — | [[FAIL_SYSTEM_N]], [[FAIL_SYSTEM_ERROR]], [[FAIL_SYSTEM_NOTE]] |

## 8. Raspberry Pi 지연과 자원

### 8-1. 장시간 자원 기록

    /opt/refound/.venv/bin/python /opt/refound/scripts/experiments/monitor_pi_resources.py --service refound.service --output /opt/refound/data/experiments/R001-resources.csv --disk-path /opt/refound/data --trial-id R001 --duration 7200

| 측정 | Placeholder |
|---|---|
| local latency | [[N_LAT_LOCAL]], [[LAT_LOCAL_MEAN]], [[LOCAL_LATENCY_P50_MS]], [[LOCAL_LATENCY_P50_CI]], [[LOCAL_LATENCY_P95_MS]], [[LOCAL_LATENCY_P95_CI]], [[LAT_LOCAL_MAX]] |
| provisional DB | [[N_LAT_DB]], [[LAT_DB_MEAN]], [[LAT_DB_P50]], [[LAT_DB_P95]], [[LAT_DB_MAX]] |
| AI round trip | [[N_LAT_AI]], [[LAT_AI_MEAN]], [[LAT_AI_P50]], [[LAT_AI_P95]], [[LAT_AI_MAX]] |
| final commit | [[N_LAT_FINAL]], [[LAT_FINAL_MEAN]], [[LAT_FINAL_P50]], [[LAT_FINAL_P95]], [[LAT_FINAL_MAX]] |
| process CPU | [[N_RESOURCE]], [[CPU_MEAN]], [[CPU_P50]], [[CPU_P95]], [[CPU_MAX]] |
| normalized CPU | [[CPU_NORM_MEAN]], [[CPU_NORM_P50]], [[CPU_NORM_P95]], [[CPU_NORM_MAX]] |
| RSS | [[RSS_MEAN]], [[RSS_P50]], [[RSS_P95]], [[RSS_MAX]] |
| thermal zone | [[N_RESOURCE_TEMP]], [[TEMP_MEAN]], [[TEMP_P50]], [[TEMP_P95]], [[TEMP_MAX]] |
| timestamp 품질 | [[LATENCY_TIMESTAMP_MISSING_RATE]] |
| throughput | [[ACHIEVED_MONITOR_FPS]], [[CAPTURE_READ_FAILURE_COUNT]], [[MONITOR_SCHEDULER_SKIP_RATE]] |
| callback queue | [[CHANGE_CALLBACK_DROP_COUNT]], [[DIAGNOSTIC_CALLBACK_DROP_COUNT]] |
| 해석 | [[RESULT_RESOURCE_INTERPRETATION]] |

현재 resource recorder는 장치 자원을 수집하지만 action_end→local/DB/final과 ai_request→ai_response timestamp 전체 계측은 애플리케이션 원장에 추가로 연결해야 한다. frame/drop 누적 counter도 현재 없고 queue 포화 시 generic last_error만 남으므로, 물품 change와 진단 callback을 구분하는 영속 counter를 먼저 구현한다.

local p50/p95는 점추정치와 recording-session cluster bootstrap 95% CI를 분리해 입력한다. 다른 latency 행의 p50/p95 placeholder에는 점추정치와 같은 방식의 CI를 함께 표기하고, matched TP 수와 timestamp 결측률을 반드시 병기한다.

### 8-2. 전력

| Placeholder | 조건 |
|---|---|
| [[POWER_MEASUREMENT_STATUS]] | 미측정이면 “외부 계측 미실시”라고 명시 |
| [[POWER_IDLE_W]] | 서비스 idle의 외부 계측 평균 |
| [[POWER_MONITOR_W]] | 카메라 감시 중 평균 |
| [[POWER_EVENT_W]] | 사건 처리 구간 평균 |

외부 계측기가 없다면 전력 숫자를 빼고 CPU, RSS와 온도만 보고한다. 보드 사양이나 소프트웨어 지표로 소비전력을 추정하지 않는다.

## 9. 선택적 VLM 실험

현재 애플리케이션은 최대 4장 입력을 구현한다. provider=auto일 때만 OpenAI 실패 후 Gemini를 순차 시도하며, openai 또는 gemini를 명시하면 다른 provider로 교차 fallback하지 않는다. V1–V4 비교에서는 auto fallback을 끄고 단일 provider/model을 고정한다. 증거 구성 ablation runner와 model ID, prompt hash, request byte, token, 비용, 요청·응답 timestamp를 보존하는 VLM 원장은 아직 없으므로 실험 전에 추가한다.

| 구성 | Placeholder |
|---|---|
| V1 after crop | [[V1_ACTION_ACC]], [[V1_ACTION_SELECTIVE_ACC]], [[V1_CATEGORY_ACC]], [[V1_NAME_ACC]], [[V1_COVERAGE]], [[V1_UNCERTAIN]], [[V1_LATENCY]], [[V1_BYTES]] |
| V2 crop pair | [[V2_ACTION_ACC]], [[V2_ACTION_SELECTIVE_ACC]], [[V2_CATEGORY_ACC]], [[V2_NAME_ACC]], [[V2_COVERAGE]], [[V2_UNCERTAIN]], [[V2_LATENCY]], [[V2_BYTES]] |
| V3 scene pair | [[V3_ACTION_ACC]], [[V3_ACTION_SELECTIVE_ACC]], [[V3_CATEGORY_ACC]], [[V3_NAME_ACC]], [[V3_COVERAGE]], [[V3_UNCERTAIN]], [[V3_LATENCY]], [[V3_BYTES]] |
| V4 scene+crop pairs | [[V4_ACTION_ACC]], [[V4_ACTION_SELECTIVE_ACC]], [[V4_CATEGORY_ACC]], [[V4_NAME_ACC]], [[V4_COVERAGE]], [[V4_UNCERTAIN]], [[V4_LATENCY]], [[V4_BYTES]] |

exact action 전체 정확도는 GT-added/GT-removed decisive 표본 [[N_VLM_ACTION]]개에서 계산하고 uncertain을 오답으로 처리한다. selective accuracy는 uncertain이 아닌 응답만 분모로 하고 coverage를 함께 쓴다. category와 name은 GT-added [[N_VLM_GT_ADDED]]개에서만 평가한다. non-removal/retain [[N_VLM_RETAIN]]개는 raw exact action 표에 섞지 않고 아래 운영 결정으로 평가한다.

| 운영 결정 | Placeholder | 정의 |
|---|---|---|
| added register/hold | [[VLM_REGISTER_DECISION_ACC]] | added 경로에서 올바른 등록 또는 안전한 보류를 선택한 비율 |
| verify recover | [[VLM_RECOVER_DECISION_ACC]] | 실제 제거에서 recovered 전환을 올바르게 선택한 비율 |
| verify retain safety | [[VLM_RETAIN_SAFETY_ACC]] | non-removal/외형 변화에서 기존 물품을 유지한 비율 |

호출 정책:

| Placeholder | 정의 |
|---|---|
| [[TOTAL_MONITORED_EPISODES]] | 실제 감시 episode 전체 |
| [[LOCAL_EVENT_COUNT]] | 로컬 물품 사건 수 |
| [[VLM_CALL_COUNT]] | added와 verify_removed에서 생성된 logical inference job 수 |
| [[VLM_CALL_RATE]] | VLM_CALL_COUNT / TOTAL_MONITORED_EPISODES |
| [[VLM_GATE_RECALL_ADDED_CI]] | 모든 GT-added 중 logical job이 생성된 비율과 95% CI |
| [[VLM_GATE_RECALL_REMOVAL_CI]] | 사전 라벨된 [[N_GT_AMBIGUOUS_REMOVAL]]개 모호 제거 중 logical job이 생성된 비율과 95% CI |
| [[VLM_ATTEMPT_COUNT]] | auto fallback의 재시도를 포함한 provider HTTP attempt 수 |
| [[VLM_SUCCESS_COUNT]] | 유효 JSON 응답까지 얻은 attempt 또는 job 수; 어느 분모인지 명시 |
| [[TRANSFER_REDUCTION_RESULT]] | 모든 analyzing episode의 전후 전체 장면을 보내는 no-gating 기준선 대비 동일 replay의 직렬화 payload byte 변화 |
| [[ALL_FRAME_TRANSFER_UPPER_BOUND]] | 모든 처리 frame 전송 대비 분석적 상한; 실측과 구분 |
| [[COST_PER_EPISODE]], [[COST_PER_ATTEMPT]] | provider usage·청구 원장에 근거한 원화 또는 USD |
| [[RESULT_VLM_INTERPRETATION]] | 정확도–byte–지연 trade-off |
| [[END_TO_END_TASK_SUCCESS]] | \(D_{stream}\)에서 로컬 누락과 DB 반영까지 포함한 업무 성공률 |
| [[TASK_SUCCESS_ADDED_CI]], [[TASK_SUCCESS_MOVED_CI]], [[TASK_SUCCESS_REMOVED_CI]], [[TASK_SUCCESS_MACRO_CI]] | 종류별 종단간 업무 성공률과 세 종류 macro, 각 95% CI |

주 비교의 no-gating 기준선은 analyzing에 도달한 모든 episode에서 전후 전체 장면을 제안 방법과 같은 크기·JPEG 품질 72로 보낸다. none에는 가상 crop을 만들지 않는다. byte는 HTTP/TLS header를 제외하고 base64와 JSON을 포함한 직렬화 요청 payload로 정의하고, JPEG 원본 byte 합도 별도 기록한다. 선택 정책의 실제 1–4장 payload와 누적 byte·요청 수를 비교하되 입력 증거가 다르므로 정확도 직접 비교로 해석하지 않는다. “모든 프레임 전송 대비” 상한은 가상의 30 FPS가 아니라 실제 처리 FPS, 동일 JPEG 품질과 실제 관찰 시간을 사용하며 분석적 추정으로 표시한다.

## 10. 운영 안정성

| Placeholder | 입력 |
|---|---|
| [[LONG_RUN_DURATION_HOURS]] | 유효 장시간 실행시간 |
| [[REGRESSION_TEST_COUNT]] | 최종 commit에서 실제 다시 실행한 test 수 |
| [[CAMERA_DISCONNECT_COUNT]] | 의도하지 않은 disconnect |
| [[CAMERA_RECONNECT_P50_MS]], [[CAMERA_RECONNECT_P95_MS]] | disconnect 인지부터 정상 frame 재개까지의 지연 분포 |
| [[SERVICE_RESTART_COUNT]] | crash 또는 수동 제외 restart |
| [[DB_ERROR_COUNT]] | 장시간 실행 중 DB write/transaction 오류 수 |
| [[VLM_FAILURE_COUNT]] | timeout, HTTP, parse, key/network failure |
| [[FAULT_INJECTION_CASE_COUNT]] | \(D_{fault}\)에서 의도적으로 주입한 장애 수와 유형별 support |
| [[PROVISIONAL_PRESERVATION_RATE]] | \(D_{fault}\)의 added 장애 중 관리자 확인 가능한 임시 행 보존 비율 |
| [[CAPTURE_READ_FAILURE_COUNT]] | capture read 실패 누적 수 |
| [[MONITOR_SCHEDULER_SKIP_RATE]] | 목표 monitor tick 중 처리하지 못한 비율 |
| [[CHANGE_CALLBACK_DROP_COUNT]] | queue 포화로 누락된 물품 change callback |
| [[DIAGNOSTIC_CALLBACK_DROP_COUNT]] | queue 포화로 누락된 진단 callback |

통제 장애별 입력:

| 장애 | 주입 수 | 성공 지표 |
|---|---|---|
| DB write 실패 | [[FAULT_DB_WRITE_N]] | [[FAULT_DB_SAFE_RATE]]: 부분·손상 행 없이 오류가 기록된 비율 |
| VLM timeout | [[FAULT_VLM_TIMEOUT_N]] | [[FAULT_VLM_TIMEOUT_PRESERVATION_RATE]]: 생성된 provisional 보존 비율 |
| malformed JSON | [[FAULT_MALFORMED_RESPONSE_N]] | [[FAULT_MALFORMED_RESPONSE_PRESERVATION_RATE]]: 생성된 provisional 보존 비율 |
| 원격 작업 queue 포화 | [[FAULT_REMOTE_QUEUE_FULL_N]] | [[FAULT_REMOTE_QUEUE_PRESERVATION_RATE]]: 이미 생성된 provisional 보존·확인 필요 표시 비율 |
| change callback queue 포화 | [[FAULT_CALLBACK_QUEUE_FULL_N]] | [[FAULT_CALLBACK_DROP_ACCOUNTING_RATE]]: drop이 누적 counter와 진단 원장에 남은 비율 |
| 오래된 added 응답 | [[FAULT_STALE_ADDED_N]] | [[FAULT_STALE_ADDED_BLOCK_RATE]]: 관리자 수정·현재 상태 덮어쓰기 차단 비율 |
| 오래된 verify 응답 | [[FAULT_STALE_VERIFY_N]] | [[FAULT_STALE_VERIFY_BLOCK_RATE]]: 변경된 signature에 대한 회수 전환 차단 비율 |
| 처리 중 재시작 | [[FAULT_PROCESS_RESTART_N]] | [[FAULT_RESTART_RECOVERY_RATE]]: DB 일관성과 서비스 복귀 성공 비율 |

관찰 구간에 added 실패가 0건이면 장시간 실행의 보존률은 100%가 아니라 정의 불가이다. 장애 내성 주장은 \(D_{fault}\)의 통제된 분모로 평가한다. 현재 코드에는 위 drop counter가 없으므로 계측 후에만 값을 입력한다. 소프트웨어 회귀 test 통과는 현장 정확도가 아니다.

## 11. 초록과 결론에 마지막으로 넣을 값

모든 본문 표를 고정한 뒤에만 아래를 작성한다.

- [[ABSTRACT_KO_CONCLUSION]]
- [[ABSTRACT_EN_CONCLUSION]]
- [[CONCLUSION_RESULT_1]]
- [[CONCLUSION_RESULT_2]]
- [[CONCLUSION_RESULT_3]]
- [[CONCLUSION_RESULT_4]]
- [[FINAL_EVIDENCE_BOUNDED_CLAIM]]

권장 작성 규칙:

- “F1이 높았다” 대신 비교 대상, 절대값, 차이와 CI를 함께 쓴다.
- “실시간” 대신 목표 FPS, 달성 FPS와 p95를 쓴다.
- “저전력”은 외부 전력계 결과가 있을 때만 쓴다.
- “호출량을 절감했다”는 동일 workload의 비교 분모와 byte 또는 call 수가 있을 때만 쓴다.
- “안정적”은 장시간 실행시간, 오류 수와 복구 결과가 있을 때만 쓴다.

## 12. 그림 준비

| 그림 | 필요한 자료 | 완료 |
|---|---|---|
| [[FIGURE_1_SYSTEM_ARCHITECTURE]] | 기존 Mermaid를 논문용으로 단순화 | [ ] |
| [[FIGURE_2_STATE_MACHINE]] | calibrating–monitoring–settling–stabilizing–analyzing | [ ] |
| [[FIGURE_3_PIPELINE_STAGES]] | 동일 사건의 before/aligned/diff/mask/bbox | [ ] |
| [[FIGURE_4_SEQUENCE]] | 성공·uncertain·failure 분기 | [ ] |
| Figure 5 ablation 그래프 | nuisance별 profile error rate와 CI | [ ] |
| Figure 6 실패 사례 | 개인정보 제거한 4~6개 대표 crop | [ ] |

그림 원본, 생성 script, crop 좌표와 익명화본을 함께 보관한다. 이미지 편집으로 검출 결과를 미화하지 않는다.

## 13. 최종 제출 전 체크

- [ ] 초안의 이중 대괄호 placeholder 검색 결과가 0개다.
- [ ] 모든 결과 수치는 원본 CSV까지 역추적된다.
- [ ] 참고문헌 번호와 본문 등장 순서가 일치한다.
- [ ] [3], [7], [21]의 로마자명과 영문 제목을 확인했다.
- [ ] 저자 식별정보를 제거한 심사용 원고를 별도로 만들었다.
- [ ] 표 제목은 위, 그림 제목은 아래에 국·영문으로 병기했다.
- [ ] 사람 얼굴, 이메일, API key, 내부 IP가 그림과 부록에 없다.
- [ ] 보관 기간을 법정 기한으로 표현하지 않았다.
- [ ] code test 수를 정확도 근거로 표현하지 않았다.
- [ ] JDCS 최신 공식 HWP 양식과 투고 규정을 제출 당일 다시 확인했다.

서지 확인 placeholder:

- [[VERIFY_ENGLISH_TITLE_AND_ROMANIZATION]]
- [[VERIFY_AUTHOR_ROMANIZATION]]
