"""Reproducible editorial revision from the archived September 15 draft."""
from pathlib import Path
import re
import json

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'docs/paper'
ARCHIVE = PAPER / 'archive/2026-09-16-before-full-revision'
old = (ARCHIVE/'PAPER_DRAFT_JDCS.md').read_text(encoding='utf-8')
front = (ARCHIVE/'RESEARCH_FRONT_MATTER.md').read_text(encoding='utf-8')

front = front.replace('## 3. 관련 연구와 본 연구의 위치', '### 2-4 관련 연구와 본 연구의 위치')
front = front.replace(
    '연구 질문은 다음과 같다. 첫째, 안정된 장면을 기준으로 추가·이동·제거를 구분할 수 있는가. 둘째, 장면 정합과 조명 보정은 방해요인에 의한 오탐에 어떤 영향을 주는가. 셋째, 필요한 사건만 외부 모델에 전달하는 구성에서 판단 성능, 처리 지연과 호출량은 어떠한가.',
    '연구 질문은 다음과 같다. 첫째, 안정 장면 분석과 영상 보정은 추가·이동·제거의 검출 성능 및 오탐에 어떤 영향을 주는가. 둘째, 이 과정의 대기시간과 연산 부담은 Raspberry Pi의 처리 지연과 자원 사용량에 어떻게 나타나는가. 셋째, 필요한 사건만 외부 모델에 전달할 때 호출량, 누락과 최종 업무 성공률 사이에 어떤 관계가 있는가.')
front = front.replace(
    '본 연구는 새로운 학습 모델을 제안하기보다 기존 영상처리와 외부 모델의 역할을 보관대 업무에 맞게 구성한다. 관련 연구와 데이터·장치·평가 단위가 다르므로 보고된 정확도를 직접 비교하지 않는다. 이후 연구방법에서는 사건 감지, 선택적 추론과 관리 기록의 연결 절차를 구체화하고, 실험을 통해 각 구성의 효과와 한계를 확인한다.',
    '본 연구의 기여는 안정 장면을 이용한 사건 선별, 선택적 의미 추론 및 물품 관리 이력을 연결하는 시스템 구성에 있다. 특히 오탐 억제와 지연, 외부 호출 감소와 사건 누락의 관계를 함께 평가한다. 관련 연구와 데이터·장치·평가 단위가 다르므로 문헌의 정확도를 직접 비교하지 않으며, 동일 영상에 적용한 비교 구성으로 설계의 효과와 한계를 확인한다.')
(PAPER/'briefing/RESEARCH_FRONT_MATTER.md').write_text(front, encoding='utf-8')

front_body, early_refs = front.split('## 참고문헌', 1)
front_body = front_body.replace('<!-- PAGEBREAK -->', '').strip()
front_body = front_body.replace('## 1. 서론', '# 1. 서론').replace('## 2. 이론적 배경', '# 2. 이론적 배경 및 관련 연구')
front_body = re.sub(r'^### (\d-\d)', r'## \1', front_body, flags=re.M)
front_body = front_body.replace('표 1. 관련 연구의 대상과 본 연구의 초점\nTable 1. Research targets and the focus of this study', '**표 1. 관련 연구의 대상과 본 연구의 초점 / Table 1. Research targets and the focus of this study**')
front_body = front_body.replace('\n\nAn Event-', '\n\nAn Event-', 1)
lines = front_body.splitlines()
lines.insert(2, '> 2026-09-16 전면 개정본 · 구현 및 실험 설계 원고. 정량 실험 전이며 투고 최종본이 아니다. 결과 장의 이중 대괄호는 실제 측정 후 채운다. PDF의 “입력 대기”도 결과값이 아니다.\n')
front_body = '\n'.join(lines)

