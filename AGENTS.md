# Re:Found 작업 인계 및 재개 지침

이 파일은 2026-09-30 문서 동기화와 9월 29일까지의 사용자 시연 보고를 포함한 작업 상태를 다음 세션이 이어받기 위한 저장소 수준의 인계 문서다. 아래 최신 우선순위가 과거 재개 지침보다 우선한다.

## 최신 반영 — 2026-09-30 / 외부 환경의 9월 29일 시연 백업

- 최신 시연 원문은 루트 `REFOUND_WINDOWS_HOTSPOT_GUIDE.md`다. 아래 9월 22일의 친구 응답 대기·Android/Tailscale 기본 계획보다 이 기록이 우선한다. 읽기 순서는 `START_HERE.md` → 이 절 → 핫스팟 백업 → `docs/SESSION_HANDOFF_2026-09-18.md`다.
- **9월 30일 후속 사용자 확인:** 실행 **7단계**, 종료 **4단계**, `Could not resolve hostname` 대응 **5단계**를 최종 사용 순서로 다시 제시했다. 원문 가이드 2·3·4절과 `START_HERE.md`의 ‘확정한 시연 실행·종료 순서’에 반영했다. 실행은 **학교 Wi-Fi → ReFoundLaptop → Pi 전원 → 2~3분 → 노트북 PowerShell → 아래 SSH 명령 → 브라우저**다. 이름 오류는 **Windows 설정의 모바일 핫스팟 연결 장치 → 현재 Pi IP 확인 → `@` 뒤만 교체 → 수정한 SSH 실행 → 같은 브라우저 주소**다. `192.168.137.243`은 목록에 실제로 표시될 때만 쓴다.
- **재개 우선순위:** 사용자가 새로 선택한 작업을 먼저 수행한다. ‘계속 진행’만 있으면 기존 v3 PPT 검토·캡처 보완을 기본으로 하고, 시연 실행을 요청하면 확정된 사용 순서를 안내한다. 시연 재점검·실기 검증을 선택했을 때 아래 남은 시험을 이어간다. 미확인 시험을 발표/문서 작업의 선행 조건으로 강제하거나 연결 방식·설치를 처음부터 다시 묻지 않는다. 이번 후속 메시지는 절차 재확정이며 별도의 전원 재인가 시험 성공 보고는 아니다.
- 현재 구성: **Windows 노트북의 `ReFoundLaptop` 핫스팟 → Pi → 같은 노트북의 SSH 터널**. 앱·카메라는 기존 Pi에서 실행한다. 노트북에 앱을 설치하거나 `setup.ps1`·`start.ps1`을 실행할 필요가 없다.
- **로그 확인:** `ReFoundLaptop` 신호 100/WPA2 검색과 `wlan0` 활성화. 최종 프로필 UUID `7cd76ca8-c636-49e0-98ab-581153a2c91b`. 먼저 만든 프로필 UUID와 후속 `unknown connection`의 원인 불명 경과를 성공한 최종 프로필과 혼동하지 않는다.
- **사용자 성공 보고:** Windows 새 PowerShell에서 SSH 터널을 시작한 뒤 노트북 웹 접속·OpenAI API 동작 성공. 처음 Pi 내부에서 터널을 실행한 문제를 바로잡았다. 개별 API 응답·9월 29일 모델명·정량 정확도·지연은 수집하지 않았다. 9월 22일 모델 설정을 현재 모델 검증으로 취급하지 않는다.
- 실행: 상위 인터넷 Wi-Fi → 노트북 핫스팟 → Pi 전원 → 부팅 대기 → **Windows PowerShell**에서 `ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local` → 같은 노트북 브라우저 `http://127.0.0.1:18000`. 창과 핫스팟을 유지한다. 이름 실패 시 `@` 뒤만 현재 Pi IP로 바꾼다. 관찰 IP `192.168.137.243`은 고정값이 아니다.
- **시연 재점검을 선택할 때의 남은 확인:** 최종 프로필의 자동 연결·우선순위와 서비스 enabled 확인 → 정상 종료 → 랜선 분리·전원 재인가 → 핫스팟 자동 연결·터널 재실행·영상/AI 복귀. 새 구성에서의 이 확인은 아직 미확인이다. 매번 사용 순서에 설정 변경 명령을 추가하지 않는다. 예전 `s24+`는 시험 중 끈다. 자동 연결 수정 명령은 안내됐지만 실행 결과를 받지 않았다.
- 친구 Tailscale 수락·접속은 별도 미확인이다. 현재 SSH 시연을 친구 초대 응답 때문에 중단하지 않는다. 기존 Tailscale 설정을 삭제하거나 다시 설치하지 않는다. 종료는 Pi에서 `sudo shutdown -h now`, ACT 종료 점멸이 끝난 뒤 전원 분리, 마지막에 핫스팟을 끈다.
- 이번 요청은 관련 안내 전반의 동기화와 Git 대량 반영의 실행 무결성 점검이다. 기존 원고/PDF/PPTX·Pi·운영 데이터는 보존한다. 기존 v3 PPT의 사실 기준은 9월 22일이며 후속 사용자 보고는 작성 가이드에 보완 사항으로 기록한다.
- 저장소는 현재 Git checkout이며 점검 시작 HEAD는 `956b346`(Until-2026-09-30), 부모는 `258efc1`이다. 핫스팟 원문은 시작 시 미추적이었다. 소스/검증 근거·실행 점검 결과와 남은 Git 관리 문제는 `output/maintenance/2026-09-30-sync-review/REVIEW.md`를 따른다. 과거 `.git` 부재와 검사 횟수는 당시 기록이다. 이전 JSON 원장은 덮어쓰지 않는다.
- **점검 완료:** 복사된 실행 소스는 9월 22일 설치 배포본과 동일하며 Python **272개**, Node **37개** 재실행 통과. 격리 DB의 실제 `run.py` 시작과 화면·정적 파일·API HTTP 200 확인. `.gitattributes`에 Pi 셸/서비스 LF 보호, `.gitignore`에 새 임시 환경 제외, 패키징에 핫스팟 원문 포함을 추가했다. 원문·수정·점검 파일은 아직 커밋하지 않았다. Pi·실제 AI/SMTP·브라우저 실기는 재실행하지 않았고 새 네트워크 재부팅 성공으로 해석하지 않는다.
- **커밋 전 정리 완료:** 사용자가 불필요한 파일 삭제를 요청해 활성 프로세스가 없는 테스트 브라우저 프로필 3개, 이번 임시 runtime·합성 데이터, 이전 빈 test-runtime, 검사용 패키지·일회성 문서 수정 스크립트·빈 로그를 삭제했다. **10개 대상, 6,079개 파일, 237.96MiB**. 삭제 직후 보존 파일 **396개 해시 일치**. Git 삭제 **715개는 모두 테스트 프로필**이며 다음 전체 커밋에 삭제를 포함한다(아직 미스테이징·미커밋, 과거 이력은 유지). 최종 로그·소스 백업·PPT/PDF·render-v3·실제 data·dist는 보존했다. 문서는 기존 경로를 유지했다. `output/maintenance/2026-09-30-sync-review/commit-cleanup-*.json`을 따른다. 검사 재실행 시 의존성 환경을 다시 준비하며, 정리 때문에 앱 검사를 반복 실행하지 않았다.

