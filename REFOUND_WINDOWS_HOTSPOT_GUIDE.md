# Re:Found — 노트북 핫스팟 실행·종료·문제 해결 총정리

작성일: **2026-09-29**

**2026-09-30 사용자 재확인:** 2절의 실행 7단계·3절의 종료 4단계·4절의 이름 오류 대응 5단계를 최종 시연 사용 순서로 다시 확인했습니다. `START_HERE.md`와 `AGENTS.md`에도 이 기준을 반영했습니다. 이번 확인은 사용 절차의 확정이며, 아래 미확인으로 남은 전원 재인가 시험 결과가 새로 보고된 것은 아닙니다.

이 문서 하나에 현재 사용하는 연결 방식, 매번 실행·종료하는 순서, 접속 오류 대응, 이번에 설정한 과정과 남은 확인을 정리했습니다.

**백업 범위:** 9월 29일의 친구 노트북·핫스팟 접속 문제부터 웹 화면·OpenAI API 동작 성공 보고, 이후 사용자가 정리한 실행 7단계·종료 4단계·이름 오류 대응 5단계까지 대화와 대조했습니다. **이 파일만 복사해 보관해도 해당 과정과 사용법을 읽을 수 있도록** 필요한 명령·관찰 결과를 본문에 담았습니다. 다른 문서와 공식 문서 링크는 추가 참고용입니다.

평소에는 **2절 실행 → 3절 종료**, 이름으로 접속되지 않으면 **4절**, 다른 오류는 **5절**을 봅니다. **6~7절은 초기 설정과 문제 해결 경과**이므로 매번 반복하지 않습니다. 비밀번호·API 키의 실제 값은 백업하지 않으며, 비밀번호를 입력해야 하는 위치와 종류를 구분해 적었습니다.

**현재 확인한 결과:** Pi의 `ReFoundLaptop` 연결 활성화 로그를 확인했고, 사용자가 노트북에서 웹 화면 접속과 OpenAI API 동작에 성공했다고 보고했습니다. **새 구성에서 전원을 껐다 켠 뒤의 자동 연결·재접속은 아직 확인하지 않았습니다.**

## 1. 현재 사용하는 구성

```text
학교·집 Wi-Fi의 인터넷
        ↓
Windows 노트북
        ├─ 모바일 핫스팟 ReFoundLaptop → Raspberry Pi
        └─ PowerShell SSH 터널 → 같은 노트북의 브라우저
```

| 항목 | 현재 사용하는 값·방법 |
|---|---|
| Pi 장비 | Raspberry Pi 4 Model B 2GB + CSI 카메라, 기존 앱 설치 유지 |
| 노트북 핫스팟 이름 | `ReFoundLaptop` |
| 핫스팟 비밀번호 | 노트북과 Pi에 저장한 값을 유지. 이 문서에는 기록하지 않음 |
| Pi 로그인 계정 | `refound` |
| Pi 이름 | `refound-pi.local` |
| 확인 당시 Pi IP | `192.168.137.243` — 다음 접속 때 바뀔 수 있음 |
| 노트북 브라우저 주소 | `http://127.0.0.1:18000` |
| Pi 내부 앱 주소 | `http://127.0.0.1:8000` |
| 앱 자동 실행 서비스 | `refound.service` |

현재 방법은 일반 SSH 터널을 사용하므로 Tailscale 접속이 선행 조건은 아닙니다. 외부 AI 분석에는 Pi까지 인터넷이 공유돼야 합니다.

노트북은 Pi의 웹 화면을 여는 역할을 합니다. 이 방식으로 접속하려고 **노트북에 Re:Found 앱을 새로 설치하거나 `setup.ps1`·`start.ps1`을 실행할 필요는 없습니다.** 앱과 카메라는 Pi에서 실행됩니다.

### 명령을 입력할 창과 비밀번호 구분

| 보이는 표시·질문 | 의미·입력할 내용 |
|---|---|
| `PS C:\Users\...>` | 노트북의 PowerShell. 웹 접속용 `ssh -L ...` 명령을 시작할 곳 |
| `refound@refound-pi:~ $` | Pi에 로그인된 터미널. `nmcli`, `systemctl`, `sudo shutdown ...`을 실행할 곳 |
| `refound@... password:` | **Pi 로그인 비밀번호**. Pi를 처음 설치할 때 정한 값 |
| `[sudo] password for refound:` | 역시 **Pi 로그인 비밀번호** |
| `nmcli --ask`의 Wi-Fi `Password` 질문 | **노트북 핫스팟 비밀번호** |