core = old.split('# 3. 시스템 설계', 1)[1].split('# 6. 결과 및 논의', 1)[0]
core = '# 3. 시스템 설계' + core
mapping = {22:9,23:10,24:11,25:12,12:13,13:14,14:15,26:16,9:17}
core = re.sub(r'(?<!\[)\[(\d+)\](?!\])', lambda m: '['+str(mapping.get(int(m[1]),int(m[1])))+']', core)
core = core.replace('기준 영상의 Shi–Tomasi 코너를 Lucas–Kanade 피라미드 광류로', '기준 영상의 Shi–Tomasi 코너[13]를 Lucas–Kanade 피라미드 광류[14]로')
core = core.replace('RANSAC 기반 부분 affine 변환을 추정한다.', 'RANSAC[15] 기반 부분 affine 변환을 추정한다.', 1)
core = core.replace('B2: OpenCV MOG2와 동일한', 'B2: 적응 가우시안 혼합 배경 모델[17]을 사용하는 OpenCV MOG2와 동일한')
core = core.replace('[[FIGURE_1_SYSTEM_ARCHITECTURE]]', '![그림 1 시스템 구조](manuscript/figures/figure-1.svg)')
core = core.replace('[[FIGURE_2_STATE_MACHINE]]', '![그림 2 상태 전이](manuscript/figures/figure-2.svg)')
core = core.replace('[[FIGURE_3_PIPELINE_STAGES]]', '![그림 3 변화 후보 처리 구조](manuscript/figures/figure-3.svg)')
core = core.replace('[[FIGURE_4_SEQUENCE]]', '![그림 4 비동기 처리 흐름](manuscript/figures/figure-4.svg)')
core = re.sub(r'^편집 지시:.*\n', '', core, flags=re.M)
core = core.replace('그림 3. 로컬 변화 검출의 중간 결과 / Fig. 3. Intermediate results of local change detection', '그림 3. 변화 후보 생성과 활성 물품 대응 절차 / Fig. 3. Change-candidate generation and active-item association')
core = core.replace('이 설계는 행동 중 손과 사람을 물품으로 분석하는 것을 피하고,', '이 설계는 행동 중 손과 사람을 물품으로 분석할 가능성을 줄이기 위해')
core = core.replace('새 물품의 내부나 이전에 경계가 없었던 윤곽은 양쪽 영상에 공통으로 존재하지 않으므로 그대로 남는다.', '양쪽 영상의 공통 경계에 해당하지 않는 변화는 남긴다. 다만 새 물품의 윤곽이 기존 경계와 겹치는 경우에는 실제 변화도 약화될 수 있으므로 작은 물품과 저대비 물품의 recall을 별도로 확인한다.')
core = core.replace('형식 오류는 실패로 처리한다.', '모든 provider 경로에서 JSON schema가 강제되는 것은 아니므로 형식 오류가 가능하며, 파싱 오류는 실패로 처리한다.')
core = core.replace('callback worker가 정상 접수한 신규 added 사건은 원격 요청 전에', 'callback worker가 정상 접수한 신규 added 사건은 저장에 성공한 경우 원격 요청 전에')
core = core.replace('1. 카메라 준비 이후', '1. 카메라 준비 이후', 1)

tradeoffs = '''## 3-4. 저사양 제약에 따른 설계 선택

본 연구에서 저사양 대응은 학습 모델의 양자화나 가지치기가 아니라, 분석 시점·해상도·외부 요청 범위를 조절하는 시스템 설계이다. 카메라 수집, 움직임 감시, 누적 변화 검사와 웹 미리보기의 목표 주기를 분리하고, 기하 정합에는 축소 영상을 사용한다. 세부 외형이 필요한 후보 crop은 별도로 유지한다. 표 3의 목표 FPS는 실행 설정이며 실제 처리율을 보장하지 않는다.

첫째, 안정 장면을 기다리면 행동 도중의 손과 중간 위치를 분석할 가능성을 줄일 수 있으나 물품을 놓은 즉시 등록되지는 않는다. 따라서 검출 F1과 함께 물리적 행동 종료부터 로컬 사건까지의 지연을 보고한다. 둘째, 정합·조명 보정·지속 경계 억제는 방해요인 오탐을 줄이기 위한 처리인 동시에 추가 연산과 실제 변화 약화의 원인이 될 수 있다. 보정 단계별 오탐, recall과 코어 계산시간을 함께 비교한다.

셋째, added와 verify_removed만 외부에 보내면 로컬에서 확정한 이동·제거에는 원격 요청이 필요하지 않다. 그러나 로컬에서 놓친 신규 물품은 외부 모델의 의미 판단 기회도 얻지 못한다. 호출률만 낮은 구성을 효율적이라고 결론 내리지 않고 gate recall과 종단간 업무 성공률을 함께 확인한다. 넷째, 임시 저장은 원격 응답을 기다리기 전에 관찰 기록을 남기는 정책이므로 미확정 등록과 관리자 확인 업무가 발생할 수 있다. 저장 이후 보존 성능과 저장 이전 callback drop을 분리해서 평가한다.

이러한 선택은 제한된 장치에서 감지와 관리 서비스를 함께 실행하기 위한 가설이다. 실제 비교 결과가 나오기 전에는 가장 빠른 구성, 최적 구성 또는 저전력 시스템으로 단정하지 않는다.

'''
core = core.replace('# 4. 제안 방법', tradeoffs+'# 4. 제안 방법', 1)