## 이전 종료 기록 — 2026-09-22 다음 세션 준비·정리 완료

- **후속 시작 안내 점검:** 사용자가 `START_HERE.md` 내용 유실을 우려해 확인했다. 수정 전 SHA-256은 종료 원장의 값과 일치하여 해당 저장 이후 유실은 확인되지 않았다. 프로젝트 소개·현재 PPT 보완 순서·PC 실행 안내를 보강했다. 사용자가 PC 루트 `.venv`를 직접 삭제했고 파일시스템에서도 부재를 확인했다. 아래 ‘`.venv` 보존’은 정리 당시 상태다. `start.ps1`은 환경을 자동 생성하지 않으므로 다음 PC 앱 실행 전에 `setup.ps1`로 생성·실행 의존성 설치가 필요하다(Python 3.11 이상·패키지 다운로드 연결). PPT 검토만 할 때는 재설치하지 않는다. 이번 후속 작업은 문서만 수정하며 Pi 환경을 변경하지 않는다.
- 사용자가 PPT에 **“일단 좋아”**라고 응답한 뒤 오늘 작업 종료, 다음 LLM을 위한 문서 정리와 캐시 삭제를 요청했다. 이는 초안의 우선 수용이며 빈 캡처·수치가 채워졌거나 추가 실기가 성공했다는 뜻이 아니다. 이번 마무리에서는 새 PPT·계측·논문 작성·Pi 연결을 시작하지 않았다.
- 다음 세션 읽기 순서: **`START_HERE.md` → 이 최신 절 → `docs/SESSION_HANDOFF_2026-09-18.md` 0·6절 → `output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md`**. 기본 재개는 기존 v3 PPT 검토·캡처 보완이다. 사용자가 친구 공유·핫스팟을 선택하면 기존 초대 수락 대기 지점에서 이어간다. 이미 정한 목적·분량 위임·수업 일정을 다시 전부 묻거나 PPT를 새로 만들지 않는다.
- 현재 UI에는 물품 ID가 글자로 표시되지 않는다. 가이드의 읽기 전용 `/api/items`·`/api/items/{id}` 조회로 확인해 사진 아래 별도 캡션에 적는다. 발표용 캡처를 위해 앱 코드를 바꿀 필요는 없다. 공식 진행률·AI 성능은 실제 근거가 있을 때만 채운다.
- 사용자 승인 범위에서 **24개 대상: 캐시·합성 fixture·이전 렌더·중간 파일 2,386개, 약 188.81MiB 및 작업용 node_modules junction 1개**를 삭제했다. 외부 런타임은 그대로다. 삭제 전후 보존 파일 **364개** 해시가 일치했다. 최종 PPT·가이드·`render-v3`·원본 코드·운영 data·dist·논문·백업·검사 로그를 보존했다. `.venv`, 설치된 test-runtime, 활성 여부를 조회하지 못한 테스트 브라우저 프로필 3곳도 보존했다.
- 정리 원장: `output/maintenance/2026-09-22-session-close/cleanup-plan.json`, `cleanup-execution.json`, `SESSION_STATUS.json`. 예전 삭제 차단 기록은 과거 경과이고, 이번 삭제는 실제 완료다. 제작 당시 `FINAL_CHECKS.json`은 유지하며 정리 후 검사는 `2026-09-22-midterm-build/POST_CLEANUP_CHECKS.json`이다. 삭제된 v1/v2 렌더 비교는 보존한 해시 원장을 사용하고 최종 v3 렌더 30장을 대조한다. 새 앱 테스트나 현장 실험을 실행한 결과가 아니다.

## 제작 기록 — 2026-09-22 개발 중간보고 PPT

- 사용자가 첨부한 `프로젝트개발중간보고 목차구성.md`의 7개 대항목·34개 세부 항목을 근거로 중간보고를 제작했다. 원문은 `docs/presentation/midterm/OUTLINE_REFERENCE.md`에 보존한다. 첨부의 ‘약 6주차’보다 실제 수업 일정이 우선한다.
- 사용자는 분량을 맡겼고, 수업 일정을 제공했다. **2026-10-13(7주차) 중간보고 발표, 10-27 최종보고 연습, 11-03 최종보고**, 이후 11-10 본론·11-17 팀논문·11-24 최종논문 발표다. PPT는 교수님·수강생을 가정한 본문 27장과 보충자료 3장(16:9)으로 만들었다. 15–20분은 제작상의 출발점이며 사용자가 정한 제한 시간은 아니다.
- 최신 파일: **`output/presentation/REFOUND_PROJECT_MIDTERM_2026-09-22_v3.pptx`**. 채우는 방법과 첨부 목차 대응표는 **`output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md`**다. 표·구성도·코드·그래프는 편집 가능하다. S1 Git 이력(11쪽), S2–S4 실제 등록·이동·회수(14쪽), S5 실제 Pi 화면(15쪽)을 빈 자리로 둔다. 공식 진행률(9쪽)·정량 AI 성능(19쪽)은 근거 없이 채우지 않았다.
- 발표 작성 기준일은 **2026-09-22**다. 10월 13일까지 할 일과 최종보고 계획을 완료 실적으로 취급하지 않는다. 24쪽 27.756/13.212ms 그래프는 9월 18일 PC 합성 입력 개발 검사이며 Pi 실측·AI 정확도·종단간 지연이 아니다. 272/37/7은 과거 회귀 검사 기록이다.
- 생성 원본은 `docs/presentation/midterm/build_midterm.mjs`. 검사·렌더링은 `output/maintenance/2026-09-22-midterm-build/`에 보존한다. 기존 논문 PPT/PDF, 앱 코드·실제 데이터·배포는 보존했다. 새 앱 검사·실제 Pi·원격 AI·SMTP·논문 실험을 수행하지 않았다.
- 다음 발표 작업은 **현재 PPT 검토 → 실제 캡처와 새 실기 결과 보완 → 팀 기준 진행률·정량 결과 반영**이다. 친구 접속 대기는 계속 별개로 남아 있다. 이번 프로젝트 발표에 과거 논문용 PDF 캡처 4장 형식을 강제하지 않는다. PPT에서 수동 편집한 수정본은 생성 스크립트에 자동 반영되지 않으므로 새 이름으로 보존한다.

## 이전 요청 — 2026-09-22 시연 초기화와 새 SD 설치

