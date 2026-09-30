# 새 microSD에서 Re:Found 다시 시작하기

**2026-09-30 현재:** 새 SD 설치·카메라·기본 실물 흐름·재부팅 확인은 9월 22일 완료했습니다. 9월 29일에는 Windows 노트북 `ReFoundLaptop` 핫스팟의 Pi 연결 로그와 노트북 SSH 웹·OpenAI 성공 보고가 추가됐습니다. 현재 시연 재개는 [Windows 실행·종료 안내](../../REFOUND_WINDOWS_HOTSPOT_GUIDE.md)와 [실기 확인표](PI_ACCEPTANCE_CHECKLIST.md)의 전원 재인가·자동 연결 시험입니다. 친구 Tailscale 수락은 미확인이지만 현재 방식의 선행 조건이 아닙니다.

**아래는 새 카드를 다시 만들 때만 사용하는 설치 절차입니다.** 기존 Pi에 반복 실행하지 않습니다. 노트북에서 Pi 화면만 열 때에는 PC 앱 설치도 필요 없습니다. 이전 카드의 OS·설정·키·DB는 새 카드로 자동 복구되지 않으므로 실제 새 설치에서는 다시 확인합니다.

대상: Raspberry Pi 4 Model B 2GB + CSI 카메라 + Windows PC. 새 설치는 **OS → 앱 → SSH 터널 확인 → 필요하면 Tailscale** 순서입니다. 집 공유기 LAN으로 설치하고 이후 시연 네트워크로 바꿀 수 있습니다. 아래 Android 공개 핫스팟 설명은 별도 대안이며 현재 Windows 핫스팟에는 저장된 비밀번호를 사용합니다. 비밀값은 문서에 적지 않습니다.

## 1. 새 카드에 OS 기록

