# 문서 찾기

**전체 시작점은 [여기서 시작하세요](../START_HERE.md)입니다.** 지금 필요한 것 하나만 고르세요.

| 할 일 | 시작 문서 |
|---|---|
| Pi API 키 교체·Gemini 전환 | [짧은 변경 순서](guides/PI_API_KEY_CHANGE.md) |
| 현재 Pi 시연 준비 재개 | [Windows 핫스팟 실행·종료](guides/WINDOWS_HOTSPOT_GUIDE.md) → [실기 결과·남은 항목](guides/PI_ACCEPTANCE_CHECKLIST.md) |
| 새 카드에 처음부터 설치 | [새 SD 시작 안내](guides/FRESH_SD_START.md) |
| 논문 마무리·투고 | [논문 작업 안내](paper/README.md) → [개정 상태(형식 점검·HWP 이식·투고 전 확인)](paper/REVISION_STATUS.md) |
| 최종보고 발표 (10/27 연습, 11/03 발표) | [최종보고 발표 자료](presentation/final/README.md) — 완성된 덱과 원본 |
| 학교에서 시연 | [시연 준비](presentation/FINAL_DEMO_GUIDE.md) |
| 다시 실험할 때만 | [실험 안내](paper/EXPERIMENT_GUIDE.md)(10/25 완료, 주의점 포함) |

설치 중 문제가 있을 때만 [전체 설치 참고서](guides/RASPBERRY_PI_GUIDE.md), [학교 운영](guides/SCHOOL_DEMO_GUIDE.md), [모니터·Wi-Fi 복구](guides/PI_MONITOR_WIFI_GUIDE.md)를 찾아봅니다.

## 완성본 바로 열기