- **최신 사용자 요청은 진행 상태 정리와 다음 세션 준비다.** 프로젝트 코드·시작 안내·실기 기록·논문/발표 자료의 역할을 대조하고 기존 문서를 갱신했다. 다음 요청은 **친구 공유·핫스팟 등 시연 준비 계속** 또는 **발표 PPT 제작**일 수 있다. 발표를 명시적으로 선택하면 친구 응답·남은 실기 확인을 선행 조건으로 강제하지 말고, 확인 범위를 정확히 표시한 자료를 준비한다. 새 발표의 목적·시간·청중·형식은 미정이다. 이번 기록 요청만으로 PPT·원고·계측 개발을 시작하지 않는다.
- 사용자 진입점은 `START_HERE.md`, 상세 인계는 **`docs/SESSION_HANDOFF_2026-09-18.md`(파일명 유지, 9월 22일 내용으로 갱신)**다. `docs/guides/PI_ACCEPTANCE_CHECKLIST.md`는 이제 빈 양식이 아니라 로그·사용자 보고·부분 확인·미확인을 구분한 누적 기록이다. 발표 시작점 `docs/IMPROVEMENTS.md`에는 최신 코드/검사 근거와 기존 PPTX의 용도를 연결했다. 과거 `docs/presentation/PRESENTATION.md`는 8월 16일 자료임을 명시했다.
- 이번 인계 정리는 문서와 상태 기록만 바꿨다. 앱·배포·기존 원고/PDF/PPTX는 보존하고 앱 테스트도 다시 실행하지 않는다. 배포 안의 안내 문서는 PC의 최신 인계보다 오래될 수 있다. 두 기존 9월 22일 `VALIDATION.json`의 미설치/실기 미실시 플래그는 당시 스냅샷이며, 최신 진행은 `output/maintenance/2026-09-22-network-plan/SESSION_STATUS.json`을 따른다.
- **현재 재개 지점: 친구에게 Pi 공유 초대 링크 전송 완료, 응답 대기로 중단.** 사용자가 초대 링크를 친구에게 보냈고 친구가 응답하면 나머지를 진행하겠다고 했다. `Reusable link`를 꺼도 친구의 첫 수락 이후 공유 관계는 유지된다고 설명했다. 실제 수락·친구 노트북 접속·핫스팟 연결은 아직 미확인이다. Pi의 `sudo shutdown -h now` 정상 종료를 안내했으며 실제 종료·전원 분리 완료는 아직 보고받지 않았다. 다음 세션은 **Pi 전원 켜기 → 친구가 시연 노트북 Tailscale과 같은 계정으로 초대 수락 → 친구 노트북에서 전체 HTTPS 주소 확인 → 친구 핫스팟으로 랜선 없는 부팅 시험**으로 이어간다. 설치·초대 링크 전송을 처음부터 반복시키지 않는다. 인증·공유 초대 링크는 기록하지 않는다.
- **확인된 원격 접속:** Tailscale **1.102.4** 설치·인증·Serve 백그라운드 실행과 `Tailscale access is ready`를 사용자 로그로 확인했다. PC에서 HTTPS 화면·영상 확인에 사용자가 “나와”라고 보고했다. 새 Pi 주소는 **`https://refound-pi-1.tail7a1a61.ts.net/`**이며 `-1`을 생략하지 않는다. 앱은 loopback을 유지하고 출력은 `tailnet only`이며 Funnel 비활성 검사도 통과했다.
- 재부팅·재접속 안내 뒤 사용자가 2026-09-22 18:57 KST의 `check-system.sh` 출력을 전달했다. 서비스 `active`, DB·카메라·inventory 연결, `phase=monitoring`, privacy 꺼짐, OpenAI 설정과 `Local checks passed`를 확인했다. 온도 62.3°C, `throttled=0x0`은 해당 시점 상태다.
- SSH 터널로 웹 화면과 시연 초기화 버튼을 확인한 뒤 초기화·실물 등록 절차에 사용자가 “잘 돼”, 같은 물건의 이동 시 중복 방지와 치운 뒤 회수 완료 확인에 “어 다 돼”라고 보고했다. 해당 흐름은 사용자 성공 보고이며 개별 물품·원격 AI 응답 로그를 받지 않았으므로 AI 판정 정확도나 모델별 성공을 단정하지 않는다. 초기화는 모든 물품·활동·알림·사진을 백업 없이 삭제하며 설정과 키는 유지한다.
- 사용자가 Pi의 `.env`를 편집하고 서비스를 재시작한 뒤 `check-system.sh`의 **`Local checks passed`** 출력을 전달했다(2026-09-22 18:48 KST). 서비스 `active`, DB·카메라·inventory 연결, privacy 꺼짐을 확인했다. 설정된 AI는 `openai`, 모델은 `gpt-5.6-luna`이며 **실제 원격 API 호출·물품 판정 성공 로그는 아직 미확인**이다. 앞선 로컬 웹 확인은 PC SSH 터널의 `http://127.0.0.1:18000`을 사용했으며 현재는 위 Tailscale HTTPS 주소를 확인할 단계다.
- 앞선 `check-camera.sh`에서 **OV5647 센서 인식, JPEG 촬영, 서비스 가상환경의 Picamera2 프레임 획득까지 통과**했다. 후속 종합 진단 시 온도 59.4°C, `throttled=0x0`, 저장 공간 23G 가용, 메모리 1.5Gi available이었다. 이는 단일 상태 확인이며 지속 부하 시험이나 논문 성능 결과가 아니다. 설치 뒤 SSH 연결 장애는 복구됐으며 정확한 원인은 미확인이다.
- 연결 장애 당시 읽기 전용 확인: 사용자 PC Ethernet interface 3은 `192.168.0.2`, gateway `192.168.0.1`이었다. 이전 Pi link-local 주소 `fe80::e65f:1ff:feea:ed3b%3`에 ping 2회가 timeout/unreachable이었으나 원인을 확정하는 근거는 아니다. 이 진단을 현재도 연결 불가라는 뜻으로 취급하지 않는다.
- **최신 네트워크 계획:** 집 공유기 LAN 포트에 Pi를 랜선으로 연결하고 사용자 PC로 설치한다. Imager에는 친구의 **안드로이드 핫스팟**을 미리 저장한다. Pi는 사용자 본인 Tailscale 소유로 두고 실제 시연 노트북에 로그인된 **친구 계정에 Pi 한 대만 공유**한다. 친구가 같은 계정으로 공유를 수락하면 전체 Serve HTTPS 주소로 접속한다. 친구도 앱의 편집·초기화 등 관리 권한을 갖는다. 기존 문서의 ‘외부 장치 공유 금지/같은 tailnet만 가능’은 이 계획과 공식 지원 범위에 맞게 수정했다. 안내는 `docs/guides/SCHOOL_DEMO_GUIDE.md` 1-5절이다.
- 사용자는 시연 시간에만 **비밀번호 없는 핫스팟**을 쓰는 방안도 제안했고 친구 폰이 안드로이드임을 확인했다. 해당 폰에서 보안 없음/None을 지원하면 Imager의 공개 네트워크와 정확한 SSID로 설정 가능하다. 비밀번호 사용을 권장했지만 실제 SSID·보안 방식은 아직 확정하지 않았다. 비밀번호는 채팅에 요청하지 않는다. **랜선을 뺀 Pi 부팅과 친구 노트북 접속은 아직 미검증**이다.
- **최신 설치 진행: 앱 설치·카메라 검사·기본 실물 흐름과 재부팅 후 진단 확인.** 사용자가 새 SD 부팅·SSH 접속·Pi 측 패키지 SHA-256 `OK`에 이어 `install.sh`의 **`Installation complete` 및 새 서비스 PID 7147의 `http://127.0.0.1:8000` 응답 성공** 출력을 전달했다. 자동 시작 서비스가 등록됐고 후속 카메라·종합 진단도 통과했다. 초기화·실물 등록·이동·회수와 재부팅 후 진단은 위 사용자 보고를 따른다. 세부 편집·기한·메일·친구 핫스팟 연결은 아직 확인하지 않았다. 앱은 loopback을 유지하며 Tailscale Serve로 PC 접속을 확인했고 친구에게 장치 공유 초대 링크를 전송했다. 친구 수락은 대기 중이다.
- **새 Pi에서 사용자 출력으로 확인한 환경:** Debian GNU/Linux 13 Trixie / `DEBIAN_VERSION_FULL=13.7`, `aarch64`, 커널 `6.18.50+rpt-rpi-v8`, 시각 `2026-09-22 18:25:40 KST`. 서비스 가상환경 Python **3.13.5**, NumPy **2.2.4**, OpenCV **4.10.0**, Picamera2 **0.3.37**, FastAPI **0.141.1**, Pydantic **2.13.5**, Uvicorn **0.53.0**, HTTPX **0.28.1** import 통과. 이는 실제 촬영·AI 성공을 의미하지 않는다. 배포 SHA-256은 `92007237f6cf4ee5fdeb2e099961153893012e8f9c0ad8f1be7596c2127cf4ae`. 관련 패키지 검사는 `output/maintenance/2026-09-22-network-plan/`이다. 재설치 SSH 키 경고는 해당 주소의 이전 기록만 갱신해 해결했다.
- 사용자는 차근차근 진행하기를 원한다. 기존 Pi 4 2GB·CSI 카메라 등 나머지 장비는 이전 성공 때와 같다고 설명했다. 초기의 ‘새 카드만 준비, OS 미기록’ 상태는 위 사용자 완료 보고로 갱신됐으므로 OS 기록을 다시 시키지 않는다.
- 대시보드 상단에 **시연 초기화** 버튼을 추가했다. 버튼 → 확인창의 **백업 없이 초기화** 한 번으로 실행하며 문구 입력은 없다. 먼저 물건을 치워야 한다. 실제 카메라 등록까지 포함한 **모든** 물품·활동·알림·캡처를 삭제하고 기준 화면을 다시 잡는다. 설정·API 키·기존 백업은 보존한다. 삭제한 시연 기록은 되돌릴 수 없다.
- 기존 설정 → 시스템 초기화는 자동 백업·확인 문구 입력 방식을 유지한다. API `/api/maintenance/reset`는 기본 `mode=backup`, 명시적 `mode=quick`일 때 확인값 `시연 초기화`를 요구한다. 두 경로는 같은 작업 종료·잠금·경로 검사·감시 재개 절차를 사용한다. 느린 worker 때문에 취소된 삭제는 자동 재시도하지 않는다.
- 변경 전 소스와 검증 기록은 `output/maintenance/2026-09-22-quick-reset/`에 있다. 테스트는 임시 DB·합성 카메라·AI·SMTP를 사용한다. 기존 알림 검사에 실시간 시계 의존성이 있어 해당 검사에서만 시계를 고정했다. 운영 알림 코드는 변경하지 않았다.
- 최종 검증: Python **272개**, Node **37개**, 실제 Chromium **7개** 통과. 1440/1024/390/320px에서 버튼·확인·취소, 실제 임시 DB 삭제·설정 보존·다음 등록과 기존 백업 초기화 진입을 확인했다. 컴파일·JS 문법·배포 내용 검사도 통과했다. 이전 실패 로그는 경과 기록이며 최종 요약은 같은 폴더 `VALIDATION.json`이다. 실제 Pi·원격 AI·SMTP 수신 검증은 아니다.
- `dist/refound-pi.tar.gz`와 `.sha256`를 이번 버튼이 포함된 최신 기본 배포 파일로 갱신했다. PC의 실제 `.env`·DB·사진은 포함하지 않는다. 사용자용 시작점과 설치 안내·실기 확인표도 갱신했다. 논문·발표 파일은 변경하지 않았다.