core += '''## 5-6. 설계 선택과 평가 결과의 연결

첫 번째 연구 질문은 표 7의 동일 연속 영상 비교와 표 8·9의 방해요인 평가로 검증한다. 상태기계의 효과는 B1과 P1의 차이로, 보정 단계의 누적 효과는 공통 코어의 profile 차이로 확인한다. F1 상승만 보고하지 않고 사건 종류별 recall, none 오작동과 제거 검증 의뢰율을 함께 제시한다.

두 번째 질문은 표 10의 장치 자원과 누적 지연으로 검증한다. 기본 settle 3.0초와 stable 1.2초는 순차 대기 정책이므로 계산이 빠르더라도 사용자 체감 등록은 늦을 수 있다. 검출기의 마지막 motion 시각은 영상에서 라벨링한 action_end_at과 다를 수 있어 두 값을 대체하지 않는다. 필요하면 개발 세트에서 대기시간 후보를 비교한 뒤 본 실험 설정을 고정하고, 최종 평가 결과에 맞추어 유리한 설정을 다시 선택하지 않는다.

세 번째 질문은 표 11의 증거 구성 비교와 전체 감시 구간의 gate recall·호출 수·업무 성공률로 검증한다. V1–V4는 같은 사건에서 시각 증거만 바꾸는 비교이며, 선택 호출과 no-gating의 전송량 비교는 대상 집합과 증거 구성이 다른 운영 비교이다. 두 결과를 합쳐 네 장의 증거 또는 선택 호출이 정확도를 향상시켰다고 단정하지 않는다. 표 13의 장애 주입은 외부 실패 시 기록 보존과 상태 변경 차단을 별도로 평가한다.

'''

raw_results = old.split('# 6. 결과 및 논의',1)[1].split('# 7. 결론',1)[0]
chunks = re.split(r'(?=^\*\*표 \d+\.)',raw_results,flags=re.M)
tables={}
for chunk in chunks:
    m=re.match(r'\*\*표 (\d+)\.',chunk)
    if not m: continue
    # Keep only the title/panel label/table portion, not the old measured-tense prose.
    ls=chunk.splitlines(); end=0
    for i,l in enumerate(ls):
        if l.startswith('|'): end=i+1
        elif i>0 and l.startswith('## '): break
        elif i>0 and l.startswith('[[RESULT_'): break
        elif i>0 and l.startswith('plain에서'): break
    tables[int(m[1])]='\n'.join(ls[:end]).strip()

