# Re:Found 발표 이미지 준비 목록

이 폴더의 JPG 4장은 저장소에 남아 있던 실제 감지 crop을 발표용으로 모은 것입니다.

| 파일 | 실제 내용 | 사용 위치 |
|---|---|---|
| `01_remote_before_crop.jpg` | 리모컨이 놓이기 전 배경 crop | 4-image hybrid evidence 설명 |
| `02_remote_after_crop.jpg` | 리모컨이 놓인 뒤 물체 crop | 4-image hybrid evidence 설명 |
| `03_pen_before_crop.jpg` | 볼펜이 놓이기 전 배경 crop | 등록·회수 또는 배경 복원 설명 |
| `04_pen_after_crop.jpg` | 볼펜이 놓인 뒤 물체 crop | 등록·회수 또는 배경 복원 설명 |

이 이미지는 전체 장면이 아니라 변화 영역 crop입니다. 발표에서 전체 프레임이라고 설명하면 안 됩니다.

## 사용자가 추가로 촬영할 이미지

아래 파일은 Raspberry Pi를 켠 뒤 직접 준비합니다. 가능하면 화면 캡처는 1920×1080, 브라우저 배율 100%, Windows 작업 표시줄과 개인 알림을 숨긴 상태로 만듭니다.

1. `05_dashboard_overview.png`
   - 개요 대시보드 전체
   - 1일·60일·90일 물품이 보이도록 시연 데이터를 준비
   - API 키, 이메일 주소, Tailscale 계정 정보는 보이지 않게 함
2. `06_camera_stable.png`
   - 카메라 페이지 전체
   - 라이브뷰와 `변화를 기다리는 중` 상태가 동시에 보이게 함
3. `07_camera_detecting_pen.png`
   - 파란색 볼펜을 놓은 뒤 감지 상자 또는 분석 상태가 보이는 화면
4. `08_item_detail_pen.png`
   - 파란색 볼펜 상세 화면
   - 이름, 일반 물품, 60일, 분석 제공자가 보이게 함
5. `09_activity_added_recovered.png`
   - 같은 물품의 등록과 회수 활동이 시간순으로 보이는 활동 기록
6. `10_settings_ai.png`
   - 설정의 AI 제공자와 모델 선택 화면
   - API 키 값은 절대 노출하지 않음
7. `11_pi_camera_device.jpg`
   - Raspberry Pi 4, CSI 카메라, 거치대와 촬영 영역이 함께 보이는 실제 사진
   - 배경은 정돈하고 학교·개인 식별정보는 치움
8. `12_tailscale_remote_web.png`
   - 노트북 브라우저에서 Pi 웹이 열린 모습
   - 주소는 필요하면 `refound-pi…ts.net`처럼 일부 가림
9. `13_service_active.png`
   - 터미널의 `systemctl is-active refound.service` 결과 `active`
   - 터미널에 API 키나 비밀번호가 없는지 확인
10. `14_pytest_82_passed.png`
    - 다음 테스트 결과의 마지막 부분: `82 passed`
    - 경로에 개인 이름이 보이면 잘라냄

## 전체 장면 4-image 증거용 추가 촬영

하이브리드 증거 슬라이드를 완성하려면 아래 두 이미지를 같은 카메라 위치에서 캡처합니다.

11. `15_scene_before_full.png`
    - 물건을 놓기 전 전체 카메라 장면
12. `16_scene_after_full.png`
    - 볼펜을 놓은 뒤 전체 카메라 장면

`15`, `16`과 이 폴더의 `03`, `04`를 2×2로 배치하면 다음 역할을 정확히 설명할 수 있습니다.

```text
전체 BEFORE + 전체 AFTER = 무엇이 추가/제거됐는지, 사건의 방향과 주변 맥락
crop BEFORE + crop AFTER = 물건의 색상·형태·재질·세부 종류
```

## 촬영하지 않아도 되는 것

- API 키가 보이는 `.env`
- Gmail 앱 비밀번호
- Tailscale 로그인 계정 또는 관리 콘솔 개인정보
- 실제 학생 개인정보가 들어간 문서나 모니터
- 인터넷에서 가져온 의미 없는 Raspberry Pi 스톡 사진

실제 장치 사진을 준비하기 전에는 슬라이드에 `11_pi_camera_device.jpg 촬영 예정`처럼 정직한 자리표시자를 사용합니다.
