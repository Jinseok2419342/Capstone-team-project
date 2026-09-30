# Re:Found 논문 작업공간

[시작 안내로 돌아가기](../../START_HERE.md)

## 지금 열 파일

| 할 일 | 파일 |
|---|---|
| 논문 읽기 | [전체 PDF](../../output/pdf/REFOUND_FULL_MANUSCRIPT.pdf) |
| 본문 수정 | [편집 원고](PAPER_DRAFT_JDCS.md) |
| 실험 준비·수치 입력 | [측정 시작 안내](PERFORMANCE_MEASUREMENT_START.md) → [실험 설계](EXPERIMENT_GUIDE.md) → [결과 입력표](RESULTS_FILL_SHEET.md) |
| 기존 논문 발표 열기 | [PDF 캡처 4장 PPTX](../../output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx) |

**현재 원고·PDF는 9월 16일 실측 전 버전입니다.** 9월 18·22일 앱 개선을 아직 반영하지 않았습니다. 9월 22일 새 SD 설치·촬영·재부팅 진단을 통과했고 기본 실물 동작·본인 PC Tailscale 영상은 사용자 성공 보고가 있습니다. 친구 공유는 초대 링크 전송 후 수락·접속·핫스팟 시험 대기입니다. 이 진행은 논문용 정량 실험이 아닙니다. [현재 실기 기록](../guides/PI_ACCEPTANCE_CHECKLIST.md)

논문 작업을 선택하면 먼저 [개선점 요약](../IMPROVEMENTS.md)과 원고의 구현 설명을 대조합니다. 프로젝트 발표 PPT를 선택하면 [발표 준비](../IMPROVEMENTS.md)로 이동합니다. 아래 과거 인계·다른 AI 전달 문서도 최신 코드와 대조해야 합니다. 실제 측정 전에는 수치 placeholder를 채우지 않습니다.

이 디렉터리는 현재 소스 코드와 루트 `README.md`를 기준으로 만든 논문 준비 패킷이다. 과거 기획서의 계획과 현재 구현이 충돌하면 현재 코드와 루트 README를 우선한다.

## 최신 산출물 — 2026-09-16

- [대화 요점 백업·사용자 선호·다음 AI 재개 안내](SESSION_HANDOFF_2026-09-16.md)
- [전체 원고 PDF — 19쪽](../../output/pdf/REFOUND_FULL_MANUSCRIPT.pdf)
- [발표용 전반부 PDF — 4쪽](../../output/pdf/RESEARCH_FRONT_MATTER.pdf)
- [전반부 발표 PowerPoint — PDF 캡처 4장](../../output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx)
- [성능 수치를 채우는 쉬운 절차](PERFORMANCE_MEASUREMENT_START.md)
- [완료 내용·실측 대기·다음 작업](REVISION_STATUS.md)

전체 원고는 구현·실험 설계와 결과 작성 틀까지 개정했다. 실제 성능 수치는 아직 없고, 원고와 입력표의 고유 입력 항목 297종이 일치한다. 그림 4개, 표 13개, 수식 6개 및 참고문헌 17개를 포함한다. 편집용 PDF는 단일단이며 최종 투고 HWP가 아니다.

## 현재 결정

- 1순위 투고처: **디지털콘텐츠학회논문지(JDCS)**
- 2순위 투고처: **실천공학교육논문지(JPEE)** — 캡스톤 교육과정과 학습성과 평가를 추가할 때만 권장
- 논문 유형: 새로운 AI 모델 제안 논문이 아니라 **저사양 엣지 사건 감지와 선택적 멀티모달 추론을 결합한 시스템 설계·구현·실증 논문**
- 권장 제목: **저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템**
- 목표 분량: JDCS 공식 양식 기준 9~10쪽

## 파일 역할

| 파일 | 역할 | 언제 사용하나 |
|---|---|---|
| `PAPER_DRAFT_JDCS.md` | 현재 코드에 근거한 JDCS용 국·영문 초록부터 참고문헌까지의 전체 논문 초안 | 본문 수정과 최종 HWP 이식의 기준본 |
| `RESULTS_FILL_SHEET.md` | 초안의 모든 실측 placeholder, 원천 자료, 우선순위와 제출 전 점검표 | 실험 직후 수치 입력 및 과장 방지 |
| `PAPER_AI_HANDOFF.md` | 코드에서 확인한 구현 사실, 연구 논지, 실험 설계, 주장 금지선, AI 작성 프롬프트 | 다른 AI에 가장 먼저 전달 |
| `VENUE_AND_RELATED_WORK_STRATEGY.md` | 두 학술지 비교, 공식 형식·비용, 예시 논문 분석, 선행연구 차별화 | 투고처 결정과 관련연구 작성 |
| `EXPERIMENT_GUIDE.md` | 원시 스키마, 이미지 쌍 ablation, 지표 집계, Pi 자원 측정 절차와 해석 경계 | 실험 설계·실행 전 필독 |
| `VISION_PAIR_MANIFEST_TEMPLATE.csv` | 안정된 전·후 이미지와 정답 bbox를 연결하는 입력 양식 | 로컬 코어 ablation 입력 |
| `EXPERIMENT_RECORD_TEMPLATE.csv` | 사건별 핵심 값을 한 행으로 보는 51개 열 보조 템플릿 | 파생표·수동 점검용 |
| `REFERENCES.bib` | 영상 정합·엣지 컴퓨팅·관련 국내 논문의 출발 서지 | 참고문헌 관리 |

