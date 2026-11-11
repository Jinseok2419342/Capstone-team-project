# Re:Found 논문 작업공간

[시작 안내로 돌아가기](../../START_HERE.md)

**2026-11-11 공식 양식 반영 완료.** 학회 홈페이지에서 공식 투고 규정과 논문 양식(2026년 7월 수정 HWP)을 직접 받아 원고를 다시 맞췄다: 첫 쪽은 제목·요약·색인어만, 영문 요약 168단어(규격 120–170), 표·그림 안의 글은 영문, 캡션은 국문 줄 아래 영문 줄, 그림은 jpg, 참고문헌은 양식의 유형별 형식. 숫자와 실험 내용은 10/26 결과 반영본 그대로다. 공식 용지(210 × 280 mm) 기준 근사 조판으로 **10쪽**(마지막 쪽은 4분의 1만 사용)이며 빈칸은 없다. 남은 일은 **학회 HWP 양식으로 옮기기와 투고 전 확인 2가지**(저자 정보, 참고문헌 [3]의 개최 장소)다([개정 상태](REVISION_STATUS.md) 3·4절).

## 지금 열 파일

| 할 일 | 파일 |
|---|---|
| 원고 읽기 | [공식 양식 근사 조판 PDF — 10쪽(심사용, 저자 정보 없음)](REFOUND_FULL_MANUSCRIPT.pdf) |
| 원고 수정·HWP로 옮기기 | [편집 원고](PAPER_DRAFT_JDCS.md) |
| 공식 규격 대조·HWP 이식 방법·투고 전 확인 | [개정 상태](REVISION_STATUS.md) |
| 학회 공식 양식·규정 | [양식 HWP(2026년 7월)](template/JDCS_TEMPLATE_2026-07.hwp) · [양식 안내문 텍스트](template/JDCS_TEMPLATE_2026-07.txt) · [투고 규정](template/JDCS_SUBMISSION_RULES.txt) |
| 숫자 근거 | [10/25 실험 결과](RESULTS_2026-10-25.md)(발표·논문 공통 원본) · [원고 숫자 출처표](MANUSCRIPT_NUMBERS.md)(원고 숫자 하나하나의 출처와 계산) |
| 다시 실험할 때만 | [실험 진행 안내](EXPERIMENT_GUIDE.md)(10/25에 알게 된 주의점 포함) |

## 현재 결정

- 투고처: **디지털콘텐츠학회논문지(JDCS)**. 심사 원고는 학회의 **공식 HWP 양식** 그대로 작성해 HWP로 낸다(용지 210 × 280 mm, 첫 쪽 1단·본문 2단, 바탕 9.1 pt, 영문 요약 120–170단어, 표·그림 안의 글은 영문). 이 저장소의 PDF는 쪽수·배치 확인용 근사 조판이다.
- 논문 유형: 새 AI 모델이 아니라 **저사양 장치의 사건 기반 감지와 선택적 외부 AI 호출을 결합한 시스템 설계·구현·실험 논문**.
- 제목: **저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템**
- 실험(2026-10-25): 물품 10종 × 10회 × 등록·이동·제거를 손으로 기록(계획 300회, 줄이어폰 이동·제거 20회는 시도 불가 → 실제 280회). 줄이어폰 제외 9종 270회 중 244회(90.4%), AI 이름·분류 84회 중 80회(95.2%). 처리 시간·속도·호출 수는 본 실험 전 보조 구간(도우미 38회)의 Pi 기록으로 계산했다. 도우미 자동 판정(57.9%)은 쓰지 않는다.
- 원고 구성: 표 8개, 그림 6개(영문 도식 3, 실제 사진·캡처 3), 수식 2개, 알고리즘 1개, 참고문헌 18편. 표와 알고리즘의 내용은 영문이다.
- 그림 2·5·6은 실험 캡처와 장치 사진만 쓴다(GPT 그림 금지). 그림 6장은 모두 `manuscript/make_figures.py`가 jpg로 만든다.

## 이번 논문 범위에서 뺀 것