## 사용자용 문서 탐색·정리

- **최종 정리 완료:** 사용자가 수정된 스크립트를 직접 실행했다. 후속 파일시스템 검사에서 대상 18개 폴더가 모두 없어졌고, 보존 대상 121개 파일의 해시가 그대로임을 확인했다. 삭제 대상은 캐시·합성 테스트 데이터·빈 tmp의 1,091개 파일(약 4.1MiB)이었다. 아래 차단·오류·재실행 대기 설명은 이전 경과이며 현재 미완료 상태가 아니다. `workspace-cleanup.json`의 `user_execution_verification.status=complete`가 최종 상태다.
- 사용자는 파일과 안내가 복잡하다고 했으며 목적별 시작점과 불필요한 캐시 정리를 요청했다. 사용자에게는 루트 `START_HERE.md`부터 안내한다. 새 안내 문서를 계속 늘리기보다 이 시작점과 각 분야의 기존 안내를 갱신한다.
- 설치·실물 테스트는 `docs/guides/FRESH_SD_START.md`, 논문은 `docs/paper/README.md`, 개선점 설명·발표는 `docs/IMPROVEMENTS.md`다. 새 개선점 발표 PPTX는 아직 없다.
- 논문 안내에 9월 16일 원고와 9월 18일 구현의 차이를 표시했다. privacy 부팅 복원은 이미 구현됐으므로 다시 미구현으로 취급하지 않는다.
- 캐시 7곳과 빈 `tmp` 폴더 삭제는 자동 승인 검토가 `blocked by policy`로 거절하여 **실행되지 않았다**. 이전 삭제 거절 대상도 다시 시도하지 않았다. 논문·과거 팀 산출물·실제 데이터·검증 증거는 보존했다. 이번 탐색 정리와 삭제 차단 기록은 `output/maintenance/2026-09-18-fresh-sd/workspace-cleanup.json`이다. 다음 세션에서 다른 명령으로 삭제를 우회하지 않는다.
- 이후 사용자가 삭제 재시도를 명시적으로 요청했다. 캐시 8곳·합성 브라우저 fixture 9곳·빈 `tmp`를 다시 검증했으나 삭제 명령은 동일하게 차단됐고 실제 삭제는 0개다. `cleanup-retry-plan.json`에 대상, `cleanup-protected-hashes.json`에 보존 파일 해시를 기록했다. 사용자 직접 실행용 `cleanup-temporary-files.ps1`은 같은 maintenance 폴더에 있으며 문법만 검사하고 실행하지 않았다. 이전 거절 이력은 `workspace-cleanup.json`에 보존한다.
- 사용자 실행에서 Windows PowerShell 5.1의 JSON 배열이 중첩되어 `Join-Path`에 배열이 전달되는 오류가 발생했다. 스크립트의 바깥 `@(...)`를 제거하고 항목별 경로 타입 검사를 추가했다. 수정 후 실제 `powershell.exe ... -WhatIf`로 18개 대상의 미리보기를 완료했다(exit 0). 에이전트가 실제 삭제를 수행한 것은 아니며, 사용자 재실행 결과는 아직 미확인이다.

## 9월 18일 재설치 준비 당시 기록 — 현재 진행은 상단 우선

