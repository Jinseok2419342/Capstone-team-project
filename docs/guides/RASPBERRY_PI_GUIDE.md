# Re:Found Raspberry Pi 4 완전 초보 설치 가이드

이 문서는 Raspberry Pi를 처음 사용하는 사람도 다음 구성을 처음부터 만들 수 있도록 한 단계씩 설명합니다.

```text
Raspberry Pi 4 + Camera Module
        │
        ├─ 물체 변화 감지·저장·관리 웹 실행
        ├─ 인터넷이 있으면 OpenAI/Gemini와 메일 사용
        └─ Tailscale을 통해 관리자 노트북에서 안전하게 접속
```

기준 장비는 **Raspberry Pi 4 Model B 2GB**, Raspberry Pi Camera Module, Raspberry Pi OS Lite 64-bit입니다. 명령은 별도 표시가 없다면 Raspberry Pi의 터미널에서 실행합니다.

> 이 가이드는 2026년 8월 25일 기준입니다. 현재 Raspberry Pi OS의 카메라 체계인 `rpicam`/Picamera2를 사용하며, 오래된 `raspistill` 또는 Legacy Camera 기능은 사용하지 않습니다.

---

## 먼저 결론: 학교에서는 이렇게 접속합니다

학교 Wi-Fi와 노트북이 같은 네트워크인지 몰라도 괜찮습니다. 권장 순서는 다음과 같습니다.

| 우선순위 | Raspberry Pi 연결 | 노트북 연결 | 접속 방법 | AI API |
|---:|---|---|---|---|
| 1 | 휴대전화 핫스팟 | 학교 Wi-Fi 또는 다른 인터넷 | **Tailscale 주소** | 가능 |
| 2 | 휴대전화 핫스팟 | 같은 휴대전화 핫스팟 | **Tailscale 주소** | 가능 |
| 3 | Pi가 만든 `ReFound-Demo` Wi-Fi | `ReFound-Demo`에 직접 연결 | `http://10.42.0.1:8000` | 인터넷이 없으면 불가능 |

Tailscale은 두 장치가 서로 다른 Wi-Fi를 사용해도, 양쪽에 인터넷만 있으면 연결해 주는 사설망입니다. 노트북과 Pi가 **같은 tailnet**에 속하고 Tailscale 접근 정책(ACL)이 연결을 허용해야 합니다. 꼭 같은 로그인 계정일 필요는 없습니다.

세 번째 방식은 인터넷이 완전히 끊긴 상황을 위한 **오프라인 비상 모드**입니다. 라이브뷰, 로컬 감지, 목록과 관리자 조작은 가능하지만 그 순간의 OpenAI/Gemini 분석은 성공하지 않습니다. 감지 증거와 물품은 로컬에 관리자 확인 상태로 남지만, 인터넷이 복구돼도 AI가 자동으로 다시 분류하지 않으므로 관리자가 이름과 분류를 직접 확인해야 합니다. 메일은 별도 재시도 상태를 가질 수 있지만 시연에서는 반드시 직접 확인합니다.

### 하지 말아야 할 것

- 공유기의 8000번 포트를 인터넷에 포트포워딩하지 마세요.
- Tailscale **Funnel**을 켜지 마세요. 이 프로젝트는 현재 공개 인터넷용 로그인 화면을 제공하지 않습니다.
- 학교 공용 Wi-Fi에서 앱을 `0.0.0.0`으로 열지 마세요. 제공된 스크립트는 평소에는 `127.0.0.1`, 오프라인 핫스팟에서는 전용 주소 `10.42.0.1`에만 바인딩합니다.
- API 키를 소스 코드, 발표 자료, 화면 캡처, 메신저 또는 Git에 넣지 마세요.

---

## 0. 준비물과 계정

### 필수 준비물

- Raspberry Pi 4 Model B 2GB
- Raspberry Pi Camera Module과 Pi 4용 15핀 리본 케이블
- 16GB 이상 microSD 카드: 32GB 이상 A1 등급 권장
- 안정적인 USB-C 5V 3A 전원 어댑터
- 방열판 또는 팬이 있는 케이스 권장
- microSD 카드 리더가 있는 Windows 노트북
- 최초 설치용 인터넷: 집 Wi-Fi 또는 휴대전화 핫스팟
- 학교 시연 때 사용할 휴대전화와 충전기