## 다른 AI에 전달할 최소 묶음

소스 코드를 직접 읽지 못하는 AI에는 다음 파일이면 논문 구조와 사실관계를 이해시킬 수 있다.

1. `PAPER_DRAFT_JDCS.md`
2. `RESULTS_FILL_SHEET.md`
3. `PAPER_AI_HANDOFF.md`
4. `VENUE_AND_RELATED_WORK_STRATEGY.md`
5. `EXPERIMENT_GUIDE.md`
6. 실제 값이 채워진 `episodes.csv`, `events.csv`, 지표 요약 CSV

루트 `README.md`와 `REFERENCES.bib`도 함께 첨부하면 구현·서지 교차검증이 쉽다. 그림을 만들 때는 `docs/presentation/diagrams/`와 `docs/presentation/assets/`를 추가한다. 다른 AI에는 “초안의 이중 대괄호 값을 근거 없이 만들지 말 것”을 첫 지시로 준다.

## 지금 우리 대화에서 계속하는 편이 좋은 이유

현재 세션은 코드 구조, 실제 구현과 과거 계획의 차이, 논문에서 주장해도 되는 범위, 가장 가까운 선행연구까지 이미 연결해 두었다. 따라서 **실험 로깅 추가, 결과 해석, 초안 작성까지는 이 대화에서 이어가는 편이 효율적**이다. 다른 AI는 문장 스타일 교정이나 독립적인 반론·심사자 관점 검토에 쓰면 좋다. 이 패킷은 그때 맥락 손실을 줄이는 용도다.

## 아직 만들면 안 되는 주장

다음은 측정값이 생기기 전에는 초안에 수치나 단정으로 넣지 않는다.

- 사건 감지 정확도와 “높은 정확도” 주장
- 실시간 처리 여부와 p50/p95 지연
- Pi CPU, RAM, 온도, 전력
- VLM 호출 절감률, 네트워크 전송량, 비용
- 장시간 안정성, 실제 반환 성공률

자동화 테스트 136개 통과는 이전 인계 시점의 기록이며 이번 원고 작업에서 재실행한 결과가 아니다. 테스트와 사용자 진술에 따른 실제 장비 구동 확인은 현장 인식 정확도를 증명하지 않는다.

## 다음 작업 순서

**논문 작업을 선택한 경우**의 순서다. 먼저 9월 18·22일 변경을 원고에 반영한다. privacy 부팅 동기화는 이미 구현했으며, 현재 재부팅 진단은 privacy 꺼짐 상태만 확인했으므로 켠 상태의 복원은 별도 실기 항목이다. 사용자 선택 없이 아래 계측 개발을 시작하지 않는다.

1. 실제 상태기계·DB·VLM timestamp와 job/attempt/usage/drop 영속 계측을 추가한다.
2. 논문 비교군 공통 replay 및 장애 주입 runner를 준비한다. 기존 개발 회귀 검사와 논문용 실험 실행기를 구분한다.
3. `EXPERIMENT_GUIDE.md`의 20~50건 파일럿으로 촬영·라벨·baseline adapter·임계값을 고정한다.
4. D_pair/D_stream/D_vlm/D_fault로 분리하여 본 실험을 수행한다.
5. 원시 CSV를 검증·집계하고 그래프를 생성한 뒤 `PAPER_DRAFT_JDCS.md`의 이중 대괄호 값을 교체한다.
6. 저자 식별정보를 제거한 심사용 원고를 JDCS 공식 HWP 양식으로 편집한다.

재현 가능한 원시 스키마, 일대일 사건 매칭·지표 집계, 안정 이미지 쌍 ablation runner와 Pi 자원 기록기는 구현되어 있다. 완성도에 가장 큰 영향을 주는 다음 작업은 **파일럿 데이터 확보와 종단간 timestamp 계측**이다.
