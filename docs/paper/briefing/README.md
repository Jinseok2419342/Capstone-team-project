# 논문 전반부 발표 원고

2026-09-16 전체 개정본과 내용·인용 번호를 맞춘 연구방법 이전 4쪽 원고다. 최신 슬라이드는 사용자 수정 요청에 따라 **PDF 페이지 전체 캡처를 왼쪽에, 짧은 설명 세 개를 오른쪽에** 놓은 4장이다. 대본은 포함하지 않는다.

## 파일

- [원고 PDF](../../../output/pdf/RESEARCH_FRONT_MATTER.pdf): 화면 공유와 인쇄에 사용할 4쪽 원고.
- [최신 발표 PowerPoint](../../../output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx): PDF 1–4쪽을 그대로 캡처한 이미지와 짧은 설명. 원문 이미지는 200 dpi로 삽입했으며 오른쪽 설명은 편집할 수 있다. 세로 원고를 크게 보여주도록 4:3 화면으로 구성했다.
- 이전 6장 재조판 시안과 생성기는 2026-10-07 정리했다. 현재는 위 PDF 캡처 4장만 사용한다.
- `build_pdf_capture_slides.mjs`: `pdf_pages/page-1.png`–`page-4.png`에서 최신 PPTX 생성. PDF가 바뀌면 페이지 이미지를 다시 렌더링한 뒤 새 출력 경로로 생성한다.
- [원고와 옆 설명 보기](RESEARCH_FRONT_MATTER_VIEW.html): 원고 PDF를 크게 표시하고 오른쪽에 이해를 돕는 설명을 붙인 로컬 HTML. 같은 저장소의 PDF를 참조하므로 HTML만 따로 옮기지 않는다.
- [편집용 원문](RESEARCH_FRONT_MATTER.md): 이후 문장 수정의 기준. 페이지 구분 주석을 포함한다.
- `build_front_matter.py`: 원문에서 PDF와 브라우저 보기를 생성하는 스크립트.
- `BUILD_REPORT.json`: 페이지 수, 인용 순서와 초록 분량의 구조 검사 결과.

## 이번 범위와 구성

1. 제목, 국문 요약, 영문 Abstract, 국·영문 주제어
2. 서론: 배경과 필요성, 문제 정의, 목적과 범위
3. 이론적 배경: 장면 변화 감지, 엣지 및 선택적 영상 분석, 멀티모달 추론
4. 관련 연구 비교, 본 연구의 위치, 참고문헌

본문을 읽는 시간과 발표 시간은 같지 않다. 5분 발표에서는 제목을 소개하고, 서론의 보관대 문제, 세 배경 개념, 관련 연구 비교의 차이를 차례로 짚는다. 국·영문 요약이나 참고문헌 전체를 읽을 필요는 없다.

## 기존 초안과의 관계

- 전체 `../PAPER_DRAFT_JDCS.md`와 `../RESULTS_FILL_SHEET.md`도 이번에 개정했다. 세부 변경과 남은 일은 `../REVISION_STATUS.md`에 정리했다.
- 원래 초안의 서론·관련 연구를 사용하되, 이론적 배경을 별도 절로 풀어 설명했다.
- 코드 세부 알고리즘, 구현 설정, 실험 절차와 결과표는 이번 범위에 포함하지 않았다.
- 측정값 placeholder 대신 구현된 사실과 앞으로 평가할 내용을 구분했다.
- 참고문헌은 이번 범위의 8개를 수록했으며, 전체 원고의 [1]–[8]과 번호가 일치한다.
- 차량 전후 비교 논문 [3]은 학술대회 논문이다. 공식 영문 제목과 로마자 표기를 확정하지 않아 발표본에는 확인된 국문 서지를 사용했다.
- 수업 발표에서 이름·소속이 필요하면 최종 저자 순서 확인 후 제목 아래에 넣는다.

## 형식 결정과 확인한 출처

이번 원고는 JDCS의 제목·국영문 요약·키워드·번호 인용 구성을 참고한 발표용 단일단 PDF다. 공식 JDCS HWP 투고 양식을 복제하거나 최종 제출 적합성을 검증한 파일은 아니다. 발표 가독성을 위해 본문 약 10pt, A4 단일단, 4쪽으로 구성했다. 현재 Windows 번들에는 LibreOffice가 없어 Word 페이지 렌더링 대신 PDF를 직접 생성하고 페이지 이미지를 검사한다.

2026-09-16에 확인한 공식 안내:

- [JDCS 투고 규정](https://dcs.or.kr/homepage/custom/rule): 국·영문 요약과 키워드, 번호 인용, 최종 투고의 2단 형식과 HWP 작성 기준.
- [JDCS 공식 양식 게시물](https://dcs.or.kr/board/forms/article/199654): 2025년 3월 수정 HWP 양식 안내. 이번 결과물은 이 첨부 HWP를 직접 편집한 것이 아니다.
- [JPEE 원고 작성 지침](https://journal.kipee.or.kr/common/guide): 제목·초록·키워드·본문·참고문헌 구성 확인.
- [JPEE 투고 안내](https://journal.kipee.or.kr/common/inst): 실천공학교육에 기여하는 연구 범위 확인. 이번 기술 중심 원고에는 JDCS 방향을 유지했다.

논문 내용과 서지 확인 출처:

- [정하민 등 논문 저자 초록과 서지](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002401814)
- [장현상 등 학회 원문](https://www.ki-it.com/_common/do.php?a=full&aidx=44102&b=22&bidx=3983)
- [양형준·최규상 논문 저자 초록과 서지](https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE12288829)
- [Wallflower 저자기관 설명](https://www.microsoft.com/en-us/research/publication/wallflower-principles-and-practice-of-background-maintenance/)
- [엣지 컴퓨팅 논문 저자 공개본](https://elijah.cs.cmu.edu/DOCS/satya-edge2016.pdf)
- [NoScope 학회 원문](https://www.vldb.org/pvldb/vol10/p1586-kang.pdf)
- [Reducto 저자 공개본](https://artpad6.github.io/papers/reducto_sigcomm20.pdf)
- [BLIP-2 공식 학회 서지와 초록](https://proceedings.mlr.press/v202/li23q.html)

사진 기반 등록과 차량 전후 비교 논문은 공개된 저자 초록·서지 범위에서 요약했다. 열람하지 않은 본문에 특정 기능이 없다고 단정하지 않았다. 문헌별 성능 수치의 직접 우열 비교도 하지 않았다.

## 다음 검토

교수님 피드백을 받으면 제목 길이, 이론적 배경과 관련 연구의 분리 여부, 연구 범위부터 조정한다. 정량 실험 이후의 전체 논문에는 별도의 결과 기반 초록과 연구방법·결과·결론이 필요하다.
