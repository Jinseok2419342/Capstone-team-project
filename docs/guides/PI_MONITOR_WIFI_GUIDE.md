# Raspberry Pi 모니터·키보드 현장 Wi-Fi 연결 가이드

이 문서는 Re:Found Raspberry Pi가 처음 보는 Wi-Fi나 Android 핫스팟에 연결되지 않을 때, **모니터와 USB 키보드로 Pi에 직접 로그인해 네트워크를 설정하는 방법**입니다.

새 microSD에는 먼저 [새 SD 설치 절차](FRESH_SD_START.md)를 적용합니다. 이 문서는 접속에 실패했을 때 펼치는 복구 안내이며 이전 카드의 Wi-Fi·계정이 새 카드에도 있다고 가정하지 않습니다.

현재 사용 중인 Raspberry Pi OS Lite는 일반적인 바탕화면 대신 검은색 문자 로그인 화면이 나타나는 것이 정상입니다.

---

## 가장 중요한 연결 방식

```text
Raspberry Pi 4의 micro-HDMI 0 ──micro-HDMI to HDMI──> 모니터의 HDMI 입력
Raspberry Pi 4의 USB 단자      ──USB────────────────> 키보드
Raspberry Pi 4의 USB-C 단자    <──────────────────── 전원 어댑터
```

micro-HDMI 케이블은 다음처럼 연결합니다.

- 작은 micro-HDMI 단자: Raspberry Pi 4
- 큰 HDMI 단자: 모니터 또는 TV의 `HDMI IN`
- Pi 4의 micro-HDMI 단자 두 개 중 **USB-C 전원 단자에 더 가까운 `HDMI0`** 사용 권장

> 노트북이나 데스크톱 본체의 HDMI 단자는 대부분 화면을 내보내는 **출력**입니다. Pi 화면을 받을 수 없습니다. 반드시 별도 모니터·TV의 HDMI 입력에 연결하세요. 노트북 화면을 꼭 써야 한다면 HDMI 캡처 장치가 별도로 필요합니다.

PC와 같은 모니터를 사용한다면 모니터의 남는 HDMI 입력에 Pi를 연결하고 `입력 소스`를 전환하면 됩니다. 남는 입력이 없으면 PC의 HDMI 케이블을 잠시 빼고 Pi를 연결해 설정한 뒤 되돌립니다. 일반 모니터에서는 PC 화면과 Pi 화면이 동시에 표시되는 것이 아니라 선택한 입력 하나만 보입니다.

---

## 1. 준비물

- Raspberry Pi 4와 기존 microSD 카드
- Pi용 정격 USB-C 전원 어댑터
- micro-HDMI to HDMI 케이블
- HDMI 입력이 있는 모니터 또는 TV
- USB 키보드
- 모바일 데이터가 가능한 Android 휴대전화
- 발표용 Windows 노트북

현재 계정 정보도 알고 있어야 합니다.

```text
사용자 이름: refound
비밀번호: Raspberry Pi Imager에서 처음 정한 비밀번호
```

핫스팟은 다음 값을 권장합니다.

```text
이름: ReFoundPhone
주파수: 2.4GHz
보안: WPA2-Personal 우선
숨겨진 네트워크: 끔
자동 종료: 끔
```

핫스팟 비밀번호는 문서나 발표 자료에 기록하지 않습니다.

---

## 2. 전원이 꺼진 상태에서 연결

Pi 전원이 이미 켜져 있고 SSH 접속이 가능하다면 먼저 다음 명령으로 종료합니다.

```bash
sudo shutdown -h now
```

30초 정도 기다리고 초록색 ACT LED가 멈춘 뒤 전원을 뽑습니다. 빨간 전원 LED는 전원선이 연결된 동안 계속 켜져 있을 수 있습니다.

이제 다음 순서로 연결합니다.

1. Pi 4의 USB-C 전원 단자 옆에 가까운 `HDMI0`에 micro-HDMI 단자를 꽂습니다.
2. 케이블의 큰 HDMI 단자를 모니터의 `HDMI IN`에 꽂습니다.
3. USB 키보드를 Pi의 USB 단자에 꽂습니다. 검은색이나 파란색 단자 어느 쪽이든 됩니다.
4. 모니터 전원을 켭니다.
5. 모니터의 입력 선택 버튼으로 케이블을 꽂은 `HDMI 1` 또는 `HDMI 2`를 선택합니다.
6. Android 모바일 데이터와 `ReFoundPhone` 핫스팟을 켭니다.
7. 마지막으로 Pi의 USB-C 전원을 연결합니다.

