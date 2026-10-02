from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / 'docs/presentation/midterm/build_midterm.mjs').read_text(encoding='utf-8')
source = source.replace('C:/Users/pppp', 'C:/Users/USER').replace('26.909.61513', '26.930.11008')
source = source.replace("2026-09-22-midterm-build", "2026-10-02-midterm-review")
source = source.replace("process.env.DECK_REVISION||'v3'", "process.env.DECK_REVISION||'v4_reviewed'")
source = source.replace('REFOUND_PROJECT_MIDTERM_2026-09-22${', 'REFOUND_PROJECT_MIDTERM_2026-10-02${')
source = source.replace("const meta=[];", "const typography=[];\nconst meta=[];")
source = source.replace("const src={", "const src={hotspot:'REFOUND_WINDOWS_HOTSPOT_GUIDE.md',sync:'output/maintenance/2026-09-30-sync-review/REVIEW.md',git:'git log at 69eb6ff (2026-10-02 inspection)',")
source = source.replace("자료 기준일: 2026-09-22.", "자료 정리일: 2026-10-02. 실기 보고: 2026-09-29까지. 개발 검사: 2026-09-30까지.")
source = source.replace("asOf:'2026-09-22'", "asOf:'2026-10-02'")
source = source.replace("screenshots:['S1','S2','S3','S4','S5']", "screenshots:['development detail: 2026-09-18','development dashboard: 2026-09-22']")

# Keep the existing design and editable objects. Explicit word boundaries are
# measured in the same installed font; no Korean syllable-level fallback.
pos = source.index('function tx(')
source = source[:pos] + r'''
const {createCanvas,GlobalFonts}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@napi-rs/canvas/index.js')).href);
GlobalFonts.registerFromPath('C:/Windows/Fonts/malgun.ttf','Malgun Gothic');
GlobalFonts.registerFromPath('C:/Windows/Fonts/malgunbd.ttf','Malgun Gothic');
const measure=createCanvas(2,2).getContext('2d');
function keepWords(text,width,size,bold=false,font=FONT){
 measure.font=`${bold?'bold ':''}${size}px "${font}"`;
 const result=[];
 for(const paragraph of String(text).split('\n')){
  if(!paragraph.trim()){result.push('');continue;}
  let line='';
  for(const word of paragraph.split(/\s+/)){
   if(measure.measureText(word).width>width-10)throw new Error(`Unbreakable word exceeds width: ${word}`);
   const next=line?line+' '+word:word;
   if(line && measure.measureText(next).width>width-10){result.push(line);line=word;}else line=next;
  }
  result.push(line);
 }
 return result.join('\n');
}
async function screenshot(s,file,x,y,w,h,alt){
 const bytes=await fs.readFile(path.join(ROOT,file));
 s.images.add({blob:bytes,contentType:'image/png',alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});
}
''' + source[pos:]
source = source.replace('t.text=value; t.text.style=', "const safe=extra.typeface==='Consolas'?value:keepWords(value,w,size,bold,extra.typeface||FONT);\n typography.push({slide:p.slides.items.length,kind:'text',text:safe,x,y,w,h,size,bold,font:extra.typeface||FONT});\n t.text=safe; t.text.style=")
source = source.replace("autoFit:'none',wrap:'square'", "autoFit:'none',wrap:'none'")
source = source.replace(' const t=s.tables.add({rows:values.length', " values=values.map((row,r)=>row.map((v,c)=>keepWords(v,widths[c]-28,size,r===0)));\n typography.push({slide:p.slides.items.length,kind:'table',values,widths,x,y,w,h,size});\n const t=s.tables.add({rows:values.length")
source = source.replace('fontSize:size,bold:r===0,color:', "fontSize:size,bold:r===0,wrap:'none',autoFit:'none',color:")
source = source.replace(" n.text=label;n.text.style=", " n.text=keepWords(label,w-24,25,true);n.text.style=")
source = source.replace("verticalAlignment:'middle',insets", "verticalAlignment:'middle',wrap:'none',autoFit:'none',insets")
source = source.replace("발표 2026.10.13   /   구현·검증 기준 2026.09.22", "발표 2026.10.13   /   자료 정리 2026.10.02")
source = source.replace("현재 근거의 기준일은 2026-09-22이며 이후 실기 결과를 미리 반영하지 않음.", "실기 근거는 9월 29일 사용자 보고, 개발 검사는 9월 30일 기록까지 반영. 10월 2일에는 슬라이드를 검토·수정했으며 새 앱·Pi 실험은 수행하지 않음.")
source = source.replace("프로젝트 개발 중간보고',76", "프로젝트 개발 중간보고서',76")
source = source.replace("본문 27장 / 보충자료 3장", "개발 진행상태 및 중간점검")
source = source.replace("'SMTP / systemd / Tailscale'", "'SMTP / systemd / SSH'")
source = source.replace("구현·검사 결과 공유  →  자료 검토  →  실제 시연 점검", "구현·검사 결과를 공유하고 자료 검토와 실제 시연을 진행")

