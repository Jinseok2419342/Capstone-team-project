# 논문 실측값 입력표 — 2026-10-11 축소판

[논문 안내](README.md) · [실험 진행 안내](EXPERIMENT_GUIDE.md)

`PAPER_DRAFT_JDCS.md`의 이중 대괄호 자리 32종 전체 목록이다(이전 297종에서 축소). 대부분은 실험 진행 도우미(`run_experiment.py`)가 끝날 때 만드는 `paper-results/paper_tables.md`에 자동으로 계산되어 나온다.

## 사용 원칙

1. 추정값이나 예시로 채우지 않는다. 값이 없으면 빈칸으로 두고 해당 문장을 뺀다.
2. 결과가 예상과 다르면 요약·6장·결론 문장을 결과에 맞게 고친다. 실패 사례도 그대로 보고한다.
3. 실험 후 설정을 바꿔 다시 시험했다면 마지막에 고정한 설정의 시험 결과만 쓰고, 바꾼 이유를 메모한다.
4. 도우미가 만든 `paper-run-…` 폴더(trials.csv, activities.json, health.csv, resources.csv, paper-results)를 그대로 보관한다.

## 1. 표 통째로 교체 (자동)

| 자리 | 교체 방법 |
|---|---|
| `[[T5]]` 표 5 혼동행렬 | `paper_tables.md`의 표 5로 교체 |
| `[[T6]]` 표 6 사건별 정밀도·재현율·F1 | 표 6으로 교체 |
| `[[T7]]` 표 7 외부 모델 호출·인식 | 표 7로 교체 |
| `[[T8]]` 표 8 자원 사용량 | 표 8로 교체 |

## 2. 본문 숫자 (자동)

`paper_tables.md` 끝의 ‘본문 자리표시자 값’ 목록을 그대로 옮긴다.

| 자리 | 의미 | 원천 |
|---|---|---|
| `[[N_TRIALS]]` | 전체 시도 수(계획 100) | trials.csv |
| `[[ACC_OVERALL]]` | 전체 정확도(%) | trials.csv |
| `[[ACC_CI]]` | 정확도 Wilson 95% 신뢰구간 | trials.csv |
| `[[MACRO_F1]]` | 등록·이동·제거 평균 F1 | trials.csv |
| `[[HAND_FP]]`, `[[LIGHT_FP]]`, `[[SHADOW_FP]]` | 손·조명·그림자 무변화 시도의 오탐 수 | trials.csv |
| `[[NUISANCE_FP]]` | 조명+그림자 오탐 수(요약용) | trials.csv |
| `[[AI_NAME_ACC]]`, `[[AI_CATEGORY_ACC]]` | 등록 성공 사건의 이름·분류 정확도(%) | 이름은 사용자 확인, 분류는 자동 채점 |
| `[[AI_CALL_RATIO]]` | 외부 호출 / 전체 감지 사건(%) | activities.json |
| `[[IDLE_HOURS]]`, `[[IDLE_FP]]` | 무인 감시 시간, 그동안의 잘못된 사건 수 | activities.json + 자동 기록 시각 |
| `[[FRAMES_PROCESSED]]` | 실험 중 분석한 프레임 수 | health.csv |
| `[[FPS_MEAN]]`, `[[PROC_MS_MEAN]]` | 평균 분석 프레임률, 프레임당 처리 시간 | health.csv |
| `[[CPU_MEAN]]`, `[[RSS_MAX]]`, `[[TEMP_MAX]]` | 평균 CPU(%), 최대 서비스 메모리(MiB), 최고 온도(°C) | resources.csv |

## 3. 직접 채우는 항목

| 자리 | 넣을 내용 | 확인 방법 |
|---|---|---|
| `[[EQUIP_STORAGE]]` | microSD 용량(예: microSD 32GB) | 카드 라벨 |
| `[[EQUIP_COOLING]]` | 방열판·팬·케이스(예: 방열판, 팬 없음) | 장치 확인 |
| `[[EQUIP_CAMERA_GEOMETRY]]` | 설치 높이·거리·각도(예: 책상 위 60cm, 하향 약 70°) | 줄자 |
| `[[VLM_MODEL_DATE]]` | 제공자·모델명·실험일(예: OpenAI gpt-…, 2026-10-20) | 설정 화면 |
| `[[NETWORK_CONDITION]]` | 연결 방식(예: 학교 Wi-Fi에 연결된 노트북 핫스팟) | 실험 당일 |
| `[[EXPERIMENT_DATE_PLACE]]` | 날짜·장소(예: 2026년 10월 20일 교내 실습실) | 실험 당일 |
| `[[OBJECT_LIST]]` | 물품 10종 이름 | session.json |
| `[[MAIN_ERROR]]` | 표 5에서 가장 많은 오류 1–2문장(예: “오류는 주로 ○○을 ○○으로 판정한 경우였다.”) | 표 5·메모 |
| `[[FAIL_CASES]]` | 대표 실패 사례와 원인 1–2문장 | 메모·캡처 |

표 4의 운영체제·카메라·소프트웨어 버전은 9월 22일 Pi 진단 출력으로 채워 두었다. Pi를 다시 설치했다면 실험 직전 `check-system.sh` 출력으로 다시 확인한다.

## 4. 그림

| 그림 | 파일 | 내용 |
|---|---|---|
| 그림 1, 3, 4 | `manuscript/figures/figure-1·3·4.svg` | 구조·상태 전이·후보 처리 도식(완성, 빌드 시 생성) |
| 그림 2 | `manuscript/figures/figure-2.png` | 관리자 웹 화면 캡처 |
| 그림 5 | `manuscript/figures/figure-5.png` | 실험 장면 사진(보관대와 카메라 설치) |
| 그림 6 | `manuscript/figures/figure-6.png` | 판정 성공 예 2개와 실패 예 1개를 한 장으로 |

그림 2·5·6 파일이 없으면 PDF에 ‘사진 입력 예정’ 상자가 표시된다.

## 5. 제출 전 점검

- [ ] 이중 대괄호가 남아 있지 않다.
- [ ] 요약의 숫자와 6장·결론의 숫자가 같다.
- [ ] 결과가 나쁜 항목을 좋은 것처럼 쓰지 않았다.
- [ ] JDCS 공식 HWP 양식(2단, 신명조 9.1pt)으로 옮긴 뒤 10쪽 안팎인지 확인했다.
- [ ] 심사용 원고에서 저자명·소속·감사의 글을 뺐다.
- [ ] 투고 당일 학회 홈페이지에서 최신 투고 규정과 양식을 다시 확인했다.