Pi 비밀번호를 입력할 때 글자·점·별표가 보이지 않아도 정상입니다. 입력 후 Enter를 누릅니다. 명령은 코드 블록 안의 내용만 복사합니다. `PS C:\...>`나 `refound@refound-pi:~ $` 표시, 채팅의 `mailto:` 링크, 주소 앞의 역슬래시를 함께 붙여넣지 않습니다.

## 2. 매번 실행하는 순서

1. **노트북을 학교 Wi-Fi에 연결합니다.** 브라우저에서 인터넷이 되는지 확인하고, 학교 Wi-Fi에 별도 로그인이 필요하면 완료합니다. 집에서는 인터넷이 되는 집 Wi-Fi를 사용해도 됩니다.
2. **노트북의 `ReFoundLaptop` 모바일 핫스팟을 켭니다.** 설정 → 네트워크 및 인터넷 → 모바일 핫스팟에서 켜고, 이름·비밀번호는 기존 값으로 유지합니다.
3. **Pi 전원을 연결합니다.** 노트북 핫스팟을 먼저 켜두는 순서입니다.
4. **약 2~3분 기다립니다.** 윈도우 핫스팟의 연결된 장치에 Pi가 나타나는지 확인합니다.
5. **노트북에서 PowerShell 새 창을 엽니다.** 명령을 입력하기 전 줄이 `PS C:\Users\...>`로 시작해야 합니다.
6. **아래 명령을 입력하고 Pi 로그인 비밀번호로 로그인합니다.**

   ```powershell
   ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local
   ```

   처음 접속하는 이름·IP라면 `Are you sure you want to continue connecting ...?` 질문이 먼저 나올 수 있습니다. 확인 방법은 5절의 SSH 첫 접속 설명을 따릅니다. 로그인 뒤에는 `refound@refound-pi:~ $`로 바뀌는 것이 정상입니다. **이 PowerShell 창은 계속 열어두세요.**

7. **같은 노트북의 Chrome 또는 Edge 주소창에 입력합니다.**

   ```text
   http://127.0.0.1:18000
   ```

화면이 열리면 실제 카메라 영상과 필요한 물품의 AI 처리를 확인합니다. 사용 중에는 노트북 핫스팟과 SSH 창을 유지하고, 노트북이 절전 상태에 들어가지 않도록 합니다.

### 따로 일반 SSH 접속을 먼저 할 필요가 있나요?

아래 명령을 별도로 먼저 실행할 필요는 없습니다.

```powershell
ssh -o ConnectTimeout=10 refound@refound-pi.local
```

6번의 `-L`이 포함된 명령이 **SSH 로그인과 웹 접속용 터널 생성**을 함께 합니다. 위 일반 SSH 명령은 Pi의 설정이나 상태만 확인할 때 사용할 수 있습니다.

### 자동으로 되는 것과 매번 해야 하는 것

| 구분 | 동작 |
|---|---|
| Pi Wi-Fi | 저장된 프로필의 자동 연결이 켜져 있고 핫스팟이 보이면 연결 시도. 새 구성의 부팅 시험은 아직 남음 |
| Pi 앱 | 설치 때 부팅 자동 실행을 설정했고, 9월 22일 재부팅 후 실행을 확인함 |
| Wi-Fi 정보·API 키 | 매번 새로 입력할 필요 없음 |
| 노트북 핫스팟 | 매번 켜져 있는지 확인 |
| SSH 터널 | Pi 재부팅이나 SSH 창 종료 후 다시 실행 |
| 웹 화면 | 노트북 브라우저에서 위 주소 열기 |

## 3. 종료하는 순서

1. 물품 조작과 진행 중인 AI 처리가 끝날 때까지 기다립니다.
2. **Pi에 로그인된 창**에서 아래 명령을 실행합니다. 줄이 `refound@refound-pi:~ $`로 표시된 창입니다.

   ```bash
   sudo shutdown -h now
   ```

3. **Pi가 정상 종료된 뒤 전원을 분리합니다.** SSH가 끊겼다고 바로 전원을 뽑지 마세요. Pi 4의 **초록 ACT LED가 종료 시 점멸을 마치고 멈출 때까지** 기다립니다. 빨간 전원 LED는 전원이 연결돼 있는 동안 남아 있을 수 있습니다.
4. 그다음 **노트북 핫스팟을 끕니다.**

