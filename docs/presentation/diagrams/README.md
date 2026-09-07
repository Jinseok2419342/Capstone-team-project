# 발표용 Mermaid 다이어그램

현재 `app/`, `templates/`, `static/`, Raspberry Pi 스크립트와 SQLite 스키마를 기준으로 작성한 발표용 원본입니다.

| 파일 | 발표에서 사용할 위치 | 설명 |
|---|---|---|
| `01-system-architecture.mmd` | 2.3 현재 시스템 구성 | 하드웨어, 엣지 런타임, 외부 API와 관리자 접속 구조 |
| `02-core-features.mmd` | 1.2 핵심 기능 / 4.2 구현 결과 | 감지부터 회수·폐기까지의 주요 기능 |
| `03-data-ai-design.mmd` | 5.1~5.2 데이터·AI 설계 | 전처리, 사건 판단, 4-image 입력과 AI 결과 검증 |
| `04-uiux-service-structure.mmd` | 2.1 UI/UX / 6.1 시스템 통합 | 관리자 화면과 FastAPI 서비스 연결 |
| `05-data-model.mmd` | 데이터베이스 구성 또는 부록 | SQLite 네 개 테이블과 관계 |
| `all-diagrams.md` | 검토용 | 다섯 다이어그램을 한 문서에서 확인 |

## PPT에 넣는 방법

1. 필요한 `.mmd` 파일의 내용을 Mermaid Live Editor에 붙여 넣습니다.
2. SVG로 내보냅니다. PNG보다 확대했을 때 선과 글자가 선명합니다.
3. PowerPoint 또는 Canva에서 SVG를 삽입하고 슬라이드 비율에 맞게 자릅니다.

발표 본문에는 1번, 3번, 4번을 우선 사용하고 5번 데이터 모델은 부록에 두는 구성이 적합합니다. 노드가 많은 그림은 글자를 줄이지 말고 슬라이드 두 장으로 나누세요.

