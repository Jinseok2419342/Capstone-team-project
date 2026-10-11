# Re:Found 논문 작업공간

[시작 안내로 돌아가기](../../START_HERE.md)

**2026-10-11 축소 개정.** 원고·실험 계획이 학회 양식과 분량에 비해 과하다는 판단에 따라, JDCS 심사용 원고(2단, 약 8–10쪽)에 맞게 원고를 다시 쓰고 실험을 **하루 약 2시간 반**으로 줄였다. 이전 원고(19쪽, 입력 항목 297종, 실험 자료군 4개·비교 방법 3개·통계 검정)는 Git 기록(커밋 `55d59a9`)에만 남긴다.

## 지금 열 파일

| 할 일 | 파일 |
|---|---|
| 원고 읽기 | [2단 근사 조판 PDF — 현재 7쪽(사진·결과 전)](../../output/pdf/REFOUND_FULL_MANUSCRIPT.pdf) |
| 원고 수정 | [편집 원고](PAPER_DRAFT_JDCS.md) |
| **실험하기** | [실험 진행 안내](EXPERIMENT_GUIDE.md) → `python scripts\experiments\run_experiment.py` |
| 결과 넣기 | [실측값 입력표 — 32종](RESULTS_FILL_SHEET.md) |
| 현재 상태 | [개정 상태](REVISION_STATUS.md) |

## 현재 결정

- 투고처: **디지털콘텐츠학회논문지(JDCS)**. 심사 원고는 학회 홈페이지에서 내려받는 **공식 HWP 양식** 그대로 작성한다(A4 2단, 신명조 9.1pt, 국문 요약 약 500자, 영문 요약 약 200단어). 이 저장소의 PDF는 쪽수 확인용 근사 조판이고, 최종본은 HWP로 옮긴다.
- 논문 유형: 새 AI 모델이 아니라 **저사양 장치의 사건 기반 감지와 선택적 외부 AI 호출을 결합한 시스템 설계·구현·실험 논문**.
- 제목: **저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템**
- 실험: 실제 보관대에서 100회(등록·이동·제거 각 20, 무변화 40) + 무인 1시간. 진행 도우미가 화면 결과 판정·기록·집계를 자동으로 하므로 사용자는 안내대로 행동하고 Enter, 끝에 AI 이름 20개만 확인한다.
- 원고 구성: 표 8개, 그림 6개(도식 3, 사진·캡처 3), 수식 2개, 알고리즘 1개, 참고문헌 18편.

## 이번 논문 범위에서 뺀 것

다른 방법(단순 차영상·MOG2)과의 비교, 보정 단계별 ablation, AI 입력 사진 수 비교, 장애 주입, 8시간 이상 장시간 실험, 전력 측정, bootstrap·McNemar 통계. 심사위원이 요청하면 그때 추가한다. 기존 `experiments/`의 이미지 쌍 비교·매칭 도구는 그 경우에 다시 쓸 수 있다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `PAPER_DRAFT_JDCS.md` | 원고 원본. HWP로 옮길 기준본 |
| `EXPERIMENT_GUIDE.md` | 실험 당일 순서, 기록 방법, 파일 모으기, 집계 명령 |
| `TRIAL_SHEET_TEMPLATE.csv` | 도우미를 쓸 수 없을 때의 손 기록지(100행 미리 채움) |
| `RESULTS_FILL_SHEET.md` | 원고의 이중 대괄호 32종과 채우는 방법 |
| `manuscript/build_manuscript.py` | 2단 근사 PDF와 도식 SVG 생성 |
| `REFERENCES.bib` | 참고문헌 후보 모음(원고는 18편 사용) |
| `VENUE_AND_RELATED_WORK_STRATEGY.md` | 투고처 비교·비용·심사 절차(9월 15일 조사) |
| `PAPER_AI_HANDOFF.md`, `SESSION_HANDOFF_2026-09-16.md` | 9월 원고 당시 기록. 실험 설계 부분은 이번 축소판으로 대체됨 |

실험 도구: `scripts/experiments/run_experiment.py`(진행 도우미: 결과 자동 판정, 처리 속도 기록, Pi 자원 기록 시작·회수, AI 이름 확인, 표 5–8 생성, `--resume`으로 이어하기). 손 기록 대안용으로 `poll_health.py`, `make_paper_tables.py`가 있다. 모두 노트북의 표준 Python만으로 실행된다(자원 기록은 기존 Pi 설치본의 `monitor_pi_resources.py`를 SSH로 실행).

## PDF 다시 만들기

```powershell
python docs\paper\manuscript\build_manuscript.py
```

`reportlab`, `pypdf`가 필요하다. Windows에서는 바탕·맑은 고딕, Linux에서는 WenQuanYi 글꼴을 쓴다. 그림 2·5·6은 `manuscript/figures/figure-2.png`, `figure-5.png`, `figure-6.png`를 넣으면 자동으로 들어가고, 없으면 ‘사진 입력 예정’ 상자가 표시된다. `manuscript/FINAL_VALIDATION.json`, `SOURCE_CHECK.json`은 9월 16일 원고의 검사 기록이다.

## 아직 쓰면 안 되는 주장

실험 전에는 정확도, 오탐 수, 호출 비율, CPU·온도·처리 속도 숫자를 쓰지 않는다. 결과가 나쁘면 요약·고찰·결론을 결과에 맞게 고친다. 자동화 테스트 통과나 시연 성공 보고는 현장 인식 정확도가 아니다.