카메라 리본 케이블은 Pi 전원이 연결된 상태에서 만지거나 뽑지 않습니다.

---

## 3. 문자 로그인 화면

부팅하는 동안 여러 문장이 지나가거나 잠시 검은 화면이 나올 수 있습니다. 1~3분 기다리면 다음과 비슷한 화면이 나타납니다.

```text
Raspberry Pi OS GNU/Linux
refound-pi login:
```

`login:` 뒤에 다음 사용자 이름을 입력하고 `Enter`를 누릅니다.

```text
refound
```

다음으로 비밀번호를 묻습니다.

```text
Password:
```

Raspberry Pi Imager에서 정한 Pi 로그인 비밀번호를 입력하고 `Enter`를 누릅니다.

> 비밀번호를 입력해도 화면에는 글자, 점 또는 별표가 전혀 나타나지 않습니다. 키보드 입력이 안 되는 것이 아니라 Linux의 정상적인 보안 동작입니다.

로그인에 성공하면 다음과 비슷한 줄이 나타납니다.

```text
refound@refound-pi:~ $
```

이제 명령을 입력할 수 있습니다.

자동 로그인이 설정된 Pi라면 `login:` 질문 없이 바로 `refound@refound-pi:~ $`가 나타날 수도 있습니다. 이 경우 다시 로그인할 필요 없이 명령을 입력하면 됩니다.

---

## 4. Android 핫스팟 찾기

아래 명령은 **Pi에 연결한 키보드**로 한 줄씩 입력합니다.

먼저 Wi-Fi 기능 상태를 확인합니다.

```bash
nmcli radio wifi
```

`disabled`라고 나오면 다음 명령으로 켭니다.

```bash
sudo nmcli radio wifi on
```

이제 주변 네트워크를 다시 검색합니다.

```bash
nmcli dev wifi rescan
```

잠시 기다린 뒤 목록을 봅니다.

```bash
nmcli -f IN-USE,SSID,SIGNAL,SECURITY dev wifi list
```

목록에서 `ReFoundPhone`을 찾습니다.

보이지 않으면 다음을 확인합니다.

1. Android 모바일 데이터가 켜져 있습니다.
2. Android 핫스팟이 켜져 있습니다.
3. 핫스팟 주파수가 2.4GHz입니다.
4. 숨겨진 네트워크가 꺼져 있습니다.
5. Pi와 휴대전화가 너무 멀리 떨어져 있지 않습니다.

확인 후 위의 두 명령을 다시 실행합니다.

---

## 5. 핫스팟에 연결

`ReFoundPhone`이 보이면 실행합니다.

```bash
sudo nmcli --ask dev wifi connect "ReFoundPhone"
```

이 과정에서 비밀번호를 최대 두 번 물을 수 있습니다.

### 첫 번째 비밀번호

```text
[sudo] password for refound:
```

이것은 **Pi 로그인 비밀번호**입니다.

### 두 번째 비밀번호

```text
Password (802-11-wireless-security.psk):
```

이것은 **Android 핫스팟 비밀번호**입니다.

두 비밀번호 모두 입력하는 동안 화면에 아무 글자도 나타나지 않을 수 있습니다. 정확히 입력하고 `Enter`를 누릅니다.

성공하면 다음과 비슷한 문장이 나옵니다.

```text
Device 'wlan0' successfully activated with '...'.
```

모니터와 키보드로 직접 작업 중이므로 Wi-Fi가 변경돼도 현재 화면은 끊기지 않습니다.

---

## 6. 연결과 자동 접속 확인

현재 활성 연결을 확인합니다.

```bash
nmcli -t -f NAME,DEVICE connection show --active
```

다음과 비슷한 줄이 있으면 정상입니다.

```text
ReFoundPhone:wlan0
```

저장된 Wi-Fi 연결 이름도 확인합니다.

```bash
nmcli -f NAME,TYPE,AUTOCONNECT,DEVICE connection show
```

연결 이름이 정확히 `ReFoundPhone`이면 다음을 실행합니다.

```bash
sudo nmcli connection modify "ReFoundPhone" connection.autoconnect yes connection.autoconnect-priority 50
```

목록에 `ReFoundPhone 1`처럼 다른 이름이 표시되면 명령의 따옴표 안에도 그 실제 이름을 사용합니다.