앱에 처리 중인 작업이 있으면 종료에 몇 분 걸릴 수 있습니다. 현재 서비스의 종료 대기는 최대 300초로 설정돼 있습니다. 정상 종료는 물품·설정·API 키를 초기화하는 작업이 아닙니다. [Raspberry Pi 공식 종료 안내](https://www.raspberrypi.com/documentation/computers/getting-started.html#shutdown-options)

다음에 사용할 때는 다시 **2절의 실행 순서**를 따르면 됩니다.

## 4. `Could not resolve hostname` 오류가 뜰 때

`refound-pi.local`은 Pi를 찾는 이름이고, `192.168.…`은 그때 Pi에 배정된 숫자 주소입니다. 이름으로 찾지 못하면 **현재 IP 주소로 접속**합니다.

1. 노트북에서 **설정 → 네트워크 및 인터넷 → 모바일 핫스팟 → 연결된 장치**로 이동합니다.
2. **Pi 항목의 현재 IP 주소**를 확인합니다. 노트북 자신의 주소를 사용하지 않습니다.
3. SSH 명령의 **`@` 뒤에 있는 `refound-pi.local`만 현재 Pi IP로 바꿉니다.**
4. 예를 들어, 목록의 Pi IP가 실제로 `192.168.137.243`이라면 **노트북 PowerShell**에서 다음처럼 실행합니다.

   ```powershell
   ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@192.168.137.243
   ```

5. Pi 로그인 비밀번호를 입력하고 창을 유지한 뒤, 브라우저에서 기존 주소를 엽니다.

   ```text
   http://127.0.0.1:18000
   ```

**바꾸는 것은 `@` 뒤의 Pi 주소뿐입니다.** 명령 중간의 `18000:127.0.0.1:8000`과 브라우저 주소는 그대로 유지합니다.

앞의 `18000`은 노트북에서 접속할 포트이고, 뒤의 `127.0.0.1:8000`은 SSH로 연결한 Pi 내부 앱 주소입니다. 브라우저의 `127.0.0.1:18000`은 지금 브라우저를 실행한 노트북을 가리킵니다. 그래서 터널을 Pi 내부에서 시작하면 노트북 브라우저로 열리지 않았던 것입니다.

`192.168.137.243`은 9월 29일 확인한 주소이며 고정 주소로 설정한 것은 아닙니다. 주소가 달라져도 Pi를 재설치하거나 Wi-Fi 프로필을 다시 만들 필요는 없습니다. [Raspberry Pi 공식 IP·SSH 접속 안내](https://www.raspberrypi.com/documentation/computers/remote-access.html#connect-to-an-ssh-server)

## 5. 다른 문제가 생겼을 때

| 증상 | 먼저 할 일 |
|---|---|
| 윈도우 핫스팟 목록에 Pi가 없음 | 노트북 핫스팟 켜짐, 이름·비밀번호 유지, Pi 전원과 부팅 대기 시간을 확인합니다. 선택 가능하면 대역을 2.4GHz로 설정합니다. 기존 `s24+` 휴대폰 핫스팟에 붙지 않도록 시험 중에는 그 핫스팟을 꺼둡니다. |
| `Connection timed out` / `Connection refused` | 현재 Pi IP로 시도했는지 확인하고 오류 전체를 남깁니다. Wi-Fi 연결과 SSH 상태를 확인해야 하며, 이름 변경만으로 해결된다고 단정하지 않습니다. |
| `Permission denied` | 핫스팟 비밀번호가 아니라 **Pi 로그인 비밀번호**를 입력했는지 확인합니다. |
| `Address already in use` / `cannot listen to port: 18000` | 노트북에 이전 터널 창이 열려 있는지 확인합니다. 기존 터널을 사용하거나 그 창을 닫은 뒤 새로 실행합니다. 다른 프로그램이 사용하는 포트라면 오류를 남겨 확인합니다. |
| SSH 로그인은 되는데 웹이 안 열림 | 터널 명령을 **노트북의 새 PowerShell에서 시작했는지**, 창이 계속 열려 있는지 확인합니다. 아래 앱 상태 확인 명령을 사용할 수 있습니다. |
| `client_loop: send disconnect: Connection reset` | SSH 연결이 끊어진 것입니다. Wi-Fi 전환·핫스팟 종료·Pi 종료 등 여러 원인이 있을 수 있습니다. 현재 Pi가 노트북 핫스팟에 연결됐는지 확인하고 노트북에서 터널을 다시 엽니다. |
| `unknown connection 'ReFoundLaptop'` | 보이는 Wi-Fi 이름과 Pi에 저장된 연결 프로필은 별개입니다. 아래 연결 목록을 확인하고, 저장된 프로필이 없으면 6절의 직접 연결 명령으로 연결·저장합니다. |
| 화면은 열리는데 AI만 안 됨 | 노트북의 상위 인터넷, Pi에 대한 인터넷 공유, 앱의 AI 오류를 확인합니다. 화면이 열린 사실만으로 외부 API 성공까지 확인되지는 않습니다. |

### SSH 첫 접속 확인창

이번 대화에서 실제로 다음 질문이 나왔습니다.

```text
The authenticity of host 'refound-pi.local (192.168.137.243)' can't be established.
ED25519 key fingerprint is SHA256:aqKxlxbP3bZS4IePMOvlMSCuInFnPDjMHKNvxlmx2pk.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

이것은 처음 접속하는 이름·IP의 서버 키를 확인하는 질문입니다. 이미 확인한 해당 Pi의 지문과 일치하면 `yes`를 입력하고 Enter를 누른 뒤 Pi 로그인 비밀번호를 입력합니다. 위 지문은 **9월 29일 전달받은 출력**이며 영구히 고정된 보증값은 아닙니다.

현재 Pi의 지문을 따로 확인해야 한다면, Pi에 직접 연결한 터미널이나 이미 신뢰할 수 있는 Pi 접속 창에서 다음 읽기 전용 명령을 실행해 비교할 수 있습니다.

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

지문이 다르면 접속 대상이나 재설치 여부부터 확인합니다. 이번 기록에는 키 검사를 끄거나 기존 키 기록을 일괄 삭제하는 절차를 넣지 않았습니다. [OpenSSH 서버 키 확인 안내](https://man.openbsd.org/ssh.1#VERIFYING_HOST_KEYS)

### 웹이 안 열릴 때 앱 상태 확인

아래는 **Pi에 로그인된 창**에서 하나씩 실행합니다.

```bash
systemctl is-active refound.service
```

```bash
curl --fail --max-time 10 http://127.0.0.1:8000/api/health
```

첫 명령의 정상 기준은 `active`, 두 번째는 앱의 JSON 응답입니다. 오류가 나오면 명령과 출력 내용을 함께 남깁니다.

### Pi가 노트북 핫스팟을 찾는지 확인

**Pi에 SSH 또는 모니터·키보드로 접속 가능한 경우**에 실행합니다.

```bash
nmcli device status
```

```bash
sudo nmcli -f IN-USE,SSID,SIGNAL,SECURITY device wifi list ifname wlan0 --rescan yes
```

`ReFoundLaptop`이 보이는 것은 무선 검색 성공이고, `wlan0`가 `connected`이며 연결 이름이 `ReFoundLaptop`인 것은 실제 연결 상태입니다.

저장된 연결 목록을 확인할 때는 다음을 사용합니다.

```bash
sudo nmcli -f NAME,UUID,TYPE connection show
```

목록에 `ReFoundLaptop` 프로필이 있고 노트북 핫스팟도 켜져 있다면, **Pi 창에서** 아래 명령으로 저장된 연결을 활성화할 수 있습니다.

```bash
sudo nmcli connection up "ReFoundLaptop" ifname wlan0
```

이번 대화에서는 이 명령이 `unknown connection 'ReFoundLaptop'`로 실패했고, 이후 6절의 `device wifi connect`로 성공했습니다. 동일 오류가 나온다고 기존 `s24+` 설정을 삭제하거나 Wi-Fi·SD 설치를 처음부터 반복할 필요는 없습니다.

SSH 접속 자체가 안 되는 상태에서는 Pi용 명령을 노트북 PowerShell에 그대로 입력할 수 없습니다. 기존에 연결되던 `s24+`를 다시 켜고 노트북도 그 네트워크에 연결해 SSH를 복구하거나, Pi에 별도 모니터·USB 키보드를 연결해야 합니다. 복구되면 위 상태·검색 결과부터 확인합니다.

## 6. 처음 설정할 때 진행한 방법 — 매번 반복하지 않음

**현재 Pi는 연결에 성공했으므로 이 절의 연결 생성 명령을 다시 실행할 필요가 없습니다.** 새 장치 설정이나 실제 연결 정보가 사라졌을 때 참고하는 절입니다.

### Windows 노트북 핫스팟 준비

인터넷이 되는 Wi-Fi에 노트북을 연결하고, 설정 → 네트워크 및 인터넷 → 모바일 핫스팟에서 아래처럼 설정합니다.

| 항목 | 설정 |
|---|---|
| 인터넷 연결 공유 원본 | Wi-Fi |
| 공유 방식 | Wi-Fi |
| 네트워크 이름 | `ReFoundLaptop` |
| 비밀번호 | 직접 정한 8자리 이상 비밀번호 |
| 대역 | 선택 가능하면 2.4GHz |

Windows 기본 모바일 핫스팟에는 비밀번호가 필요합니다. Pi에 처음 저장돼 있던 **비밀번호 없는 `s24+`**와는 다른 연결 정보를 저장해야 했습니다. [Windows 공식 핫스팟 설정](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/use-your-windows-device-as-a-mobile-hotspot), [비밀번호 규격](https://learn.microsoft.com/en-us/uwp/api/windows.networking.networkoperators.networkoperatortetheringaccesspointconfiguration.passphrase)

### 초기 설정 중 노트북의 Wi-Fi를 바꿔가며 진행한 순서

사용자는 노트북에 Wi-Fi 등이 연결돼 있어야 윈도우 핫스팟을 설정할 수 있다고 보고했습니다. 이에 **설정을 먼저 만들고, 기존 `s24+`로 잠깐 돌아가 Pi에 새 정보를 저장하는 방법**을 안내했습니다.

1. 노트북을 인터넷이 되는 Wi-Fi에 연결하고 `ReFoundLaptop`의 이름·비밀번호를 설정합니다.
2. 노트북을 기존 비밀번호 없는 **휴대폰 `s24+`**에 연결합니다. Pi도 기존 `s24+`에 붙어 있을 때 일반 SSH 명령으로 접속합니다.

   ```powershell
   ssh -o ConnectTimeout=10 refound@refound-pi.local
   ```

3. 짧게라도 SSH가 유지될 때 Pi에 새 연결 정보를 저장합니다. 이때 노트북 핫스팟이 꺼져 있다면 **프로필 저장만** 할 수 있고, 아래의 직접 연결 명령은 핫스팟이 켜지고 검색돼야 사용할 수 있습니다.
4. 저장 성공을 확인한 뒤 노트북을 학교·집 Wi-Fi로 다시 연결하고, **노트북의 `ReFoundLaptop` 핫스팟을 켭니다.** 상위 Wi-Fi를 바꾼 뒤 모바일 핫스팟이 계속 켜져 있는지도 확인합니다.
5. 새 핫스팟을 켠 다음 기존 **휴대폰 `s24+` 핫스팟을 끄고**, Pi가 새 핫스팟에 나타나는지 확인합니다. 저장 성공만으로 실제 연결까지 완료됐다고 판단하지 않습니다.

위 과정에서 `connection add`는 성공했지만 실제 자동 연결은 확인되지 않았고, 아래 7절의 후속 진단·직접 연결로 최종 성공했습니다. 이 초기 설정 과정을 매번 재현할 필요는 없습니다.

### Pi에 연결 정보를 저장하고 활성화

기존 네트워크를 통한 SSH 또는 Pi에 직접 연결한 모니터·키보드로 로그인한 상태에서 설정합니다. 아래 명령을 쓸 때는 **노트북 핫스팟이 켜져 있고 Pi에서 검색돼야 합니다.**

```bash
sudo nmcli --ask device wifi connect "ReFoundLaptop" ifname wlan0 name "ReFoundLaptop"
```

이 문서의 명령은 비밀번호를 따로 묻는 방식입니다. `[sudo] password for refound:`에는 **Pi 로그인 비밀번호**, Wi-Fi `Password` 질문에는 **노트북 핫스팟 비밀번호**를 입력합니다. 당시에는 같은 작업을 비밀번호 인자를 넣은 명령으로 수행했습니다. 비밀값은 기록하지 않습니다.

성공 시 다음과 같은 출력이 나옵니다. Wi-Fi가 전환되면 기존 SSH가 끊길 수 있으며, 그 뒤 노트북 핫스팟의 연결된 장치 목록과 새 SSH 접속으로 확인합니다.

```text
Device 'wlan0' successfully activated with '7cd76ca8-c636-49e0-98ab-581153a2c91b'.
```

새로 생성하는 연결의 UUID는 달라집니다. 위 UUID는 **이번에 실제 성공한 연결**의 값입니다. [NetworkManager 연결 명령](https://www.networkmanager.dev/docs/api/latest/nmcli.html)

### 자동 연결·자동 실행을 한 번 확인

다음은 **이번 연결 UUID를 기준으로** Pi 창에서 실행하도록 안내한 명령입니다. 실행 결과는 아직 별도로 전달받지 않았습니다.

```bash
sudo nmcli connection modify uuid 7cd76ca8-c636-49e0-98ab-581153a2c91b connection.autoconnect yes connection.autoconnect-priority 100
```

```bash
systemctl is-enabled refound.service
```

첫 명령은 오류 없이 완료돼야 하고, 두 번째는 `enabled`가 정상 기준입니다. UUID를 찾지 못하면 아래 목록에서 현재 연결을 확인하고, 생성 명령을 무작정 반복하지 않습니다.

```bash
nmcli -f NAME,UUID,AUTOCONNECT,DEVICE connection show
```

자동 연결 우선순위를 높여도 이미 유지 중인 다른 Wi-Fi를 즉시 끊고 옮기지는 않습니다. 기존 `s24+`가 끊기거나 다음 부팅 때 새 연결을 선택할 수 있도록 한 설정입니다. [NetworkManager 자동 연결 설명](https://www.networkmanager.dev/docs/api/latest/settings-connection.html)

## 7. 이번 연결 과정에서 확인한 내용

| 단계 | 진행 내용·결과 |
|---|---|
| 기존 상태 | 9월 22일 Pi 설치·카메라 검사·앱 자동 실행과 본인 PC Tailscale 접속을 확인한 기록이 있었음. 친구 Tailscale 접속은 미확인 |
| 휴대폰 핫스팟 | Pi에 비밀번호 없는 `s24+`가 저장돼 있었고 실제로 연결됐다고 사용자가 설명함. 데이터 사용량은 조금 늘었으나 Tailscale에서 연결됐다고 보이지 않는다고 보고함. 이어서 핫스팟 자체가 간헐적으로 끊겨 SSH도 가끔만 된다고 설명함. 정확한 원인은 미확인 |
| 연결 방법 선택 | 랜선 직접 연결·노트북의 인터넷 공유를 검토함. 사용자는 노트북에서 Wi-Fi를 받아 핫스팟으로 Pi에 제공하는 방식을 선택함. 랜선만으로 인터넷 공유가 자동 설정되는 것은 아니며, 이번 성공 경로는 Windows 핫스팟과 SSH 터널임 |
| 기존 이름 그대로 쓰는 제안 | 사용자가 노트북에도 비밀번호 없는 `s24+`를 만들자고 제안했으나, Windows 기본 핫스팟의 비밀번호 요구 때문에 새 이름·비밀번호를 Pi에 저장하는 방법으로 진행함. 다른 Android 폰에 열린 `s24+`를 만드는 방법도 대안으로 설명했지만 실행 성공 보고는 없음 |
| 프로필만 먼저 저장 | `connection add`의 성공 출력은 받았지만 후속 명령에서 `unknown connection 'ReFoundLaptop'`가 발생함. 그 원인은 확인하지 못함. 저장 성공과 실제 연결 성공은 구분함 |
| Wi-Fi 검색 | 사용자 로그에서 `wlan0`는 미연결이고 `ReFoundLaptop`은 신호 100/WPA2로 검색됨 |
| 실제 연결 | `device wifi connect` 명령으로 `wlan0` 활성화에 성공. 최종 UUID는 `7cd76ca8-c636-49e0-98ab-581153a2c91b` |
| 터널 실행 위치 수정 | 처음에는 Pi 내부에서 터널 명령을 실행해 노트북 브라우저에서 열리지 않았음. **Windows 새 PowerShell에서 시작하도록 바로잡음** |
| 최종 사용자 보고 | 노트북 웹 화면 접속 성공과 OpenAI API 동작 성공을 사용자가 보고함 |
| 다음 확인 | 새 구성의 자동 연결 설정 확인, 정상 종료·전원 재인가, 화면·영상·AI 복귀 시험이 남음 |

SSH 터널 명령을 입력하기 **전**에는 노트북의 `PS C:\...>` 창이어야 합니다. 해당 명령으로 로그인한 **후** `refound@refound-pi:~ $`가 되는 것은 정상입니다. 이 차이가 이번 웹 접속 문제 해결에서 중요했습니다.

### 핵심 명령·출력 원장

아래는 **당시 경과를 보존한 기록**이며 매번 실행할 절차가 아닙니다. 비밀번호 인자만 `<노트북 핫스팟 비밀번호>`로 치환했습니다. 이는 그대로 입력할 비밀번호가 아닙니다. 주변의 다른 Wi-Fi 이름은 이 문제 해결에 필요하지 않아 옮기지 않았습니다.

**① 연결 프로필 저장 성공**

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name "ReFoundLaptop" ssid "ReFoundLaptop" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<노트북 핫스팟 비밀번호>" connection.autoconnect yes connection.autoconnect-priority 100 ipv4.method auto
```

```text
Connection 'ReFoundLaptop' (eac4d899-d710-4941-9288-6b59588695a3) successfully added.
```

이후 사용자는 노트북 핫스팟에 Pi가 연결됐다고 보이지 않는다고 보고했습니다. 이 첫 UUID와 아래 최종 성공 UUID는 서로 다릅니다.

**② SSH 재접속 후 상태·검색 확인**

```text
client_loop: send disconnect: Connection reset
```

사용자는 다시 SSH 로그인에 성공한 뒤 다음 상태를 전달했습니다.

```text
DEVICE         TYPE      STATE                                  CONNECTION
eth0           ethernet  connecting (getting IP configuration)  netplan-eth0
lo             loopback  connected (externally)                 lo
wlan0          wifi      disconnected                           --
p2p-dev-wlan0  wifi-p2p  disconnected                           --
tailscale0     tun       unmanaged                              --
```

Wi-Fi 검색에는 **`ReFoundLaptop`, 신호 `100`, 보안 `WPA2`**가 표시됐습니다. 이 상태 출력만으로 SSH가 어느 인터페이스를 이용했는지, 랜선 단독 통신이 됐는지, Tailscale 장애 원인이 무엇인지는 확정하지 않았습니다.

**③ 저장된 연결 활성화 시도와 실패**

```bash
sudo nmcli connection up "ReFoundLaptop" ifname wlan0
```

```text
Error: unknown connection 'ReFoundLaptop'.
```

프로필 저장 성공 로그와 후속 조회 실패가 함께 있었지만 원인을 확인한 로그는 없습니다. 프로필이 왜 보이지 않았는지 추측해 결론 내리지 않았습니다.

**④ 보이는 Wi-Fi에 직접 연결해 성공**

```bash
sudo nmcli device wifi connect "ReFoundLaptop" password "<노트북 핫스팟 비밀번호>" ifname wlan0 name "ReFoundLaptop"
```

```text
Device 'wlan0' successfully activated with '7cd76ca8-c636-49e0-98ab-581153a2c91b'.
```

**⑤ SSH 터널의 실행 위치 수정**

처음에는 다음처럼 **Pi에 로그인된 상태**에서 터널 명령을 실행했습니다.

```text
refound@refound-pi:~ $ ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local
```

이때 SSH 로그인은 됐지만 노트북 브라우저에서 웹 주소가 열리지 않았습니다. 출력에는 Pi IP `192.168.137.243`과 5절의 첫 접속 지문이 표시됐습니다. 이후 **Windows 새 PowerShell**에서 아래 명령을 실행하도록 정정했습니다.

```powershell
ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@192.168.137.243
```

로그인한 창을 유지하고 노트북에서 `http://127.0.0.1:18000`을 열도록 안내한 뒤, 사용자는 다음과 같이 성공을 보고했습니다.

> 좋아 성공했고 오픈AI API도 잘 잘됐어.

이 성공 뒤의 대화는 다음 부팅·종료 방법과 IP 오류 대응을 정리한 것이며, 새로 전원을 껐다 켜서 시험한 결과가 추가로 전달된 것은 아닙니다.

## 8. 완료한 것과 남은 것

- **로그 확인:** `ReFoundLaptop` 검색 및 Pi Wi-Fi 연결 활성화.
- **사용자 성공 보고:** 노트북 SSH 터널을 통한 웹 화면 접속, OpenAI API 동작.
- **기존 확인:** 9월 22일 서비스 부팅 자동 실행. 새 네트워크의 재부팅 시험과는 구분.
- **아직 미확인:** 자동 연결 우선순위 명령의 실행 결과, 새 구성에서 정상 종료 후 전원 재인가·자동 연결·화면/AI 복귀, 랜선을 분리한 무선 단독 동작, 친구 Tailscale 접속, 장시간 안정성.
- 개별 AI 응답·현재 모델·정량 정확도·지연은 이번 사용자 보고로 측정한 것이 아닙니다.
- 실제 노트북의 상위 Wi-Fi 이름과 친구의 Tailscale 공유 초대 수락 여부도 이번 대화에서 확정하지 않았습니다. 학교 Wi-Fi 사용은 사용자가 정리한 다음 실행 절차입니다.

첫 재실행 시험은 아래 항목을 확인하면 됩니다.

- [ ] 기존 `s24+` 휴대폰 핫스팟은 끄고, 노트북 핫스팟을 먼저 켰다.
- [ ] Pi를 정상 종료하고, 무선 단독 시험이라면 종료 후 랜선을 분리했다.
- [ ] Pi에 전원을 다시 연결하자 노트북 핫스팟에 자동으로 나타났다.
- [ ] **Windows PowerShell**에서 SSH 터널을 다시 열고 웹 화면·영상을 확인했다.
- [ ] 실물 하나로 AI 동작을 다시 확인했다.

## 9. 단일 파일 백업 검토 결과

사용자가 최종 정리한 순서는 뜻을 유지하면서 비밀번호 입력·창 유지·LED 구분을 보충했습니다.

| 대화·사용자 정리의 항목 | 이 파일의 위치·반영 내용 |
|---|---|
| 실행 7단계 | 2절. 학교 Wi-Fi → 노트북 핫스팟 → Pi 전원 → 부팅 대기 → Windows PowerShell → SSH 터널 → 브라우저 |
| 종료 4단계 | 3절. 작업 완료 → Pi에서 종료 명령 → 정상 종료·초록 ACT LED 확인 후 전원 분리 → 핫스팟 끄기 |
| 이름 오류 대응 5단계 | 4절. 윈도우 연결 기기 목록 → 현재 Pi IP 확인 → `@` 뒤만 교체 → 전체 SSH 명령 예시 → 같은 브라우저 주소 |
| 일반 SSH 명령을 따로 입력하는지 | 2절. 웹 터널 명령이 로그인을 포함하므로 매번 먼저 실행할 필요 없음 |
| 명령을 잘못된 창에서 입력했던 문제 | 1·2·7절. Windows와 Pi 프롬프트, 로그인 전후 변화, 실제 실패·정정 과정 |
| 비밀번호와 첫 접속 질문 | 1·5절. Pi 로그인·sudo·Wi-Fi 비밀번호 구분, 입력이 안 보이는 현상, 지문 확인과 `yes` |
| 기존 `s24+`와 대안 검토 | 6·7절. 열린 휴대폰 핫스팟의 간헐적 끊김, 랜선·다른 폰·Windows 핫스팟 검토 |
| Windows에 인터넷을 먼저 연결해야 했던 상황 | 6절. 핫스팟 설정 → `s24+`로 돌아가 SSH → 새 프로필 저장 → 인터넷 Wi-Fi·노트북 핫스팟 복귀 |
| 저장 성공 뒤 실제 연결이 안 됐던 과정 | 7절. 첫 UUID, 상태 출력, `unknown connection`, 최종 직접 연결 명령과 성공 UUID |
| 화면·OpenAI API 성공 범위 | 7·8절. 사용자 성공 보고를 보존하고 개별 응답·정량 측정과 구분 |
| 다음 부팅 때 무엇을 다시 하는지 | 2·8절. 노트북 핫스팟·SSH 재실행, 설정 재입력 불필요, 새 구성의 실제 재부팅 확인은 대기 |

실제 비밀번호·API 키와 문제 해결에 관계없는 주변 Wi-Fi 목록을 제외하고, 이 에피소드의 실행 방법·핵심 명령·오류·해결·미확인 항목을 이 파일에 보존했습니다. 이것은 관련 대화의 정리본이며 모든 메시지를 그대로 옮긴 원문 전사본은 아닙니다.

저장소 전체가 함께 있을 때 참고할 추가 원장은 [PI_ACCEPTANCE_CHECKLIST.md](docs/guides/PI_ACCEPTANCE_CHECKLIST.md), 이전 Android/Tailscale 안내는 [SCHOOL_DEMO_GUIDE.md](docs/guides/SCHOOL_DEMO_GUIDE.md)입니다. **이 파일만 따로 백업하면 해당 상대 링크가 열리지 않을 수 있지만, 이번 연결 에피소드의 핵심 내용과 절차는 위 본문에 포함돼 있습니다.**

이번 검토에서는 이 Markdown 파일만 수정했습니다. 앱·배포·데이터·Pi 설정을 바꾸거나, 재부팅·API 시험을 에이전트가 직접 실행한 것은 아닙니다.

**2026-09-30 저장소 반영:** 위 마지막 문장은 9월 29일 백업 작성 당시의 범위입니다. 이후 이 기록을 시작 안내·인계·실기 확인표·설치/발표/논문 안내에 반영했습니다. 이 원문의 성공·미확인 범위는 유지하며, 루트 위치에 맞게 위 상대 링크만 바로잡았습니다. 저장소 점검은 `output/maintenance/2026-09-30-sync-review/`에 별도로 기록합니다.
