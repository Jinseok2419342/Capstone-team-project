import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../../..');
const RT='C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime';
const SKILL='C:/Users/pppp/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.61513/skills/presentations';
process.env.RUNTIME_NODE_MODULES=path.join(RT,'dependencies/node/node_modules');
process.env.RUNTIME_NODE=path.join(RT,'dependencies/node/bin/node.exe');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const BUILD=path.join(ROOT,'output/maintenance/2026-09-22-midterm-build');
const revision=process.env.DECK_REVISION||'v3';
const FINAL=path.join(ROOT,'output/presentation',`REFOUND_PROJECT_MIDTERM_2026-09-22${revision==='v1'?'':'_'+revision}.pptx`);
if(await fs.stat(FINAL).then(()=>true,()=>false))throw new Error('Output exists. Set DECK_REVISION to a new revision name; preserve any manually edited PPTX.');
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#102D3C',ink:'#183442',teal:'#067C80',muted:'#566B77',line:'#CFDBDE',pale:'#EEF6F5',white:'#FFFFFF',amber:'#9B5A10'};
const FONT='Malgun Gothic';
const meta=[]; const tableOwners=[]; const chartOwners=[]; const noteText=new WeakMap();
const src={readme:'README.md',accept:'docs/guides/PI_ACCEPTANCE_CHECKLIST.md',state:'output/maintenance/2026-09-22-network-plan/SESSION_STATUS.json',check:'output/maintenance/2026-09-22-quick-reset/VALIDATION.json',vision:'docs/VISION_REVIEW_2026-09-18.md',arch:'docs/ARCHITECTURE_REVIEW_2026-09-18.md',live:'docs/LIVE_FLOW_REVIEW_2026-09-18.md'};
function tx(s,value,x,y,w,h,size=26,bold=false,color=C.ink,extra={}){
 const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 t.text=value; t.text.style={typeface:FONT,fontSize:size,bold,color,lineSpacing:1.12,autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0},...extra}; return t;
}
function line(s,x,y,w,color=C.line){s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:0},fill:'none',line:{fill:color,width:1}});}
function slide(title,section,refs=[],foot=''){
 const s=p.slides.add();s.background.fill=C.white;
 tx(s,section,64,29,1120,25,18,true,C.teal);
 tx(s,title,64,76,1152,77,44,true);
 line(s,64,650,1152);
 if(foot)tx(s,foot,64,668,1085,28,16,false,C.muted);
 tx(s,String(p.slides.items.length).padStart(2,'0'),1160,667,56,30,18,true,C.muted,{alignment:'right'});
 const baseNotes='자료 기준일: 2026-09-22. 발표 예정일: 2026-10-13.\n근거:\n'+refs.map(r=>'- '+r).join('\n'); noteText.set(s,baseNotes); s.speakerNotes.textFrame.setText(baseNotes);
 meta.push({slide:p.slides.items.length,title,section,sources:refs});return s;
}
function note(s,text){const combined=noteText.get(s)+'\n'+text;noteText.set(s,combined);s.speakerNotes.textFrame.setText(combined);}
function para(s,title,body,x,y,w=530){tx(s,title,x,y,w,40,29,true,C.teal);tx(s,body,x,y+54,w,139,27);}
function rows(s,items,{x=64,y=187,w=1152,gap=93,labelW=255}={}){
 items.forEach(([a,b],i)=>{tx(s,a,x,y+i*gap,labelW,45,27,true,C.teal);tx(s,b,x+labelW+28,y+i*gap,w-labelW-28,gap-9,26); if(i<items.length-1)line(s,x,y+i*gap+gap-17,w);});
}
function tab(s,values,widths,{x=64,y=181,w=1152,h=398,size=23}={}){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
 t.styleOptions={headerRow:false,bandedRows:false};
 const range=t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length});
 range.assign({textStyle:{typeface:FONT,fontSize:size,color:C.ink},margins:{left:14,right:14,top:12,bottom:10},anchor:'middle'});
 t.borders.assign({fill:C.line,width:1,style:'solid'});
 for(let r=0;r<values.length;r++){t.rows[r].height=h/values.length;for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill=r===0?C.navy:(r%2?C.white:'#F4F8F8');cell.text.style={typeface:FONT,fontSize:size,bold:r===0,color:r===0?C.white:C.ink};}}
 tableOwners.push(p.slides.items.length);return t;
}
function slot(s,id,label,x,y,w,h,detail=''){
 const sh=s.shapes.add({geometry:'rect',name:`FILL_${id}`,position:{left:x,top:y,width:w,height:h},fill:'#F5F8F8',line:{fill:'#8BA6AB',style:'dashed',width:2}});
 tx(s,id,x+24,y+25,w-48,35,22,true,C.teal);
 tx(s,label,x+24,y+h/2-37,w-48,88,31,true,C.muted,{alignment:'center'});
 if(detail)tx(s,detail,x+24,y+h-69,w-48,50,19,false,C.muted,{alignment:'center'});
 return sh;
}
function node(s,label,x,y,w,h,{fill=C.pale,color=C.ink}={}){
 const n=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:C.teal,width:1.5}});
 n.text=label;n.text.style={typeface:FONT,fontSize:25,bold:true,color,alignment:'center',verticalAlignment:'middle',insets:{left:12,right:12,top:15,bottom:12}};return n;
}
function connect(s,a,b,from='right',to='left',kind='straight'){
 return s.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:C.teal,width:2},tail:{type:'arrow',width:'med',length:'med'}});
}
// 01
{
 const s=p.slides.add();s.background.fill=C.navy;
 tx(s,'Re:Found',70,129,1110,112,88,true,C.white);
 tx(s,'분실물 자동 추론 및 시각화 관리 시스템',76,269,1100,76,40,true,'#BDE8E2');
 tx(s,'프로젝트 개발 중간보고',76,374,1100,61,35,false,C.white);
 tx(s,'동양미래대학교 인공지능소프트웨어학과\n상부상조(2조)  장진석 · 권기원',76,536,1100,75,24,false,C.white);
 tx(s,'발표 2026.10.13   /   구현·검증 기준 2026.09.22',76,650,1110,30,20,false,'#BDE8E2');
 s.speakerNotes.textFrame.setText('출처: README.md의 프로젝트명·소속·팀원. 발표일은 사용자가 제공한 수업 일정. 현재 근거의 기준일은 2026-09-22이며 이후 실기 결과를 미리 반영하지 않음.');
 meta.push({slide:1,title:'Re:Found 프로젝트 개발 중간보고',section:'표지',sources:[src.readme,'사용자 제공 수업 일정']});
}
// 02
{
 const s=slide('발표 구성','중간보고',[ '첨부: 프로젝트개발중간보고 목차구성.md','사용자 제공 수업 일정'],'본문 27장 / 보충자료 3장');
 const labels=['프로젝트 개요 및 개발 목표','시스템 설계 및 개발 구조','프로젝트 개발 진행 현황','핵심 기능 구현 결과','AI 모델 및 데이터 개발 현황','테스트 결과 및 문제점 분석','향후 개발 및 완성 계획'];
 labels.forEach((v,i)=>{tx(s,String(i+1).padStart(2,'0'),74,186+i*57,64,38,25,true,C.teal);tx(s,v,160,186+i*57,900,44,28);});
}
// 03
{
 const s=slide('분실물 보관대의 기록과 관리 문제','1. 프로젝트 개요 및 개발 목표',[src.readme]);
 para(s,'해결할 문제','물품을 발견해도 사진 등록과 분류,\n기한 확인을 담당자가 이어서 처리해야 한다.',64,186,1100);
 rows(s,[['기록의 일관성','물품을 옮겼을 때 같은 기록을 유지하고,\n사라졌을 때 상태와 이력을 연결해야 한다.'],['주요 사용자','학교 행정실, 도서관, 공용공간의 분실물 관리자'],['적용 환경','카메라를 고정할 수 있는 보관대와 실내 수거 공간']],{y:365,gap:84,labelW:250});
 note(s,'문제 정의와 적용 환경은 프로젝트의 설계 가정이다. 기관별 업무 실태 조사나 정량적인 수작업 절감 결과로 제시하지 않는다.');
}
// 04
{
 const s=slide('로컬 사건 감지와 선택적 AI 추론','1. 프로젝트 개요 및 개발 목표',[src.readme,'app/main.py:534','app/ai.py:80']);
 tx(s,'Pi가 변화 시점을 찾고, 필요한 사건의 의미를 AI로 보완한다.',64,177,1152,64,32,true,C.teal);
 rows(s,[['장면 관찰','고정 카메라에서 물품의 추가·이동·제거 후보를 찾는다.'],['AI의 역할','신규 물품의 이름·분류를 제안하고 모호한 제거를 검증한다.'],['관리 업무','보관 기한과 알림, 회수·폐기·복원을 같은 기록에 연결한다.'],['최종 산출물','Pi 카메라 장치 + FastAPI 서버 + 관리자 웹\n설치 패키지와 실행·검증 기록']],{y:280,gap:85,labelW:228});
}
// 05
{
 const s=slide('전체 시스템 구성','2. 시스템 설계 및 개발 구조',[src.readme,'app/main.py','app/vision.py','app/store.py','app/ai.py'],'화살표는 주요 데이터 전달 방향을 나타냄');
 const a=node(s,'CSI 카메라\nPicamera2',64,215,219,116);
 const b=node(s,'로컬 사건 감지\nOpenCV',328,215,239,116);
 const c=node(s,'사건 처리 · API\nFastAPI',620,215,272,116);
 const d=node(s,'관리자 웹\nHTML / CSS / JS',965,215,251,116);
 connect(s,a,b);connect(s,b,c);connect(s,c,d);
 tx(s,'프레임',285,181,140,29,18,false,C.muted);
 tx(s,'후보·증거',566,181,140,29,18,false,C.muted);
 tx(s,'JSON / MJPEG',917,181,244,29,18,false,C.muted);
 const db=node(s,'SQLite WAL\n물품·활동·알림·설정',601,468,310,123);
 const ai=node(s,'외부 VLM API\nOpenAI / Gemini',956,468,260,123);
 connect(s,c,db,'bottom','top');connect(s,c,ai,'bottom','top','elbow');
 tx(s,'관찰 기록을 먼저 저장',409,368,335,38,22,true,C.teal);
 tx(s,'added / verify_removed\n사건만 요청',783,408,285,57,20,true,C.teal);
 tx(s,'Pi 내부에 사진 파일 저장\nsystemd 자동 시작',64,489,479,93,24,false,C.muted);
 note(s,'AI 응답은 FastAPI로 돌아와 현재 기록과 검토 상태를 확인한 뒤 반영한다. 웹의 편집 요청도 FastAPI로 들어온다. 간결성을 위해 그림은 주요 흐름만 표시했다.');
}
// 06
{
 const s=slide('모듈별 역할과 기술 스택','2. 시스템 설계 및 개발 구조',[src.readme,src.state,'app/camera_sources.py','app/notifier.py']);
 tab(s,[['모듈','담당 기능','구현 기술'],['카메라·비전','프레임 입력, 안정화, 변화 감지','Picamera2 / OpenCV'],['사건·AI 처리','임시 저장, 추론 요청, 응답 검증','Python / HTTPX'],['서버·저장','API, 상태 전이, 사진과 활동 이력','FastAPI / SQLite WAL'],['관리자 화면','실시간 영상, 목록, 편집, 설정','Vanilla HTML / CSS / JS'],['운영·배포','만료 알림, 서비스 자동 시작','SMTP / systemd / Tailscale']],[245,465,442],{h:365});
 tx(s,'실제 장치   Raspberry Pi 4 Model B 2GB + CSI 카메라(OV5647)',64,571,1152,35,25,true,C.teal);
 tx(s,'확인 환경   Debian 13 Trixie / Python 3.13.5 / OpenCV 4.10.0',64,610,1152,30,22,false,C.muted);
}
// 07
{
 const s=slide('팀 역할과 협업 방식','2. 시스템 설계 및 개발 구조',[src.readme],'역할은 현재 README 기준. 커밋별 기여도는 별도 확인 필요');
 para(s,'장진석  ·  팀장 / 시스템 통합','기획·아키텍처와 로컬 비전 구현\n멀티모달 AI, FastAPI, 관리자 웹 연결\nPi 배포와 테스트·문서화',64,197,548);
 para(s,'권기원  ·  개발 / 시연 지원','구현과 발표 자료 검토\n자료 교정\n시연 준비와 운영 지원',682,197,534);
 tx(s,'연계 업무',64,450,240,42,29,true,C.teal);
 tx(s,'구현·검사 결과 공유  →  자료 검토  →  실제 시연 점검\n발견한 오류와 미확인 항목을 다음 수정·검증에 반영',64,511,1152,96,28);
}
// 08
{
 const s=slide('현재 위치와 수업 일정','3. 프로젝트 개발 진행 현황',['사용자 제공 수업 일정',src.vision,src.live,src.state],'개발 기록 기준일은 9월 22일. 발표일까지의 작업은 계획으로 구분');
 tab(s,[['시점','수업·발표 일정','현재 근거 또는 예정 작업'],['9/08  ·  3주차','팀프로젝트 현황보고','기존 프로젝트 소개 단계'],['9/18  ·  개발 기록','앱·비전·처리 구조 보완','연결 복구와 데이터 보존 회귀 검사'],['9/22  ·  5주차 / 현재','중간보고 작성 시작','새 SD 설치·카메라·재부팅 진단 확인'],['9/29  ·  6주차','중간보고 작성','실기 증거 확보와 자료 보완 예정'],['10/13  ·  7주차','프로젝트 개발 중간보고 발표','현재 구현·검증 결과와 남은 계획 보고'],['10/27 / 11/03','최종보고 연습 / 최종보고 발표','추가 평가·안정화 결과 제출 예정']],[265,415,472],{h:429,size:22});
}
// 09
{
 const s=slide('초기 계획과 실제 구현의 차이','3. 프로젝트 개발 진행 현황',[src.readme],'작업 범위·완료 기준 합의 후 산정 / 남은 작업: 실제 AI 정량 평가와 현장 운영 검증');
 tab(s,[['초기 계획','현재 구현','변경 이유'],['Pi 5 / USB 카메라','Pi 4 2GB / CSI 카메라','보유 장비에 맞춘 배포'],['YOLO·CNN·로컬 LLM','OpenCV + 외부 VLM','장치 부담과 열린 물품 범주 고려'],['클라우드 DB','SQLite WAL + 사진 파일','단일 장치 운영 단순화'],['AI 응답 후 등록','관찰 우선 저장 후 비동기 추론','API 장애 때에도 기록 보존'],['React·복수 백엔드 검토','Vanilla JS + FastAPI','배포·유지보수 구조 단순화']],[370,420,362],{h:393,size:23});
 tx(s,'공식 전체 진행률  [입력] %',64,600,1152,38,28,true,C.teal);
 note(s,'공식 진행률의 분모·가중치·완료 기준이 제공되지 않았으므로 수치를 만들지 않았다. 작성 가이드의 가중 작업 산식으로 산정 후 입력한다. 초기 계획 대비 빠름/지연은 기존 예정 완료일이 없어 단정하지 않는다.');
}
// 10
{
 const s=slide('기능별 구현과 실기 확인 상태','3. 프로젝트 개발 진행 현황',[src.readme,src.accept,src.check],'구현 여부와 현장 확인 수준을 분리함. 미확인은 실패 판정이 아님');
 tab(s,[['기능','코드 상태','현재 확인 범위'],['카메라 입력·실시간 화면','구현','촬영 로그 + PC 화면 성공 보고'],['추가·이동·제거 처리','구현','기본 실물 흐름 사용자 성공 보고'],['외부 AI 분류·제거 검증','구현','설정 확인 / 개별 원격 응답 미수집'],['편집·기한·폐기·복원','구현','자동 검사 / 실제 Pi 상세 실기 대기'],['웹 알림·SMTP 메일','구현','모의 검사 / 실제 메일 수신 대기'],['시연 초기화·재시작','구현','초기화 성공 보고 + 재부팅 진단'],['친구 노트북·핫스팟 시연','준비 중','공유 초대 전송 / 접속·무선 부팅 대기']],[330,175,647],{h:432,size:22});
}
// 11
{
 const s=slide('팀 수행 내용과 버전관리 근거','3. 프로젝트 개발 진행 현황',[src.readme,'로컬 폴더의 .git 부재 확인','output/maintenance/'],'로컬 변경 백업과 검사 로그는 보존. Git 커밋 이력과는 구분');
 tx(s,'README의 수행 분담',64,180,507,38,28,true,C.teal);
 tx(s,'장진석\n시스템 구현·통합, 배포, 검사와 문서화\n\n권기원\n자료 검토·교정과 시연 준비 지원',64,242,518,229,27);
 tx(s,'현재 작업 폴더에는 .git이 없어\n커밋·작성자별 기여를 확인하지 못했다.',64,526,533,89,25,false,C.muted);
 slot(s,'S1','저장소 개발 이력 캡처',644,185,572,357,'날짜 · 작성자 · 커밋 메시지 포함');
 tx(s,'저장소 URL [입력]  /  주요 커밋 3~5개 [입력]',644,566,572,66,22,false,C.muted);
}
// 12
{
 const s=slide('실행 가능한 핵심 사건 처리','4. 핵심 기능 구현 결과',['app/vision.py','app/main.py:534','app/main.py:432'],'자동 회수는 화면상 사라짐을 기록한 상태이며 실제 소유자 반환의 증거는 아님');
 tab(s,[['입력 사건','주요 처리','출력'],['added  ·  새 물품','임시 기록 저장 후 AI 분류 요청','이름·분류 확정 또는 확인 필요'],['moved  ·  같은 물품 이동','활성 물품 대응과 위치·사진 갱신','기존 ID 유지'],['removed  ·  명확한 제거','저장된 배경과 제거 근거 확인','회수 상태와 활동 이력'],['verify_removed  ·  모호한 제거','외부 AI로 사라짐 여부 재검증','회수 또는 추적·검토 유지']],[376,421,355],{h:377,size:24});
 tx(s,'움직임이 끝나고 장면이 안정된 뒤 사건 후보를 처리한다.',64,596,1152,39,27,true,C.teal);
}
// 13
{
 const s=slide('AI 응답보다 관찰 저장을 먼저 수행','4. 핵심 기능 구현 결과',['app/main.py:361','app/main.py:534','app/classification.py:49',src.arch]);
 const a=node(s,'물품 감지',64,199,244,102), b=node(s,'임시 기록 저장',360,199,270,102), c=node(s,'AI 비동기 요청',681,199,275,102),d=node(s,'검토·확정',1007,199,209,102);
 connect(s,a,b);connect(s,b,c);connect(s,c,d);
 tx(s,'실제 코드 발췌  ·  app/main.py',64,352,720,35,23,true,C.teal);
 tx(s,'with _item_mutation_lock:\n    item = create_provisional_item(event)',64,405,775,94,27,false,C.ink,{typeface:'Consolas'});
 tx(s,'submit_classification(\n    classify_existing_item, item["id"], event,\n    item_tracking_signature(item)\n)',64,512,804,127,24,false,C.ink,{typeface:'Consolas'});
 tx(s,'AI 오류·불확실 응답에도\n사진과 관찰 기록을 보존\n\n관리자 수정 뒤의 응답은\n현재 검토 상태를 확인',897,370,319,241,24);
 note(s,'두 코드는 app/main.py handle_vision_change의 실제 문장에서 발췌했으며 중간 예외 처리·조건문은 생략했다. 아래 submit_classification 표현은 호출부만 발췌한 것으로 전체 if 문은 보충자료와 원본 코드에서 확인한다.');
}
// 14
{
 const s=slide('실물 등록·이동·회수 실행 화면','4. 핵심 기능 구현 결과',[src.accept],'현재 근거: 사용자 성공 보고. 아래에는 같은 물품의 실제 Pi 화면을 삽입');
 slot(s,'S2','물품 등록 후',64,209,359,253,'물품 이름 · ID · 사진');
 slot(s,'S3','같은 물품 이동 후',460,209,359,253,'동일 ID · 바뀐 위치');
 slot(s,'S4','물품 제거 후',857,209,359,253,'회수 상태 · 활동 기록');
 tx(s,'1  물품을 놓고 손을 뺀다',64,493,359,45,25,true,C.teal);
 tx(s,'등록된 기록과 사진을 확인',64,553,359,69,25);
 tx(s,'2  같은 물품을 옮긴다',460,493,359,45,25,true,C.teal);
 tx(s,'기존 ID와 물품 수를 비교',460,553,359,69,25);
 tx(s,'3  물품을 완전히 치운다',857,493,359,45,25,true,C.teal);
 tx(s,'같은 기록의 상태 전환 확인',857,553,359,69,25);
}
// 15
{
 const s=slide('관리자 화면과 운영 기능','4. 핵심 기능 구현 결과',['templates/index.html','static/app.js','app/main.py:1287',src.accept]);
 slot(s,'S5','실제 Pi 관리자 화면',64,185,763,431,'대시보드 또는 물품 상세 화면 / 주소창 제외');
 tx(s,'물품 관리',879,195,337,40,29,true,C.teal);
 tx(s,'검색·상세 편집\n기한 연장·폐기·복원\n확인 필요 항목 검토',879,251,337,151,26);
 tx(s,'시연 초기화',879,432,337,42,29,true,C.teal);
 tx(s,'물품을 치운 뒤 확인\n모든 운영 기록·사진 삭제\n설정·API 키는 보존',879,490,337,128,25);
 note(s,'시연 초기화는 백업 없이 삭제하며 되돌릴 수 없다. 설정의 일반 초기화는 자동 백업을 유지한다. 실제 Pi의 세부 편집·기한·폐기·복원 실기는 아직 미확인이다. 캡처 S5의 상세 작업은 확인한 내용만 설명한다.');
}
// 16
{
 const s=slide('통합된 기능과 남은 개발 범위','4. 핵심 기능 구현 결과',[src.live,src.accept,'experiments/pair_runner.py',src.arch]);
 para(s,'연동 구현 완료','카메라·사건 처리·SQLite·API·웹 연결\n임시 저장 후 비동기 AI 반영\n기한 검사와 알림, 상태·활동 이력 연결',64,192,552);
 para(s,'현장 확인 대기','친구 노트북과 핫스팟 연결\n실제 AI 응답·SMTP 수신\n여러 물품과 장시간 운영',679,192,537);
 tx(s,'정량 평가를 위해 추가할 부분',64,456,1152,44,29,true,C.teal);
 tx(s,'종단간 사건·API 호출의 영속 측정 원장\n공통 영상으로 B0/B1/B2를 비교할 스트림 실행기\n정답 라벨 데이터와 반복 측정 결과',64,518,1152,117,27);
}
// 17
{
 const s=slide('데이터 수집과 AI 입력 구성','5. AI 모델 및 데이터 개발 현황',['app/vision.py:1741','app/ai.py:137','app/config.py',src.readme]);
 tab(s,[['단계','현재 처리'],['원시 입력','고정 CSI 카메라의 연속 프레임'],['로컬 전처리','움직임 종료·안정화, 기하 정합, 조명 보정, 변화 영역 산출'],['전후 전체 장면 2장','변화 방향과 주변 문맥 확인 / JPEG 기본 품질 72'],['전후 후보 crop 2장','물품의 세부 특징 확인 / JPEG 기본 품질 88'],['저장·평가 데이터','물품·사진·이력 저장. 정답 라벨 평가 세트는 아직 미확보']],[285,867],{h:388,size:24});
 tx(s,'외부 요청당 최대 4장. 별도 모델 학습·증강·파인튜닝은 수행하지 않았다.',64,595,1152,48,25,true,C.teal);
}
// 18
{
 const s=slide('사전학습 VLM의 구조화 추론','5. AI 모델 및 데이터 개발 현황',['app/ai.py:179','app/ai.py:250','app/config.py:104',src.state]);
 rows(s,[['적용 모델','Pi 설정: OpenAI gpt-5.6-luna\nGemini 경로도 구현. 실제 원격 응답의 개별 검증은 남아 있음.'],['선정 이유','전후 이미지와 문맥으로 다양한 물품의 이름·분류를 요청\nPi에는 로컬 영상 처리와 서비스 운영을 배치'],['추론 방법','전후 증거 + 분실물 판단 프롬프트 + JSON schema\nOpenAI strict 형식, 완료 상태·응답 내용 검사'],['결과 활용','action, 물품명, category, confidence, 근거를 해석\n불확실·오류 응답은 관리자 확인 대상으로 보존']],{y:183,gap:111,labelW:219});
 note(s,'모델명은 현지 설정 문자열이다. 모델 공급사의 성능 우위를 검증한 결과로 제시하지 않는다. auto 모드에서만 다른 공급자 대체를 시도하며 특정 공급자 고정 시 다른 공급자를 호출하지 않는다. RAG·미세조정·자체 학습 데이터셋은 없다.');
}
// 19
{
 const s=slide('AI 성능과 사건 정확도는 측정 예정','5. AI 모델 및 데이터 개발 현황',[src.readme,src.accept,'docs/paper/EXPERIMENT_GUIDE.md'],'빈칸은 미측정값. 0 또는 자동화 테스트 통과율로 채우지 않음');
 tab(s,[['평가 항목','현재 값','측정 단위·조건'],['사건 감지 Precision / Recall / F1','[입력]','추가·이동·제거별 정답 라벨'],['물품 분류 정확도','[입력] %','정답 분류와 응답 비교 / 표본 N=[입력]'],['불확실 판정 비율','[입력] %','전체 평가 사건에서 uncertain 비율'],['감지 후 DB 반영 지연','p50 [입력] / p95 [입력] ms','행동 종료·기록 반영 시각을 함께 수집'],['성공·오류 사례','[사례 입력]','같은 사건의 원본 사진·정답·AI 응답 보존']],[443,313,396],{h:396,size:22});
 tx(s,'현재 확보한 기본 동작 성공 보고만으로 인식 정확도를 계산할 수 없다.',64,603,1152,35,25,true,C.teal);
}
// 20
{
 const s=slide('Baseline 비교와 AI 개선 방향','5. AI 모델 및 데이터 개발 현황',['AGENTS.md:필수 비교군','experiments/ablation.py','experiments/pair_runner.py','docs/paper/EXPERIMENT_GUIDE.md']);
 tab(s,[['비교군','목적','현재 상태'],['B0  순수 grayscale 차분','기본 변화 검출과 비교','공통 스트림 실행기 구현 예정'],['B1  안정화 상태기계 제거','안정화 대기의 효과·지연 확인','공통 스트림 실행기 구현 예정'],['B2  OpenCV MOG2','배경 모델 방식과 비교','공통 스트림 실행기 구현 예정'],['P1  Re:Found 전체 로컬 처리','현재 제안 파이프라인 평가','앱 구현 / 동일 조건 실측 대기']],[442,419,291],{h:335,size:22});
 tx(s,'개선 방향',64,548,242,40,28,true,C.teal);
 tx(s,'그림자·손 가림·저대비·다중 물품 사례를 확보하고\n같은 데이터에서 입력 구성과 판정 기준을 비교한다.',309,548,907,87,26);
 note(s,'기존 stable image pair runner는 _detect_changes 코어 평가용이다. 캡처·상태기계·callback·DB·VLM을 포함하지 않는다. 기존 plain profile은 순수 grayscale baseline이 아니므로 B0로 표시하지 않는다. 초기 baseline 성능 비교값은 아직 없다.');
}
// 21
{
 const s=slide('자동화 테스트와 통합 검사','6. 테스트 결과 및 문제점 분석',[src.check,src.live],'2026-09-22 개발 검사 / 합성 카메라·임시 DB·모의 AI·SMTP 사용');
 [['272','Python 검사 통과'],['37','Node 검사 통과'],['7','Chromium 검사 통과']].forEach(([n,l],i)=>{tx(s,n,64+i*402,176,360,97,76,true,C.teal);tx(s,l,67+i*402,278,360,43,27,true);});
 tab(s,[['검사 대상','조건과 결과'],['사건·저장·API 연동','합성 프레임 + 임시 DB + 모의 AI로 연속 흐름 확인'],['관리 생명주기','편집·만료·알림·연장·폐기·복원 연결 검사'],['시연 초기화 UI','1440 / 1024 / 390 / 320px에서 확인·취소·후속 등록']],[350,802],{y:376,h:232,size:23});
 note(s,'272/37/7은 9월 22일 검사 요약의 별도 도구별 개수이며 정확도나 운영 성공률이 아니다. live-stream 및 management 연동 검사는 기존 구현을 검증하며 이번 작성에서 재실행하지 않았다. 이전 264/33 및 브라우저 12+4와 합산하지 않는다.');
}
// 22
{
 const s=slide('실제 Pi에서 확인한 결과와 근거','6. 테스트 결과 및 문제점 분석',[src.state,src.accept],'2026-09-22 확인. 단일 상태 진단과 사용자 보고를 논문용 정량 실험과 구분');
 tab(s,[['항목','확인 수준','결과'],['설치·촬영','사용자 제공 로그','설치 완료, OV5647 인식·JPEG·프레임 획득'],['재부팅 후 서비스','사용자 제공 로그','active, DB·카메라 연결, Local checks passed'],['등록·이동·회수','사용자 성공 보고','기본 흐름 정상 / 개별 사진·ID 원본 미수집'],['본인 PC 원격 화면','사용자 성공 보고','Tailscale HTTPS 화면·영상 확인'],['원격 AI·메일·장시간 운영','미확인','응답 원본·실제 수신·지속 관찰 기록 필요'],['친구 노트북·핫스팟','진행 중','초대 전송 / 수락·접속·무선 부팅 대기']],[327,271,554],{h:431,size:22});
}
// 23
{
 const s=slide('주요 문제의 원인과 해결','6. 테스트 결과 및 문제점 분석',[src.vision,src.arch,src.live,'docs/APP_REVIEW_2026-09-18.md']);
 tab(s,[['문제','원인','수정과 확인'],['정지 화면이 미세하게 흔들림','분석용 정합 결과를 화면에도 사용','원본 미리보기와 박스 투영 분리'],['사건 누락·중복 위험','DB 반영 전에 기준 장면 전진','반영 확인 후 갱신, 사건 ID로 중복 제어'],['늦은 AI 응답과 편집 충돌','분석 시작 후 현재 기록이 달라짐','검토 상태·물리 revision 확인'],['연속 저장·모바일 넘침','배경 갱신 잠금·숨김 라벨 위치','작업 잠금 분리, 390px 배치 수정'],['새 SD 교체·재설치 부담','카드 고장 뒤 환경 재구성 필요','설치기·진단·체크섬으로 복구 확인']],[370,364,418],{h:434,size:23});
 note(s,'화면 미세 흔들림의 소프트웨어 원인은 합성 장면에서 재현했다. 센서의 실제 노출·물리 흔들림까지 해결됐다고 주장하지 않는다. 늦은 added 응답은 pending 상태일 때만 반영하고, verify_removed는 물리 signature가 달라지면 반영을 취소한다.');
}
// 24
{
 const s=slide('개발 환경에서의 정지 장면 연산 비교','6. 테스트 결과 및 문제점 분석',[src.vision,'output/maintenance/2026-09-18-vision-review/benchmark-comparison.json'],'PC 합성 입력의 개발 검사 / Pi 성능·AI 정확도·종단간 지연 결과가 아님');
 tx(s,'분석 프레임당 처리 시간 (ms)',64,179,722,45,27,true,C.teal);
 const chart=s.charts.add('bar',{position:{left:64,top:235,width:697,height:348},categories:['변경 전','변경 후'],series:[{name:'처리 시간 (ms)',values:[27.756,13.212],fill:C.teal,dataLabelOverrides:[{idx:0,text:'27.76',showValue:false,textStyle:{typeface:FONT,fontSize:24,bold:true,fill:C.ink}},{idx:1,text:'13.21',showValue:false,textStyle:{typeface:FONT,fontSize:24,bold:true,fill:C.ink}}]}],barOptions:{direction:'column',grouping:'clustered',gapWidth:125},hasLegend:false,xAxis:{textStyle:{typeface:FONT,fontSize:25,fill:C.ink},majorGridlines:null},yAxis:{min:0,max:35,majorUnit:10,numberFormatCode:'0',textStyle:{typeface:FONT,fontSize:21,fill:C.muted},majorGridlines:{fill:C.line,width:1}},dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:FONT,fontSize:24,bold:true,fill:C.ink}},chartFill:C.white,chartLine:{fill:'none',width:0},plotAreaFill:C.white});
 applyPresentationChartFont(chart,{fontFamily:FONT});chartOwners.push(p.slides.items.length);
 tx(s,'수정 내용',823,181,393,40,29,true,C.teal);
 tx(s,'기준 grayscale 캐시\n무변화 프레임의 조기 종료\n중복 정합 제거\n미리보기 해상도 축소',823,240,393,216,27);
 tx(s,'9/18 Windows 합성 입력\nOpenCV 1 thread, 160 입력 프레임\n호스트 부하·설정 변화 포함\n실제 Pi 개선율은 별도 측정',823,470,393,156,22,false,C.muted);
 note(s,'원천 값은 before_ms=27.756, after_ms=13.212. 이전/이후의 전체 최적화 조합을 비교한 개발 표본이며 단일 수정의 인과 효과로 해석하지 않는다. 변경 전후 처리 프레임 수 80/112, 미리보기 크기 1280×720/800×450. 호스트 스케줄링·부하·온도는 통제하지 않았으며 다른 실행의 변동 기록도 보존했다.');
}
// 25
{
 const s=slide('중간보고 전후의 개발 우선순위','7. 향후 개발 및 완성 계획',[src.accept,'AGENTS.md:정량 실험 대기 작업','사용자 제공 수업 일정'],'아래 항목은 제안 계획. 구현 완료나 실측 결과로 표시하지 않음');
 rows(s,[['우선 1  시연 연결','친구 공유 수락, 노트북 HTTPS 접속, 핫스팟 무선 부팅\n완료 근거: 실제 장소와 장비의 화면·영상'],['우선 2  운영 검증','여러 물품, 세부 편집, 메일, privacy 재부팅, 장시간 감시\n완료 근거: 조건·예상·실제 결과를 적은 실기 기록'],['우선 3  평가 기반','영속 사건·호출 시각과 정답 라벨, 공통 비교 실행기\n완료 근거: 검증 가능한 원시 CSV와 같은 입력의 비교 결과'],['AI 개선 반복','약 40건 파일럿으로 오류 유형·기록 절차 점검\n개발 자료로 기준을 고정한 뒤 별도 평가 자료로 재측정']],{y:185,gap:111,labelW:267});
 note(s,'약 40건 파일럿은 추가·이동·제거·none 각 10건의 예비 구성을 제안한 것이다. 논문 최종 표본 수나 이미 확보한 데이터 수가 아니다. 정량 목표는 파일럿 이후 현재 수준·운영 허용 오차를 근거로 확정한다.');
}
// 26
{
 const s=slide('11월 3일 최종보고까지의 일정','7. 향후 개발 및 완성 계획',['사용자 제공 수업 일정'],'수업의 발표일은 확정 일정 / 사이의 개발 작업은 제안 일정');
 tab(s,[['기간','개발·검증 계획','완료 산출물'],['9/23~9/29','친구 접속·핫스팟, 기본 실기 추가 확인','접속 확인과 실제 화면 캡처'],['9/30~10/12','통합 리허설, 측정 원장·파일럿 준비','중간보고 PPT와 실행 증거'],['10/13  ·  중간보고','구현·확인 범위와 남은 계획 발표','중간보고 피드백'],['10/14~10/26','정답 데이터, 반복 비교, 오류 수정','평가표·실패 사례·안정화 기록'],['10/27  ·  발표 연습','전체 시연, 결과표·화면 최종 점검','최종 발표 수정 목록'],['10/28~11/02 → 11/03','자료 보완·배포 고정 → 최종보고','최종 PPT·실행 패키지·검증 기록']],[316,451,385],{h:437,size:22});
}
// 27
{
 const s=slide('최종보고의 완료 기준','7. 향후 개발 및 완성 계획',[src.readme,src.accept,'docs/paper/EXPERIMENT_GUIDE.md']);
 tx(s,'현재: 통합 프로토타입 구현과 기본 실물 흐름 확인',64,182,1152,55,33,true,C.teal);
 rows(s,[['실행 증거','실물 등록·이동·회수의 동일 물품 기록과 화면 확보'],['운영 안정성','실제 발표 장비의 연결·재시작·관리 기능을 반복 확인'],['AI 성능','정답·원본·응답을 연결해 정확도·불확실 비율·지연 제시'],['재현 가능한 결과물','고정된 코드·배포본과 원시 기록, 결과표를 함께 보존']],{y:295,gap:80,labelW:267});
 tx(s,'정량 성능과 현장 운영 증거를 보완해 최종 결과를 설명한다.',64,610,1152,32,25,true,C.teal);
}
// 28
{
 const s=slide('늦은 AI 응답을 적용하기 전 상태 확인','보충자료 A. 핵심 코드',['app/classification.py:70','app/main.py:432','app/item_policy.py']);
 tx(s,'app/classification.py  ·  process()의 실제 발췌',64,180,1152,36,25,true,C.teal);
 tx(s,'with self.mutation_lock:\n    current = self.store.get_item(item_id)\n    if not current or review_status(current) != "pending":\n        return',64,248,1152,174,28,false,C.ink,{typeface:'Consolas'});
 tx(s,'관리자가 확인·편집을 마친 기록에는 뒤늦은 분류를 적용하지 않는다.',64,444,1152,58,28,true,C.teal);
 tx(s,'모호한 제거 검증은 별도로 물리 추적 signature를 검사한다.\n이미 이동하거나 처리한 물품에 이전 제거 판정을 적용하지 않는다.',64,529,1152,99,27);
 note(s,'app/classification.py의 current 조회와 pending 검사 4줄을 그대로 발췌했다. signature와 revision은 이름·분류·기한의 단순 편집과 물리 추적 변경을 구분한다.');
}
// 29
{
 const s=slide('발표용 캡처 준비 목록','보충자료 B. 화면 채우기',[src.accept,'출력물: REFOUND_MIDTERM_FILL_GUIDE.md'],'실제 Pi 화면 사용. 합성 테스트 화면을 쓰면 해당 사실을 표시');
 tab(s,[['자리','캡처 내용','반드시 보여줄 것'],['S1  ·  11쪽','저장소의 개발 이력','날짜·작성자·기능별 주요 커밋'],['S2  ·  14쪽','실물 하나를 등록한 뒤 상세 확인','물품 이름, ID, 사진과 상태'],['S3  ·  14쪽','같은 물품을 옮긴 뒤 동일 기록','같은 ID, 바뀐 위치·사진, 중복 없음'],['S4  ·  14쪽','물품을 제거한 뒤 같은 기록','회수 상태와 해당 활동 이력'],['S5  ·  15쪽','실제 Pi 관리자 화면','전체 화면 구성 또는 핵심 관리 작업']],[234,452,466],{h:378,size:23});
 tx(s,'PNG 권장. 주소창·계정·키·개인 식별 정보는 제외한다.\n자세한 촬영 순서와 PPT 교체 방법은 함께 제공한 작성 가이드에 있다.',64,578,1152,64,23,false,C.muted);
}
// 30
{
 const s=slide('진행률과 결과표를 채우는 기준','보충자료 C. 미확정 항목',['첨부: 프로젝트개발중간보고 목차구성.md','docs/paper/EXPERIMENT_GUIDE.md']);
 rows(s,[['9쪽  공식 진행률','합의한 작업 항목의 가중치 합을 100으로 설정\n진행률 = 완료로 인정한 작업의 가중치 합'],['19쪽  성능값','정답 라벨과 원시 응답을 모은 뒤 계산\n표본 수·실패·불확실 응답을 분모에서 임의로 제외하지 않음'],['11쪽  수행·커밋','팀원별 실제 산출물과 커밋 작성자를 대조\n담당 역할과 확인 가능한 코드 기여를 분리'],['발표 전 갱신','10/13까지의 새 실기 결과와 캡처 반영\n확인일과 근거 수준을 함께 갱신']],{y:181,gap:112,labelW:272});
 note(s,'공식 진행률은 미확정 상태를 유지한다. 구현된 기능 수를 전체 프로젝트 진행률 100%로 바꾸지 않는다. 실제 AI·SMTP 검증이나 현장 정량 결과를 수행하지 않은 채 완료로 변경하지 않는다.');
}