이 설정을 하면 다음 부팅 때 핫스팟이 보일 경우 Pi가 자동으로 연결합니다.

---

## 7. 인터넷·Tailscale·Re:Found 확인

다음 명령을 한 줄씩 실행합니다.

```bash
tailscale status
```

```bash
sudo tailscale serve status
```

```bash
sudo systemctl status refound.service --no-pager
```

```bash
curl --fail http://127.0.0.1:8000/api/health
```

정상 기준은 다음과 같습니다.

- `tailscale status`에 이 Pi가 연결된 상태로 나옵니다.
- Serve 상태에 이 Pi의 실제 HTTPS 주소가 나옵니다. 새 SD에서는 이전 주소와 달라질 수 있습니다.
- `refound.service`가 `active (running)`입니다.
- health 응답의 `ok`가 `true`이고 DB·카메라가 정상입니다. `bash /opt/refound/scripts/raspberry-pi/check-system.sh`로 함께 확인합니다.

기존 Tailscale Serve 설정은 Wi-Fi를 바꿔도 유지됩니다. 위 항목이 정상이면 `setup-tailscale.sh`를 다시 실행하지 않습니다.

---

## 8. Windows 노트북에서 관리자 웹 열기

학교에서 가장 단순한 구성은 노트북도 같은 `ReFoundPhone`에 연결하는 것입니다.

1. Windows 노트북의 Wi-Fi를 `ReFoundPhone`에 연결합니다.
2. Windows 작업 표시줄에서 Tailscale을 엽니다.
3. 상태가 `Connected`인지 확인합니다.
4. 브라우저에서 `sudo tailscale serve status`에 표시된 이 Pi의 실제 HTTPS 주소를 엽니다. 이전 SD의 북마크를 그대로 사용하지 않습니다.

5. 카메라 라이브뷰가 나오는지 확인합니다.
6. 감지 상태가 잠시 후 **변화를 기다리는 중**으로 바뀌는지 확인합니다.

여기까지 되면 모니터와 키보드에서 더 설정할 것은 없습니다.

---

## 9. 자동 연결 재부팅 시험

Android 모바일 데이터와 핫스팟을 계속 켜 둔 상태에서 Pi에 입력합니다.

```bash
sudo reboot
```

화면이 꺼졌다가 다시 부팅되는 동안 2~3분 기다립니다. 다시 로그인하지 않아도 Re:Found와 Tailscale은 자동으로 시작합니다.

노트북에서 다음만 확인합니다.

1. Android의 연결 기기 목록에 `refound-pi`가 있습니다.
2. Windows Tailscale이 `Connected`입니다.
3. 기존 관리자 주소가 열립니다.
4. 라이브뷰가 정상입니다.

이 시험에 성공하면 이후에는 모니터와 키보드를 연결하지 않아도 됩니다.

---

## 10. 학교에서 핫스팟을 처음 설정하는 경우

집에서 핫스팟을 저장하지 못했어도 지금 준비한 모니터와 키보드가 있으면 학교에서 설정할 수 있습니다.

현장 순서는 다음과 같습니다.

```text
Pi 전원 꺼짐
→ Pi를 모니터 HDMI 입력과 USB 키보드에 연결
→ Android 모바일 데이터·2.4GHz 핫스팟 켜기
→ Pi 전원 연결
→ refound 계정 로그인
→ nmcli로 ReFoundPhone 연결
→ Tailscale·서비스 상태 확인
→ 노트북도 ReFoundPhone 연결
→ Tailscale Connected 확인
→ 관리자 HTTPS 주소 열기
```

네트워크가 연결된 뒤에는 다음 작업도 학교에서 이어서 할 수 있습니다.

- 관리자 웹의 카메라 기준 화면 재설정
- 운영 데이터 초기화
- AI 제공자와 모델 변경
- SSH 또는 로컬 터미널에서 `.env` API 키 변경
- 서비스 재시작과 로그 확인

다만 발표 당일 처음 API 키나 감지 민감도를 바꾸는 것은 권장하지 않습니다. 네트워크만 연결하고, 이미 집에서 검증한 설정을 그대로 사용하는 편이 안전합니다. 관객이 모니터를 볼 수 있는 상태에서 `nano /opt/refound/.env`를 열면 API 키가 노출될 수 있으므로 키 편집은 집이나 비공개된 시간에만 합니다.

---

## 11. 자주 생기는 문제

### 모니터에 `신호 없음`만 표시됨