def replace_slide(n, block):
    global source
    pattern = rf'// {n:02d}\n.*?(?=// {n+1:02d}\n)' if n < 30 else r'// 30\n.*?(?=\nawait fs.mkdir\(BUILD)'
    source, count = re.subn(pattern, lambda m: f'// {n:02d}\n{{\n{block}\n}}\n', source, flags=re.S)
    assert count == 1, n

replace_slide(8, r'''
 const s=slide('개발 경과와 현재 단계','3. 프로젝트 개발 진행 현황',[src.vision,src.state,src.hotspot,src.sync,'사용자 제공 수업 일정'],'10월 2일 현재 중간보고 준비 단계 / 중간보고 10월 13일, 최종보고 11월 3일');
 tab(s,[['시점','진행 단계','완료 내용 또는 예정 산출물'],['9/18','앱 안정성 보완','영상·사건 처리·데이터 보존 개선'],['9/22','Pi 설치와 기본 실기','촬영·재부팅 진단, 실물 흐름 성공 보고'],['9/29','노트북 시연 연결','Windows 핫스팟·SSH 웹·AI 성공 보고'],['9/30','저장소 실행 점검','Python 272개·Node 37개 재검사 통과'],['10/02~10/12','중간보고 준비','자료 보완, 실제 캡처와 리허설 예정'],['10/13','7주차 중간보고','개발 결과와 남은 검증 계획 발표']],[220,330,602],{h:427,size:24});
''')
source = source.replace("'장치 부담과 열린 물품 범주 고려'", "'저사양 장치에서 다양한 물품 처리'")
source = source.replace("'공식 전체 진행률  [입력] %'", "'전체 진행률: 산정 기준 미확정'")
source = source.replace("작업 범위·완료 기준 합의 후 산정 / 남은 작업: 실제 AI 정량 평가와 현장 운영 검증", "전체 진행률(%)은 팀의 작업 가중치·완료 기준 합의 후 산정")
replace_slide(10, r'''
 const s=slide('기능별 구현과 실기 확인 상태','3. 프로젝트 개발 진행 현황',[src.readme,src.accept,src.check,src.hotspot],'기능별 상태는 구현·검증 근거로 표시 / 구현률(%)의 합의된 기준은 미확정');
 tab(s,[['기능','구현 상태','확인 결과와 남은 검증'],['카메라·실시간 화면','구현 완료','촬영 로그, 웹 화면·영상 성공 보고'],['등록·이동·회수','구현 완료','기본 실물 흐름 성공 보고'],['외부 AI 분석','구현 완료','9/29 동작 성공 보고, 정량 성능 미측정'],['편집·기한·폐기·복원','구현 완료','자동 검사 통과, Pi 상세 실기 대기'],['웹 알림·SMTP','구현 완료','모의 검사 통과, 실제 메일 수신 대기'],['Windows 무선 시연','검증 진행','연결 성공, 전원 재인가 시험 대기'],['평가 원장·비교 실행기','미구현','사건 시각·정답 기록과 공통 평가 필요']],[325,190,637],{h:434,size:23});
''')
replace_slide(11, r'''
 const s=slide('팀 수행 내용과 Git 개발 이력','3. 프로젝트 개발 진행 현황',[src.readme,src.git],'커밋 반영일과 기능 개발일은 다름 / 커밋 수로 팀 기여율을 산정하지 않음');
 tx(s,'장진석: 구현·통합·배포·검사     권기원: 검토·교정·시연 지원',64,176,1152,52,26,true,C.teal);
 tab(s,[['반영일','커밋','확인한 변경 내용'],['9/08','258efc1','기존 프로젝트 파일 업로드'],['9/30','956b346','9월 30일까지의 소스·자료 일괄 반영'],['9/30','69eb6ff','최신 시연 절차 반영과 임시 파일 정리']],[190,220,742],{y:249,h:268,size:25});
 tx(s,'GitHub  Jinseok2419342 / Capstone-team-project',64,550,1152,43,27,true,C.teal);
 tx(s,'표의 커밋 작성자: Jinseok2419342. 역할별 산출물은 README·검사 기록과 대조.',64,606,1152,32,22,false,C.muted);
 note(s,'로컬 git log에서 날짜·해시·작성자·메시지를 확인했다. 저장소: https://github.com/Jinseok2419342/Capstone-team-project . 표는 실제 이력을 옮긴 편집 가능한 표이며 화면 캡처를 합성하지 않았다. 팀의 담당 역할은 README의 정의로, 개별 팀원이 언제 어떤 검토를 수행했는지에 관한 추가 기록은 수집하지 않았다.');
''')
source = source.replace("'이름·분류 확정 또는 확인 필요'", "'분류 확정 또는 검토 대기'")
replace_slide(14, r'''
 const s=slide('물품 상세 화면과 처리 흐름','4. 핵심 기능 구현 결과',[src.accept,src.live,'output/maintenance/2026-09-18-live-flow-review/browser-classified-detail.png'],'9/18 개발 검사 화면 / 합성 물품·모의 AI 사용. 화면의 97%는 실제 모델 정확도가 아님');
 await screenshot(s,'output/maintenance/2026-10-02-midterm-review/assets/detail.png',64,171,399,466,'합성 데이터 개발 검사에서 저장된 물품 상세 화면');
 rows(s,[['등록','물품을 놓고 손을 뺀 뒤 임시 기록 생성\nAI 분석 후 이름·분류를 확정하거나 검토 대기'],['이동','같은 물품의 위치·사진 갱신\n새 기록을 만들지 않고 기존 ID 유지'],['회수','화면에서 사라지면 같은 기록의 상태 전환\n활동 이력에 처리 결과 저장']],{x:515,y:195,w:701,gap:125,labelW:95});
 tx(s,'실물 흐름은 9/22 성공 보고. 동일 ID의 실제 Pi 캡처는 미확보.',515,595,701,49,22,false,C.muted);
 note(s,'왼쪽은 기존 개발 검사 PNG의 상세 창 영역만 비율을 유지해 잘랐다. 실제 카메라·원격 모델 결과로 해석하지 않는다. 오른쪽은 구현 흐름이다. 사용자 보고에서는 실물 등록·이동 시 중복 방지·제거 후 회수 확인에 성공했다고 했으나 개별 ID·사진은 수집하지 않았다.');
''')
replace_slide(15, r'''
 const s=slide('관리자 대시보드와 운영 기능','4. 핵심 기능 구현 결과',['templates/index.html','static/app.js',src.check,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png'],'9/22 개발 검사 화면 / 물품 수·사진·영상은 합성 테스트 데이터');
 await screenshot(s,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png',64,178,740,455,'합성 카메라·임시 DB를 사용한 관리자 대시보드');
 tx(s,'대시보드',850,180,366,42,29,true,C.teal);
 tx(s,'실시간 카메라와 보관 현황\n기한 도래·확인 필요 항목\n물품 검색과 상세 편집',850,237,366,144,25);
 tx(s,'시연 초기화',850,414,366,42,29,true,C.teal);
 tx(s,'확인 후 모든 물품·기록 삭제\n백업 없이 실행\n설정과 API 키는 유지',850,471,366,124,25);
 note(s,'실제 Pi 관리자 화면은 추가 확보 대상이다. 이 슬라이드는 보존된 개발 검사 캡처로 구현된 UI를 설명한다. 일반 초기화는 자동 백업을 유지하며, 시연 초기화는 사진까지 백업 없이 삭제한다. 실물은 초기화 전에 카메라 범위에서 치운다.');
''')
source = source.replace("'친구 노트북과 핫스팟 연결\\n실제 AI 응답·SMTP 수신\\n여러 물품과 장시간 운영'", "'새 네트워크의 전원 재인가와 자동 연결\\n개별 AI 응답 기록과 실제 SMTP 수신\\n여러 물품과 장시간 운영'")
replace_slide(17, r'''
 const s=slide('데이터 수집과 AI 입력 구성','5. AI 모델 및 데이터 개발 현황',['app/vision.py','app/ai.py','app/config.py',src.readme],'운영 사진의 전체 수량은 미집계 / 정답 라벨이 있는 평가 세트는 미확보');
 tab(s,[['단계','현재 처리와 확보 수준'],['원시 데이터','고정 CSI 카메라의 연속 영상과 사건별 사진'],['로컬 전처리','움직임 종료·장면 안정화, 기하 정합과 조명 보정'],['전체 장면 전후 2장','변화 방향과 주변 문맥 확인, JPEG 품질 72'],['후보 영역 전후 2장','물품의 세부 특징 확인, JPEG 품질 88'],['평가 데이터','정답 라벨·AI 응답을 연결한 평가 자료 수집 예정']],[290,862],{h:393,size:24});
 tx(s,'요청당 최대 4장. 자체 학습·데이터 증강·파인튜닝은 수행하지 않았다.',64,597,1152,40,25,true,C.teal);
 note(s,'통계형 결측치 대치나 학습 데이터 정규화는 적용 대상이 아니다. 프레임 읽기 실패는 연결 복구 흐름에서 처리한다. 사진 수량과 평가 사건 수를 근거 없이 만들지 않았다.');
''')
replace_slide(18, r'''
 const s=slide('적용 모델과 구조화 추론 방법','5. AI 모델 및 데이터 개발 현황',['app/ai.py','app/config.py',src.state,src.hotspot],'모델별 정확도·비용 비교는 미실시 / RAG·자체 학습·파인튜닝은 미적용');
 rows(s,[['모델·선정 이유','OpenAI 사용, Gemini 연동 경로도 구현\n다양한 물품을 전후 이미지와 문맥으로 해석'],['설정 확인 범위','9/22 설정: gpt-5.6-luna\n9/29 OpenAI 동작 성공 보고, 당일 모델명은 미수집'],['프롬프트·출력','전후 증거와 판단 지침, JSON schema를 함께 전달\naction·물품명·분류·확신도·근거를 해석'],['응답 검증','기본 모델의 reasoning low, 출력 상한 2,048토큰\n완료 상태와 내용을 검사하고 오류·불확실 기록 보존']],{y:181,gap:111,labelW:239});
 note(s,'모델은 Pi 설정 로그의 문자열을 날짜와 함께 표시했다. 학습 조건이 아니라 추론 요청 설정이다. OpenAI strict schema와 기본 모델의 낮은 추론 강도 설정은 app/ai.py 근거다. 특정 모델의 우수성이 비교 실험으로 확인됐다는 뜻은 아니다.');
''')
replace_slide(19, r'''
 const s=slide('현재 성능 확인 범위와 평가 지표','5. AI 모델 및 데이터 개발 현황',[src.hotspot,src.accept,'docs/paper/EXPERIMENT_GUIDE.md'],'9/29 OpenAI 동작 성공 보고 확보 / 정답·개별 응답·표본 수를 연결한 정량 결과는 없음');
 tab(s,[['평가 항목','현재 상태','수집할 근거'],['사건 Precision / Recall / F1','미측정','추가·이동·제거별 TP·FP·FN'],['물품 분류 정확도','미측정','정답 분류와 AI 응답, 표본 수 N'],['불확실 판정 비율','미측정','전체 사건 수와 uncertain 건수'],['종단간 지연 p50 / p95','미측정','행동 종료와 DB 반영 시각'],['성공·실패 사례 분석','원본 미수집','같은 사건의 사진·정답·응답']],[410,210,532],{h:397,size:25});
 tx(s,'다음 평가: 사건별 정답과 응답을 함께 저장하고 지표를 계산한다.',64,603,1152,40,26,true,C.teal);
''')
source = source.replace("'공통 스트림 실행기 구현 예정'", "'비교 실행기 미구현'")
source = source.replace("'앱 구현 / 동일 조건 실측 대기'", "'앱 구현, 실측 대기'")
source = source.replace("{h:335,size:22}", "{h:335,size:24}")
replace_slide(21, r'''
 const s=slide('자동화 테스트와 통합 검사','6. 테스트 결과 및 문제점 분석',[src.check,src.live,src.sync],'합성 카메라·임시 DB·모의 AI·SMTP를 사용한 개발 검사');
 [['272','Python 검사','9/30 재실행 통과'],['37','Node 검사','9/30 재실행 통과'],['7','Chromium 검사','9/22 검사 통과']].forEach(([n,l,d],i)=>{tx(s,n,64+i*402,169,360,91,76,true,C.teal);tx(s,l,67+i*402,264,360,39,27,true);tx(s,d,67+i*402,310,360,35,23,false,C.muted);});
 tab(s,[['검사 조건','예상 결과와 실제 결과'],['합성 사건·관리 흐름','등록·이동·상태 변경·활동 이력 연결 검사 통과'],['초기화·반응형 화면','확인·취소·설정 보존·후속 등록 검사 통과'],['9/30 격리 서버 시작','화면·정적 파일·주요 API의 HTTP 200 확인']],[350,802],{y:382,h:238,size:24});
 note(s,'Python 272개·Node 37개는 9월 30일 재실행 기록이다. Chromium 7개는 9월 22일 기록이며 9월 30일에 재실행하지 않았다. 10월 2일에는 슬라이드 검토만 수행했다. 개수를 서로 합산하거나 AI 정확도로 해석하지 않는다.');
''')
replace_slide(22, r'''
 const s=slide('실제 Pi 시연에서 확인한 결과','6. 테스트 결과 및 문제점 분석',[src.state,src.accept,src.hotspot],'로그 확인과 사용자 성공 보고를 구분 / 새 네트워크의 전원 재인가 시험은 아직 미확인');
 tab(s,[['확인일·항목','근거','결과'],['9/22 설치·촬영','사용자 제공 로그','설치 완료, OV5647 촬영·프레임 획득'],['9/22 재부팅 진단','사용자 제공 로그','서비스 active, DB·카메라 연결'],['9/22 등록·이동·회수','사용자 성공 보고','기본 실물 흐름 정상'],['9/29 Windows 핫스팟','사용자 제공 로그','Wi-Fi 검색과 Pi 연결 활성화'],['9/29 SSH 웹·OpenAI','사용자 성공 보고','노트북 화면 접속과 API 동작 성공'],['추가 확인 대상','미확인','자동 재연결, 실제 메일·장시간 운영']],[345,240,567],{h:429,size:24});
 note(s,'9월 22일 본인 PC의 Tailscale 화면·영상도 성공 보고가 있다. 현재 주 시연 경로는 Windows 핫스팟과 SSH 터널이다. 친구 Tailscale 수락·접속은 별도 미확인으로 남으며 현재 시연의 선행 조건이 아니다.');
''')
replace_slide(23, r'''
 const s=slide('주요 문제의 원인과 해결','6. 테스트 결과 및 문제점 분석',[src.vision,src.arch,src.live,src.hotspot],'데이터 보존과 시연 연결을 우선 점검 / 해결 후 확인 범위는 해당 검사·보고 기준');
 tab(s,[['문제','확인한 원인','수정과 확인'],['정지 화면의 미세 흔들림','정합 영상을 미리보기에 사용','원본 영상과 박스 좌표 투영 분리'],['사건 누락·중복 위험','DB 저장 전 기준 장면 갱신','저장 확인 후 갱신, 사건 ID 검사'],['늦은 AI 응답의 충돌','추론 중 물품 기록·상태 변경','검토 상태와 추적 revision 검사'],['연속 편집·모바일 넘침','갱신 잠금·숨김 라벨 위치','작업 잠금 분리, 390px 검사'],['SSH 로그인 후 웹 접속 실패','Pi 내부에서 터널 시작','Windows에서 실행 후 성공 보고']],[334,360,458],{h:432,size:24});
 note(s,'정지 영상 문제는 합성 장면에서 소프트웨어 원인을 재현했다. 센서 노출이나 물리 흔들림까지 해결됐다고 주장하지 않는다. 새 SD 설치 복구는 설치기·체크섬·카메라 및 시스템 진단 로그로 확인했다. SSH 오류 원인은 이번 9/29 터널 위치 오류에 한정한다. 다른 끊김이나 프로필 오류의 원인을 추측하지 않는다.');
''')
replace_slide(25, r'''
 const s=slide('최종보고 전 개발·검증 우선순위','7. 향후 개발 및 완성 계획',[src.accept,src.hotspot,'docs/paper/EXPERIMENT_GUIDE.md','사용자 제공 수업 일정'],'제안 계획 / 성능 목표 수치는 파일럿 결과와 운영 허용 오차를 바탕으로 확정');
 rows(s,[['우선 1  시연 안정화','핫스팟 자동 연결과 전원 재인가 후 영상·AI 복귀\n완료 근거: 같은 발표 장비의 반복 실행 기록'],['우선 2  운영 검증','다중 물품, 편집·메일, privacy 복원, 장시간 감시\n완료 근거: 조건·예상·실제 결과를 연결한 점검표'],['우선 3  평가 구현','사건·API 시각 원장, 정답 라벨, 공통 비교 실행기\n완료 근거: 원시 CSV와 동일 입력의 비교 결과'],['AI 개선 반복','약 40건 파일럿으로 오류 유형과 기록 절차 확인\n입력·판정 기준을 고정한 뒤 별도 자료로 재평가']],{y:181,gap:111,labelW:267});
 note(s,'약 40건은 추가·이동·제거·none 각 10건의 제안 구성이며 확보한 데이터나 최종 표본 수가 아니다. 기존 모델 학습은 없으므로 입력 증거·프롬프트·판정 기준의 조정과 필요한 경우 모델 변경을 비교한다.');
''')
replace_slide(26, r'''
 const s=slide('11월 3일 최종보고까지의 일정','7. 향후 개발 및 완성 계획',['사용자 제공 수업 일정',src.hotspot],'발표일은 수업 확정 일정 / 개발 작업과 완료 목표는 제안 일정');
 tab(s,[['기간','개발·검증 계획','완료 산출물'],['10/02~10/12','실제 캡처, 연결 리허설, 평가 설계','중간보고 자료·시연 기록'],['10/13 중간보고','구현·검증 범위와 남은 계획 발표','피드백과 수정 우선순위'],['10/14~10/20','측정 원장·비교 실행기, 파일럿','원시 CSV·정답 라벨·오류 목록'],['10/21~10/26','동일 입력 비교, 운영 안정화','평가표·실패 사례·반복 검사'],['10/27 발표 연습','전체 시연과 결과·화면 점검','최종 수정 목록'],['10/28~11/03','자료 보완, 배포 고정, 최종보고','최종 PPT·패키지·검증 기록']],[255,510,387],{h:431,size:23});
 note(s,'10/20은 중간고사 일정이므로 실제 팀 작업량에 맞춰 10/14~10/20의 범위를 조정한다. 구현·계측은 팀장 주도, 자료 검토·시연 준비는 팀원 지원이라는 현재 역할을 기준으로 협업하며 세부 담당과 마감은 팀 합의가 필요하다.');
''')
replace_slide(29, r'''
 const s=slide('현재 시연 연결 구조','보충자료 B. 시연 운영',[src.hotspot],'앱·카메라는 Pi에서 실행 / 시연 노트북은 핫스팟과 웹 접속을 담당');
 rows(s,[['인터넷 연결','노트북을 인터넷 Wi-Fi에 연결한 뒤 모바일 핫스팟 실행'],['Pi 시작','핫스팟을 먼저 켜고 Pi 전원 연결, 약 2~3분 대기'],['웹 접속','Windows PowerShell에서 SSH 터널 시작\n같은 노트북 브라우저에서 관리자 화면 접속'],['종료·재실행','작업 완료 후 Pi 정상 종료, 종료 점멸이 끝나면 전원 분리\n다음 실행 때 핫스팟과 SSH 터널을 다시 시작']],{y:185,gap:106,labelW:232});
 note(s,'상세 실행 7단계·종료 4단계·이름 오류 대응 5단계는 REFOUND_WINDOWS_HOTSPOT_GUIDE.md를 따른다. 공개 발표자료에는 내부 접속 주소·비밀번호·키를 적지 않았다. 이 사용 순서의 확정과 새 구성의 실제 전원 재인가 성공은 별개다.');
''')
replace_slide(30, r'''
 const s=slide('정량 평가의 설계와 해석 기준','보충자료 C. 평가 방법',['docs/paper/EXPERIMENT_GUIDE.md','AGENTS.md']);
 rows(s,[['평가 자료','안정 이미지 쌍, 연속 영상, 동일 사건의 VLM 증거를 구분\n그림자·가림·저대비·다중 물품 조건을 기록'],['공통 비교 조건','같은 영상·FPS·정답 라벨로 B0/B1/B2/P1 비교\n개발 자료에서 기준을 정한 뒤 별도 자료로 평가'],['정확도와 지연','사건별 TP·FP·FN, 분류 정답, 불확실·실패 응답 기록\n지연에는 표본 수·검출률·시각 누락률을 함께 제시'],['운영 검증','동일 물품 ID, 상태·사진·활동 이력을 함께 확인\n실패 시 조건·실제 결과·복구 과정을 보존']],{y:184,gap:111,labelW:255});
 note(s,'평가 설계이며 수행 결과가 아니다. pair runner는 detector core만 평가한다. FP/hour와 실제 DB 중복 방지, 종단간 지연은 연속 입력과 영속 기록이 필요하다. 공식 진행률은 팀이 합의한 전체 작업 가중치와 완료 기준으로 별도 산정한다.');
''')

