# Re:Found — 여기서 시작하세요

**Re:Found는 Raspberry Pi 4와 카메라로 물품의 등록·이동·회수를 감지하고, 웹에서 분실물을 관리하는 프로젝트입니다.** 로컬 영상 처리로 변화 사건을 선별하고 필요한 사건에 외부 AI 분석을 요청합니다. 현재 구현·구조·전체 실행 설명은 [README.md](README.md)에 있습니다.

**아래에서 지금 할 일 하나만 고르면 됩니다.** 모든 문서나 `AGENTS.md`를 읽을 필요는 없습니다.

## 지금 상태 — 2026-10-26

| 항목 | 상태 |
|---|---|
| **최종보고 발표 자료** (11/03, 시연 포함 10분) | **완성.** 발표 파일은 [최종 PDF](docs/presentation/REFOUND_PROJECT_FINAL_2026-11-03.pdf)(25장, 10/26 덱에서 내려받은 것). 편집은 [Re:Found 최종보고 덱](https://claude.ai/artifact/DsBPmugyoDJ7YLKdYD5G9B), 원본·그림은 [최종보고 발표 자료](docs/presentation/final/README.md) |
| **시연** (10/27 연습, 11/03 발표) | [시연 준비](docs/presentation/FINAL_DEMO_GUIDE.md) 한 장만 보면 됩니다. 10/27 연습 때 백업 영상을 녹화합니다 |
| **10월 25일 실험** | **완료.** [10/25 실험 결과](docs/paper/RESULTS_2026-10-25.md) — 놓기·옮기기·치우기 270번 중 244번(90.4%), AI 이름·분류 84번 중 80번(95.2%), 손을 뗀 뒤 이름까지 7.8초 |
| **논문** | **결과 반영 완료(10/26).** JDCS 형식 점검·수정 후 [원고 PDF](docs/paper/REFOUND_FULL_MANUSCRIPT.pdf) 9쪽. 남은 일은 학회 HWP 양식으로 옮기기와 투고 전 확인입니다([개정 상태](docs/paper/REVISION_STATUS.md)) |
| 개발 중간보고 (10/13) | 완료. [최종 PDF](docs/presentation/REFOUND_PROJECT_MIDTERM_2026-10-13_FINAL.pdf) |

남은 일정: **10/27 최종보고 연습, 11/03 최종보고**, 11/10 본론, 11/17 팀논문, 11/24 최종논문 발표.

### 사용자가 정하거나 해야 할 것

발표 덱은 지금 그대로 씁니다(AI 호출 81건 표기도 유지, 10/26 결정). 질의에서 물으면 “정확히는 80건, 74.1%”라고 답하면 됩니다.

| 할 것 | 언제 | 자세히 |
|---|---|---|
| 백업 영상 녹화 | 10/27 연습 때 | [시연 준비](docs/presentation/FINAL_DEMO_GUIDE.md) |
| 논문 저자 정보(저자·순서·소속·교신저자·약력) 정하기 — 나머지 투고 전 확인은 10/26에 답해서 반영 완료 | 투고 전, 지도교수님과 | [개정 상태 4절](docs/paper/REVISION_STATUS.md) |

## 할 일 고르기

다음 작업을 자동으로 정하지 않습니다. 사용자가 작업을 지정하면 바로 이어가고, “계속하자”라고만 하면 아래 선택지를 짧게 안내합니다.

| 할 일 | 먼저 열 파일 | 남은 작업 |
|---|---|---|
| **논문 마무리·투고** | [논문 안내](docs/paper/README.md) · [개정 상태(형식 점검·투고 전 확인)](docs/paper/REVISION_STATUS.md) · [2단 PDF](docs/paper/REFOUND_FULL_MANUSCRIPT.pdf) | 투고 전 확인 항목에 답하기 → 원고 수정 → 학회 HWP 양식으로 옮기기 |
| **최종보고 연습·발표** | [시연 준비](docs/presentation/FINAL_DEMO_GUIDE.md) · [최종보고 발표 자료](docs/presentation/final/README.md) | 10/27 연습(백업 영상 녹화, 시간 확인) → 고칠 점이 있으면 덱 수정 → 11/03 발표 |
| **Pi 시연·실기 확인** | [핫스팟 실행·종료](docs/guides/WINDOWS_HOTSPOT_GUIDE.md) · [실기 확인표](docs/guides/PI_ACCEPTANCE_CHECKLIST.md) | 기존 연결 방식으로 시연, 새 구성의 전원 재인가·자동 연결 등 확인 |
| **Pi API 키 교체·Gemini 전환** | [API 키 변경 간단 안내](docs/guides/PI_API_KEY_CHANGE.md) | Pi `.env` 키 수정 → 재시작 → 웹 제공자 선택 → 실물 확인 |
| **PC 자체에서 앱 실행** | 아래 ‘PC 실행 환경 다시 준비하기’ | 필요할 때 `setup.ps1` → `start.ps1` |

Pi 관련 작업(시연·실기·API 키)은 Claude가 Pi에 직접 접속할 수 없으므로, 안내받은 명령을 노트북이나 Pi에서 직접 실행하고 출력을 붙여 주면 됩니다. API 키·비밀번호는 채팅에 붙이지 않습니다.

## 다음 세션 시작하기

새 Claude Code 세션은 `AGENTS.md`(작업 지침)를 자동으로 읽고 시작합니다. 아래처럼 한 줄로 할 일을 말해 주면 됩니다.

> START_HERE.md, AGENTS.md 보고 시작하자.

이렇게만 말하면 현재 상태를 짧게 요약하고 할 일 선택지를 보여 줍니다. 할 일이 정해져 있으면 “… 보고 시작하자. 논문 HWP 이식부터 하자”처럼 작업 이름을 붙이면 바로 시작합니다.

**작업 저장 위치:** Claude가 한 작업은 세션마다 `claude/…` 작업 브랜치에 저장되고, 사용자가 “main에 반영해”라고 하면 `main`에 들어갑니다. 새 세션은 보통 `main`에서 시작하므로, **이전 세션 작업이 `main`에 반영돼 있어야** 새 세션이 그 내용을 봅니다. **10/26 작업까지는 모두 `main`에 반영돼 있습니다**([PR #20](https://github.com/Jinseok2419342/Capstone-team-project/pull/20)). 앞으로도 세션을 마칠 때 “main에 반영해”라고 하면 다음 세션이 바로 이어받습니다.

## 확정한 시연 실행·종료 순서

**2026-09-30 사용자가 최종 순서를 다시 확인했습니다.** 상세 설명과 문제 해결 과정은 [핫스팟 가이드 2–4절](docs/guides/WINDOWS_HOTSPOT_GUIDE.md#2-매번-실행하는-순서)에 있습니다.

1. 노트북을 학교 Wi-Fi 인터넷에 연결합니다.
2. 노트북의 `ReFoundLaptop` 핫스팟을 켭니다.
3. Pi 전원을 연결합니다.
4. 약 2~3분 기다립니다.
5. **노트북의 새 PowerShell**을 엽니다.
6. 아래 명령을 실행하고 Pi 로그인 비밀번호를 입력합니다. 로그인 후에도 창을 유지합니다.

   ```powershell
   ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local
   ```

7. 같은 노트북 브라우저에서 `http://127.0.0.1:18000`을 엽니다.

**종료:** 작업·AI 처리 완료 → Pi에 로그인된 창에서 `sudo shutdown -h now` → 초록 ACT LED의 종료 점멸이 끝나면 전원 분리 → 노트북 핫스팟 끄기입니다. 빨간 전원 LED가 꺼질 때까지 기다리는 뜻은 아닙니다.

**`Could not resolve hostname` 오류:** 노트북 **설정 → 네트워크 및 인터넷 → 모바일 핫스팟 → 연결된 장치**에서 현재 Pi IP를 확인하고, 명령의 `@` 뒤만 바꿉니다. 예를 들어 현재 목록이 `192.168.137.243`이라면 다음을 실행합니다.

```powershell
ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@192.168.137.243
```

브라우저 주소는 그대로 `http://127.0.0.1:18000`입니다. 예시 IP를 고정값으로 사용하지 않습니다. 노트북 앱 설치·Tailscale 초대 수락은 이 절차에 필요하지 않습니다. **사용 순서의 확정과 새 전원 재인가 시험의 성공 보고는 별개**이며, 아직 없는 시험 결과는 성공으로 기록하지 않습니다.

메인 화면의 **시연 초기화**는 물건을 치운 뒤 확인 한 번으로 모든 물품·기록·사진을 **백업 없이 삭제**합니다. 설정과 API 키는 유지합니다. 복구용 백업이 필요하면 설정의 기존 초기화를 사용하세요.

## PC 실행 환경 다시 준비하기

**Pi 화면만 노트북에서 열 때는 아래 설치가 필요 없습니다.** [핫스팟 가이드](docs/guides/WINDOWS_HOTSPOT_GUIDE.md)의 SSH 터널을 노트북 PowerShell에서 열고 `http://127.0.0.1:18000`으로 접속합니다. 아래는 PC 자체에서 앱을 실행하려는 경우입니다.

PC 프로젝트의 `.venv`는 9월 22일 사용자가 삭제했습니다. 발표 자료·문서 작업에는 재설치가 필요하지 않습니다. PC에서 앱을 실행할 때만 이 프로젝트 폴더의 PowerShell에서 아래 순서로 실행합니다. Python 3.11 이상이 `python` 명령으로 실행 가능해야 하고, 패키지를 내려받을 인터넷 연결이 필요합니다.

```powershell
.\setup.ps1
.\start.ps1
```

`setup.ps1`은 없는 `.venv`를 만들고 `requirements.txt`의 실행 패키지를 설치합니다. 기존 `.env`가 있으면 유지합니다. **`start.ps1` 자체는 가상환경을 만들지 않으므로 처음 한 번은 반드시 setup을 먼저 실행**하세요. 개발 테스트를 다시 할 때는 `requirements-dev.txt`도 별도로 설치합니다([README 안내](README.md)). 이 가상환경은 Pi의 설치 환경과는 별개입니다.

## Pi 시연의 현재 상태

새 SD에 **설치·실제 카메라 촬영 검사·재부팅 후 자동 실행**을 확인했고, 시연 초기화와 실물 등록·이동·회수가 동작합니다. **현재는 Windows 노트북 핫스팟과 SSH 터널을 사용합니다.** 10월 25일 실험도 이 방식(학교 Wi-Fi에 연결된 노트북 핫스팟)으로 진행했습니다. 새 구성의 자동 연결 설정, 정상 종료 후 전원 재인가·무선 단독 부팅·화면/영상/AI 복귀는 아직 별도 시험 기록이 없습니다. 메일 수신과 장시간 온도·안정성도 별도 확인 대상입니다. 설치를 처음부터 다시 할 때만 [새 SD 설치 안내](docs/guides/FRESH_SD_START.md)를 따릅니다. 상세 기록은 [작업 인계](docs/handoff/SESSION_HANDOFF.md)에 있습니다.

## 파일 정리 기준 — 2026-10-26

`AGENTS.md`에 쌓였던 날짜별 과거 기록은 [`docs/handoff/AGENTS_HISTORY.md`](docs/handoff/AGENTS_HISTORY.md)로 원문 그대로 옮겼습니다(새 세션이 옛 지시를 따르지 않도록). 논문 자리표시자 입력표는 결과를 넣은 뒤 지우고 [원고 숫자 출처표](docs/paper/MANUSCRIPT_NUMBERS.md)로 바꿨습니다.

최종보고 발표 자료가 완성돼, 발표를 **만드는 데만 쓰던 문서**(최종보고 준비 정리·형식 원문·발표 근거와 캡처 요령·검토자 노트·덱 확인 도구)를 삭제했습니다. 남긴 것은 완성된 덱 원본과 그림(`docs/presentation/final/`), 시연 준비 문서, 실험 결과 문서입니다. 중간보고는 최종 PDF 1개, 9월 논문 전반부 발표는 [PDF 캡처 4장 PPTX](docs/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx)가 기준입니다. 삭제한 파일은 Git 이력에서 꺼낼 수 있습니다(최종보고 준비 문서는 `main`의 2026-10-26 정리 커밋 직전, 중간보고 제작 파일은 커밋 `d7cd505`).

8월 발표 초안(`docs/presentation/2026-08-draft/`)과 Mermaid 도식(`docs/presentation/diagrams/`)은 과거 자료로 남겼습니다. 앱 소스·테스트, 실험 도우미, 학교 양식, 별도 과제의 기획·보고서, 실제 데이터·비밀값은 정리 대상이 아닙니다.

## 나머지 폴더는 언제 보나요?

| 위치 | 용도 |
|---|---|
| `dist/refound-pi.tar.gz` | 새 Pi에 복사할 배포 파일. `.sha256`도 함께 사용. **Git에 포함되지 않아** PC에만 있으며, 없으면 `scripts/raspberry-pi/package-for-pi.ps1`로 다시 만듦 |
| `docs/` | **모든 문서와 완성본.** 전체 지도는 [문서 인덱스](docs/README.md) |
| `docs/guides/` | 설치·시연·네트워크 안내. 매번 쓰는 핫스팟 실행·종료 안내도 여기 있음 |
| `docs/paper/` | 논문 PDF·원고·10/25 실험 결과·원고 숫자 출처표·개정 상태·실험 안내·참고문헌·PDF·그림 생성기 |
| `docs/presentation/` | 최종보고 발표 자료(`final/` — 덱 원본·그림), 시연 준비, 중간보고 최종 PDF, 논문 전반부 발표 PPTX, 도식, 8월 발표 초안 |
| `docs/brochure/` | 졸업작품집 브로셔 최종본(HWP·PDF). 완료된 작업 |
| `docs/development/`, `docs/handoff/` | 9월 개발 개선 기록, 다음 AI 세션용 인계(누적 기록 `SESSION_HANDOFF.md`, AGENTS 과거 기록 `AGENTS_HISTORY.md`) |
| `docs/records/` | 날짜별 검증 요약·벤치마크 원장. 평소에는 열 필요 없음 |
| `docs/project-history/` | 1학기 아이디어·기획·회의록·보고서와 9월 현황보고. 팀 활동 보관 자료이며 현재 설치 설명이 아님 |
| `data/` | 실제 DB·사진. **Git에 포함되지 않음**(PC·Pi에만 있음). 정리 대상으로 지우지 않음 |
| `AGENTS.md` | 다음 AI 세션이 자동으로 읽는 지침(현재 상태·시작 순서·규칙·환경). 사용자용 설명서는 이 문서 |

분야별 안내는 [문서 인덱스](docs/README.md), 다음 AI의 누적 기록은 [작업 인계](docs/handoff/SESSION_HANDOFF.md)에 있습니다. 다음 작업이 정해졌다면 “논문 HWP 이식”, “최종보고 연습”, “Pi 시연”처럼 작업 이름을 함께 말하면 됩니다.