results = '''# 6. 평가 결과 보고안 및 논의

> 정량 실험 전의 결과 작성 틀이다. 아래 값은 현재 미측정이며, 관찰된 성능을 보고하는 문장이 아니다. 표와 지표를 실제 원장으로 채운 뒤 절 제목을 “결과 및 논의”로 바꾸고, 관찰 결과에 맞춰 초록과 결론을 개정한다.

## 6-1. 사건 검출과 물품 식별

{t7}

표 7은 로컬에서 확정한 사건을 기준으로 작성한다. IoU 0.50의 민감도 분석 값은 [[IOU50_MACRO_F1_CI]], 제거 후보 recall은 [[REMOVAL_CANDIDATE_RECALL_CI]], 제거 후보 중 검증 의뢰율은 [[REMOVAL_VERIFY_REFERRAL_RATE_CI]]에 기록한다. verify_removed 증가로 확정 오탐이 줄어들어도 이를 제거 성능 향상으로 해석하지 않고, 최종 단계의 제거 결과와 함께 검토한다.

moved의 ID 평가는 채점 가능한 [[MOVED_ID_SCORABLE_N]]개와 coverage [[MOVED_ID_COVERAGE]]를 먼저 보고한다. matched TP에서의 ID 보존율 [[MOVED_ID_RETENTION_CI]] 및 다른 ID 할당률 [[MOVED_ID_ASSIGNMENT_ERROR_CI]]과, 전체 GT-moved의 DB 중복 행 생성률 [[MOVED_DUPLICATE_ID_RATE_CI]]을 구분한다. 화면상의 bbox 이동 성공만으로 관리 기록의 중복 방지를 주장하지 않는다.

none의 확정 사건 발생률은 [[NONE_EPISODE_TRIGGER_RATE_CI]], 검증 의뢰율은 [[NONE_VERIFY_REFERRAL_RATE_CI]]이다. 연속 none 감시의 유효 [[NONE_MONITORING_HOURS]]시간에서 확정 오탐 [[NONE_FALSE_EVENT_COUNT]]건을 집계하고, FP/hour의 Poisson exact 구간 [[FALSE_EVENTS_PER_HOUR_POISSON_CI]]과 run-block bootstrap 구간 [[FALSE_EVENTS_PER_HOUR_BLOCK_CI]]을 함께 보고한다. FP가 0이어도 감시시간과 신뢰구간을 생략하지 않는다.

## 6-2. 방해요인 억제와 추가 연산

{t8}

plain 대비 full의 Macro-F1 차이 [[ABL_F1_DELTA]]와 none 오작동률 차이 [[ABL_NONE_DELTA]]를 코어 지연 변화와 함께 해석한다. 고정 순서의 누적 ablation이므로 각 단계의 독립적 기여나 순수 차영상 대비 효과를 의미하지 않는다. 오탐이 줄면서 저대비 물품의 FN이 늘면 이를 보정의 상충 관계로 보고한다.

{t9}

방해요인별 표본 수가 다르면 FP 건수만으로 취약 조건의 순위를 정하지 않는다. 동일 물품·조건의 전후 영상, 최종 마스크와 실패 이유를 실측 후 대표 사례로 추가하고, 성공 사례만 골라 설명하지 않는다. 그림 3은 처리 구조를 나타내는 모식도이며 실제 실험 마스크가 아니다.

## 6-3. 장치 성능과 사용자 체감 지연

{t10}

지연 timestamp 결측률 [[LATENCY_TIMESTAMP_MISSING_RATE]], 실제 감시 FPS [[ACHIEVED_MONITOR_FPS]], capture read 실패 [[CAPTURE_READ_FAILURE_COUNT]]건, scheduler skip 비율 [[MONITOR_SCHEDULER_SKIP_RATE]]을 보고한다. change callback drop [[CHANGE_CALLBACK_DROP_COUNT]]건과 진단 callback drop [[DIAGNOSTIC_CALLBACK_DROP_COUNT]]건은 별도 집계한다. 목표 7 FPS를 실측 FPS로 대신 기입하지 않는다.

표 8의 코어 시간과 표 10의 local 지연 차이에는 상태기계 대기와 실행 스케줄링 등이 포함될 수 있다. 지연이 짧아진 구성이 많은 사건을 놓친 경우에는 성공한 사건만의 조건부 분포라는 점을 고려한다. 높은 CPU 사용이 항상 실패를 뜻하지는 않지만, RSS 증가·온도·처리율 변화와 연속 실행의 안정성을 함께 확인한다.

전력 측정 여부는 [[POWER_MEASUREMENT_STATUS]]에 기록한다. 외부 계측기가 있는 경우에만 idle [[POWER_IDLE_W]] W, 감시 [[POWER_MONITOR_W]] W, 사건 분석 [[POWER_EVENT_W]] W를 보고하며 계측점과 주변장치 포함 범위를 명시한다. 미측정이면 해당 수치와 저전력 주장을 삭제한다.

## 6-4. 선택적 멀티모달 추론과 최종 업무 성능

{t11}

Action 정확도는 GT-added [[N_VLM_GT_ADDED]]개와 GT-removed [[N_VLM_GT_REMOVED]]개의 decisive 표본에서 uncertain을 오답으로 채점한다. 표 11의 category·물품 의미 정확도는 GT-added만을 대상으로 한다. non-removal/retain [[N_VLM_RETAIN]]개의 운영 평가에서는 register/hold 정확도 [[VLM_REGISTER_DECISION_ACC]], recover 결정 정확도 [[VLM_RECOVER_DECISION_ACC]], retain 안전률 [[VLM_RETAIN_SAFETY_ACC]]을 별도로 보고한다.

전체 감시 [[TOTAL_MONITORED_EPISODES]]개 episode의 로컬 사건 수 [[LOCAL_EVENT_COUNT]], logical VLM job 수 [[VLM_CALL_COUNT]], episode당 호출률 [[VLM_CALL_RATE]]을 집계한다. GT-added의 gate recall [[VLM_GATE_RECALL_ADDED_CI]]과 사전 라벨된 모호 제거 [[N_GT_AMBIGUOUS_REMOVAL]]개의 gate recall [[VLM_GATE_RECALL_REMOVAL_CI]]을 함께 보고한다. 하나의 episode에서 여러 job이 만들어질 수 있으므로 job/episode 비율은 반드시 1 이하인 확률은 아니다.

운영 모드의 fallback을 포함한 HTTP attempt [[VLM_ATTEMPT_COUNT]]회와 성공 응답 [[VLM_SUCCESS_COUNT]]회를 구분한다. no-gating 기준선 대비 직렬화 payload 변화는 [[TRANSFER_REDUCTION_RESULT]], 모든 처리 프레임 전송 대비 분석적 상한은 [[ALL_FRAME_TRANSFER_UPPER_BOUND]]에 기록한다. 후자는 실측 비교가 아니다. 비용은 attempt 원장의 실제 과금·usage를 근거로 episode당 [[COST_PER_EPISODE]]원과 attempt당 [[COST_PER_ATTEMPT]]원으로 산출하고, 환산 기준일과 단가를 함께 기록한다.

V4가 가장 높은 성능을 보이지 않으면 네 장의 우수성을 주장하지 않는다. 응답한 사례만의 정확도가 높아져도 coverage가 낮으면 전체 action 정확도와 운영 결과를 함께 검토한다. 종단간 성공은 로컬 누락과 DB 반영까지 포함하며, 전체 [[END_TO_END_TASK_SUCCESS]], added [[TASK_SUCCESS_ADDED_CI]], moved [[TASK_SUCCESS_MOVED_CI]], removed [[TASK_SUCCESS_REMOVED_CI]], 세 종류 macro [[TASK_SUCCESS_MACRO_CI]]를 보고한다. 이 결과가 최종적으로 관리 업무에 미치는 효과의 근거가 된다.

## 6-5. 실패 사례와 장애 대응

{t12}

{t13}

연속 실행 [[LONG_RUN_DURATION_HOURS]]시간의 카메라 disconnect [[CAMERA_DISCONNECT_COUNT]]회와 reconnect p50/p95 [[CAMERA_RECONNECT_P50_MS]]/[[CAMERA_RECONNECT_P95_MS]] ms, 서비스 재시작 [[SERVICE_RESTART_COUNT]]회, DB 오류 [[DB_ERROR_COUNT]]회 및 원격 요청 실패 [[VLM_FAILURE_COUNT]]회를 보고한다. 실패가 관찰되지 않은 구간에서 임시 기록 보존률을 100%로 임의 정의하지 않는다. 보존 정책은 통제 장애 [[FAULT_INJECTION_CASE_COUNT]]건의 결과 [[PROVISIONAL_PRESERVATION_RATE]]와 유형별 표 13으로 평가한다.

임시 행 생성 이전의 callback drop과 DB 저장 실패는 저장 후 VLM 실패와 다르다. 기존 행 보존이 확인되어도 전체 사건의 무손실 수집을 보장하지 않는다. added의 관리자 수정 보호와 verify_removed의 추적 signature 검사는 서로 다른 코드 경로이므로 각각 장애를 주입하여 검증한다. 영상 파일과 DB의 원자적 동시 커밋이나 전원 장애에 대한 내구성은 별도 검증 없이 주장하지 않는다.

## 6-6. 타당도와 적용 범위

설치 장소 [[SITE_COUNT]]곳과 단일 Pi·카메라의 결과는 다른 설치 높이, 렌즈와 배경으로 바로 일반화할 수 없다. 물품과 recording session을 개발·평가에서 분리하더라도 장소 다양성이 부족하면 외적 타당도에 제한이 남는다. 규칙 기반 임계값, 가림, 유사한 외형의 여러 물품과 동시 이동은 별도의 실패 조건으로 다룬다.

안정 장면의 전후 상태가 같다면 중간에 물품을 들었다 다시 놓은 행동은 관찰되지 않을 수 있다. 이 시스템의 평가 단위는 보관대의 지속적인 상태 변화이며, 모든 접촉 행동의 감지나 절도·소유자 식별을 포함하지 않는다. 전역 변화 억제 후 기준 영상을 갱신하는 경우 그 구간의 실제 물품 변화가 누락될 수 있으므로 억제 건수와 해당 구간의 정답 사건을 함께 검토한다.

외부 모델의 응답과 비용은 모델 갱신 및 네트워크에 따라 달라진다. 전체 장면에는 주변 사람이 포함될 수 있어 실증 전 촬영 범위와 접근 권한, 보존 및 비식별화 절차를 정해야 한다. 현재 privacy 전환은 이미 접수된 작업을 취소하지 않고, 재시작 시 설정 자동 복원도 보완 대상이다. 보관 기한과 recovered는 애플리케이션 정책이며 법정 기한이나 물리적 반환 증명으로 해석하지 않는다.

'''.format(**{f't{k}':v for k,v in tables.items()})