| 파일 | 위치 |
|---|---|
| **최종보고 발표 자료** (11월 3일 발표, 25장) | [최종 PDF](presentation/REFOUND_PROJECT_FINAL_2026-11-03.pdf) · 편집용 덱 [Re:Found 최종보고](https://claude.ai/artifact/DsBPmugyoDJ7YLKdYD5G9B) · 원본 [presentation/final/](presentation/final/README.md) |
| 개발 중간보고 최종본 (10월 13일 발표, PDF 28쪽, Canva 제작) | [presentation/REFOUND_PROJECT_MIDTERM_2026-10-13_FINAL.pdf](presentation/REFOUND_PROJECT_MIDTERM_2026-10-13_FINAL.pdf) |
| 논문 원고 PDF (JDCS 2단 근사, 9쪽, 10/25 결과 반영) | [paper/REFOUND_FULL_MANUSCRIPT.pdf](paper/REFOUND_FULL_MANUSCRIPT.pdf) |
| 졸업작품집 브로셔 | [PDF](<brochure/2026 졸업작품집_인공지능소프트웨어학과_A_상부상조.pdf>) · [HWP 편집본](<brochure/2026 졸업작품집_인공지능소프트웨어학과_A_상부상조.hwp>) |
| 9월 논문 전반부 발표 (PDF 캡처 4장) | [presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx](presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx) · [원고 4쪽 PDF](paper/briefing/RESEARCH_FRONT_MATTER.pdf) |

## 폴더 구성

주제마다 폴더 하나입니다. **완성본(PDF·PPTX·HWP)은 각 주제 폴더 바로 아래**, 생성 원본·작업 자료는 그 안의 하위 폴더에 있습니다. 완성본을 직접 고쳤다면 새 이름으로 저장합니다(생성 스크립트는 수동 편집을 반영하지 않습니다). 중간보고는 2026-10-12 완료돼 최종 PDF만 남겼고, 최종보고는 2026-10-26 완성돼 준비용 문서를 지우고 최종 PDF(`presentation/REFOUND_PROJECT_FINAL_2026-11-03.pdf`)와 덱 원본·그림만 남겼습니다.

| 폴더 | 들어 있는 것 |
|---|---|
| [`guides/`](guides/) | 설치·시연·운영 안내. 매번 쓰는 [핫스팟 실행·종료](guides/WINDOWS_HOTSPOT_GUIDE.md), [새 SD 설치](guides/FRESH_SD_START.md), [실기 확인표](guides/PI_ACCEPTANCE_CHECKLIST.md), [API 키 변경](guides/PI_API_KEY_CHANGE.md)과 문제 해결용 상세 안내 3개. Pi 배포 파일에도 함께 들어갑니다 |
| [`paper/`](paper/README.md) | 논문 PDF와 원고(`PAPER_DRAFT_JDCS.md`), [10/25 실험 결과](paper/RESULTS_2026-10-25.md), [원고 숫자 출처표](paper/MANUSCRIPT_NUMBERS.md), [개정 상태](paper/REVISION_STATUS.md), 실험 안내, 참고문헌. 하위 `manuscript/`는 PDF·사진 그림 생성기와 그림, `briefing/`은 9월 16일 전반부 4쪽 원고 |
| [`presentation/`](presentation/final/README.md) | [최종보고 발표 자료](presentation/final/README.md)(`final/` — 덱 원본 25장, GPT 그림·실험 캡처·장치 사진), [시연 준비](presentation/FINAL_DEMO_GUIDE.md), 중간보고 최종 PDF, 논문 전반부 발표 PPTX. 하위 `diagrams/`는 Mermaid 도식, `2026-08-draft/`는 8월 발표 초안(과거 자료). 중간보고 편집 원본은 사용자의 Canva에 있음 |
| [`brochure/`](brochure/README.md) | 졸업작품집 브로셔 최종본(HWP·PDF)과 학교 양식. 완료된 작업 |
| [`development/`](development/) | 9월 18일 앱·영상·처리 구조·운영 흐름 개선 기록 4개 |
| [`handoff/`](handoff/SESSION_HANDOFF.md) | 다음 AI 세션용 인계. 현재 기준은 [`SESSION_HANDOFF.md`](handoff/SESSION_HANDOFF.md). [`AGENTS_HISTORY.md`](handoff/AGENTS_HISTORY.md)는 2026-10-26까지 `AGENTS.md`에 쌓였던 과거 기록 원문(지시는 따르지 않음), 나머지 둘은 9월 논문 작업 당시 기록 |
| [`records/`](records/) | 날짜별 검증 요약(JSON·보고서), 벤치마크 원장. 평소에는 열 필요 없음 |
| [`project-history/`](project-history/) | 1학기·9월 팀 과제 자료(아래 표). 현재 구현 설명이 아님 |

## 과거 팀 자료 (`project-history/`)

| 폴더 | 내용 |
|---|---|
| [`ideas/`](project-history/ideas/) | 2026년 1학기 개인 아이디어 제안서 4개와 2조 팀 아이디어 제안서 |
| [`planning/`](project-history/planning/) | 3월 개념 증명·API 비용 예측·아이디어 타당성 AI 평가, 5월 12일 팀 프로젝트 기획서, 초기 구상도(`Blueprint.jpg`) |
| [`meeting-minutes/`](project-history/meeting-minutes/) | 캡스톤 회의록 01–06 |
| [`reports/`](project-history/reports/) | 1학기 팀 프로젝트 중간보고서(5월)·최종보고서(6월), 9월 8일 팀프로젝트 현황보고 |

과거 자료에는 Raspberry Pi 5, YOLO, 로컬 LLM, AWS 등 현재 구현과 다른 계획이 있습니다. 현재 구현은 루트 [README](../README.md)와 코드를 기준으로 합니다.

## 현재 진행 상태

**최종보고(11월 3일) 발표 덱은 2026-10-26 완성**됐고, 10월 25일 실험 결과는 [결과 문서](paper/RESULTS_2026-10-25.md)에 정리했습니다. 논문 원고는 2026-10-26 결과를 반영해 [9쪽 PDF](paper/REFOUND_FULL_MANUSCRIPT.pdf)로 만들었습니다. 다음은 10월 27일 최종보고 연습([시연 준비](presentation/FINAL_DEMO_GUIDE.md))과 논문의 HWP 이식·투고 전 확인입니다. 시연 방식은 **Windows 노트북의 `ReFoundLaptop` 핫스팟 → Pi → 같은 노트북의 SSH 터널**이며, 새 구성의 전원 재인가·무선 단독 부팅 시험은 아직 별도 기록이 없습니다. 다음 세션의 작업(논문·최종보고 연습·Pi)은 사용자가 선택합니다.