다른 방법(단순 차영상·MOG2)과의 비교, 보정 단계별 ablation, AI 입력 사진 수 비교, 장애 주입, 장시간 실험, 전력·CPU·온도 측정, bootstrap·McNemar 통계. 원고 6-6절에 한계로 밝혔고, 심사위원이 요청하면 그때 추가한다. 기존 `experiments/`의 이미지 쌍 비교·매칭 도구는 그 경우에 다시 쓸 수 있다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `PAPER_DRAFT_JDCS.md` | 원고 원본. HWP로 옮길 기준본(장 번호 Ⅰ·1-1, 요약·Abstract·색인어·Keyword, 영문 표, 두 줄 캡션) |
| `REFOUND_FULL_MANUSCRIPT.pdf` | 공식 양식 근사 조판(`manuscript/build_manuscript.py`가 생성) |
| `template/` | 학회 공식 양식 HWP, 양식 안내문 텍스트, 투고 규정(2026-11-11에 학회 홈페이지에서 받음) |
| `RESULTS_2026-10-25.md` | 10/25 실험 결과 — 발표·논문 공통 숫자(손 기록과 Pi 기록 계산 구분, 보조 구간 상세는 5절) |
| `MANUSCRIPT_NUMBERS.md` | 원고 숫자별 출처·계산(심사 질의 대응용) |
| `REVISION_STATUS.md` | 공식 규격 대조표, 개정 내역, HWP 이식 방법, 투고 전 확인 목록 |
| `EXPERIMENT_GUIDE.md` | 실험 순서와 도우미 사용법. 다시 실험할 때만 |
| `TRIAL_SHEET_TEMPLATE.csv` | 손 기록지(100행 미리 채움) |
| `manuscript/make_figures.py` | 그림 1–6을 jpg로 생성(1·3·4는 영문 도식, 2·5·6은 실제 캡처·사진) |
| `REFERENCES.bib` | 참고문헌 후보 모음(원고는 18편 사용) |
| `VENUE_AND_RELATED_WORK_STRATEGY.md` | 투고처 비교·비용·심사 절차(9월 15일 조사) |
| [`PAPER_AI_HANDOFF.md`](../handoff/PAPER_AI_HANDOFF.md), [`PAPER_SESSION_HANDOFF_2026-09-16.md`](../handoff/PAPER_SESSION_HANDOFF_2026-09-16.md) | 9월 원고 당시 AI 인계 기록(`docs/handoff/`). 실험 설계 부분은 폐기된 계획 |

실험 도구: `scripts/experiments/run_experiment.py`(진행 도우미)와 손 기록 대안 `poll_health.py`, `make_paper_tables.py`. 모두 노트북의 표준 Python만으로 실행된다. 10/25에는 도우미 판정이 섞여 손 기록으로 바꿨으므로, 다시 실험한다면 [실험 진행 안내](EXPERIMENT_GUIDE.md) 맨 위의 주의점을 먼저 읽는다.

## PDF와 그림 다시 만들기

```powershell
python docs\paper\manuscript\make_figures.py         # 그림 1–6 jpg (Pillow)
python docs\paper\manuscript\build_manuscript.py     # PDF (reportlab, pypdf)
```

Windows에서는 바탕·맑은 고딕·Times New Roman·Arial, Linux에서는 나눔명조·나눔고딕·Liberation 글꼴을 쓴다. 나눔명조에 없는 로마 숫자·빼기 기호는 다른 글꼴로 자동 대체한다. 빌드는 이중 대괄호나 ‘입력 대기’가 남아 있거나, 영문 요약이 120–170단어를 벗어나거나, 첫 쪽이 1쪽을 넘으면 실패한다. 결과 요약은 `manuscript/PDF_BUILD_REPORT.json`에 남는다.

## 쓰면 안 되는 주장

결과 문서에 없는 숫자(CPU·온도·무변화 오탐률·다른 방법과의 비교)는 쓰지 않는다. 무변화 조건은 횟수를 세지 않았으므로 ‘관찰한 범위에서 잘못된 기록 없음’까지만 쓴다. 처리 시간·호출 수는 보조 구간 값임을 밝힌다. 자동화 테스트 통과나 시연 성공은 현장 인식 정확도가 아니다.