1. HDMI 케이블이 PC 본체가 아닌 **모니터의 HDMI 입력**에 연결됐는지 확인합니다.
2. 모니터 입력이 올바른 `HDMI 1` 또는 `HDMI 2`인지 확인합니다.
3. Pi에서는 USB-C 전원 단자에 가까운 `HDMI0`을 사용합니다.
4. Pi 전원 LED가 켜졌는지 확인합니다.
5. 전원을 안전하게 끈 뒤 케이블을 다시 꽂고 부팅합니다.

화면이 절전으로 까맣게 변한 것 같으면 키보드의 `Shift` 또는 `Enter`를 한 번 누릅니다.

### 부팅 문장은 보였지만 로그인 화면이 안 나옴

먼저 3분 기다립니다. 그래도 나오지 않으면 키보드에서 다음을 누릅니다.

```text
Ctrl + Alt + F2
```

다른 문자 콘솔의 로그인 화면이 나타날 수 있습니다.

### 비밀번호가 입력되지 않는 것처럼 보임

정상입니다. Linux 비밀번호 입력은 화면에 아무것도 표시하지 않습니다. 다음 두 비밀번호를 구분하세요.

- `login:` 다음: 사용자 이름 `refound`
- `Password:` 또는 sudo 질문: Pi 로그인 비밀번호
- Wi-Fi 연결 중 PSK 질문: Android 핫스팟 비밀번호

### 핫스팟 이름이 안 보임

Android에서 2.4GHz, 숨김 끔, 자동 종료 끔을 확인하고 실행합니다.

```bash
sudo nmcli radio wifi on
nmcli dev wifi rescan
nmcli dev wifi list
```

그래도 전혀 보이지 않을 때만 다음 메뉴에서 WLAN 국가가 `KR`인지 확인합니다.

```bash
sudo raspi-config
```

`Localisation Options → WLAN Country → KR`을 선택한 뒤 종료합니다.

### 핫스팟 비밀번호를 바꿔 연결이 실패함

저장된 `ReFoundPhone` 연결만 지우고 다시 등록할 수 있습니다.

```bash
sudo nmcli connection delete "ReFoundPhone"
sudo nmcli --ask dev wifi connect "ReFoundPhone"
```

이 명령은 `ReFoundPhone`이라는 저장 Wi-Fi 프로필만 삭제합니다. 다른 Wi-Fi와 Re:Found 데이터는 삭제하지 않습니다.

`Secrets were required, but not provided`와 비슷한 오류는 대부분 핫스팟 비밀번호 오타 또는 보안 방식 호환 문제입니다. Android 보안을 WPA2-Personal로 두고 다시 시도합니다.

### Wi-Fi는 연결됐지만 웹이 안 열림

Pi에서 확인합니다.

```bash
tailscale status
sudo tailscale serve status
sudo systemctl status refound.service --no-pager
curl --fail http://127.0.0.1:8000/api/health
```

노트북에서도 Tailscale이 `Connected`인지 확인합니다. Tailscale만 작동하지 않을 때 쓸 SSH 터널 방법은 [학교 시연 운영 가이드](SCHOOL_DEMO_GUIDE.md#tailscale만-안-될-때-쓰는-안전한-비상-접속)에 있습니다.

Android의 연결 기기 이름이 `refound-pi`가 아니라 `Unknown`으로 표시되는 기종도 있습니다. 이 경우 새로 나타난 기기의 IP 또는 MAC 주소를 함께 확인합니다.

---

## 12. 설정 후 안전하게 전원 끄기

Pi 화면에서 입력합니다.

```bash
sudo shutdown -h now
```

화면이 꺼진 뒤 30초 정도 기다리고 초록색 ACT LED가 멈추면 전원을 뽑습니다.

다음 시연부터는 아래 순서만 따르면 됩니다.

```text
Android 모바일 데이터와 ReFoundPhone 핫스팟 켜기
→ Pi 전원 연결
→ 2~3분 대기
→ 노트북 Tailscale Connected 확인
→ 새 Pi의 tailscale serve status에서 확인한 HTTPS 주소 열기
```

---

## 공식 참고 자료

- [Raspberry Pi 설정과 주변기기 연결](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi 무선 네트워크 설정](https://www.raspberrypi.com/documentation/computers/configuration.html#connect-to-a-wireless-network)
- [NetworkManager nmcli 예제](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli-examples.html)
- [Tailscale Serve 명령](https://tailscale.com/docs/reference/tailscale-cli/serve)