conclusion = '''# 7. 결론

본 논문은 Raspberry Pi 4 2GB와 고정 카메라에서 분실물의 상태 변화를 선별하고 선택된 사건의 의미를 외부 시각언어모델로 보완하는 Re:Found를 설계·구현하였다. 로컬 파이프라인은 움직임 종료와 안정 장면 확인, 기하 정합, 조명 보정, 지속 경계 억제 및 활성 물품 대응으로 추가·이동·제거와 제거 검증 사건을 구분한다. 신규 등록과 모호한 제거에 최대 네 장의 전후 증거를 사용하고, 관리 서비스에서 보관 기한과 상태 변경 이력을 연결한다.

본 연구의 설계상 특징은 분석할 시점과 대상을 제한하는 로컬 처리, 필요한 사건에 대한 의미 추론 및 비동기 결과를 운영 기록에 반영하는 절차를 함께 구성한 데 있다. 정상 접수 후 저장된 신규 물품은 원격 처리 실패에도 보존하며, 제거 검증은 기존 상태를 유지한 채 수행한다. 이러한 정책의 효과는 저장 전후의 장애를 구분한 검증으로 평가해야 한다.

현재 원고는 구현 및 실험 설계 단계이다. 따라서 정확도 향상, 지연 감소, 호출 비용 절감 또는 현장 운영의 신뢰성을 실증한 것으로 결론 내리지 않는다. 동일 연속 영상의 비교 실험, 안정 영상쌍의 보정 ablation, 전후 증거 구성 및 통제 장애 평가를 통해 설계의 이점과 부담을 확인한 뒤 정량 결과에 근거하여 결론을 확정한다. 향후에는 복수 설치 환경, 동시 다중 물품, 장기 기준 영상 변화 및 개인정보 보호 절차를 포함하여 적용 범위를 검토한다.

'''
oldrefs = dict((int(n),v.strip()) for n,v in re.findall(r'^\[(\d+)\] (.*)$',old.split('# 참고문헌',1)[1],re.M))
earlydict = dict((int(n),v.strip()) for n,v in re.findall(r'^\[(\d+)\] (.*)$',early_refs,re.M))
ref_values = {**earlydict, **{new:oldrefs[oldnum] for oldnum,new in mapping.items()}}
ref_values[14] += ' https://publications.ri.cmu.edu/an-iterative-image-registration-technique-with-an-application-to-stereo-vision-ijcai'
refs='\n\n'.join(f'[{n}] {ref_values[n]}' for n in sorted(ref_values))
draft=front_body+'\n\n'+core+results+conclusion+'# 참고문헌\n\n'+refs+'\n'
(PAPER/'PAPER_DRAFT_JDCS.md').write_text(draft,encoding='utf-8')