- **이전 Pi 실습은 성공했으나 microSD가 고장 났다.** 아래는 9월 18일 준비 당시 기록이다. 당시에는 새 SD 기록이나 Pi 설치·실험을 수행하지 않았으며, 이후 9월 22일 설치와 실기 결과는 상단에 갱신했다.
- 사용자용 시작점은 `docs/guides/FRESH_SD_START.md`, 실기 양식은 `docs/guides/PI_ACCEPTANCE_CHECKLIST.md`다. 최신 기본 배포 파일은 `dist/refound-pi.tar.gz`와 `.sha256`이며 날짜가 붙은 live-flow 파일은 이전 보관본이다.
- 다음 세션은 **설치 진행 위치 확인 → 실물 기능·재부팅 시험 → 실패 수정 → 안정되면 논문 또는 개선점 발표 자료** 순서다. 사용자 선택 전 계측 개발이나 원고·슬라이드 작성을 자동으로 시작하지 않는다.
- 상세 인계는 `docs/SESSION_HANDOFF_2026-09-18.md`를 먼저 읽는다. 이전 논문·PPTX를 보존했고, 현재 코드와 원고가 다시 동기화됐다고 주장하지 않는다.
- 설치기는 서비스 사용자 환경에서 라이브러리를 import 검사한다. `bash /opt/refound/scripts/raspberry-pi/check-system.sh`는 읽기 전용 종합 진단이다. 진단 통과는 실제 AI 분류나 메일 수신 성공을 뜻하지 않는다.
- 이번 배포·진단 검사 10개와 이를 포함한 전체 Python **268개**가 통과했다. 기록은 `output/maintenance/2026-09-18-fresh-sd/`다. Node33/브라우저16은 앞선 앱 개선 시점의 검사이며 이번에 재실행하지 않았다. 실제 Pi 검사는 아직 수행하지 않았다.

## 최신 코드 개선 — 2026-09-18

- **최신 사용자 요구: 내장 시연 버튼이 아니라 실제 카메라·관리 기능 전체를 매끄럽게 사용.** `docs/LIVE_FLOW_REVIEW_2026-09-18.md`에 후속 점검을 기록했다. 영상·사진 연결 자동 복구, 목록 오류 상태 보존, AI 요청 스키마·응답 완료 검사, DB health, Pi 재설치 설정 보존·실제 재시작을 보완했다. 소스 백업과 검사 로그는 `output/maintenance/2026-09-18-live-flow-review/`다.
- 앞선 앱 개선 시점 전체 검사: Python **264개**, Node **33개** 통과. 합성 연속 영상의 실제 capture/dispatcher·SQLite·executor·API 연결 3개, 편집·만료·알림·연장·폐기·복원 연속 검사 3개가 포함된다. 실제 Pi·원격 AI·SMTP 수신 검증이나 논문 실측을 수행한 것은 아니다.
- 실제 Chromium에서도 데스크톱 **12개**, 모바일 **4개** 흐름을 임시 데이터로 검사했다. 저장 성공 후 배경 갱신 중 다음 조작을 무시하던 잠금과 다른 물품의 늦은409 오염을 수정했다. 모바일 숨김 필터 라벨의 위치 기준을 고쳐 390px 화면이423px로 늘어나던 문제도 해결했다. 최종 요약은 같은 백업 폴더의 `browser-validation-summary.json`이며 이전 실패 원장도 보존한다.
- Pi 배포 파일 `dist/refound-pi-2026-09-18-live-flow.tar.gz`와 SHA-256 파일을 생성했다. 실제 운영 데이터·키는 포함하지 않으며 Pi에 설치한 것은 아니다.
- 기본 OpenAI 모델에는 낮은 추론 강도와 2048 출력 토큰 상한을 적용한다. OpenAI strict schema/Gemini JSON schema와 완료 상태를 확인하며 불완전·거절 응답은 확인 필요 흐름으로 보존한다. API 키 오류 문구는 길이를 자르기 전에 마스킹한다. 화면의 `키 설정됨`은 실제 AI 연결 성공을 뜻하지 않는다.
- Pi 재설치는 기존 runtime 모드·주소·포트를 보존하고 새 서비스 PID/health를 검사한다. 종료 대기는 300초이며 학교·현장 Wi-Fi 가이드를 패키지에 포함한다. 아래 **240/25개**는 직전 구조 개선 시점의 과거 검사 기록이다.

- **후속 요청: 전제·구조까지 전면 검토 후 개선.** 최신 설계는 `docs/ARCHITECTURE_REVIEW_2026-09-18.md`를 따른다. 앞선 앱/영상 개선 위에 사건 처리 확인, 독립 검토 상태, 전체 DB 페이지 조회, 시연 데이터 격리를 추가했다. 백업은 `output/maintenance/2026-09-18-architecture-review/source-before.zip`이다.
- 최종 검증은 Python **240개**, Node **25개** 통과 및 compileall/JS 문법 검사 통과다. 같은 설정의 단일 패스 성능 보존 검사에서 정적 장면13.809→13.791ms/처리 프레임, pair added86.864→87.731ms였고 사건·bbox·confidence·4개JPEG hash가 같았다. 이는 Pi 실측이 아니다. 상세 로그·최종해시는 같은 백업 폴더에 있다.
- 비전은 로컬 DB 반영 확인 전까지 장면 기준 갱신을 보류한다. 미리보기는 계속하며 사건 UUID/`source_event_id`와 `tracking_revision`으로 중복·오래된 물리 관찰을 방지한다. 진단 queue와 사건 queue를 분리했고 DB 목록 실패도 빈 장면으로 취급하지 않는다.
- `review_status=pending/needs_review/confirmed/dismissed`와 `review_reason`이 업무 상태의 기준이다. `provider` 접미사는 일부 호환 표현만 남았다. 강한 AI 거절도 삭제하지 않는다. 관리자의 확인·감지 제외·복원은 명시적이며 제외한 사진·이력도 보존한다.
- `source_kind=camera/demo/manual`은 불변 출처다. 시연 회수는 시연 물품만 대상으로 하며 편집된 시연 물품도 카메라 추적에서 제외한다. 신규 시연 데이터에는 가상 bbox를 저장하지 않는다.
- `/api/items`는 기본48·최대100의 서버 페이지 조회이며 total/limit/offset을 반환한다. 상세 편집의 `expected_updated_at` 충돌은409, `confirm_review=true`일 때만 명시적 검토 완료다. 구DB의 additive migration은 임시DB에서 검증했으며 실제 운영DB에는 이번 작업 중 적용하지 않았다.
- 아래 앱·영상 개선 기록은 같은 날 앞서 수행한 작업이다. 논문·발표 산출물은 변경하지 않았으며 새 운영 진단은 영속 실험 원장을 대신하지 않는다.

- **추가 요청: 정지 영상 울렁거림과 Pi 4 2GB 성능 개선.** 사용자는 Pi CSI와 PC USB 양쪽에서 영상 자체의 미세한 움직임·밝기 변화를 본 것 같다고 설명했다. 감지용 정합 영상을 그대로 미리보기에 쓰면서 생기는 인위적 움직임을 합성 정지 장면에서 재현하고, 원본 영상 표시와 박스 좌표 투영을 분리했다.
- 프레임 선택을 deadline 기반으로 바꿔 10fps 입력·7fps 분석이 기존 방식에서 5fps로 낮아지던 문제를 수정했다. 기준 grayscale 캐시, 무변화 조기 종료, 중복 정합 제거와 Lab 차분 연산을 개선했다. Pi 기본 미리보기는 800px/5fps이며 촬영·분석과 증거 품질은 기존 설정을 사용한다.
- `camera_mains_frequency_hz=0/50/60`을 추가했다. 기본 0은 드라이버 설정 유지, 50/60은 지원되는 CSI 카메라에서만 적용한다. 자동 초점·노출·화이트밸런스를 강제로 잠그지 않는다. 센서 정보와 실제 처리 FPS/시간은 카메라 화면에서 확인한다.
- 앞선 영상 개선 시점 검증: Python **202개**, Node **13개** 통과. 데스크톱 합성 벤치마크·재현 조건·하드웨어 미확인 범위는 `docs/VISION_REVIEW_2026-09-18.md`를 따른다. 합성 벤치마크는 논문 실측값이 아니다. 해당 변경 전 백업은 `output/maintenance/2026-09-18-vision-review/source-before.zip`이다.