### 미리 만들거나 설치할 것

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/)를 Windows에 설치합니다.
2. [Tailscale](https://tailscale.com/download/windows)을 Windows에 설치하고 로그인합니다.
3. Tailscale 계정이 없다면 개인 계정을 하나 만듭니다.
4. OpenAI 또는 Gemini API 키를 준비합니다.

### API 키는 지금 재발급하세요

기존 `.env`의 키가 테스트 화면, 로그 또는 다른 사람에게 보인 적이 있다면 **기존 키를 폐기하고 새 키를 발급**하세요. 현재 PC의 `.env`를 Pi로 통째로 복사하지 않고, 설치 후 Pi에서 새 키만 직접 입력하는 방식으로 진행합니다.

---

## 1. 전원을 뽑고 카메라 연결하기

카메라 케이블은 반드시 **Pi 전원을 완전히 분리한 상태**에서 연결합니다.

1. Raspberry Pi에서 USB-C 전원과 모든 케이블을 뽑습니다.
2. 금속 수도꼭지처럼 접지된 금속을 잠깐 만져 정전기를 줄입니다.
3. Pi 4에서 Ethernet과 HDMI 포트 사이의 `CAMERA` 또는 CSI 커넥터를 찾습니다.
4. 커넥터의 검은색 잠금 탭 양쪽을 2~3mm 정도 조심스럽게 들어 올립니다. 탭을 뽑아내지 마세요.
5. 리본 케이블을 곧게 끝까지 넣습니다.
   - Pi 쪽 은색 접점은 **HDMI 포트 방향**을 향합니다.
   - 일반 Camera Module 보드 쪽에서는 파란 보강면이 카메라 PCB 반대쪽을 향합니다.
6. 케이블을 움직이지 않게 잡은 채 잠금 탭 양쪽을 같은 높이로 눌러 닫습니다.
7. 케이블이 한쪽으로 기울지 않았고 은색 접점이 거의 보이지 않는지 확인합니다.

카메라 렌즈를 손으로 만지지 마세요. 카메라와 Pi는 시연 중 흔들리지 않도록 단단한 받침대에 고정합니다.

공식 연결 그림이 필요하면 [Raspberry Pi 카메라 연결 문서](https://www.raspberrypi.com/documentation/accessories/camera.html)를 확인하세요.

---

## 2. microSD에 Raspberry Pi OS 설치하기

> 이 과정은 선택한 microSD의 모든 내용을 지웁니다. 드라이브를 반드시 다시 확인하세요.

1. microSD 카드를 Windows 노트북에 꽂습니다.
2. Raspberry Pi Imager를 실행합니다.
3. **장치 선택**에서 `Raspberry Pi 4`를 선택합니다.
4. **운영체제 선택**에서 다음을 선택합니다.

   ```text
   Raspberry Pi OS (other)
   → Raspberry Pi OS Lite (64-bit)
   ```

5. **저장소 선택**에서 방금 꽂은 microSD를 선택합니다.
6. OS 사용자 정의 화면에서 다음처럼 설정합니다.

   | 항목 | 권장값 |
   |---|---|
   | 호스트 이름 | `refound-pi` |
   | 사용자 이름 | `refound` |
   | 비밀번호 | 본인만 아는 긴 비밀번호 |
   | Wi-Fi SSID | 집 Wi-Fi 또는 본인 휴대전화 핫스팟 |
   | Wi-Fi 국가 | `KR` |
   | 시간대 | `Asia/Seoul` |
   | SSH | 사용, 비밀번호 인증 허용 |

7. 휴대전화 핫스팟을 사용한다면 이름과 비밀번호는 영문·숫자로 단순하게 만드는 편이 안전합니다. 가능하면 호환성/2.4GHz 모드를 켭니다.
8. 설정을 저장하고 **쓰기**를 누릅니다.
9. 쓰기와 검증이 모두 끝날 때까지 기다린 뒤 microSD를 안전하게 꺼냅니다.

`refound`가 아니라 다른 사용자 이름을 선택했다면 이 문서의 `refound@...` 부분을 모두 자신의 이름으로 바꿔야 합니다. 아래 파일 전송 절차는 사용자 홈을 `~/`와 `$HOME`으로 표기하므로 별도 경로 수정은 필요 없습니다.

---

## 3. 처음 켜고 SSH로 접속하기

1. 전원이 빠져 있는지 다시 확인합니다.
2. 작성한 microSD를 Pi 밑면 슬롯에 넣습니다.
3. 카메라 케이블을 다시 확인합니다.
4. USB-C 전원을 연결합니다.
5. 첫 부팅은 파일시스템 확장 때문에 시간이 걸릴 수 있으므로 3분 정도 기다립니다.
6. Windows 노트북을 Imager에 입력한 것과 같은 Wi-Fi에 연결합니다.
7. Windows에서 PowerShell을 열고 실행합니다.

```powershell
ssh refound@refound-pi.local
```

처음 접속할 때 다음과 비슷한 질문이 나오면 `yes`를 입력합니다.

```text
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

그다음 Imager에서 정한 비밀번호를 입력합니다. 비밀번호를 입력해도 화면에 글자나 별표가 나타나지 않는 것이 정상입니다.

### `refound-pi.local`을 찾지 못할 때

다음 순서로 확인합니다.

1. Pi와 노트북이 최초 설정용 Wi-Fi에 연결되어 있는지 확인합니다.
2. 휴대전화 핫스팟의 연결 장치 목록에서 `refound-pi`의 IP 주소를 찾습니다.
3. IP가 예를 들어 `192.168.43.27`이라면 다음처럼 접속합니다.

   ```powershell
   ssh refound@192.168.43.27
   ```

4. 그래도 찾지 못하면 Pi에 모니터와 키보드를 잠시 연결하고 로그인한 뒤 다음 명령으로 주소를 확인합니다.

   ```bash
   hostname -I
   ```

접속에 성공하면 먼저 시간과 네트워크를 확인합니다.

```bash
date
hostname
hostname -I
```

날짜가 크게 틀리면 HTTPS와 AI API 연결도 실패할 수 있습니다. 잠시 인터넷에 연결한 뒤 다음으로 상태를 확인합니다.

```bash
timedatectl status
```

---

## 4. Windows에서 안전한 Pi 패키지 만들고 복사하기

SSH 창은 열어 둡니다. **새 PowerShell 창**을 하나 더 열고 프로젝트 폴더로 이동합니다.

```powershell
cd "C:\Users\pppp\Desktop\AI_based_Vision"
Get-Location
```

표시된 경로가 프로젝트 폴더인지 확인합니다. 먼저 Pi 전용 패키지를 만듭니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\raspberry-pi\package-for-pi.ps1
```

이미 이전 패키지가 있다는 오류가 나오고 새 버전으로 의도적으로 교체하려는 경우에만 마지막에 `-Force`를 붙여 다시 실행합니다.

완료되면 다음 두 파일이 생깁니다.

```text
dist\refound-pi.tar.gz
dist\refound-pi.tar.gz.sha256
```

이 패키징 스크립트는 허용 목록에 있는 실행 파일만 담습니다. 실제 `.env`, `data`, reset 백업, Windows `.venv`, Git 정보와 캐시는 검색하거나 포함하지 않습니다. 출력 마지막에 `Verified absent` 메시지가 보여야 합니다.

두 파일을 Pi의 사용자 홈으로 복사합니다.

```powershell
scp .\dist\refound-pi.tar.gz .\dist\refound-pi.tar.gz.sha256 refound@refound-pi.local:~/
```

`.local` 주소가 안 되면 앞 단계에서 확인한 IP 주소를 사용합니다.

```powershell
scp .\dist\refound-pi.tar.gz .\dist\refound-pi.tar.gz.sha256 refound@192.168.43.27:~/
```

이제 기존 SSH 창으로 돌아갑니다. 전송 중 손상되지 않았는지 검사합니다.

```bash
cd "$HOME"
sha256sum -c refound-pi.tar.gz.sha256
```

`refound-pi.tar.gz: OK`가 보여야 합니다. 그다음 설치 위치에 압축을 풉니다.

```bash
sudo install -d -m 0755 /opt/refound
sudo tar -xzf "$HOME/refound-pi.tar.gz" -C /opt/refound
cd /opt/refound
ls
```

마지막 `ls` 결과에 `app`, `scripts`, `requirements-pi.txt`, `run.py`가 보여야 합니다.

설치 스크립트가 로그인한 일반 사용자를 서비스 계정으로 지정하고 `.venv`, `.env`, `data`에 필요한 최소 소유권만 설정합니다. `/opt/refound` 전체를 재귀적으로 `chown`하지 마세요.

---

## 5. 자동 설치 스크립트 실행하기

Pi의 `/opt/refound`에서 실행합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/install.sh
```

스크립트는 필요한 시스템 패키지와 Python 환경을 설치하고 `refound.service`를 등록합니다. 질문이 표시되면 내용을 읽고 `y` 또는 `n`으로 답합니다. Pi 4와 microSD 속도에 따라 수 분 이상 걸릴 수 있습니다.

설치가 끝나면 다음 세 명령을 차례로 확인합니다.

```bash
sudo systemctl status refound.service --no-pager
curl http://127.0.0.1:8000/api/health
sudo journalctl -u refound.service -n 30 --no-pager
```

- 서비스 상태에 `active (running)`이 보이면 정상입니다.
- health 결과가 JSON으로 나오면 웹 서버가 정상입니다.
- `q`를 눌러야 빠져나오는 화면이 나타나면 `q`를 누릅니다.

서비스는 부팅 때 자동으로 시작됩니다. `uvicorn --workers 2`처럼 여러 프로세스를 별도로 실행하지 마세요. 카메라와 알림 처리에는 단일 앱 프로세스를 사용합니다.

---

## 6. 새 API 키와 메일 비밀번호 입력하기

먼저 기존 키를 제공자 대시보드에서 폐기하고 새 키를 발급합니다. 설치 스크립트는 비어 있는 `.env.example`로 Pi 전용 `.env`를 만들고 처음부터 권한을 `600`으로 제한합니다. 키를 PowerShell 명령줄에 넣으면 명령 기록에 남을 수 있으므로 Pi에서 편집기를 엽니다.

```bash
nano /opt/refound/.env
```

다음 항목에 자신의 새 키를 입력합니다. 둘 중 하나만 입력해도 됩니다. `HOST`, `PORT`, `HARDWARE_PROFILE`은 운영 스크립트가 별도 런타임 설정으로 안전하게 관리하므로 직접 바꿀 필요가 없습니다.

```dotenv
OPENAI_API_KEY=새_OpenAI_키
GEMINI_API_KEY=새_Gemini_키
SMTP_PASSWORD=메일_앱_비밀번호
```

Nano 저장 방법은 다음과 같습니다.

1. `Ctrl+O`
2. 파일 이름 질문에서 `Enter`
3. `Ctrl+X`

파일을 현재 로그인 사용자만 읽을 수 있도록 다시 확인하고 서비스를 재시작합니다.

```bash
chmod 600 /opt/refound/.env
sudo systemctl restart refound.service
sudo systemctl status refound.service --no-pager
```

다음으로 권한을 확인합니다.

```bash
ls -l /opt/refound/.env
```

권한 부분이 `-rw-------`로 시작해야 합니다. 키가 포함된 `.env`를 Windows로 다시 복사하거나 발표 화면에 띄우지 마세요.

SMTP 서버 주소, 포트, 발신 계정과 관리자 수신 주소는 나중에 관리자 웹의 **설정** 화면에서 입력합니다.

---

## 7. 카메라 검사하기

카메라는 한 번에 한 프로그램만 사용할 수 있습니다. 제공된 검사 스크립트는 실행 중인 Re:Found 서비스를 확인하고, 허락을 받은 뒤 잠시 멈췄다가 검사 종료 후 원래 상태로 복구합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/check-camera.sh
```

화면의 질문에 답하고 검사 결과를 확인합니다. 자동 확인이 필요한 경우에만 `--yes`를 붙일 수 있습니다.

```bash
sudo bash scripts/raspberry-pi/check-camera.sh --yes
```

직접 카메라 목록만 확인하려면 다음을 사용합니다.

```bash
rpicam-hello --list-cameras
```

카메라 모델명이 한 개 이상 표시되면 케이블과 OS가 카메라를 인식한 것입니다. SSH에서는 미리보기 창을 띄우려 하지 말고 검사 스크립트의 캡처 결과를 사용하세요.

카메라가 보이지 않으면 **먼저 정상 종료하고 전원 플러그를 뽑은 뒤** 리본 케이블 방향과 잠금 탭을 다시 확인합니다.

```bash
sudo shutdown -h now
```

초록색 ACT LED가 깜박임을 멈춘 뒤에만 전원을 뽑습니다.

---

## 8. Tailscale로 서로 다른 네트워크에서 접속하기

이 방식이 학교 시연의 기본 접속 방법입니다.

### 8-0. 학교에서 쓸 휴대전화 핫스팟을 먼저 저장

Imager에서 집 Wi-Fi를 입력했다면 Pi는 학교에서 본인 휴대전화 핫스팟을 모릅니다. 출발 전에 반드시 해당 접속 정보를 Pi에 저장하고 재부팅까지 시험합니다.

휴대전화 핫스팟 이름은 예를 들어 `ReFoundPhone`처럼 영문·숫자로 정하고, 호환성/2.4GHz 모드를 켭니다. 핫스팟을 켠 뒤 Pi에서 주변 목록을 확인합니다.

```bash
nmcli dev wifi list
```

목록에서 `ReFoundPhone`이 보이면 다음을 실행합니다. 비밀번호는 숨김 입력되며 명령 기록에 남지 않습니다.

```bash
sudo nmcli --ask dev wifi connect "ReFoundPhone"
```

Pi가 집 Wi-Fi에서 휴대전화로 이동하므로 현재 SSH가 끊기는 것이 정상입니다. 노트북도 잠시 `ReFoundPhone`에 연결하고 20초 정도 기다린 뒤 다시 접속합니다.

```powershell
ssh refound@refound-pi.local
```

`.local`이 안 되면 휴대전화의 연결 장치 목록에서 Pi IP를 확인합니다. 다시 접속한 Pi에서 저장 상태를 확인합니다.

```bash
nmcli -f NAME,TYPE,AUTOCONNECT connection show
```

연결 이름이 `ReFoundPhone`으로 표시됐다고 가정하면 자동 연결과 우선순위를 설정합니다. 이름이 다르면 실제 `NAME` 값으로 바꿉니다.

```bash
sudo nmcli connection modify "ReFoundPhone" connection.autoconnect yes connection.autoconnect-priority 50
sudo reboot
```

휴대전화 핫스팟을 켜 둔 채 2~3분 기다리고, Pi가 다시 연결되는지 확인합니다. 이 시험을 통과해야 학교에서 화면 없이 부팅할 수 있습니다.

> `ReFoundPhone`은 인터넷을 공급하는 **휴대전화 Wi-Fi**이고, 뒤에서 만드는 `ReFound-Demo`는 인터넷이 없을 때 Pi가 직접 만드는 **비상 Wi-Fi**입니다. 둘은 서로 다른 네트워크입니다.

### 8-1. Windows 노트북 준비

1. Windows용 Tailscale을 설치합니다.
2. 작업 표시줄의 Tailscale 아이콘을 열어 로그인합니다.
3. Pi가 들어갈 **같은 tailnet**이 선택됐고 접근 정책(ACL)이 노트북에서 Pi로의 연결을 허용하는지 확인합니다.
4. 학교에 가기 전에 설치와 로그인을 끝내 둡니다. 학교 노트북은 프로그램 설치 권한이 없을 수 있습니다.

개인 tailnet에는 신뢰하는 장치만 두고, Pi 장치를 외부 사용자에게 공유하지 마세요. 앱 자체에는 별도 로그인 기능이 없으므로 가능하면 ACL에서 관리자 노트북 또는 관리자 계정만 Pi에 접근하도록 제한합니다.

### 8-2. Pi에서 설정 스크립트 실행

Pi가 인터넷에 연결된 상태에서 실행합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/setup-tailscale.sh
```

스크립트는 다음을 안전하게 처리합니다.

1. Tailscale이 없으면 공식 설치 방법을 사용할지 물어봅니다.
2. `tailscale up` 인증 주소를 보여 줍니다.
3. 이 Pi에 남아 있을 수 있는 기존 Tailscale Serve/Funnel 게시 설정을 초기화합니다.
4. 앱을 로컬 전용 `HOST=127.0.0.1`로 바꿉니다.
5. Raspberry Pi 저부하 프로필을 유지합니다.
6. Re:Found 서비스를 다시 시작합니다.
7. Tailscale Serve를 통해 `http://127.0.0.1:8000`을 사설 HTTPS 주소에 연결합니다.

터미널에 `https://login.tailscale.com/...` 형태의 주소가 나오면 다음과 같이 진행합니다.

1. 주소 전체를 복사합니다.
2. Windows 브라우저에서 엽니다.
3. 노트북이 속한 것과 같은 tailnet의 계정 또는 초대된 구성원으로 로그인합니다.
4. Pi 연결을 승인합니다.
5. Pi 터미널로 돌아와 스크립트가 끝나는지 확인합니다.

첫 `Tailscale Serve` 실행에서는 장치 로그인과 별개로 HTTPS/Serve 사용 동의 주소가 한 번 더 나타날 수 있습니다. 스크립트는 이 주소를 숨기지 않으며, 승인될 때까지 같은 줄에서 기다리므로 멈춘 것처럼 보일 수 있습니다. 이 경우 다음처럼 처리합니다.

1. 표시된 동의 주소를 브라우저에서 엽니다.
2. tailnet 내부 HTTPS/Serve 사용만 승인합니다.
3. **Funnel 또는 Public Internet 공개 선택은 켜지 않습니다.** 이미 켜져 있다면 해제합니다.
4. Pi 터미널은 닫거나 `Ctrl+C`를 누르지 말고 그대로 둡니다.
5. 승인되면 같은 스크립트가 자동으로 계속됩니다. 명령이 이미 끝났거나 직접 중단한 경우에만 `setup-tailscale.sh`를 다시 실행합니다.

`Publishing the loopback service...` 뒤에 동의 주소, `Success` 또는 상태 출력이 하나도 없이 1분 이상 그대로라면 `Ctrl+C`로 중단해도 앱 데이터와 설치는 손상되지 않습니다. 인터넷 연결과 `tailscale status`를 확인한 뒤 설정 스크립트를 다시 실행합니다. 같은 위치에서 반복되면 화면 문구를 그대로 기록해 문제 해결에 사용합니다.

최종 출력이 `Available within your tailnet` 또는 `tailnet only`와 `https://...ts.net` 주소를 보여야 합니다. 스크립트는 JSON 구성에서 HTTPS 443, 예상한 `http://127.0.0.1:8000` 프록시와 비공개 상태를 확인하며, 구성이 없거나 Funnel 공개가 감지되면 성공으로 표시하지 않습니다.

상태와 접속 주소를 다시 보고 싶을 때는 다음을 사용합니다.

```bash
tailscale status
sudo tailscale serve status
```

`Available on the internet` 또는 `Funnel on`이 보이면 다음 명령으로 이 Pi의 공개 게시 설정을 초기화한 뒤 설정 스크립트를 다시 실행합니다. 이 명령은 이 Pi에 설정된 기존 Serve/Funnel 게시 경로도 함께 지울 수 있습니다.

```bash
sudo tailscale funnel reset
sudo bash /opt/refound/scripts/raspberry-pi/setup-tailscale.sh
```

출력에 다음과 비슷한 주소가 나타납니다.

```text
https://refound-pi.개인-tailnet이름.ts.net
```

Windows에서 Tailscale이 연결된 상태로 이 주소를 브라우저에 입력합니다. 주소는 실제 출력값을 사용하세요.

### 8-3. 정말 다른 네트워크에서도 시험하기

발표 전 집에서 다음처럼 실제 조건을 시험합니다.

1. Pi는 휴대전화 핫스팟에 연결합니다.
2. 노트북은 집 Wi-Fi에 연결합니다.
3. 두 장치 모두 인터넷이 되는지 확인합니다.
4. 노트북 Tailscale을 `Connected`로 둡니다.
5. 위의 `https://...ts.net` 주소를 엽니다.
6. 라이브뷰와 물품 목록이 갱신되는지 확인합니다.

성공했다면 학교에서도 Pi와 노트북이 같은 Wi-Fi일 필요가 없습니다. 학교 Wi-Fi가 VPN을 막거나 로그인 페이지가 복잡하면 노트북도 휴대전화 핫스팟에 연결하면 됩니다.

> Tailscale Serve는 같은 tailnet 구성원만 접속할 수 있습니다. 인터넷 전체에 공개하는 Funnel과 다릅니다. Funnel은 사용하지 마세요.

---

## 9. 인터넷이 없을 때 Pi 자체 핫스팟 사용하기

이 방식은 학교 Wi-Fi도, 휴대전화 데이터도 사용할 수 없을 때를 위한 마지막 안전망입니다.

### 중요한 제한

- Pi의 Wi-Fi가 인터넷 접속 대신 자체 무선망을 만드는 데 사용됩니다.
- Tailscale 주소는 인터넷이 없으므로 작동하지 않습니다.
- AI 분류와 메일 발송은 작동하지 않습니다.
- 감지 증거와 물품 기록은 로컬에 남고, 분류하지 못한 물품은 관리자 확인 상태로 남을 수 있습니다. 인터넷 복구 후 관리자가 상세 화면에서 이름·분류를 확인하고 메일 상태도 별도로 점검합니다.

### 9-1. 핫스팟 시작

Pi 터미널에서 실행합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/setup-hotspot.sh
```

비밀번호를 묻는다면 8자 이상의 영문·숫자 비밀번호를 입력하고 따로 기록해 둡니다. 입력 중 문자가 표시되지 않는 것이 정상입니다.

기본값은 다음과 같습니다.

```text
Wi-Fi 이름: ReFound-Demo
Pi 주소:    10.42.0.1
웹 주소:    http://10.42.0.1:8000
```

스크립트는 SSH가 끊겨도 작업이 중단되지 않도록 2초 뒤 별도 시스템 작업으로 전환을 계속합니다. 기존 Wi-Fi SSH 화면이 멈추거나 끊기는 것이 정상입니다. 약 10초 기다린 뒤 다음으로 진행합니다.

한 번 활성화한 `ReFound-Demo`는 전원을 옮기거나 Pi를 재부팅해도 다시 켜집니다. 이것은 현장 복구를 위한 의도된 동작입니다. 인터넷 Wi-Fi로 돌아가려면 단순 재부팅이 아니라 반드시 뒤의 `remove-hotspot.sh`를 실행해야 합니다.

### 9-2. 노트북에서 직접 연결

1. Windows의 Wi-Fi 목록을 엽니다.
2. `ReFound-Demo`를 선택합니다.
3. 방금 정한 비밀번호를 입력합니다.
4. Windows가 “인터넷 없음”이라고 표시해도 연결을 유지합니다.
5. 브라우저에서 다음 주소를 엽니다.

   ```text
   http://10.42.0.1:8000
   ```

6. 라이브뷰와 목록을 확인합니다.

### 9-3. 핫스팟 해제하고 인터넷 Wi-Fi로 돌아가기

노트북이 `ReFound-Demo`에 연결된 상태에서 PowerShell을 엽니다.

```powershell
ssh refound@10.42.0.1
```

Pi에 로그인한 뒤 실행합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/remove-hotspot.sh
```

핫스팟 모드에서 앱은 모든 네트워크가 아니라 AP 전용 주소 `HOST=10.42.0.1`에만 열립니다. 해제 스크립트는 앱을 다시 로컬 전용 `HOST=127.0.0.1`로 돌리고, 핫스팟을 제거한 뒤 이전에 저장된 Wi-Fi에 자동 연결합니다. 실행 도중 SSH 연결이 끊기는 것이 정상입니다. 노트북도 원래 Wi-Fi로 다시 연결합니다.

핫스팟을 찾을 수 없고 SSH도 할 수 없다면 Pi에 모니터와 키보드를 연결해 위 해제 스크립트를 실행합니다.

전환에 실패한 것 같다면 기존 Wi-Fi가 자동 복구된 뒤 Pi에 다시 SSH로 접속하여 다음 로그를 확인합니다.

```bash
sudo journalctl -u refound-hotspot-switch.service -n 80 --no-pager
```

---

## 10. 관리자 웹에서 처음 설정하기

Tailscale 주소 또는 오프라인 주소로 웹을 연 뒤 다음 순서로 준비합니다.

1. **카메라** 화면에서 라이브 영상의 전체 영역이 보이는지 확인합니다.
2. 카메라와 촬영대를 완전히 고정합니다.
3. 감시 구역의 원래 물건을 모두 치운 상태 또는 의도한 기본 상태를 만듭니다.
4. **기준 화면 재설정**을 실행합니다.
5. 설정 화면에서 카메라와 감지 상태를 확인합니다.
6. SMTP 서버, 포트, 발신 계정과 관리자 메일을 입력합니다.
7. 인터넷 연결 상태에서 테스트 메일을 보냅니다.
8. 물건 하나를 놓고 사람이 화면에서 완전히 빠진 뒤 등록되는지 기다립니다.
9. 같은 물건을 완전히 치우고 사람이 빠진 뒤 회수 상태로 바뀌는지 확인합니다.

카메라를 옮기거나 각도를 크게 바꾼 뒤에는 반드시 기준 화면을 다시 설정하세요. 발표 직전 감도 값을 크게 바꾸지 말고, 실제 발표 장소의 조명에서 미리 시험합니다.

---

## 11. 학교 시연 권장 운영안

### 발표 전날

- Pi, 카메라, 케이스와 거치대를 모두 조립합니다.
- 새 API 키로 실제 물건 추가·회수를 최소 3회 시험합니다.
- Tailscale로 Pi와 노트북을 서로 다른 네트워크에 놓고 접속합니다.
- Pi 자체 `ReFound-Demo` 핫스팟을 켠 상태로 Pi를 한 번 재부팅하고, 노트북에서 SSID와 `http://10.42.0.1:8000`이 다시 나타나는지 확인합니다. 시험 후에는 `remove-hotspot.sh`로 해제하고 Tailscale 모드도 다시 확인합니다.
- 충전기, microSD 리더, 카메라 케이블과 짧은 Ethernet 케이블을 가방에 넣습니다.
- 노트북의 Tailscale 로그인이 유지되는지 확인합니다.
- 휴대전화 핫스팟 자동 종료 기능을 끄고 데이터 잔량을 확인합니다.

### 발표 장소 도착 후

권장 구성은 다음입니다.

```text
Raspberry Pi ──Wi-Fi──> 내 휴대전화 핫스팟 ──인터넷──> Tailscale
노트북 ──학교 Wi-Fi 또는 다른 핫스팟───────────────> Tailscale
```

1. 휴대전화를 충전기에 연결합니다.
2. 핫스팟을 켜고 Pi 전원을 켭니다.
3. 2~3분 기다립니다.
4. 노트북에서 Tailscale 연결을 확인합니다.
5. 저장해 둔 `https://...ts.net` 주소를 엽니다.
6. 카메라 라이브뷰, AI 공급자, 메일 상태를 확인합니다.
7. 발표용 기준 화면을 다시 설정합니다.
8. 시연 물건을 등록하고 회수하는 리허설을 한 번 합니다.

학교 출발 전에 인터넷을 전혀 쓸 수 없다는 사실을 이미 안다면 `ReFound-Demo`를 활성화한 상태로 정상 종료해 가져갈 수도 있습니다. 현장에서는 전원만 연결해도 핫스팟이 다시 생성됩니다. 다만 이 구성은 AI API와 이메일을 사용할 수 없다는 점을 발표 계획에 반영해야 합니다.

### 발표 10분 전

- 휴대전화 절전 모드와 핫스팟 자동 종료가 꺼져 있는지 확인합니다.
- Pi 전원 경고가 없는지 확인합니다.
- 브라우저를 전체 화면으로 열어 둡니다.
- 카메라 자동 노출이 안정될 시간을 줍니다.
- API와 메일에 문제가 생기면 로컬 저장과 관리자 확인 상태를 설명할 준비를 합니다.
- 최악의 경우 사용할 `ReFound-Demo` 비밀번호와 `http://10.42.0.1:8000`을 메모해 둡니다.

---

## 12. 자주 쓰는 명령

### 서비스 상태

```bash
sudo systemctl status refound.service --no-pager
```

### 서비스 재시작

```bash
sudo systemctl restart refound.service
```

### 최근 로그 100줄

```bash
sudo journalctl -u refound.service -n 100 --no-pager
```

### 실시간 로그 보기

```bash
sudo journalctl -u refound.service -f
```

종료는 `Ctrl+C`입니다.

### 웹 서버 자체 점검

일반/Tailscale 모드에서는 다음을 사용합니다.

```bash
curl http://127.0.0.1:8000/api/health
```

Pi 오프라인 핫스팟 모드에서는 다음을 사용합니다.

```bash
curl http://10.42.0.1:8000/api/health
```

### Tailscale 점검

```bash
tailscale status
tailscale ip
sudo tailscale serve status
```

### 메모리와 온도·전원 상태

```bash
free -h
vcgencmd measure_temp
vcgencmd get_throttled
```

`get_throttled=0x0`이면 현재와 과거 부팅 구간에 기록된 저전압·스로틀 경고가 없다는 뜻입니다. 다른 값이 계속 나오면 전원 어댑터, USB-C 케이블과 냉각을 먼저 점검합니다.

### 안전하게 전원 끄기

```bash
sudo shutdown -h now
```

초록색 ACT LED가 멈출 때까지 기다린 뒤 전원을 뽑습니다. 실행 중 전원을 바로 뽑으면 SQLite DB와 microSD가 손상될 수 있습니다.

---

## 13. 문제 해결

### SSH가 안 됩니다

1. Pi 전원 LED를 확인합니다.
2. 3분 기다립니다.
3. Pi와 노트북이 최초 설정용 네트워크에 연결됐는지 확인합니다.
4. `refound-pi.local` 대신 핫스팟 또는 공유기 화면의 IP를 사용합니다.
5. 사용자 이름이 실제 Imager 설정과 같은지 확인합니다.
6. `Connection refused`이면 Imager에서 SSH를 켰는지 확인합니다.
7. 최후에는 모니터와 키보드로 로그인해 `hostname -I`와 `sudo systemctl status ssh`를 확인합니다.

### 카메라가 인식되지 않습니다

1. `sudo bash /opt/refound/scripts/raspberry-pi/check-camera.sh`를 실행합니다.
2. 실패하면 `sudo shutdown -h now`로 끕니다.
3. 전원을 완전히 뽑습니다.
4. 은색 접점 방향, 케이블의 수평 상태와 잠금 탭을 다시 확인합니다.
5. 부팅 후 `rpicam-hello --list-cameras`를 실행합니다.
6. Legacy Camera를 켜거나 `raspistill`을 설치하지 마세요.

### `Camera busy` 또는 자원 사용 중이라고 나옵니다

Re:Found가 카메라를 사용하는 동안 다른 테스트 프로그램은 카메라를 열 수 없습니다. 제공된 `check-camera.sh`를 사용하세요. 수동 검사라면 다음 순서로만 실행합니다.

```bash
sudo systemctl stop refound.service
rpicam-hello --list-cameras
sudo systemctl start refound.service
```

### Tailscale 주소가 열리지 않습니다

Pi에서 다음을 확인합니다.

```bash
tailscale status
sudo tailscale serve status
curl http://127.0.0.1:8000/api/health
```

노트북에서도 Tailscale이 `Connected`이고 Pi와 같은 tailnet인지, ACL이 접근을 허용하는지 확인합니다. 장치 인증이 만료됐다면 Pi에서 다음을 실행해 다시 인증합니다.

```bash
sudo tailscale up --force-reauth
```

학교 Wi-Fi가 VPN을 차단하면 Pi와 노트북을 모두 본인 휴대전화 핫스팟에 연결합니다.

### 학교 Wi-Fi에 Pi가 연결되지 않습니다

브라우저 로그인 페이지, 교내 계정 인증 또는 WPA2-Enterprise가 필요한 학교망은 화면 없는 Raspberry Pi OS Lite에서 바로 쓰기 어렵습니다. 발표 당일 해결하려 하지 말고 본인 휴대전화 핫스팟을 사용하세요.

### 저장한 휴대전화 핫스팟에 Pi가 연결되지 않습니다

1. Pi를 켜기 전에 휴대전화 핫스팟을 먼저 켭니다.
2. 휴대전화의 자동 핫스팟 종료와 절전 모드를 끕니다.
3. SSID와 비밀번호가 저장할 때와 완전히 같은지 확인합니다.
4. 호환성/2.4GHz 모드를 켭니다.
5. 모니터와 키보드 또는 다른 저장 Wi-Fi로 Pi에 들어갈 수 있다면 다음을 확인합니다.

   ```bash
   nmcli dev wifi list
   nmcli -f NAME,TYPE,AUTOCONNECT connection show
   ```

6. 프로필이 없거나 비밀번호가 바뀌었다면 `sudo nmcli --ask dev wifi connect "ReFoundPhone"`으로 다시 저장하고 재부팅 시험을 반복합니다.

### `ReFound-Demo`에 연결했는데 인터넷이 없습니다

정상입니다. 이것은 Pi와 노트북을 직접 잇는 오프라인 비상망입니다. 웹은 `http://10.42.0.1:8000`으로 열고, AI와 이메일이 필요하면 핫스팟을 해제한 뒤 인터넷이 있는 Wi-Fi와 Tailscale로 돌아갑니다.

### 웹은 열리지만 AI 이름이 확정되지 않습니다

1. Pi에 인터넷이 있는지 확인합니다.
2. `.env`에 새 키가 저장됐는지 확인하되 키 자체를 화면에 출력하지 마세요.
3. 서비스 재시작 후 로그를 확인합니다.

```bash
sudo systemctl restart refound.service
sudo journalctl -u refound.service -n 100 --no-pager
```

API가 끊겨도 감지 증거와 물품 기록은 관리자 확인 대상으로 남을 수 있습니다. 같은 물건을 반복해서 놓아 중복 기록을 만들기보다 로그와 상세 화면을 먼저 확인하세요.

### 라이브뷰가 느리거나 Pi가 뜨겁습니다

```bash
free -h
vcgencmd measure_temp
vcgencmd get_throttled
```

- 공식 규격에 맞는 5V 3A 전원과 짧고 품질 좋은 케이블을 사용합니다.
- Pi 4에 방열판 또는 팬을 장착합니다.
- 다른 무거운 프로그램을 동시에 실행하지 않습니다.
- 앱을 여러 worker로 실행하지 않습니다.
- 설치 스크립트가 적용한 Pi 저부하 설정을 발표 직전에 무리하게 높이지 않습니다.

### 물체가 계속 흔들린 것으로 감지됩니다

- Pi와 카메라 케이블, 카메라 거치대를 단단히 고정합니다.
- 창문, 반사면, 모니터, 움직이는 그림자와 형광등 플리커를 감시 구역에서 줄입니다.
- 부팅 직후 카메라 노출과 초점이 안정될 때까지 기다립니다.
- 물건과 사람이 없는 안정된 상태에서 기준 화면을 다시 설정합니다.

---

## 14. 문제가 생겼을 때 복구 순서

아래 순서를 위에서부터 진행하고, 해결되면 그 지점에서 멈춥니다.

### 1단계: 브라우저만 새로 고침

`Ctrl+F5`를 누르고 10초 기다립니다.

### 2단계: 서비스 상태와 health 확인

```bash
sudo systemctl status refound.service --no-pager
curl http://127.0.0.1:8000/api/health
```

현재 `ReFound-Demo` 핫스팟 모드라면 위 health 주소만 `http://10.42.0.1:8000/api/health`로 바꿉니다.

### 3단계: 서비스 재시작

```bash
sudo systemctl restart refound.service
sleep 5
curl http://127.0.0.1:8000/api/health
```

현재 `ReFound-Demo` 핫스팟 모드라면 마지막 주소를 `http://10.42.0.1:8000/api/health`로 바꿉니다.

### 4단계: 오류 로그 보관

```bash
sudo journalctl -u refound.service -n 200 --no-pager
```

오류 문구를 사진으로 남기되 API 키가 화면에 표시되면 촬영하지 않습니다.

### 5단계: 네트워크 방식 복구

- 인터넷/Tailscale로 돌아갈 때: `sudo bash /opt/refound/scripts/raspberry-pi/remove-hotspot.sh`
- Tailscale 재설정: `sudo bash /opt/refound/scripts/raspberry-pi/setup-tailscale.sh`
- 인터넷이 전혀 없을 때: `sudo bash /opt/refound/scripts/raspberry-pi/setup-hotspot.sh`

### 6단계: Pi 재부팅

```bash
sudo reboot
```

2~3분 기다린 뒤 다시 접속합니다.

### 7단계: 데이터부터 백업

재설치나 microSD 초기화 전에는 먼저 데이터를 복사합니다. SQLite는 WAL 모드로 동작하므로 실행 중인 `data` 폴더를 그대로 복사하면 서로 다른 시점의 DB 파일이 섞일 수 있습니다.

먼저 Pi의 SSH 창에서 서비스를 멈춥니다.

```bash
sudo systemctl stop refound.service
```

그다음 Windows PowerShell에서 복사합니다. 주소는 현재 SSH에 사용하는 Pi 주소로 바꿉니다. 서로 다른 네트워크라면 Pi에서 미리 `tailscale ip -4`로 확인한 `100.x.x.x` 주소도 사용할 수 있습니다.

```powershell
New-Item -ItemType Directory -Force .\refound-pi-backup
scp -r refound@refound-pi.local:/opt/refound/data .\refound-pi-backup\
```

**복사가 성공했든 실패했든 반드시** Pi의 SSH 창으로 돌아가 서비스를 다시 시작합니다. 이 단계를 빠뜨리면 Re:Found가 계속 꺼진 상태로 남습니다.

```bash
sudo systemctl start refound.service
sleep 5
curl http://127.0.0.1:8000/api/health
```

핫스팟 모드라면 마지막 주소를 `http://10.42.0.1:8000/api/health`로 바꿉니다. `.env`에는 비밀 키가 있으므로 일반 백업 폴더나 클라우드에 함께 복사하지 않습니다.

### 8단계: 설치 스크립트 다시 실행

데이터 백업을 확인한 뒤 실행합니다.

```bash
cd /opt/refound
sudo bash scripts/raspberry-pi/install.sh
sudo systemctl restart refound.service
```

### 9단계: microSD 재작성은 마지막 수단

데이터 백업이 실제로 열리는지 확인한 뒤에만 2단계부터 다시 시작합니다. 백업하지 않은 상태에서 `data`를 지우거나 microSD를 다시 쓰지 마세요.

---

## 15. 설치 완료 판정표

아래 항목을 모두 확인하면 발표용 준비가 끝난 것입니다.

- [ ] Pi 전원과 냉각이 안정적이다.
- [ ] 카메라가 `check-camera.sh` 검사를 통과한다.
- [ ] `refound.service`가 `active (running)`이다.
- [ ] `/api/health`가 정상 응답한다.
- [ ] `.env` 권한이 `-rw-------`이다.
- [ ] 기존 노출 가능성이 있는 API 키를 폐기하고 새 키를 넣었다.
- [ ] 학교용 휴대전화 핫스팟을 Pi에 저장하고 그 상태로 재부팅 접속을 시험했다.
- [ ] 노트북과 Pi가 다른 네트워크에서도 Tailscale 주소로 연결된다.
- [ ] 노트북과 Pi가 같은 tailnet에 있고 ACL이 관리자 접근만 허용한다.
- [ ] Pi 장치를 외부 사용자에게 공유하지 않았다.
- [ ] Tailscale Funnel과 공유기 포트포워딩이 꺼져 있다.
- [ ] `ReFound-Demo` 오프라인 접속과 해제를 한 번 시험했다.
- [ ] 실제 물건 추가와 회수가 각각 3회 이상 성공했다.
- [ ] 카메라 이동 후 기준 화면을 다시 설정하는 방법을 알고 있다.
- [ ] 휴대전화 핫스팟, 충전기와 오프라인 주소를 준비했다.
- [ ] 서비스를 멈춘 상태에서 발표 전 데이터 백업을 만들고 서비스를 다시 시작했다.

---

## 공식 참고 자료

- [Raspberry Pi 시작 및 Imager 설정](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi Camera 연결](https://www.raspberrypi.com/documentation/accessories/camera.html)
- [Raspberry Pi 카메라 소프트웨어](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [Raspberry Pi OS NetworkManager와 Wi-Fi](https://www.raspberrypi.com/documentation/configuration/computers/raspberry-pi.html)
- [Raspberry Pi를 무선 핫스팟으로 사용](https://www.raspberrypi.com/documentation/configuration/wireless/wireless-access-point.md)
- [Tailscale Linux 설치](https://tailscale.com/docs/install/linux)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