1. Pi 전원을 분리하고 기존 카메라 케이블을 확인합니다. 연결 그림은 [상세 가이드 1절](RASPBERRY_PI_GUIDE.md#1-전원을-뽑고-카메라-연결하기)을 참고합니다.
2. [Raspberry Pi Imager](https://www.raspberrypi.com/software/)에서 장치 **Raspberry Pi 4**, OS **Raspberry Pi OS Lite (64-bit)**를 선택합니다. Desktop/Full은 필요 없습니다. 2026-09-22 공식 다운로드 재확인 기준 일반 Lite 64-bit는 Debian 13 **Trixie**입니다. 과거 카드의 OS 버전은 확인되지 않았으므로 같다고 가정하지 않습니다. [공식 OS 목록](https://www.raspberrypi.com/software/operating-systems/)
3. **새 microSD**를 저장소로 선택합니다. 쓰기는 선택한 카드 내용을 지웁니다.
4. 사용자 정의에서 아래 값을 설정합니다. Imager 버전에 따라 화면 순서는 달라질 수 있습니다.

| 항목 | 값 |
|---|---|
| 호스트 이름 | `refound-pi` |
| 사용자 이름 | `refound` |
| 비밀번호 | 본인이 정한 비밀번호 |
| Wi-Fi | 실제로 사용할 SSID·보안 방식·비밀번호. 현재 Windows 구성은 `ReFoundLaptop`과 노트북에 저장한 비밀번호 |
| 국가 / 시간대 | `KR` / `Asia/Seoul` |
| SSH | 켬, 비밀번호 인증 허용 |

5. 쓰기와 검증을 마친 뒤 안전하게 꺼내 Pi에 넣습니다. 이번 계획에서는 **공유기 LAN 포트와 Pi를 랜선으로 연결**한 뒤 전원을 켭니다. 첫 부팅은 약 3분 기다립니다. PC는 같은 집 공유기에 Wi-Fi 또는 랜선으로 연결합니다. 친구 핫스팟이 집에 없어도 유선으로 설치할 수 있습니다. Pi도 Wi-Fi로 설치하는 경우에만 PC와 Pi를 같은 Wi-Fi에 연결합니다.

친구 안드로이드에서 핫스팟 **보안 없음/None**을 지원하고 그렇게 사용할 경우, Imager에서는 **공개 네트워크/Open network**를 선택하고 핫스팟 이름만 정확히 입력합니다. 보안 네트워크를 선택한 채 비밀번호만 비우는 방식과는 다릅니다. 비밀번호를 사용하는 핫스팟은 **보안 네트워크/Secure network**로 설정합니다. 비밀번호를 한 번 저장하면 Pi는 이후에도 자동 연결하므로 WPA2 비밀번호 사용을 권장합니다. 공개 핫스팟에는 주변 사람도 접속할 수 있습니다. [Imager 설정](https://www.raspberrypi.com/documentation/computers/getting-started.html#wi-fi), [Android 공개 핫스팟 안내](https://support.google.com/android/answer/9059108?hl=en)

휴대전화 핫스팟을 처음부터 쓸 경우 2.4GHz/호환 모드를 선택하고 자동 종료를 끕니다. Wi-Fi 연결이 안 되면 [모니터·키보드 복구 가이드](PI_MONITOR_WIFI_GUIDE.md)를 사용합니다.

## 2. SSH 접속 — 재설치 경고 처리

**Windows PowerShell:**

```powershell
ssh refound@refound-pi.local
```

`.local`을 찾지 못하면 공유기·휴대전화의 연결 장치 목록에서 Pi의 새 IP를 확인해 `.local` 대신 사용합니다. 사용자 이름을 다르게 정했다면 `refound`도 바꿉니다.

새 OS는 새 SSH 호스트 키를 만듭니다. **본인이 방금 재설치한 Pi가 맞는지 확인한 뒤**, `REMOTE HOST IDENTIFICATION HAS CHANGED`가 나타난 주소의 이전 기록만 제거합니다.

```powershell
ssh-keygen -R refound-pi.local
ssh refound@refound-pi.local
```

IP 주소로 접속했다면 `-R` 뒤에도 그 IP를 사용합니다. 모든 known_hosts를 지우거나 호스트 키 검사를 끄지 않습니다. 장치를 구분하기 어렵다면 Pi에 모니터로 로그인해 `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`의 지문을 비교합니다.

**이후 Pi 터미널:**

```bash
date
cat /etc/os-release
uname -m
```

시간이 맞고 아키텍처가 `aarch64`인지 확인합니다. 날짜가 틀리면 `timedatectl status`를 확인하고 인터넷 시간 동기화를 기다립니다.

## 3. 최신 파일 복사와 설치

**새 Windows PowerShell 창**에서 프로젝트 폴더로 이동합니다. 폴더를 옮겼다면 `cd` 경로만 현재 위치로 바꿉니다.

```powershell
cd "C:\Users\USER\Downloads\Capstone-team-project-main"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\raspberry-pi\package-for-pi.ps1 -Force
scp .\dist\refound-pi.tar.gz .\dist\refound-pi.tar.gz.sha256 refound@refound-pi.local:~/
```

최신 기본 배포 파일명은 항상 **`dist/refound-pi.tar.gz`**입니다. 날짜가 붙은 파일은 이전 검증 시점의 보관본이므로 새 설치에는 위에서 만든 파일을 씁니다. 패키지에는 PC의 `.env`·실제 DB·사진이 들어가지 않습니다.

**Pi 터미널**로 돌아와 실행합니다.

```bash
cd "$HOME"
sha256sum -c refound-pi.tar.gz.sha256
```

`OK`를 확인한 뒤 다음을 실행합니다. 실패했다면 압축을 풀지 말고 파일을 다시 복사합니다.

```bash
sudo install -d -m 0755 /opt/refound
sudo tar -xzf "$HOME/refound-pi.tar.gz" -C /opt/refound
cd /opt/refound
sudo bash scripts/raspberry-pi/install.sh
```

설치기는 OS의 OpenCV·NumPy·Picamera2와 앱용 가상환경을 구성합니다. Python 라이브러리를 실제로 불러오는 검사까지 통과해야 서비스를 시작합니다. Pi에서 따로 `pip install opencv-python` 또는 일반 `requirements.txt` 설치를 덧붙이지 않습니다. 카메라 라이브러리는 [공식 Picamera2 안내](https://github.com/raspberrypi/picamera2/blob/main/README.md)에 맞춰 apt 버전과 `--system-site-packages` 가상환경을 사용합니다.

## 4. 카메라와 API 키 설정

**Pi 터미널:**

```bash
sudo bash /opt/refound/scripts/raspberry-pi/check-camera.sh
```

서비스를 잠시 멈출지 묻는 질문에 답합니다. JPEG·Picamera2 검사 성공과 서비스 재시작을 확인합니다. 카메라를 찾지 못하면 정상 종료 후 전원을 분리하고 케이블을 확인합니다. `Legacy Camera`나 오래된 `raspistill` 설정은 사용하지 않습니다.

API 키는 Pi에서 직접 입력합니다.

```bash
nano /opt/refound/.env
```

- `OPENAI_API_KEY=` 또는 `GEMINI_API_KEY=` 중 사용할 제공자 하나를 입력합니다.
- 메일도 쓸 경우 `SMTP_PASSWORD=`에 메일 앱 비밀번호를 입력합니다.
- **SD 고장만으로 키를 새로 발급할 필요는 없습니다.** 유효하고 노출되지 않은 키를 안전하게 보관 중이면 다시 사용할 수 있습니다. 키를 잃었거나 노출됐다면 재발급합니다.
- PC의 `.env` 전체를 복사하지 않습니다. `HOST`, `PORT`, `HARDWARE_PROFILE`은 설치기가 관리합니다.

Nano에서 `Ctrl+O`, `Enter`, `Ctrl+X` 순서로 저장하고 재시작합니다.

```bash
sudo systemctl restart refound.service
bash /opt/refound/scripts/raspberry-pi/check-system.sh
```

이 한 명령으로 OS·메모리·저장 공간·Python·DB·카메라 상태를 확인합니다. API 키의 유효성과 메일 수신을 실제 호출로 검사하는 명령은 아닙니다. 시작 직후 준비 중이면 잠시 기다렸다 다시 확인합니다. 오류가 있으면 출력과 다음 로그를 보관합니다.

```bash
sudo journalctl -u refound.service -n 60 --no-pager
```

## 5. 가장 먼저 앱 열기 — Tailscale 없이 가능

**Windows의 별도 PowerShell 창:**

```powershell
ssh -N -L 18000:127.0.0.1:8000 -o ExitOnForwardFailure=yes refound@refound-pi.local
```

비밀번호 입력 뒤 아무 출력 없이 기다리면 정상입니다. **그 창을 열어 둔 채 PC 브라우저에서 `http://127.0.0.1:18000`을 엽니다.** 이 주소는 SSH 터널로 연결한 PC에서만 사용합니다. 끝낼 때 터널 창에서 `Ctrl+C`를 누릅니다.

18000번 포트를 이미 쓰고 있다면 명령의 첫 번째 `18000`과 브라우저 주소를 함께 `18001`로 바꿉니다. SSH 주소를 IP로 바꿨다면 터널 명령에도 같은 IP를 씁니다. 앱을 LAN 전체에 공개할 필요가 없습니다.

1. 카메라 영상과 개인정보 보호 모드가 꺼져 있는지 확인합니다.
2. 카메라·배경을 고정하고 빈 보관 구역에서 **기준 화면 재설정** 후 안정될 때까지 기다립니다.
3. 실물을 놓고 손을 뺍니다. 임시 등록 후 AI 분석이 끝나는지 확인합니다. `키 설정됨` 표시만으로는 성공이 아닙니다.
4. 물품을 옮겼을 때 같은 ID인지, 치웠을 때 회수되는지 확인합니다.
5. 메일 설정을 저장하고 **테스트 메일**을 실제 수신함에서 확인합니다.
6. 나머지 관리 기능과 재부팅은 [실기 확인표](PI_ACCEPTANCE_CHECKLIST.md)에 따라 확인합니다. 내장 예시 버튼은 실물 감지·AI 검증을 대신하지 않습니다.

**시연 중 처음부터 다시 시작하기:** 물건을 모두 치운 뒤 메인 화면 상단의 **시연 초기화 → 백업 없이 초기화**를 누릅니다. 실제 카메라 등록을 포함한 모든 물품·활동·알림·사진을 삭제하고 기준 화면을 다시 잡습니다. 설정과 API 키는 유지되며 삭제는 되돌릴 수 없습니다. 화면이 안정된 뒤 물품을 다시 놓습니다. 백업이 필요한 기록은 설정 → 시스템의 기존 초기화를 사용합니다.

## 6. 학교에서 쓸 원격 접속은 마지막에

위의 로컬 실물 확인을 마친 뒤, 서로 다른 네트워크에서도 사용할 경우에만 **Pi에서** 실행합니다.

```bash
sudo bash /opt/refound/scripts/raspberry-pi/setup-tailscale.sh
```

집에서 설치하는 사용자 PC와 Pi는 사용자 본인의 tailnet에 로그인합니다. 친구 노트북은 **친구 계정으로 로그인하고 Pi 장치 공유 초대를 수락**하는 별도 경로를 사용합니다. 친구에게 사용자 계정 비밀번호를 줄 필요는 없습니다. 새 SD에서는 Pi를 **새 장치로 다시 인증**하고 HTTPS/Serve 동의까지 마칩니다. 기존 카드의 주소를 그대로 쓰지 말고 아래 출력의 **전체 HTTPS 주소**를 새 북마크로 저장합니다. 공유받은 친구도 이 주소로 접속하며 양쪽의 접근 정책이 허용해야 합니다. [장치 공유와 Serve](https://tailscale.com/docs/features/tailscale-serve#identity-headers)

```bash
sudo tailscale serve status
```

기존 장치명이 남아 있으면 새 장치에 `-1` 같은 접미사가 붙을 수 있습니다. [Tailscale 장치 이름 설명](https://tailscale.com/docs/concepts/machine-names) 이전 고장 카드의 장치 항목은 새 Pi를 확실히 구분한 뒤 관리 화면에서 정리할 수 있으며, 처음 앱을 확인하는 데 필수는 아닙니다.

**Serve만 사용하고 Funnel은 켜지 않습니다.** 로그인·동의 화면의 상세 설명은 [설치 가이드 8절](RASPBERRY_PI_GUIDE.md#8-tailscale로-서로-다른-네트워크에서-접속하기), 이후 학교 운영은 [학교 가이드](SCHOOL_DEMO_GUIDE.md)를 참고합니다. 자체 `ReFound-Demo` 핫스팟은 인터넷이 없을 때의 선택 기능이며 AI·메일에는 인터넷이 필요합니다.

## 7. 다음 세션에 가져올 내용

- 선택한 OS 이름·버전, 카메라 모델 또는 `rpicam-hello --list-cameras` 출력
- `check-system.sh` 출력과 설치 패키지 SHA-256
- [실기 확인표](PI_ACCEPTANCE_CHECKLIST.md)의 성공·실패·미실시 구분
- 실패했다면 동작 순서와 증상, 필요할 때 해당 시각의 서비스 로그. API 키는 보내지 않습니다.

새 카드에서 재부팅 후 다시 동작하는 것까지 확인하면, 다음 작업은 **논문 계속 작성** 또는 **개선점 발표 자료** 중 사용자 선택에 맞춥니다. 이번 실기 점검은 논문용 정량 실험이 아니므로 성공 몇 건을 논문 정확도로 바꾸지 않습니다.

실습 종료는 `sudo shutdown -h now`로 정상 종료한 뒤 진행합니다. 백업할 실제 데이터가 생기면 서비스가 멈춘 상태에서 `data`를 별도로 보관합니다. `.env`에는 비밀값이 있으므로 일반 배포 파일·발표 자료에 넣지 않습니다.