- 사용자가 논문 실험 전에 앱 코드를 전체 검토하고 적극적으로 개선하도록 요청했다. 이번 우선순위는 앱 안정성·데이터 보존·관리 화면 오류 수정이다.
- 카메라 종료·재연결, 개인정보 보호 설정 복원, AI 지연 응답과 관리자 수정 충돌, 재시작 후 분석 대기 복구, 전체 활성 물품 조회, 알림 발송 동시성, 화면 갱신·설정 입력을 개선했다. 상세 내용과 검증 범위는 `docs/APP_REVIEW_2026-09-18.md`를 따른다.
- `VisionMonitor.stop()`과 `ExpirationScheduler.stop()`은 완전 종료 여부를 bool로 반환한다. 초기화는 종료 실패 시 409로 취소하고, 작업이 끝나면 별도 복구 worker가 감시를 재개한다. 데이터 초기화를 자동 재시도하지 않는다.
- `added` 분석에도 최초 추적 signature를 전달한다. 분석 대기·호출 중 이동/기록 변경이 있었다면 늦은 부정 판정으로 현재 물품을 삭제하지 않는다.
- 부팅 시 저장된 privacy 설정을 카메라 시작 전에 적용한다. 이미 접수된 callback/VLM 작업까지 취소하는 기능은 아니다.
- 원본 소스 백업은 `output/maintenance/2026-09-18-app-review/source-before.zip`이다. 실제 운영 DB·촬영 자료·API 키를 수정하거나 Pi/유료 API/SMTP 실험을 수행하지 않았다.
- 기존 논문/PDF/PPTX는 이번 구현 변경에 맞춰 다시 작성하지 않았다. 논문 실험 전 구현 기준일을 갱신하고, 이전 원고의 privacy·AI 지연 응답 설명을 최신 코드와 대조한다. 아래 2026-09-16 문서 작업 내역은 과거 기록이다.

## 0. 최신 원고·발표 작업 상태 — 2026-09-16

- **9월 16일 당시 마지막 요청은 대화 백업과 임시 파일 정리였다.** 당시 결정과 원고·발표 상태는 [대화 인계 요약](docs/paper/SESSION_HANDOFF_2026-09-16.md)을 읽는다. 현재 재개 순서는 위의 새 SD 지침을 따른다.
- 최신 사용자 수정 요청: 슬라이드 본문 재조판을 원하지 않는다. **PDF 각 페이지를 그대로 캡처해 왼쪽에 넣고, 오른쪽에 간단 설명 몇 개를 배치**하는 방식으로 변경했다. 최신 발표본은 `output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx` 4장(4:3)이다. 아래 6장 버전은 이전 시안이다.
- 성능 수치를 채우는 쉬운 절차와 역할 분담은 `docs/paper/PERFORMANCE_MEASUREMENT_START.md`에 추가했다. 이번 수정에서도 실제 성능값이나 새 계측 코드를 만들지는 않았다.

- 사용자가 전체 논문 개정과 초반 발표 슬라이드 작성을 요청하여 실측 전 초안과 발표 자료를 작성했다. 대본은 원하지 않는다. 발표는 제목·요약·서론·이론적 배경과 관련 연구까지 2–4쪽, 약 5분을 기준으로 한다.
- 전체 원고 `docs/paper/PAPER_DRAFT_JDCS.md`와 발표 전반부를 동기화했다. 참고문헌 17개, 고유 입력 항목 297종, 표 13개, 수식 6개, SVG 구조도 4개다. 기존 26문헌·321항목 초안은 `docs/paper/archive/2026-09-16-before-full-revision/`에 보존했다.
- 읽기용 전체 PDF: `output/pdf/REFOUND_FULL_MANUSCRIPT.pdf` 19쪽. 발표용 PDF: `output/pdf/RESEARCH_FRONT_MATTER.pdf` 4쪽. 최신 발표 PPTX: `output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx` 4장. `REFOUND_EARLY_PAPER_FINAL.pptx` 6장은 이전 시안으로만 보존한다.
- 전체 논문은 실측 전 원고이며 결과 장은 입력 틀이다. 실제 성능 수치 또는 현장 실험 결과는 생성하지 않았다. 자세한 완료·대기·검증 범위는 `docs/paper/REVISION_STATUS.md`를 따른다.
- 2026-09-16 작업은 문서·그림·발표 작성이며 애플리케이션 코드를 바꾸지 않았다. 아래 136개 테스트 통과는 과거 인계 기록이며 이번 재실행 결과가 아니다.
- `manuscript/revise_manuscript.py`는 보관본에서 이번 개정을 재현한다. 이후 수동 수정 또는 실측 입력 후 실행하면 새 편집을 덮어쓰므로 실행하지 않는다. 현재 원고에서 PDF만 재생성할 때는 `manuscript/build_manuscript.py`를 쓴다.
- 생성 스크립트의 전체 경로와 런타임은 대화 인계 요약을 따른다. 최신 PPTX 입력인 `docs/paper/briefing/pdf_pages/`와 그림 SVG, 실제 `data/captures/`, 원고 보관본은 유지한다. 임시 렌더링·중간 PPTX·캐시 정리 내역과 보존한 검사 기록은 `docs/paper/validation/`에 둔다. 외부 런타임으로 향하는 `node_modules` junction은 연결만 제거한다.
- `manuscript/validate_artifacts.py`와 `FINAL_VALIDATION.json`은 전체·전반부 원고와 **이전 6장 시안** 검사다. 최신 4장 검사 기록은 `briefing/PDF_CAPTURE_SLIDES_CHECK.json` 및 `validation/PDF_CAPTURE_SLIDES.validation.json`이다. 과거 시각 검사와 이번 백업·정리 후 무결성 검사를 구분한다.

## 1. 사용자의 현재 목표

- 고장 난 microSD를 교체한 새 설치에서 기본 실물 동작·재부팅·본인 PC Tailscale 접속을 확인했고, 9월 29일 Windows 핫스팟·SSH 웹 접속과 OpenAI 동작 성공 보고가 추가됐다. 다음에는 새 네트워크의 전원 재인가·자동 연결 시험 또는 기존 발표 PPT 보완을 진행한다. 논문은 별도 선택한 경우에 진행한다.
- 이 캡스톤 프로젝트를 현재 코드와 루트 `README.md` 기준으로 정확히 이해한다.
- 프로젝트를 기반으로 국내 학술지 투고용 논문을 작성한다.
- 1순위 투고 목표는 디지털콘텐츠학회논문지(JDCS)다.
- 실천공학교육논문지(JPEE)는 캡스톤 교육과정과 학습성과 평가를 추가할 경우의 2순위다.
- 9월 22일 새 Pi의 OS·커널·OV5647 센서·런타임과 실기 확인 결과를 기록했다. 전원·냉각·촬영 조건·장시간 실행 기록과 논문용 정량 결과는 아직 없다.
- 질문은 해도 되지만, 안전하고 합리적인 범위에서는 먼저 진행한 뒤 구체적인 결과로 보고하는 방식을 선호한다.
- 다른 AI는 코드 문맥이 없으므로, 당분간 구현 계측·실험·결과 해석·논문 수정은 이 저장소 문맥에서 계속하고 다른 AI는 독립 검토나 문장 교정에 활용하는 방향으로 정리했다.