# Preserve detailed definitions while removing obsolete result-summary and figure placeholders.
sheet=(ARCHIVE/'RESULTS_FILL_SHEET.md').read_text(encoding='utf-8')
pattern=r'\[\[[^\]]+\]\]'
current=set(re.findall(pattern,draft))
obsolete=set(re.findall(pattern,sheet))-current
kept=[]
for line in sheet.splitlines():
    keys=set(re.findall(pattern,line))
    if keys and keys.issubset(obsolete): continue
    for key in keys & obsolete:
        line=line.replace(key+', ','').replace(', '+key,'').replace(key,'')
    kept.append(line)
sheet='\n'.join(kept)+'\n'
missing=current-set(re.findall(pattern,sheet))
assert not missing,missing
sheet=sheet.replace('## 1. 사용 원칙','> 2026-09-16 개정: 전체 원고와 정확히 일치하는 '+str(len(current))+'종의 입력 항목. 실측 전 초록·결론의 결과 단정과 완성된 도식의 자리표시자를 제거했다. 원래 321종 입력표는 archive에 보존했다.\n\n## 1. 사용 원칙',1)
sheet=sheet.replace('모든 본문 표를 고정한 뒤에만 아래를 작성한다.', '현재 초록·결론은 실측 전 서술이다. 모든 본문 결과를 고정한 뒤 주요 비교 수치와 신뢰구간, 설계의 이점·부담을 반영하여 다시 작성한다.')
sheet=sheet.replace('| Figure 5 ablation 그래프 |', '| 추가 후보: ablation 그래프 |').replace('| Figure 6 실패 사례 |','| 추가 후보: 실패 사례 |')
sheet=sheet.replace('그림 원본, 생성 script, crop 좌표와 익명화본을 함께 보관한다.', '그림 1–4의 처리 구조도는 manuscript/figures/에 완성했다. 위 실측 시각화는 데이터 확보 후 추가 여부와 최종 번호를 결정한다. 그림 원본, 생성 script, crop 좌표와 익명화본을 함께 보관한다.')
sheet=sheet.replace('- [ ] [3], [7], [21]의 로마자명과 영문 제목을 확인했다.', '- [ ] 현 원고 [3]의 공식 영문 서지 또는 국문 표기 허용 여부를 확인했다. 나머지 서지도 최종 제출 규정에 맞게 정리했다.')
sheet=sheet.replace('\n서지 확인 placeholder:\n','\n저자 순서·교신저자·소속·이메일은 실제 저자와 확인하고 심사용 원고에서는 식별정보를 제거한다.\n')
(PAPER/'RESULTS_FILL_SHEET.md').write_text(sheet,encoding='utf-8')

body=draft.split('# 참고문헌')[0]
citations=list(dict.fromkeys(map(int,re.findall(r'(?<!\[)\[(\d+)\](?!\])',body))))
assert citations==list(range(1,18)),citations
assert set(re.findall(pattern,sheet))==current
report={'unique_placeholders':len(current),'removed_obsolete_placeholders':sorted(obsolete),'references':17,'first_citation_order':citations,'full_manuscript_characters':len(draft),'front_pages':4,'front_body_synchronized':True,'measured_results_available':False}
(PAPER/'manuscript/SOURCE_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='removed_obsolete_placeholders'},ensure_ascii=False))
