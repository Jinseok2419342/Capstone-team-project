from pathlib import Path
import re, shutil

root = Path(__file__).resolve().parents[3]
build = Path(__file__).resolve().parent
source = root / 'docs/presentation/midterm/build_midterm_v4.mjs'
text = source.read_text(encoding='utf-8')
text = text.replace('presentations/26.930.11008/', 'presentations/26.915.20218/')
text = text.replace("const BUILD=path.join(ROOT,'output/maintenance/2026-10-02-midterm-review');", "const BUILD=path.join(ROOT,'output/maintenance/2026-10-02-midterm-content-review');")
text = text.replace("process.env.DECK_REVISION||'v4_reviewed'", "process.env.DECK_REVISION||'v5_improved'")

def slide(number, body):
    global text
    start = text.index(f'// {number:02d}\n')
    end = text.index(f'// {number+1:02d}\n', start) if number < 30 else text.index('\nawait fs.mkdir(BUILD', start)
    text = text[:start] + f'// {number:02d}\n{{\n' + body.strip() + '\n}\n' + text[end:]

slide(3, r"""
 const s=slide('보관대의 물품과 관리 기록을 연결','1. 프로젝트 개요 및 개발 목표',[src.readme],'아래 우산 사례는 기능을 설명하기 위한 사용 시나리오이며 실제 측정 결과가 아님');
 tx(s,'담당자가 사진·분류·기한을 따로 관리하면 기록이 빠지거나 중복될 수 있다.',64,177,1152,85,30,true,C.teal);
 tab(s,[['보관대에서 생기는 일','관리자가 확인할 내용','시스템의 처리 목표'],['우산을 새로 놓음','언제 들어온 어떤 물품인가?','사진·시각 저장, AI 이름·분류 제안'],['같은 우산의 위치를 옮김','새 물품인가, 기존 물품인가?','기존 ID의 위치·사진 갱신'],['우산을 화면 밖으로 치움','어떤 기록의 상태를 바꿀 것인가?','해당 물품의 회수 상태·이력 기록']],[320,378,454],{y:285,h:258,size:23});
 tx(s,'주요 사용자  학교 행정실·도서관·공용공간의 분실물 관리자',64,573,1152,35,25,true);
 tx(s,'적용 범위  카메라를 고정할 수 있는 실내 보관대',64,615,1152,30,23,false,C.muted);
 note(s,'수기·별도 파일 관리의 누락과 중복 가능성은 문제 정의이며 실제 기관의 업무 실태를 조사한 정량 결과가 아니다. 회수 상태는 화면에서 사라짐을 기록하며 소유자에게 반환됐다는 뜻은 아니다.');
""")
slide(4, r"""
 const s=slide('로컬 감지와 AI 해석의 역할 분담','1. 프로젝트 개요 및 개발 목표',[src.readme,'app/main.py','app/ai.py']);
 rows(s,[['로컬에서 판단','움직임이 끝난 뒤 장면을 비교하고 기존 물품과 대응\n명확한 이동·제거는 로컬에서 처리'],['AI가 보완','새 물품의 이름·분류와 모호한 제거를 해석\n사건별 증거를 보내고 결과를 관리 기록에 반영'],['관리자가 결정','확인 필요 항목을 검토하고 이름·기한을 수정\n보관·회수·폐기·복원 이력을 같은 물품에 연결'],['최종 결과물','Pi 카메라 장치, FastAPI 서버, 관리자 웹\n설치 패키지·사용 안내와 검증 기록']],{y:185,gap:110,labelW:236});
 note(s,'차별화 의도는 모든 프레임에 AI를 호출하지 않고 사건을 선별하며, AI 실패 때도 관찰 기록을 보존하는 데 있다. 호출량·비용·정확도 개선율은 아직 측정하지 않았다. 자체 학습 모델이 최종 산출물인 프로젝트는 아니다.');
""")
slide(5, r"""
 const s=slide('전체 시스템 구성과 데이터 흐름','2. 시스템 설계 및 개발 구조',[src.readme,'app/main.py','app/vision.py','app/store.py','app/ai.py'],'양방향 화살표는 요청·응답 또는 조회·저장의 관계를 표시');
 const a=node(s,'CSI 카메라\nPicamera2',64,225,219,110);
 const b=node(s,'로컬 사건 감지\nOpenCV',328,225,239,110);
 const c=node(s,'사건 처리 · API\nFastAPI',620,225,272,110);
 const d=node(s,'관리자 · 웹\nHTML / CSS / JS',965,225,251,110);
 connect(s,a,b);connect(s,b,c);
 const both=(a,b,from='right',to='left',kind='straight')=>s.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:C.teal,width:2},head:{type:'arrow',width:'med',length:'med'},tail:{type:'arrow',width:'med',length:'med'}});
 both(c,d);
 tx(s,'프레임',285,185,135,29,18,false,C.muted);
 tx(s,'후보·증거',567,185,135,29,18,false,C.muted);
 tx(s,'조회·편집 / 화면 갱신',931,185,285,29,18,false,C.muted);
 const db=node(s,'SQLite WAL\n물품·활동·알림·설정',601,477,310,123);
 const ai=node(s,'외부 VLM API\nOpenAI / Gemini',956,477,260,123);
 both(c,db,'bottom','top');both(c,ai,'bottom','top','elbow');
 tx(s,'관찰 저장\n상태 조회',611,378,130,67,22,true,C.teal);
 tx(s,'증거 요청·판정 응답',925,364,278,32,21,true,C.teal);
 tx(s,'사건 처리 순서',64,420,452,39,28,true,C.teal);
 tx(s,'관찰을 먼저 DB에 저장\nAI 응답 검증 후 기록 갱신\n웹에서 조회·검토·편집',64,476,483,131,26);
 note(s,'관리자의 조회·편집 요청과 서버 응답, 외부 AI의 응답 복귀를 양방향 연결로 표시했다. SQLite는 Pi 로컬 DB이고 사진은 로컬 파일로 보존한다. added/verify_removed가 외부 AI 대상이며 명확한 moved/removed는 로컬 흐름에서 처리한다.');
""")
slide(9, r"""
 const s=slide('개발 목표 대비 현재 도달 수준','3. 프로젝트 개발 진행 현황',[src.readme,src.accept,src.hotspot,src.sync],'최초 작업별 마감일이 없어 일정 지연을 단정하지 않음 / 공식 진행률은 산정 기준 미확정');
 tab(s,[['개발 목표','현재 도달 수준','남은 작업과 이유'],['통합 프로토타입','구현 완료','Pi 4·SQLite 중심으로 배포 단순화'],['실물 등록·이동·회수','기본 흐름 확인','다중 물품·가림 조건 검증 필요'],['외부 AI 연동','동작 성공 보고','정답·개별 응답 원본 수집 필요'],['학교 시연 환경','연결 검증 진행','새 핫스팟의 재부팅 복귀 미확인'],['운영 검증·성능 평가','일부 검사 / 평가 준비','실제 메일·반복 운영·정량 자료 필요']],[310,307,535],{h:385,size:24});
 tx(s,'현재 단계: 핵심 기능 구현 이후의 현장 검증·평가 준비',64,590,1152,45,29,true,C.teal);
 note(s,'초기 계획 대비 보유 Pi 4·CSI, OpenCV+외부 VLM, SQLite, Vanilla JS+FastAPI로 구성을 단순화했다. 최초 계획의 확정 마감일·공수·가중치 자료가 없어 빠름/지연 및 프로젝트 전체 백분율을 만들지 않았다. 코드 구현 완료와 실제 환경 검증 완료를 구분한다. 공식 진행률 산식과 남은 근거는 작성 가이드에 보존한다.');
""")
slide(13, r"""
 const s=slide('AI 응답을 기다리는 동안에도 기록 보존','4. 핵심 기능 구현 결과',['app/main.py','app/classification.py','tests/test_app_resilience.py',src.arch]);
 const a=node(s,'물품 감지',64,191,244,97),b=node(s,'임시 기록 저장',360,191,270,97),c=node(s,'AI 비동기 요청',681,191,275,97),d=node(s,'검토·확정',1007,191,209,97);
 connect(s,a,b);connect(s,b,c);connect(s,c,d);
 rows(s,[['AI 정상 응답','응답 형식과 판정을 확인한 뒤 이름·분류를 반영\n관찰한 물품의 사진·시각과 AI 결과를 연결'],['실패·불확실 응답','관찰 기록을 유지하고 확인 필요 상태로 표시\n관리자가 사진을 보고 이름·분류를 확정'],['추론 중 관리자 작업','기한 연장과 명시적인 검토 완료를 보호\n늦은 응답을 적용하기 전에 현재 상태 확인']],{y:335,gap:96,labelW:261});
 tx(s,'설계 이유: 외부 API 장애가 곧 물품 기록의 누락으로 이어지지 않도록 구성',64,615,1152,31,23,true,C.teal);
 note(s,'임시 저장 성공 뒤 비동기 추론한다. DB 저장 자체의 실패까지 보존을 보장한다는 뜻은 아니다. 기한 연장은 test_late_classification_preserves_manual_extension으로 확인하고, 명시적 검토 완료 뒤의 응답 보호 코드는 보충자료 A에 제시했다.');
""")
slide(15, r"""
 const s=slide('관리자는 확인이 필요한 물품부터 처리','4. 핵심 기능 구현 결과',['templates/index.html','static/app.js','tests/test_live_management.py',src.check],'9/22 개발 검사 화면 / 물품 수·사진·영상은 합성 테스트 데이터');
 await screenshot(s,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png',64,178,740,455,'합성 카메라·임시 DB를 사용한 관리자 대시보드');
 tx(s,'확인 필요 물품',850,182,366,40,29,true,C.teal);
 tx(s,'사진과 AI 결과를 검토\n이름·분류 수정 후 검토 완료',850,239,366,91,25);
 tx(s,'기한과 처리 이력',850,372,366,40,29,true,C.teal);
 tx(s,'기한 도래 항목 확인·연장\n회수·폐기·복원 처리\n활동 이력에서 결과 확인',850,429,366,126,25);
 tx(s,'관리 흐름은 자동 검사 통과\nPi 상세 실기는 추가 확인 예정',850,580,366,63,21,false,C.muted);
 note(s,'단순 편집과 명시적인 검토 완료는 구분한다. test_review_expiry_renewal_notification_and_final_lifecycle에서 검토·만료·연장·알림·최종 처리를, test_dismiss_restore_and_lifecycle_keep_search_pages_and_stats_consistent에서 상태와 목록·통계의 일관성을 검사했다. 실제 SMTP 수신은 미확인이다.');
""")
slide(16, r"""
 const s=slide('통합 기능의 현재 범위와 남은 일','4. 핵심 기능 구현 결과',[src.live,src.accept,src.hotspot,'experiments/pair_runner.py']);
 tab(s,[['범위','현재 결과','다음 완료 조건'],['기본 처리 연결','카메라·DB·API·웹 연동 구현\n기본 실물 흐름 성공 보고','같은 물품의 등록·이동·회수\n사진·ID·이력 확보'],['관리·알림 연결','편집·기한·상태·알림 구현\n모의 환경의 연속 검사 통과','발표 장비에서 편집·기한 확인\n실제 메일 수신 결과 기록'],['시연 연결','노트북 핫스팟·SSH 성공 보고','전원 재인가 후 영상·AI 복귀\n반복 실행 기록'],['평가 도구','이미지 쌍의 감지 코어 평가 구현','사건·응답·시각 원장 추가\n연속 영상 비교기는 추가 개발']],[238,450,464],{h:407,size:24});
 tx(s,'남은 핵심 작업은 현장 증거 확보와 측정 기록 연결이다.',64,607,1152,37,27,true,C.teal);
 note(s,'통합 연결의 개발 검사와 실제 환경의 모든 시나리오 확인은 별개다. 기존 pair runner는 안정 이미지 쌍의 _detect_changes 코어 평가이며 전체 상태기계·DB·VLM의 종단간 평가기가 아니다.');
""")
slide(17, r"""
 const s=slide('전후 장면과 물품 영역을 함께 전달','5. AI 모델 및 데이터 개발 현황',['app/vision.py','app/ai.py','tests/test_services.py'],'운영 사진 수량은 미집계 / 정답 라벨이 있는 평가 세트는 미확보');
 tx(s,'고정 카메라 영상에서 움직임 종료·안정화 후 사건별 증거를 만든다.',64,178,1152,76,30,true,C.teal);
 tab(s,[['입력·처리','필요한 이유','현재 구현'],['기하 정합·조명 보정','카메라 미세 변화와 밝기 차이 완화','로컬 전처리'],['전체 장면 전후 2장','무엇이 생겼거나 사라졌는지\n주변 맥락과 함께 판단','변화 전·후를 구분해 전달'],['후보 영역 전후 2장','작은 물품의 모양·색상 등\n세부 특징을 더 크게 제공','후보 영역 crop 전달'],['정답·응답 연결','잘못된 사건·분류의 원인 분석','평가 원장 추가 예정']],[310,478,364],{y:252,h:305,size:23});
 tx(s,'요청당 최대 4장 / 자체 학습·RAG·파인튜닝·데이터 증강 미적용',64,607,1152,37,25,true,C.teal);
 note(s,'tests/test_services.py test_ai_hybrid_evidence_is_labeled_and_cost_bounded가 입력 4장과 before/after 라벨, 전체 low·crop high detail을 확인한다. 실제 처리에서 전체 장면 JPEG 품질은 72, crop은 88이다. 이미지 기반 전처리이며 통계형 결측치 대치나 학습 정규화를 수행한 것으로 쓰지 않는다.');
""")
slide(18, r"""
 const s=slide('외부 VLM 선택 이유와 추론 방식','5. AI 모델 및 데이터 개발 현황',['app/ai.py',src.readme,src.state,src.hotspot],'선정 근거는 설계상 판단 / 모델 간 정확도·비용 우열을 측정한 결과는 없음');
 tab(s,[['검토 방식','적합한 역할과 제약'],['OpenCV 로컬 처리','변화 시점·위치 감지에 사용, 물품 이름 해석은 AI로 보완'],['고정 클래스 검출·분류 모델','대상 클래스가 고정됨, 새 물품 유형에는 추가 학습 검토'],['외부 VLM  ·  현재 방식','전후 이미지로 다양한 물품을 설명, 통신·호출 비용 의존']],[382,770],{h:255,size:24});
 tx(s,'추론 요청',64,469,215,38,27,true,C.teal);
 tx(s,'전후 증거 + 판단 지침 + JSON schema\n응답 완료·형식을 검사해 결과 반영 또는 확인 필요로 전환',303,469,913,83,25);
 tx(s,'모델 확인',64,569,215,37,27,true,C.teal);
 tx(s,'9/22 설정: gpt-5.6-luna\n9/29 OpenAI 동작 성공 보고, 당일 모델명은 미수집',303,569,913,75,24);
 note(s,'OpenAI를 사용하는 설정이 확인됐고 Gemini 연동도 구현했다. Pi 4 2GB에서 감지와 웹 운영을 맡기고 외부 VLM에 의미 해석을 맡긴 설계다. 고정 클래스 검출·분류 방식은 프로젝트의 초기 YOLO/CNN 검토 맥락이며 모든 현대 검출 모델의 기능을 일반화한 비교는 아니다. 추론 설정은 기본 모델 reasoning low·출력 최대 2048토큰이며 학습 하이퍼파라미터가 아니다.');
""")
slide(19, r"""
 const s=slide('AI 동작 확인과 정량 평가의 구분','5. AI 모델 및 데이터 개발 현황',[src.hotspot,'tests/test_services.py','docs/paper/EXPERIMENT_GUIDE.md'],'현재 정량 성능은 미측정 / 아래 지표는 수집·계산할 항목');
 tx(s,'확인한 결과  9/29 OpenAI 동작 성공 보고',64,178,1152,42,31,true,C.teal);
 tx(s,'아직 필요한 근거  같은 사건의 정답·원본 사진·실제 AI 응답·처리 시각',64,237,1152,58,26);
 tab(s,[['평가 지표','평가에 필요한 기록'],['사건 Precision / Recall / F1','추가·이동·제거별 예측과 정답의 TP·FP·FN'],['물품 분류 정확도','분류 정답 수 / 전체 평가 대상 수 N'],['불확실·실패 응답 비율','uncertain·API 실패 건수 / 전체 요청 수'],['종단간 지연 p50 / p95','행동 종료와 DB 반영 시각, 표본 수·시각 누락률']],[414,738],{y:320,h:280,size:24});
 tx(s,'모의 응답 처리 검사는 통과했으며, 실제 모델의 판정 품질은 별도 평가한다.',64,617,1152,29,23,true,C.teal);
 note(s,'9/29는 동작 성공의 사용자 보고로 개별 사건의 원본·정답·모델 응답은 수집하지 않았다. 자동 검사에서 JSON 정규화, 유효하지 않은 분류·확신도의 uncertain 처리 등을 확인했다. 이것은 실제 AI의 성공·실패 사례 비교 결과가 아니다. 분류 정확도의 분모에는 평가 대상의 불확실·실패를 포함하고 별도 응답 성공 조건의 정확도가 필요하면 구분해 보고한다.');
""")
slide(21, r"""
 const s=slide('오류 조건을 포함한 자동화 검사','6. 테스트 결과 및 문제점 분석',[src.sync,src.check,'tests/test_app_resilience.py','tests/test_reset.py','tests/test_services.py'],'임시 DB·합성 카메라·모의 AI·SMTP의 개발 검사 / 실제 모델 성능 시험과 구분');
 tx(s,'Python 272개 · Node 37개',64,169,733,53,37,true,C.teal);
 tx(s,'9/30 재실행 통과',64,230,733,33,24,false,C.muted);
 tx(s,'Chromium 7개',850,172,366,45,31,true,C.teal);
 tx(s,'9/22 검사 통과',850,230,366,33,24,false,C.muted);
 tab(s,[['재현한 조건','예상 결과','확인 결과'],['AI 작업 제출 실패','임시 물품 보존·검토 대기','기록 유지 통과'],['기한 연장 뒤 AI 응답 도착','관리자가 연장한 기한 유지','기한 일치 통과'],['시연 초기화 실행','물품·사진 삭제, 설정·키 유지','삭제·보존 검사 통과'],['알림 작업 동시 실행','같은 물품의 중복 발송 방지','모의 발송 1회 확인']],[366,493,293],{y:300,h:322,size:23});
 note(s,'모든 Python 사례는 9/30 272개 통과 기록과 현재 test 소스를 대조했다. test_executor_rejection_preserves_item_and_releases_slot, test_late_classification_preserves_manual_extension, test_quick_reset_skips_backup_and_preserves_settings_and_existing_backups, test_scheduler_lock_prevents_concurrent_duplicate_email. 시연 초기화의 키 보존 검사는 임시 테스트 키로 수행했고 실제 키 값을 발표 자료에 옮기지 않았다. 10/2에는 앱 테스트를 재실행하지 않았다. 9/30에는 별도 격리 run.py의 화면·정적 파일·API HTTP 200도 확인했다.');
""")
slide(25, r"""
 const s=slide('최종보고의 필수 과제와 추가 실험','7. 향후 개발 및 완성 계획',[src.accept,src.hotspot,'docs/paper/EXPERIMENT_GUIDE.md'],'제안 계획 / 아래 횟수는 앞으로 수행할 점검 목표이며 기존 성공 횟수가 아님');
 tab(s,[['우선순위','11월 3일까지의 과제','완료 증거'],['필수  ·  시연','발표 장비에서 연결·종료·재시작\n등록·이동·회수 흐름 확인','연속 3회 점검 기록\n동일 물품 ID·사진·이력'],['필수  ·  관리','검토·편집·기한 연장과 알림 확인\n오류 시 기록 보존·복구 확인','조건·예상·실제 결과표\n실제 메일 수신 또는 남은 한계'],['필수  ·  AI 평가','정답·원본·응답·시각을 연결\n표본 수와 성공·불확실·실패 집계','원시 기록과 평가표\n성공·오류 사례 및 개선 내용'],['추가  ·  비교 연구','같은 영상의 B0/B1/B2/P1 비교\n입력 구성·모델 변경 효과 비교','공통 실행기·반복 실험 결과\n핵심 과제 이후 범위 확정']],[230,517,405],{h:420,size:23});
 tx(s,'일정이 부족하면 추가 비교 범위를 줄이고 필수 시연·평가 증거를 먼저 확보',64,615,1152,31,23,true,C.teal);
 note(s,'연속 3회는 새로 제안한 시연 리허설 기준이다. AI 성능 목표 수치는 파일럿과 허용 오차를 확인한 뒤 확정한다. 비교 연구를 생략 완료로 처리하는 것이 아니라 중간보고 이후 추가 개발 대상으로 우선순위를 정한 것이다.');
""")
slide(26, r"""
 const s=slide('최종보고까지의 주차별 완료 목표','7. 향후 개발 및 완성 계획',['사용자 제공 수업 일정',src.hotspot],'발표일은 수업 확정 일정 / 작업 배분과 세부 완료일은 제안 계획');
 tab(s,[['기간','먼저 완료할 작업','산출물'],['10/02~10/12','실제 화면·동일 ID 캡처, 연결 리허설','중간보고 자료·시연 점검표'],['10/13 중간보고','현재 근거와 남은 과제 설명','피드백·수정 우선순위'],['10/14~10/20','사건별 기록 양식·저장 연결, 파일럿','원본·정답·응답, 오류 목록'],['10/21~10/26','입력·판정 기준 보완, 별도 자료 평가\n관리·메일·재시작 시험','지표·실패 사례·운영 점검표'],['10/27 발표 연습','실제 장비로 처음부터 끝까지 시연','최종 수정 목록'],['10/28~11/03','수정 확인, 배포 고정, 최종보고','최종 PPT·패키지·원시 기록']],[255,545,352],{h:414,size:23});
 note(s,'10/20 중간고사 일정을 고려해 파일럿·기록 연결 범위부터 진행한다. 구현·측정은 장진석 주도, 자료 검토·시연 준비는 권기원 지원이라는 README 역할을 기준으로 제안하며 실제 세부 담당과 날짜는 팀이 확정한다. 공통 baseline 실행기는 필수 현장 검증을 막지 않는 추가 과제로 둔다.');
""")
slide(27, r"""
 const s=slide('최종보고에서 제시할 결과물','7. 향후 개발 및 완성 계획',[src.readme,src.accept,'docs/paper/EXPERIMENT_GUIDE.md']);
 tx(s,'현재: 통합 프로토타입 구현과 기본 실물 흐름 확인',64,178,1152,62,33,true,C.teal);
 rows(s,[['실행 가능한 시스템','발표 장비에서 재시작 후 등록·이동·회수\n동일 ID와 관리자 처리 이력으로 확인'],['AI 평가 자료','정답·원본·응답을 묶어 지표와 사례 제시\n불확실·실패도 포함하고 평가 표본 수 명시'],['재현 가능한 배포본','고정한 코드·설정·패키지와 실행 안내\n점검표·원시 기록·남은 제한 사항을 함께 전달']],{y:287,gap:104,labelW:274});
 tx(s,'다음 단계의 초점: 새 기능 확대보다 실제 환경의 검증 근거 확보',64,618,1152,28,24,true,C.teal);
 note(s,'마무리에서 기능 구현 완료와 정량 성능 미측정을 동시에 설명한다. 제시한 산출물은 최종보고의 제안 완료 기준이며 이미 완성한 결과물 목록으로 읽지 않는다.');
""")
slide(29, r"""
 const s=slide('시연 실행과 데이터 초기화 구분','보충자료 B. 시연 운영',[src.hotspot,src.check],'앱·카메라는 Pi에서 실행 / 상세 단계는 저장소의 Windows 핫스팟 가이드');
 rows(s,[['시작','노트북 Wi-Fi·핫스팟 실행 후 Pi 전원 연결\n2~3분 뒤 Windows에서 SSH 터널, 같은 노트북 웹 접속'],['정상 종료','Pi 정상 종료 명령 후 종료 점멸이 끝날 때까지 대기\nPi 전원 분리 후 핫스팟 종료'],['시연 초기화','확인 후 모든 물품·활동·알림·사진을 백업 없이 삭제\n설정·API 키·기존 백업은 유지'],['설정의 일반 초기화','자동 백업과 확인 문구 입력을 거쳐 실행\n시연 초기화와 보존 방식이 다름']],{y:183,gap:111,labelW:263});
 note(s,'시연을 다시 시작할 때마다 초기화할 필요는 없다. 필요한 기록이 있으면 보존하고, 초기화 전 물품을 카메라 범위에서 치운다. 실행 7단계·종료 4단계·이름 오류 5단계는 REFOUND_WINDOWS_HOTSPOT_GUIDE.md를 따른다. 현재 시연 연결 성공 보고와 새 구성 전원 재인가 성공은 별개다. 내부 접속 주소·키는 발표자료에 적지 않았다.');
""")
slide(30, r"""
 const s=slide('AI 개선을 위한 파일럿과 재평가','보충자료 C. 평가 방법',['docs/paper/EXPERIMENT_GUIDE.md','AGENTS.md'],'아래는 제안 실험 설계 / 확보한 사건 수나 수행 결과가 아님');
 rows(s,[['1  기록 절차 점검','추가·이동·제거·변화 없음 각 10건, 약 40건 파일럿\n사건 ID로 원본·정답·응답·시각을 연결'],['2  오류 유형 분류','그림자·가림·저대비·다중 물품의 실패 조건 확인\n감지 실패, AI 오분류, 불확실·통신 실패를 구분'],['3  기준 보완·고정','입력 증거·프롬프트·판정 기준을 개발 자료에서 보완\n평가 전 코드·모델·설정을 고정'],['4  별도 자료 평가','새 평가 자료에서 지표·표본 수·실패 사례 보고\n연속 영상 Baseline 비교는 추가 실험으로 수행']],{y:184,gap:111,labelW:266});
 note(s,'파일럿 약 40건은 기록 절차·오류 유형 확인용 제안이며 최종 성능의 대표 표본이라고 주장하지 않는다. 개선에 사용한 자료와 최종 평가 자료를 분리한다. B0/B1/B2/P1 비교는 같은 영상·FPS·정답·워밍업으로 수행하고, 기존 pair runner로 시간당 오탐이나 종단간 지연을 주장하지 않는다. Accuracy의 분모에는 불확실·실패 처리를 명시하고 사건 Precision/Recall/F1과 분류 정확도를 구분한다.');
""")

for filename in ['korean_typography.py', 'inspect_powerpoint.ps1']:
    shutil.copy2(root/'output/maintenance/2026-10-02-midterm-review'/filename, build/filename)
(root/'docs/presentation/midterm/build_midterm_v5.mjs').write_text(text,encoding='utf-8')
print('Wrote build_midterm_v5.mjs; original v3/v4 sources preserved.')