## 2. 사실의 우선순위

1. 현재 실행 코드
2. 루트 `README.md`
3. 실제 실험 원장과 장비 기록
4. `docs/paper/`의 논문 준비 문서
5. 과거 기획서·발표자료·회의록

과거 계획에는 Raspberry Pi 5, YOLOv8, 커스텀 CNN, 로컬 LLM, AWS RDS, Firebase, AR, 4인 팀 등 현재 구현과 충돌하는 내용이 있다. 논문의 구현 사실로 사용하지 않는다.

## 3. 프로젝트와 논문 방향

- 프로젝트명: Re:Found 분실물 자동 추론 및 시각화 관리 시스템
- 장치: Raspberry Pi 4 Model B 2GB와 CSI 카메라
- 서비스: Python, OpenCV, Picamera2, FastAPI, SQLite WAL, vanilla HTML/CSS/JavaScript
- 핵심 방향: 모든 프레임에 무거운 객체탐지 모델을 실행하는 연구가 아니다.
- 로컬 역할: 움직임 종료와 장면 안정화를 확인한 뒤 기하 정합, 조명 보정, 지속 경계 억제, 변화 후보와 활성 물품 대응을 통해 사건을 선별한다.
- 사건: `added`, `moved`, `removed`, `verify_removed`
- 외부 VLM 역할: `added`와 모호한 제거인 `verify_removed`에만 전체 장면 전후 및 후보 crop 전후를 최대 4장 전송해 의미를 보완한다.
- 운영 역할: 물품 등록, 보관 기한, 알림, 회수, 폐기, 복원과 활동 이력을 연결한다.
- 논문의 성격: 새로운 학습 모델 제안이 아니라 저사양 엣지 사건 감지, 선택적 멀티모달 추론 및 운영 생명주기를 통합한 시스템 설계·구현·실증 연구다.
- 권장 제목: `저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템`

## 4. 반드시 지킬 코드 기반 주장 경계

- 현재 저장소에는 현장 사건 정확도, 지연, FPS, CPU, RAM, 온도, 전력, VLM 정확도·비용의 논문용 정량 결과가 없다. 값을 추측하거나 만들지 않는다.
- 자동화 테스트 통과는 소프트웨어 회귀 검증이지 현장 인식 정확도가 아니다.
- 안정 이미지 pair runner는 `_detect_changes()` 코어만 호출한다. 캡처, 움직임/안정 상태기계, callback, DB, VLM과 종단간 지연을 평가하지 않는다.
- `plain` profile은 순수 grayscale absolute difference가 아니다. Lab·contour·그림자·사건·활성 물품 로직을 공유하는 단계적 ablation이다.
- 안정 이미지 pair로 FP/hour나 실제 DB ID 중복 방지를 주장하지 않는다. FP/hour는 연속 none 감시의 유효 wall-clock으로 계산한다.
- `global_change_suppressed`는 물품 `ChangeEvent`가 아니라 내부 억제 후 발생하는 진단 결과다.
- 후보 crop JPEG 품질은 88, full-scene 품질은 72다.
- 외부 모델의 양쪽 경로에 JSON schema를 요청하며 OpenAI는 strict 모드다. 응답 완료 여부와 로컬 의미 검사를 추가했지만, 사용자 지정 모델의 schema 지원·계정 권한·실제 판정 정확도는 별도 검증 대상이다.
- 초기 활성 물품 대응은 bbox overlap을 사용한다. 중심 거리와 크기는 떨어진 후보의 relocation 검사에서 추가로 사용한다.
- callback의 로컬 반영 확인 후 기준 장면을 전진한다. queue 포화·DB 실패는 기준을 유지하고 실패 사건만 재시도한다. 강제 종료 전 아직 미접수인 장면은 영속 복구하지 않는다.
- 이미 생성된 provisional 행은 API key 부재, timeout, parse 실패, 낮은 신뢰도 또는 원격 작업 queue 포화 후에도 보존된다.
- `added`의 낮은 신뢰도·강한 거절 모두 확인 필요 상태로 남는다. `verify_removed`의 불확실·오류·queue 포화도 물품의 검토 상태를 기록하고 추적을 유지한다.
- `added` 응답은 명시적 pending 상태일 때만 적용한다. `verify_removed`는 물리 추적 signature가 달라지면 적용을 취소한다. 이름·분류·기한·stored↔due 전환은 물리 revision을 바꾸지 않는다.
- privacy를 켜면 capture 분석과 미처리 장면의 후속 callback·재시도를 취소한다. 이미 성공한 DB 반영, 진행 중 callback 한 건, 접수된 VLM 작업은 남을 수 있다. 취소된 미반영 사건은 상태·로그로 보고한다.
- 2026-09-18 개선으로 재시작 시 DB의 privacy 설정을 `VisionMonitor` 시작 전에 재적용한다.
- `recovered`는 시스템에서 화면상 사라짐을 뜻하는 운영 상태이며 실제 소유자에게 물리적으로 반환됐음을 증명하지 않는다.
- valuable/general/food의 90/60/1일은 법정 기한이 아니라 현재 애플리케이션 기본 운영 정책이다.

## 5. 완성된 논문 준비 산출물

- `docs/paper/PAPER_DRAFT_JDCS.md`: 국·영문 초록부터 결론과 참고문헌까지의 JDCS 전체 초안
- `docs/paper/RESULTS_FILL_SHEET.md`: 초안의 모든 실측 placeholder 정의와 원천·우선순위
- `docs/paper/PAPER_AI_HANDOFF.md`: 다른 AI에 전달할 코드 사실, 논지, 금지선과 작성 프롬프트
- `docs/paper/VENUE_AND_RELATED_WORK_STRATEGY.md`: JDCS/JPEE 선택과 선행연구 전략
- `docs/paper/EXPERIMENT_GUIDE.md`: 데이터 스키마, 실행, 지표, 통계와 해석 경계
- `docs/paper/REFERENCES.bib`: 국내외 출발 참고문헌
- `docs/paper/README.md`: 논문 패킷의 진입점과 사용 순서
- `docs/paper/VISION_PAIR_MANIFEST_TEMPLATE.csv`
- `docs/paper/EXPERIMENT_RECORD_TEMPLATE.csv`

다른 AI에 전달할 최소 묶음은 `PAPER_DRAFT_JDCS.md`, `RESULTS_FILL_SHEET.md`, `PAPER_AI_HANDOFF.md`, `EXPERIMENT_GUIDE.md`, `VENUE_AND_RELATED_WORK_STRATEGY.md`다. 실제 실험 후에는 원시·요약 CSV도 함께 전달한다.

## 6. 현재 검증 상태