# Shape/table text is now explicitly broken at spaces. PowerPoint's Korean
# paragraph settings are additionally applied to the OOXML candidate.
source = source.replace("await(await PresentationFile.exportPptx(p)).save(candidatePath);", "await(await PresentationFile.exportPptx(p)).save(candidatePath);\nconst {execFileSync}=await import('node:child_process');\nexecFileSync(path.join(RT,'dependencies/python/python.exe'),[path.join(BUILD,'korean_typography.py'),candidatePath],{stdio:'inherit'});\nawait fs.writeFile(path.join(BUILD,`typography-${revision}.json`),JSON.stringify(typography,null,2));")
source = source.replace("const renderDir=path.join(BUILD,`render-${revision}`);", "const renderDir=path.join(BUILD,`render-${revision}`);")
source = source.replace("const finalDeck=await PresentationFile.importPptx", "if(process.env.SKIP_ARTIFACT_RENDER==='1'){console.log(JSON.stringify({final:FINAL,slides:30}));process.exit(0);}\nconst finalDeck=await PresentationFile.importPptx")
source = source.replace('저사양 장치에서 다양한 물품 처리', '저사양 장치·다양한 물품 대응')
source = source.replace('SSH 로그인 후 웹 접속 실패', 'SSH 후 웹 접속 실패')
source = source.replace("tx(s,n,64+i*402,169,360,91,76", "tx(s,n,64+i*402,165,360,100,76")
source = source.replace("tx(s,'장진석: 구현·통합·배포·검사     권기원: 검토·교정·시연 지원',64,176,1152,52,26,true,C.teal);", "tx(s,'장진석: 구현·통합·배포·검사',64,176,575,52,26,true,C.teal);\n tx(s,'권기원: 검토·교정·시연 지원',675,176,541,52,26,true,C.teal);")
source = source.replace('관리자가 확인·편집을 마친 기록에는 뒤늦은 분류를 적용하지 않는다.', '관리자가 검토를 완료한 기록에는 뒤늦은 분류를 적용하지 않는다.')
(ROOT / 'docs/presentation/midterm/build_midterm_v4.mjs').write_text(source,encoding='utf-8')
print('Updated authoring source: build_midterm_v4.mjs')