await fs.mkdir(BUILD,{recursive:true});
const candidatePath=path.join(BUILD,`candidate-${revision}.pptx`);
await(await PresentationFile.exportPptx(p)).save(candidatePath);
await fs.writeFile(path.join(BUILD,`deck-manifest-${revision}.json`),JSON.stringify({slides:meta,tableOwners,chartOwners,asOf:'2026-09-22',presentationDate:'2026-10-13',finalReportDate:'2026-11-03',fontPolicy:{basis:'design',families:[FONT,'Consolas']},screenshots:['S1','S2','S3','S4','S5']},null,2));
await finalizePresentation({workspaceDir:ROOT,candidatePath,finalPath:FINAL,pythonExecutable:path.join(RT,'dependencies/python/python.exe'),integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--validate-bullet-geometry',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:30,requiredNativeTableOwnerSlides:tableOwners,requiredNativeChartOwnerSlides:chartOwners,materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT,'Consolas']},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation-${revision}.json`)});
const finalDeck=await PresentationFile.importPptx(await FileBlob.load(FINAL));
const renderDir=path.join(BUILD,`render-${revision}`);await fs.mkdir(renderDir,{recursive:true});
for(let i=0;i<finalDeck.slides.items.length;i++){
 const s=finalDeck.slides.items[i];
 const blob=await finalDeck.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(renderDir,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
 const layout=await s.export({format:'layout'});await fs.writeFile(path.join(renderDir,`slide-${String(i+1).padStart(2,'0')}.layout.json`),await layout.text());
 console.log(`Rendered ${i+1}/30`);
}
console.log(JSON.stringify({final:FINAL,slides:finalDeck.slides.items.length,renderDir}));