- 논문 초안과 결과 입력표의 고유 placeholder 297종이 양방향으로 정확히 일치한다.
- 초안 참고문헌은 1–17번이 연속이고 본문 첫 인용 순서와 일치한다.
- `REFERENCES.bib`에는 중복 없는 28개 key가 있고 중괄호 수가 일치한다.
- 표는 1–13, 그림은 1–4, 알고리즘은 1번까지 연속이다.
- 그림 캡션은 그림 placeholder 아래로 배치했다.
- 국문 초록은 현재 공백 제외 434자, 영문 초록은 185단어다. 실측 결과를 반영한 뒤 분량을 다시 확인한다.
- 과거 인계 기록: `python -m unittest discover -s tests -q` 136개 테스트 통과. 이번 문서·백업 작업의 재실행 결과가 아니다.
- 과거 인계 기록: `python -m compileall -q app experiments` 통과. 현재 실행 환경의 의존성을 확인하고 필요할 때 재검증한다.
- 작업공간은 Git checkout이 아닐 수 있으므로 Git 명령 성공을 전제로 하지 않는다.

## 7. 논문 초안의 현재 상태

- 초안은 실험값 입력 전의 전체 골격이며 투고 가능한 최종본은 아니다.
- 이중 대괄호 `[[...]]`는 실제 측정이나 최종 확인 후에만 교체한다.
- 성능 결과가 가설과 다르면 가설에 맞추지 말고 초록·결론·기여 표현을 결과에 맞춘다.
- 본문 분량은 누락 방지를 위해 길게 작성했다. 최종 JDCS HWP 조판에서는 약 25–30% 줄이고 표 3·4, 표 9·12·13, 그림 1·2의 통합을 검토한다.
- 표 7의 두 panel은 하나의 복합 표로 조판한다.
- 7열인 VLM 표 11은 전폭 배치하거나 action 성능과 운영 비용 표로 나눈다.
- 그림 1–4의 SVG 처리 구조도는 `docs/paper/manuscript/figures/`에 완성했다. 실제 촬영·마스크·실패 사례 시각화는 실험 후 추가하고 비식별화한다.
- 현 참고문헌 [3]은 확인된 국문 서지를 사용한다. 공식 영문 서지 또는 국문 표기 허용 여부를 최종 제출 전에 확인한다. 과거 [7], [21]은 현 원고 인용 목록에서 제외했다.

## 8. 고정한 실험 논리

- `D_pair`: 안정 전후 이미지 쌍. detector core의 단계적 nuisance-defense ablation 전용
- `D_stream`: 연속 replay 또는 실제 camera episode. 상태기계, 사건 종류, ID, FP/hour, 종단간 지연과 DB 결과 평가
- `D_vlm`: 같은 사건 증거로 V1–V4를 paired 비교. 단일 provider/model, auto fallback off
- `D_fault`: DB 실패, timeout, malformed JSON, queue 포화, stale 응답과 재시작을 통제 주입
- moved의 GT bbox는 이동 후 위치이고, 이전 위치·ID는 `active_bbox`, `active_item_id`로 보존한다.
- 로컬 확정 사건 평가에서 `verify_removed`를 removed TP로 세지 않는다. 제거 후보 recall과 referral을 따로 보고, VLM 이후 final stage를 재채점한다.
- IoU 0.30을 주 기준으로 하고 0.50 민감도 분석을 함께 한다.
- `action_end_at`은 물품 또는 조작하는 손의 마지막 물리적 접촉이 끝나고 최종 상태에 머물기 시작한 첫 frame이다.
- recording session을 주 bootstrap cluster로 고정하고 동일 physical item은 development/final 사이에 걸치지 않게 group split한다.
- FP/hour는 Poisson exact CI와 run-block bootstrap을 보고한다.
- McNemar는 F1에 직접 적용하지 않고 episode 전체 정답 여부의 paired binary endpoint에만 적용하며 Holm 보정한다.
- 지연은 matched TP 조건부 분포이므로 N, recall과 timestamp 결측률을 함께 보고한다.
- VLM exact action은 decisive GT-added/GT-removed에서 uncertain을 오답으로 처리한다. non-removal/retain은 recover/retain 운영 결정으로 따로 평가한다.
- logical VLM job, provider HTTP attempt와 성공 응답을 구분한다.
- 종단간 업무 성공률은 added/moved/removed별 값과 macro를 함께 보고한다.

## 9. 필수 비교군

같은 `D_stream` replay에서 아래를 비교한다.

- B0: 순수 grayscale absolute difference
- B1: 제안 코어에서 settle/stable 상태기계를 제거한 구성
- B2: OpenCV MOG2
- P1: Re:Found 전체 로컬 pipeline

B0–B2의 공통 FPS, warm-up, 후보 병합 시간창, foreground→사건 adapter, 참조 갱신 규칙과 MOG2 파라미터를 개발 세트에서 먼저 고정한다. 이것이 정의되기 전에는 세 사건 종류의 Macro-F1 비교를 만들지 않는다.

## 10. 다음 재개 지점

현재 시연 준비의 재개 지점은 **Windows 핫스팟의 자동 연결 설정 확인·전원 재인가·무선 단독 복귀 시험**이다. 사용자가 발표 PPT를 선택하면 `docs/IMPROVEMENTS.md`부터 시작한다. 아래는 **논문용 정량 실험을 명시적으로 선택했을 때만** 수행할 대기 작업이다.

1. 실제 `VisionMonitor`의 motion 시작, action 종료, stable 확정, local callback, provisional DB와 final commit timestamp를 영속 원장에 추가한다.
2. VLM logical job ID, provider attempt, 성공 여부, model ID, prompt hash, 직렬화 payload byte, token/usage/cost와 request/response timestamp를 기록한다.
3. capture read 실패, scheduler skip, change callback drop, diagnostic callback drop과 reconnect 시간을 분리 계측한다.
4. privacy 설정의 부팅 동기화는 2026-09-18 구현·회귀 검증 완료. 실제 Pi 재시작에서도 확인한다.
5. B0/B1/B2 공통 replay runner와 fault-injection runner를 구현한다.
6. `EXPERIMENT_GUIDE.md` 기준 20–50건 파일럿으로 촬영·라벨·threshold protocol을 고정한다.
7. 본 실험을 `D_pair`, `D_stream`, `D_vlm`, `D_fault`로 분리해 수행한다.
8. CSV를 검증·집계하고 `RESULTS_FILL_SHEET.md`와 초안의 placeholder를 실제 값으로 교체한다.
9. 결과에 맞춰 초록·논의·결론을 다시 쓰고 그림을 제작한다.
10. 저자 식별정보를 제거한 심사용 JDCS HWP 원고로 옮기고 최신 투고 규정을 제출 당일 재확인한다.

사용자가 “계속 진행”이라고만 하면 최신 종료 기록에 따라 **기존 중간보고 PPT 검토·캡처 보완**부터 이어받는다. 시연·핫스팟을 선택하면 최신 Windows 핫스팟 백업의 8절에서 이어간다. Tailscale 공유를 별도로 선택할 때만 기존 친구 초대 수락 여부를 확인한다. 발표 목적과 수업 일정은 이미 정했으므로 반복 확인하지 않는다. 완료한 설치를 반복하거나 위 계측 1번부터 자동 실행하지 않는다.

## 11. 재검증 명령

```powershell
python -m unittest discover -s tests -q
python -m compileall -q app experiments
```

초안과 결과 입력표의 placeholder 정합성은 두 파일에서 `\[\[[^\]]+\]\]` 패턴을 추출해 unique set을 양방향 비교한다. 실험 실행 명령과 CSV 필드는 `docs/paper/EXPERIMENT_GUIDE.md`를 따른다.
