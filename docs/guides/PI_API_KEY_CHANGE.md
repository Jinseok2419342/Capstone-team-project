# Pi 시연용 API 키 바꾸기

**Pi의 `/opt/refound/.env`에서 키 수정 → 앱 재시작 → 웹에서 제공자 선택** 순서입니다. 새로 설치할 필요는 없습니다.

## 1. Pi에 접속

인터넷이 되는 노트북의 `ReFoundLaptop` 핫스팟과 Pi를 켠 뒤, **노트북 PowerShell**에서 실행합니다. 이미 Pi에 로그인한 SSH 창이 있으면 그 창에서 2번부터 진행합니다.

```powershell
ssh -o ExitOnForwardFailure=yes -L 18000:127.0.0.1:8000 refound@refound-pi.local
```

Pi 로그인 비밀번호를 입력합니다. 이름 오류가 나면 `@` 뒤를 핫스팟 연결 장치 목록의 **현재 Pi IP**로 바꿉니다. [연결 안내](../../REFOUND_WINDOWS_HOTSPOT_GUIDE.md)

## 2. 키 수정

**Pi에 로그인된 창**에서 실행합니다.

```bash
nano /opt/refound/.env
```

아래 중 필요한 **기존 줄의 `=` 오른쪽만** 바꿉니다. 같은 항목을 중복 추가하지 않습니다.

| 하려는 작업 | 바꿀 내용 |
|---|---|
| 다른 OpenAI 키로 교체 | `OPENAI_API_KEY=새_OpenAI_키` |
| Gemini 키로 전환 | `GEMINI_API_KEY=새_Gemini_키` |

`새_OpenAI_키`·`새_Gemini_키` 자리에 발급받은 실제 키를 붙여 넣습니다. 다른 설정은 그대로 둡니다. 키는 채팅·발표 자료에 올리지 않습니다.

## 3. 저장하고 앱 재시작

Nano에서 **Ctrl+O → Enter → Ctrl+X** 순서로 저장·종료한 뒤 실행합니다.

```bash
sudo systemctl restart refound.service
```

명령이 끝날 때까지 기다립니다. 재시작 중 웹 화면은 잠시 끊길 수 있습니다.

## 4. 웹에서 사용할 AI 선택

SSH 창을 열어둔 채 노트북 브라우저에서 `http://127.0.0.1:18000`을 새로고침합니다.

**설정 → AI 분석 → AI 제공자**에서 아래처럼 선택하고 저장합니다.

- OpenAI 키를 교체했다면 **OpenAI**.
- Gemini로 바꿨다면 **Google Gemini**. 기존 OpenAI 키가 남아 있어도 Gemini만 사용합니다.

**모델**은 선택한 제공자의 모델명을 확인합니다. 기존 모델을 새 키로도 사용할 수 있으면 그대로 두고, 모델 접근 오류가 나면 해당 계정에서 사용 가능한 이미지·구조화 응답 지원 모델 ID로 변경합니다. 모델명은 `.env`가 아닌 이 웹 화면에서 설정합니다.

## 5. 물품 하나로 확인

카메라에 새 물품 하나를 놓고 AI 분석 결과를 확인합니다. **‘키 설정됨’ 표시는 키 입력 확인일 뿐, 실제 API 성공 확인은 아닙니다.**

실패하면 Pi 창에서 최근 오류를 확인합니다.

```bash
sudo journalctl -u refound.service -n 40 --no-pager
```

OpenAI의 **키 만료·무효 오류**는 키를 교체하고, **잔액·사용 한도 부족**은 충전이나 한도 확인이 필요합니다. 같은 계정·프로젝트의 키만 새로 만들어도 부족한 잔액·한도가 해결되지는 않습니다. [OpenAI 공식 오류 안내](https://developers.openai.com/api/docs/guides/error-codes)

작성: 2026-10-07. 현재 저장소의 설정·화면·제공자 선택 코드를 대조한 안내이며, 새 키의 실제 Pi 호출 시험은 수행하지 않았습니다.
