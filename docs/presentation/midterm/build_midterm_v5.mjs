import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../../..');
const RT='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime';
const SKILL='C:/Users/USER/.codex/plugins/cache/openai-primary-runtime/presentations/26.915.20218/skills/presentations';
process.env.RUNTIME_NODE_MODULES=path.join(RT,'dependencies/node/node_modules');
process.env.RUNTIME_NODE=path.join(RT,'dependencies/node/bin/node.exe');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const BUILD=path.join(ROOT,'output/maintenance/2026-10-02-midterm-content-review');
const revision=process.env.DECK_REVISION||'v5_improved';
const FINAL=path.join(ROOT,'output/presentation',`REFOUND_PROJECT_MIDTERM_2026-10-02${revision==='v1'?'':'_'+revision}.pptx`);
if(await fs.stat(FINAL).then(()=>true,()=>false))throw new Error('Output exists. Set DECK_REVISION to a new revision name; preserve any manually edited PPTX.');
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#102D3C',ink:'#183442',teal:'#067C80',muted:'#566B77',line:'#CFDBDE',pale:'#EEF6F5',white:'#FFFFFF',amber:'#9B5A10'};
const FONT='Malgun Gothic';
const typography=[];
const meta=[]; const tableOwners=[]; const chartOwners=[]; const noteText=new WeakMap();
const src={hotspot:'REFOUND_WINDOWS_HOTSPOT_GUIDE.md',sync:'output/maintenance/2026-09-30-sync-review/REVIEW.md',git:'git log at 69eb6ff (2026-10-02 inspection)',readme:'README.md',accept:'docs/guides/PI_ACCEPTANCE_CHECKLIST.md',state:'output/maintenance/2026-09-22-network-plan/SESSION_STATUS.json',check:'output/maintenance/2026-09-22-quick-reset/VALIDATION.json',vision:'docs/VISION_REVIEW_2026-09-18.md',arch:'docs/ARCHITECTURE_REVIEW_2026-09-18.md',live:'docs/LIVE_FLOW_REVIEW_2026-09-18.md'};

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
function tx(s,value,x,y,w,h,size=26,bold=false,color=C.ink,extra={}){
 const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 const safe=extra.typeface==='Consolas'?value:keepWords(value,w,size,bold,extra.typeface||FONT);
 typography.push({slide:p.slides.items.length,kind:'text',text:safe,x,y,w,h,size,bold,font:extra.typeface||FONT});
 t.text=safe; t.text.style={typeface:FONT,fontSize:size,bold,color,lineSpacing:1.12,autoFit:'none',wrap:'none',insets:{left:0,right:0,top:0,bottom:0},...extra}; return t;
}
function line(s,x,y,w,color=C.line){s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:0},fill:'none',line:{fill:color,width:1}});}
function slide(title,section,refs=[],foot=''){
 const s=p.slides.add();s.background.fill=C.white;
 tx(s,section,64,29,1120,25,18,true,C.teal);
 tx(s,title,64,76,1152,77,44,true);
 line(s,64,650,1152);
 if(foot)tx(s,foot,64,668,1085,28,16,false,C.muted);
 tx(s,String(p.slides.items.length).padStart(2,'0'),1160,667,56,30,18,true,C.muted,{alignment:'right'});
 const baseNotes='자료 정리일: 2026-10-02. 실기 보고: 2026-09-29까지. 개발 검사: 2026-09-30까지. 발표 예정일: 2026-10-13.\n근거:\n'+refs.map(r=>'- '+r).join('\n'); noteText.set(s,baseNotes); s.speakerNotes.textFrame.setText(baseNotes);
 meta.push({slide:p.slides.items.length,title,section,sources:refs});return s;
}
function note(s,text){const combined=noteText.get(s)+'\n'+text;noteText.set(s,combined);s.speakerNotes.textFrame.setText(combined);}
function para(s,title,body,x,y,w=530){tx(s,title,x,y,w,40,29,true,C.teal);tx(s,body,x,y+54,w,139,27);}
function rows(s,items,{x=64,y=187,w=1152,gap=93,labelW=255}={}){
 items.forEach(([a,b],i)=>{tx(s,a,x,y+i*gap,labelW,45,27,true,C.teal);tx(s,b,x+labelW+28,y+i*gap,w-labelW-28,gap-9,26); if(i<items.length-1)line(s,x,y+i*gap+gap-17,w);});
}
function tab(s,values,widths,{x=64,y=181,w=1152,h=398,size=23}={}){
 values=values.map((row,r)=>row.map((v,c)=>keepWords(v,widths[c]-28,size,r===0)));
 typography.push({slide:p.slides.items.length,kind:'table',values,widths,x,y,w,h,size});
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
 t.styleOptions={headerRow:false,bandedRows:false};
 const range=t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length});
 range.assign({textStyle:{typeface:FONT,fontSize:size,color:C.ink},margins:{left:14,right:14,top:12,bottom:10},anchor:'middle'});
 t.borders.assign({fill:C.line,width:1,style:'solid'});
 for(let r=0;r<values.length;r++){t.rows[r].height=h/values.length;for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill=r===0?C.navy:(r%2?C.white:'#F4F8F8');cell.text.style={typeface:FONT,fontSize:size,bold:r===0,wrap:'none',autoFit:'none',color:r===0?C.white:C.ink};}}
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
 n.text=keepWords(label,w-24,25,true);n.text.style={typeface:FONT,fontSize:25,bold:true,color,alignment:'center',verticalAlignment:'middle',wrap:'none',autoFit:'none',insets:{left:12,right:12,top:15,bottom:12}};return n;
}
function connect(s,a,b,from='right',to='left',kind='straight'){
 return s.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:C.teal,width:2},tail:{type:'arrow',width:'med',length:'med'}});
}
// 01
{
 const s=p.slides.add();s.background.fill=C.navy;
 tx(s,'Re:Found',70,129,1110,112,88,true,C.white);
 tx(s,'분실물 자동 추론 및 시각화 관리 시스템',76,269,1100,76,40,true,'#BDE8E2');
 tx(s,'프로젝트 개발 중간보고서',76,374,1100,61,35,false,C.white);
 tx(s,'동양미래대학교 인공지능소프트웨어학과\n상부상조(2조)  장진석 · 권기원',76,536,1100,75,24,false,C.white);
 tx(s,'발표 2026.10.13   /   자료 정리 2026.10.02',76,650,1110,30,20,false,'#BDE8E2');
 s.speakerNotes.textFrame.setText('출처: README.md의 프로젝트명·소속·팀원. 발표일은 사용자가 제공한 수업 일정. 실기 근거는 9월 29일 사용자 보고, 개발 검사는 9월 30일 기록까지 반영. 10월 2일에는 슬라이드를 검토·수정했으며 새 앱·Pi 실험은 수행하지 않음.');
 meta.push({slide:1,title:'Re:Found 프로젝트 개발 중간보고',section:'표지',sources:[src.readme,'사용자 제공 수업 일정']});
}
// 02
{
 const s=slide('발표 구성','중간보고',[ '첨부: 프로젝트개발중간보고 목차구성.md','사용자 제공 수업 일정'],'개발 진행상태 및 중간점검');
 const labels=['프로젝트 개요 및 개발 목표','시스템 설계 및 개발 구조','프로젝트 개발 진행 현황','핵심 기능 구현 결과','AI 모델 및 데이터 개발 현황','테스트 결과 및 문제점 분석','향후 개발 및 완성 계획'];
 labels.forEach((v,i)=>{tx(s,String(i+1).padStart(2,'0'),74,186+i*57,64,38,25,true,C.teal);tx(s,v,160,186+i*57,900,44,28);});
}
// 03
{
const s=slide('보관대의 물품과 관리 기록을 연결','1. 프로젝트 개요 및 개발 목표',[src.readme],'아래 우산 사례는 기능을 설명하기 위한 사용 시나리오이며 실제 측정 결과가 아님');
 tx(s,'담당자가 사진·분류·기한을 따로 관리하면 기록이 빠지거나 중복될 수 있다.',64,177,1152,85,30,true,C.teal);
 tab(s,[['보관대에서 생기는 일','관리자가 확인할 내용','시스템의 처리 목표'],['우산을 새로 놓음','언제 들어온 어떤 물품인가?','사진·시각 저장, AI 이름·분류 제안'],['같은 우산의 위치를 옮김','새 물품인가, 기존 물품인가?','기존 ID의 위치·사진 갱신'],['우산을 화면 밖으로 치움','어떤 기록의 상태를 바꿀 것인가?','해당 물품의 회수 상태·이력 기록']],[320,378,454],{y:285,h:258,size:23});
 tx(s,'주요 사용자  학교 행정실·도서관·공용공간의 분실물 관리자',64,573,1152,35,25,true);
 tx(s,'적용 범위  카메라를 고정할 수 있는 실내 보관대',64,615,1152,30,23,false,C.muted);
 note(s,'수기·별도 파일 관리의 누락과 중복 가능성은 문제 정의이며 실제 기관의 업무 실태를 조사한 정량 결과가 아니다. 회수 상태는 화면에서 사라짐을 기록하며 소유자에게 반환됐다는 뜻은 아니다.');
}
// 04
{
const s=slide('로컬 감지와 AI 해석의 역할 분담','1. 프로젝트 개요 및 개발 목표',[src.readme,'app/main.py','app/ai.py']);
 rows(s,[['로컬에서 판단','움직임이 끝난 뒤 장면을 비교하고 기존 물품과 대응\n명확한 이동·제거는 로컬에서 처리'],['AI가 보완','새 물품의 이름·분류와 모호한 제거를 해석\n사건별 증거를 보내고 결과를 관리 기록에 반영'],['관리자가 결정','확인 필요 항목을 검토하고 이름·기한을 수정\n보관·회수·폐기·복원 이력을 같은 물품에 연결'],['최종 결과물','Pi 카메라 장치, FastAPI 서버, 관리자 웹\n설치 패키지·사용 안내와 검증 기록']],{y:185,gap:110,labelW:236});
 note(s,'차별화 의도는 모든 프레임에 AI를 호출하지 않고 사건을 선별하며, AI 실패 때도 관찰 기록을 보존하는 데 있다. 호출량·비용·정확도 개선율은 아직 측정하지 않았다. 자체 학습 모델이 최종 산출물인 프로젝트는 아니다.');
}
// 05
{
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
}
// 06
{
 const s=slide('모듈별 역할과 기술 스택','2. 시스템 설계 및 개발 구조',[src.readme,src.state,'app/camera_sources.py','app/notifier.py']);
 tab(s,[['모듈','담당 기능','구현 기술'],['카메라·비전','프레임 입력, 안정화, 변화 감지','Picamera2 / OpenCV'],['사건·AI 처리','임시 저장, 추론 요청, 응답 검증','Python / HTTPX'],['서버·저장','API, 상태 전이, 사진과 활동 이력','FastAPI / SQLite WAL'],['관리자 화면','실시간 영상, 목록, 편집, 설정','Vanilla HTML / CSS / JS'],['운영·배포','만료 알림, 서비스 자동 시작','SMTP / systemd / SSH']],[245,465,442],{h:365});
 tx(s,'실제 장치   Raspberry Pi 4 Model B 2GB + CSI 카메라(OV5647)',64,571,1152,35,25,true,C.teal);
 tx(s,'확인 환경   Debian 13 Trixie / Python 3.13.5 / OpenCV 4.10.0',64,610,1152,30,22,false,C.muted);
}
// 07
{
 const s=slide('팀 역할과 협업 방식','2. 시스템 설계 및 개발 구조',[src.readme],'역할은 현재 README 기준. 커밋별 기여도는 별도 확인 필요');
 para(s,'장진석  ·  팀장 / 시스템 통합','기획·아키텍처와 로컬 비전 구현\n멀티모달 AI, FastAPI, 관리자 웹 연결\nPi 배포와 테스트·문서화',64,197,548);
 para(s,'권기원  ·  개발 / 시연 지원','구현과 발표 자료 검토\n자료 교정\n시연 준비와 운영 지원',682,197,534);
 tx(s,'연계 업무',64,450,240,42,29,true,C.teal);
 tx(s,'구현·검사 결과를 공유하고 자료 검토와 실제 시연을 진행\n발견한 오류와 미확인 항목을 다음 수정·검증에 반영',64,511,1152,96,28);
}
// 08
{

 const s=slide('개발 경과와 현재 단계','3. 프로젝트 개발 진행 현황',[src.vision,src.state,src.hotspot,src.sync,'사용자 제공 수업 일정'],'10월 2일 현재 중간보고 준비 단계 / 중간보고 10월 13일, 최종보고 11월 3일');
 tab(s,[['시점','진행 단계','완료 내용 또는 예정 산출물'],['9/18','앱 안정성 보완','영상·사건 처리·데이터 보존 개선'],['9/22','Pi 설치와 기본 실기','촬영·재부팅 진단, 실물 흐름 성공 보고'],['9/29','노트북 시연 연결','Windows 핫스팟·SSH 웹·AI 성공 보고'],['9/30','저장소 실행 점검','Python 272개·Node 37개 재검사 통과'],['10/02~10/12','중간보고 준비','자료 보완, 실제 캡처와 리허설 예정'],['10/13','7주차 중간보고','개발 결과와 남은 검증 계획 발표']],[220,330,602],{h:427,size:24});

}
// 09
{
const s=slide('개발 목표 대비 현재 도달 수준','3. 프로젝트 개발 진행 현황',[src.readme,src.accept,src.hotspot,src.sync],'최초 작업별 마감일이 없어 일정 지연을 단정하지 않음 / 공식 진행률은 산정 기준 미확정');
 tab(s,[['개발 목표','현재 도달 수준','남은 작업과 이유'],['통합 프로토타입','구현 완료','Pi 4·SQLite 중심으로 배포 단순화'],['실물 등록·이동·회수','기본 흐름 확인','다중 물품·가림 조건 검증 필요'],['외부 AI 연동','동작 성공 보고','정답·개별 응답 원본 수집 필요'],['학교 시연 환경','연결 검증 진행','새 핫스팟의 재부팅 복귀 미확인'],['운영 검증·성능 평가','일부 검사 / 평가 준비','실제 메일·반복 운영·정량 자료 필요']],[310,307,535],{h:385,size:24});
 tx(s,'현재 단계: 핵심 기능 구현 이후의 현장 검증·평가 준비',64,590,1152,45,29,true,C.teal);
 note(s,'초기 계획 대비 보유 Pi 4·CSI, OpenCV+외부 VLM, SQLite, Vanilla JS+FastAPI로 구성을 단순화했다. 최초 계획의 확정 마감일·공수·가중치 자료가 없어 빠름/지연 및 프로젝트 전체 백분율을 만들지 않았다. 코드 구현 완료와 실제 환경 검증 완료를 구분한다. 공식 진행률 산식과 남은 근거는 작성 가이드에 보존한다.');
}
// 10
{

 const s=slide('기능별 구현과 실기 확인 상태','3. 프로젝트 개발 진행 현황',[src.readme,src.accept,src.check,src.hotspot],'기능별 상태는 구현·검증 근거로 표시 / 구현률(%)의 합의된 기준은 미확정');
 tab(s,[['기능','구현 상태','확인 결과와 남은 검증'],['카메라·실시간 화면','구현 완료','촬영 로그, 웹 화면·영상 성공 보고'],['등록·이동·회수','구현 완료','기본 실물 흐름 성공 보고'],['외부 AI 분석','구현 완료','9/29 동작 성공 보고, 정량 성능 미측정'],['편집·기한·폐기·복원','구현 완료','자동 검사 통과, Pi 상세 실기 대기'],['웹 알림·SMTP','구현 완료','모의 검사 통과, 실제 메일 수신 대기'],['Windows 무선 시연','검증 진행','연결 성공, 전원 재인가 시험 대기'],['평가 원장·비교 실행기','미구현','사건 시각·정답 기록과 공통 평가 필요']],[325,190,637],{h:434,size:23});

}
// 11
{

 const s=slide('팀 수행 내용과 Git 개발 이력','3. 프로젝트 개발 진행 현황',[src.readme,src.git],'커밋 반영일과 기능 개발일은 다름 / 커밋 수로 팀 기여율을 산정하지 않음');
 tx(s,'장진석: 구현·통합·배포·검사',64,176,575,52,26,true,C.teal);
 tx(s,'권기원: 검토·교정·시연 지원',675,176,541,52,26,true,C.teal);
 tab(s,[['반영일','커밋','확인한 변경 내용'],['9/08','258efc1','기존 프로젝트 파일 업로드'],['9/30','956b346','9월 30일까지의 소스·자료 일괄 반영'],['9/30','69eb6ff','최신 시연 절차 반영과 임시 파일 정리']],[190,220,742],{y:249,h:268,size:25});
 tx(s,'GitHub  Jinseok2419342 / Capstone-team-project',64,550,1152,43,27,true,C.teal);
 tx(s,'표의 커밋 작성자: Jinseok2419342. 역할별 산출물은 README·검사 기록과 대조.',64,606,1152,32,22,false,C.muted);
 note(s,'로컬 git log에서 날짜·해시·작성자·메시지를 확인했다. 저장소: https://github.com/Jinseok2419342/Capstone-team-project . 표는 실제 이력을 옮긴 편집 가능한 표이며 화면 캡처를 합성하지 않았다. 팀의 담당 역할은 README의 정의로, 개별 팀원이 언제 어떤 검토를 수행했는지에 관한 추가 기록은 수집하지 않았다.');

}
// 12
{
 const s=slide('실행 가능한 핵심 사건 처리','4. 핵심 기능 구현 결과',['app/vision.py','app/main.py:534','app/main.py:432'],'자동 회수는 화면상 사라짐을 기록한 상태이며 실제 소유자 반환의 증거는 아님');
 tab(s,[['입력 사건','주요 처리','출력'],['added  ·  새 물품','임시 기록 저장 후 AI 분류 요청','분류 확정 또는 검토 대기'],['moved  ·  같은 물품 이동','활성 물품 대응과 위치·사진 갱신','기존 ID 유지'],['removed  ·  명확한 제거','저장된 배경과 제거 근거 확인','회수 상태와 활동 이력'],['verify_removed  ·  모호한 제거','외부 AI로 사라짐 여부 재검증','회수 또는 추적·검토 유지']],[376,421,355],{h:377,size:24});
 tx(s,'움직임이 끝나고 장면이 안정된 뒤 사건 후보를 처리한다.',64,596,1152,39,27,true,C.teal);
}
// 13
{
const s=slide('AI 응답을 기다리는 동안에도 기록 보존','4. 핵심 기능 구현 결과',['app/main.py','app/classification.py','tests/test_app_resilience.py',src.arch]);
 const a=node(s,'물품 감지',64,191,244,97),b=node(s,'임시 기록 저장',360,191,270,97),c=node(s,'AI 비동기 요청',681,191,275,97),d=node(s,'검토·확정',1007,191,209,97);
 connect(s,a,b);connect(s,b,c);connect(s,c,d);
 rows(s,[['AI 정상 응답','응답 형식과 판정을 확인한 뒤 이름·분류를 반영\n관찰한 물품의 사진·시각과 AI 결과를 연결'],['실패·불확실 응답','관찰 기록을 유지하고 확인 필요 상태로 표시\n관리자가 사진을 보고 이름·분류를 확정'],['추론 중 관리자 작업','기한 연장과 명시적인 검토 완료를 보호\n늦은 응답을 적용하기 전에 현재 상태 확인']],{y:335,gap:96,labelW:261});
 tx(s,'설계 이유: 외부 API 장애가 곧 물품 기록의 누락으로 이어지지 않도록 구성',64,615,1152,31,23,true,C.teal);
 note(s,'임시 저장 성공 뒤 비동기 추론한다. DB 저장 자체의 실패까지 보존을 보장한다는 뜻은 아니다. 기한 연장은 test_late_classification_preserves_manual_extension으로 확인하고, 명시적 검토 완료 뒤의 응답 보호 코드는 보충자료 A에 제시했다.');
}
// 14
{

 const s=slide('물품 상세 화면과 처리 흐름','4. 핵심 기능 구현 결과',[src.accept,src.live,'output/maintenance/2026-09-18-live-flow-review/browser-classified-detail.png'],'9/18 개발 검사 화면 / 합성 물품·모의 AI 사용. 화면의 97%는 실제 모델 정확도가 아님');
 await screenshot(s,'output/maintenance/2026-10-02-midterm-review/assets/detail.png',64,171,399,466,'합성 데이터 개발 검사에서 저장된 물품 상세 화면');
 rows(s,[['등록','물품을 놓고 손을 뺀 뒤 임시 기록 생성\nAI 분석 후 이름·분류를 확정하거나 검토 대기'],['이동','같은 물품의 위치·사진 갱신\n새 기록을 만들지 않고 기존 ID 유지'],['회수','화면에서 사라지면 같은 기록의 상태 전환\n활동 이력에 처리 결과 저장']],{x:515,y:195,w:701,gap:125,labelW:95});
 tx(s,'실물 흐름은 9/22 성공 보고. 동일 ID의 실제 Pi 캡처는 미확보.',515,595,701,49,22,false,C.muted);
 note(s,'왼쪽은 기존 개발 검사 PNG의 상세 창 영역만 비율을 유지해 잘랐다. 실제 카메라·원격 모델 결과로 해석하지 않는다. 오른쪽은 구현 흐름이다. 사용자 보고에서는 실물 등록·이동 시 중복 방지·제거 후 회수 확인에 성공했다고 했으나 개별 ID·사진은 수집하지 않았다.');

}
// 15
{
const s=slide('관리자는 확인이 필요한 물품부터 처리','4. 핵심 기능 구현 결과',['templates/index.html','static/app.js','tests/test_live_management.py',src.check],'9/22 개발 검사 화면 / 물품 수·사진·영상은 합성 테스트 데이터');
 await screenshot(s,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png',64,178,740,455,'합성 카메라·임시 DB를 사용한 관리자 대시보드');
 tx(s,'확인 필요 물품',850,182,366,40,29,true,C.teal);
 tx(s,'사진과 AI 결과를 검토\n이름·분류 수정 후 검토 완료',850,239,366,91,25);
 tx(s,'기한과 처리 이력',850,372,366,40,29,true,C.teal);
 tx(s,'기한 도래 항목 확인·연장\n회수·폐기·복원 처리\n활동 이력에서 결과 확인',850,429,366,126,25);
 tx(s,'관리 흐름은 자동 검사 통과\nPi 상세 실기는 추가 확인 예정',850,580,366,63,21,false,C.muted);
 note(s,'단순 편집과 명시적인 검토 완료는 구분한다. test_review_expiry_renewal_notification_and_final_lifecycle에서 검토·만료·연장·알림·최종 처리를, test_dismiss_restore_and_lifecycle_keep_search_pages_and_stats_consistent에서 상태와 목록·통계의 일관성을 검사했다. 실제 SMTP 수신은 미확인이다.');
}
// 16
{
const s=slide('통합 기능의 현재 범위와 남은 일','4. 핵심 기능 구현 결과',[src.live,src.accept,src.hotspot,'experiments/pair_runner.py']);
 tab(s,[['범위','현재 결과','다음 완료 조건'],['기본 처리 연결','카메라·DB·API·웹 연동 구현\n기본 실물 흐름 성공 보고','같은 물품의 등록·이동·회수\n사진·ID·이력 확보'],['관리·알림 연결','편집·기한·상태·알림 구현\n모의 환경의 연속 검사 통과','발표 장비에서 편집·기한 확인\n실제 메일 수신 결과 기록'],['시연 연결','노트북 핫스팟·SSH 성공 보고','전원 재인가 후 영상·AI 복귀\n반복 실행 기록'],['평가 도구','이미지 쌍의 감지 코어 평가 구현','사건·응답·시각 원장 추가\n연속 영상 비교기는 추가 개발']],[238,450,464],{h:407,size:24});
 tx(s,'남은 핵심 작업은 현장 증거 확보와 측정 기록 연결이다.',64,607,1152,37,27,true,C.teal);
 note(s,'통합 연결의 개발 검사와 실제 환경의 모든 시나리오 확인은 별개다. 기존 pair runner는 안정 이미지 쌍의 _detect_changes 코어 평가이며 전체 상태기계·DB·VLM의 종단간 평가기가 아니다.');
}
// 17
{
const s=slide('전후 장면과 물품 영역을 함께 전달','5. AI 모델 및 데이터 개발 현황',['app/vision.py','app/ai.py','tests/test_services.py'],'운영 사진 수량은 미집계 / 정답 라벨이 있는 평가 세트는 미확보');
 tx(s,'고정 카메라 영상에서 움직임 종료·안정화 후 사건별 증거를 만든다.',64,178,1152,76,30,true,C.teal);
 tab(s,[['입력·처리','필요한 이유','현재 구현'],['기하 정합·조명 보정','카메라 미세 변화와 밝기 차이 완화','로컬 전처리'],['전체 장면 전후 2장','무엇이 생겼거나 사라졌는지\n주변 맥락과 함께 판단','변화 전·후를 구분해 전달'],['후보 영역 전후 2장','작은 물품의 모양·색상 등\n세부 특징을 더 크게 제공','후보 영역 crop 전달'],['정답·응답 연결','잘못된 사건·분류의 원인 분석','평가 원장 추가 예정']],[310,478,364],{y:252,h:305,size:23});
 tx(s,'요청당 최대 4장 / 자체 학습·RAG·파인튜닝·데이터 증강 미적용',64,607,1152,37,25,true,C.teal);
 note(s,'tests/test_services.py test_ai_hybrid_evidence_is_labeled_and_cost_bounded가 입력 4장과 before/after 라벨, 전체 low·crop high detail을 확인한다. 실제 처리에서 전체 장면 JPEG 품질은 72, crop은 88이다. 이미지 기반 전처리이며 통계형 결측치 대치나 학습 정규화를 수행한 것으로 쓰지 않는다.');
}
// 18
{
const s=slide('외부 VLM 선택 이유와 추론 방식','5. AI 모델 및 데이터 개발 현황',['app/ai.py',src.readme,src.state,src.hotspot],'선정 근거는 설계상 판단 / 모델 간 정확도·비용 우열을 측정한 결과는 없음');
 tab(s,[['검토 방식','적합한 역할과 제약'],['OpenCV 로컬 처리','변화 시점·위치 감지에 사용, 물품 이름 해석은 AI로 보완'],['고정 클래스 검출·분류 모델','대상 클래스가 고정됨, 새 물품 유형에는 추가 학습 검토'],['외부 VLM  ·  현재 방식','전후 이미지로 다양한 물품을 설명, 통신·호출 비용 의존']],[382,770],{h:255,size:24});
 tx(s,'추론 요청',64,469,215,38,27,true,C.teal);
 tx(s,'전후 증거 + 판단 지침 + JSON schema\n응답 완료·형식을 검사해 결과 반영 또는 확인 필요로 전환',303,469,913,83,25);
 tx(s,'모델 확인',64,569,215,37,27,true,C.teal);
 tx(s,'9/22 설정: gpt-5.6-luna\n9/29 OpenAI 동작 성공 보고, 당일 모델명은 미수집',303,569,913,75,24);
 note(s,'OpenAI를 사용하는 설정이 확인됐고 Gemini 연동도 구현했다. Pi 4 2GB에서 감지와 웹 운영을 맡기고 외부 VLM에 의미 해석을 맡긴 설계다. 고정 클래스 검출·분류 방식은 프로젝트의 초기 YOLO/CNN 검토 맥락이며 모든 현대 검출 모델의 기능을 일반화한 비교는 아니다. 추론 설정은 기본 모델 reasoning low·출력 최대 2048토큰이며 학습 하이퍼파라미터가 아니다.');
}
// 19
{
const s=slide('AI 동작 확인과 정량 평가의 구분','5. AI 모델 및 데이터 개발 현황',[src.hotspot,'tests/test_services.py','docs/paper/EXPERIMENT_GUIDE.md'],'현재 정량 성능은 미측정 / 아래 지표는 수집·계산할 항목');
 tx(s,'확인한 결과  9/29 OpenAI 동작 성공 보고',64,178,1152,42,31,true,C.teal);
 tx(s,'아직 필요한 근거  같은 사건의 정답·원본 사진·실제 AI 응답·처리 시각',64,237,1152,58,26);
 tab(s,[['평가 지표','평가에 필요한 기록'],['사건 Precision / Recall / F1','추가·이동·제거별 예측과 정답의 TP·FP·FN'],['물품 분류 정확도','분류 정답 수 / 전체 평가 대상 수 N'],['불확실·실패 응답 비율','uncertain·API 실패 건수 / 전체 요청 수'],['종단간 지연 p50 / p95','행동 종료와 DB 반영 시각, 표본 수·시각 누락률']],[414,738],{y:320,h:280,size:24});
 tx(s,'모의 응답 처리 검사는 통과했으며, 실제 모델의 판정 품질은 별도 평가한다.',64,617,1152,29,23,true,C.teal);
 note(s,'9/29는 동작 성공의 사용자 보고로 개별 사건의 원본·정답·모델 응답은 수집하지 않았다. 자동 검사에서 JSON 정규화, 유효하지 않은 분류·확신도의 uncertain 처리 등을 확인했다. 이것은 실제 AI의 성공·실패 사례 비교 결과가 아니다. 분류 정확도의 분모에는 평가 대상의 불확실·실패를 포함하고 별도 응답 성공 조건의 정확도가 필요하면 구분해 보고한다.');
}
// 20
{
 const s=slide('Baseline 비교와 AI 개선 방향','5. AI 모델 및 데이터 개발 현황',['AGENTS.md:필수 비교군','experiments/ablation.py','experiments/pair_runner.py','docs/paper/EXPERIMENT_GUIDE.md']);
 tab(s,[['비교군','목적','현재 상태'],['B0  순수 grayscale 차분','기본 변화 검출과 비교','비교 실행기 미구현'],['B1  안정화 상태기계 제거','안정화 대기의 효과·지연 확인','비교 실행기 미구현'],['B2  OpenCV MOG2','배경 모델 방식과 비교','비교 실행기 미구현'],['P1  Re:Found 전체 로컬 처리','현재 제안 파이프라인 평가','앱 구현, 실측 대기']],[442,419,291],{h:335,size:24});
 tx(s,'개선 방향',64,548,242,40,28,true,C.teal);
 tx(s,'그림자·손 가림·저대비·다중 물품 사례를 확보하고\n같은 데이터에서 입력 구성과 판정 기준을 비교한다.',309,548,907,87,26);
 note(s,'기존 stable image pair runner는 _detect_changes 코어 평가용이다. 캡처·상태기계·callback·DB·VLM을 포함하지 않는다. 기존 plain profile은 순수 grayscale baseline이 아니므로 B0로 표시하지 않는다. 초기 baseline 성능 비교값은 아직 없다.');
}
// 21
{
const s=slide('오류 조건을 포함한 자동화 검사','6. 테스트 결과 및 문제점 분석',[src.sync,src.check,'tests/test_app_resilience.py','tests/test_reset.py','tests/test_services.py'],'임시 DB·합성 카메라·모의 AI·SMTP의 개발 검사 / 실제 모델 성능 시험과 구분');
 tx(s,'Python 272개 · Node 37개',64,169,733,53,37,true,C.teal);
 tx(s,'9/30 재실행 통과',64,230,733,33,24,false,C.muted);
 tx(s,'Chromium 7개',850,172,366,45,31,true,C.teal);
 tx(s,'9/22 검사 통과',850,230,366,33,24,false,C.muted);
 tab(s,[['재현한 조건','예상 결과','확인 결과'],['AI 작업 제출 실패','임시 물품 보존·검토 대기','기록 유지 통과'],['기한 연장 뒤 AI 응답 도착','관리자가 연장한 기한 유지','기한 일치 통과'],['시연 초기화 실행','물품·사진 삭제, 설정·키 유지','삭제·보존 검사 통과'],['알림 작업 동시 실행','같은 물품의 중복 발송 방지','모의 발송 1회 확인']],[366,493,293],{y:300,h:322,size:23});
 note(s,'모든 Python 사례는 9/30 272개 통과 기록과 현재 test 소스를 대조했다. test_executor_rejection_preserves_item_and_releases_slot, test_late_classification_preserves_manual_extension, test_quick_reset_skips_backup_and_preserves_settings_and_existing_backups, test_scheduler_lock_prevents_concurrent_duplicate_email. 시연 초기화의 키 보존 검사는 임시 테스트 키로 수행했고 실제 키 값을 발표 자료에 옮기지 않았다. 10/2에는 앱 테스트를 재실행하지 않았다. 9/30에는 별도 격리 run.py의 화면·정적 파일·API HTTP 200도 확인했다.');
}
// 22
{

 const s=slide('실제 Pi 시연에서 확인한 결과','6. 테스트 결과 및 문제점 분석',[src.state,src.accept,src.hotspot],'로그 확인과 사용자 성공 보고를 구분 / 새 네트워크의 전원 재인가 시험은 아직 미확인');
 tab(s,[['확인일·항목','근거','결과'],['9/22 설치·촬영','사용자 제공 로그','설치 완료, OV5647 촬영·프레임 획득'],['9/22 재부팅 진단','사용자 제공 로그','서비스 active, DB·카메라 연결'],['9/22 등록·이동·회수','사용자 성공 보고','기본 실물 흐름 정상'],['9/29 Windows 핫스팟','사용자 제공 로그','Wi-Fi 검색과 Pi 연결 활성화'],['9/29 SSH 웹·OpenAI','사용자 성공 보고','노트북 화면 접속과 API 동작 성공'],['추가 확인 대상','미확인','자동 재연결, 실제 메일·장시간 운영']],[345,240,567],{h:429,size:24});
 note(s,'9월 22일 본인 PC의 Tailscale 화면·영상도 성공 보고가 있다. 현재 주 시연 경로는 Windows 핫스팟과 SSH 터널이다. 친구 Tailscale 수락·접속은 별도 미확인으로 남으며 현재 시연의 선행 조건이 아니다.');

}
// 23
{

 const s=slide('주요 문제의 원인과 해결','6. 테스트 결과 및 문제점 분석',[src.vision,src.arch,src.live,src.hotspot],'데이터 보존과 시연 연결을 우선 점검 / 해결 후 확인 범위는 해당 검사·보고 기준');
 tab(s,[['문제','확인한 원인','수정과 확인'],['정지 화면의 미세 흔들림','정합 영상을 미리보기에 사용','원본 영상과 박스 좌표 투영 분리'],['사건 누락·중복 위험','DB 저장 전 기준 장면 갱신','저장 확인 후 갱신, 사건 ID 검사'],['늦은 AI 응답의 충돌','추론 중 물품 기록·상태 변경','검토 상태와 추적 revision 검사'],['연속 편집·모바일 넘침','갱신 잠금·숨김 라벨 위치','작업 잠금 분리, 390px 검사'],['SSH 후 웹 접속 실패','Pi 내부에서 터널 시작','Windows에서 실행 후 성공 보고']],[334,360,458],{h:432,size:24});
 note(s,'정지 영상 문제는 합성 장면에서 소프트웨어 원인을 재현했다. 센서 노출이나 물리 흔들림까지 해결됐다고 주장하지 않는다. 새 SD 설치 복구는 설치기·체크섬·카메라 및 시스템 진단 로그로 확인했다. SSH 오류 원인은 이번 9/29 터널 위치 오류에 한정한다. 다른 끊김이나 프로필 오류의 원인을 추측하지 않는다.');

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
const s=slide('최종보고의 필수 과제와 추가 실험','7. 향후 개발 및 완성 계획',[src.accept,src.hotspot,'docs/paper/EXPERIMENT_GUIDE.md'],'제안 계획 / 아래 횟수는 앞으로 수행할 점검 목표이며 기존 성공 횟수가 아님');
 tab(s,[['우선순위','11월 3일까지의 과제','완료 증거'],['필수  ·  시연','발표 장비에서 연결·종료·재시작\n등록·이동·회수 흐름 확인','연속 3회 점검 기록\n동일 물품 ID·사진·이력'],['필수  ·  관리','검토·편집·기한 연장과 알림 확인\n오류 시 기록 보존·복구 확인','조건·예상·실제 결과표\n실제 메일 수신 또는 남은 한계'],['필수  ·  AI 평가','정답·원본·응답·시각을 연결\n표본 수와 성공·불확실·실패 집계','원시 기록과 평가표\n성공·오류 사례 및 개선 내용'],['추가  ·  비교 연구','같은 영상의 B0/B1/B2/P1 비교\n입력 구성·모델 변경 효과 비교','공통 실행기·반복 실험 결과\n핵심 과제 이후 범위 확정']],[230,517,405],{h:420,size:23});
 tx(s,'일정이 부족하면 추가 비교 범위를 줄이고 필수 시연·평가 증거를 먼저 확보',64,615,1152,31,23,true,C.teal);
 note(s,'연속 3회는 새로 제안한 시연 리허설 기준이다. AI 성능 목표 수치는 파일럿과 허용 오차를 확인한 뒤 확정한다. 비교 연구를 생략 완료로 처리하는 것이 아니라 중간보고 이후 추가 개발 대상으로 우선순위를 정한 것이다.');
}
// 26
{
const s=slide('최종보고까지의 주차별 완료 목표','7. 향후 개발 및 완성 계획',['사용자 제공 수업 일정',src.hotspot],'발표일은 수업 확정 일정 / 작업 배분과 세부 완료일은 제안 계획');
 tab(s,[['기간','먼저 완료할 작업','산출물'],['10/02~10/12','실제 화면·동일 ID 캡처, 연결 리허설','중간보고 자료·시연 점검표'],['10/13 중간보고','현재 근거와 남은 과제 설명','피드백·수정 우선순위'],['10/14~10/20','사건별 기록 양식·저장 연결, 파일럿','원본·정답·응답, 오류 목록'],['10/21~10/26','입력·판정 기준 보완, 별도 자료 평가\n관리·메일·재시작 시험','지표·실패 사례·운영 점검표'],['10/27 발표 연습','실제 장비로 처음부터 끝까지 시연','최종 수정 목록'],['10/28~11/03','수정 확인, 배포 고정, 최종보고','최종 PPT·패키지·원시 기록']],[255,545,352],{h:414,size:23});
 note(s,'10/20 중간고사 일정을 고려해 파일럿·기록 연결 범위부터 진행한다. 구현·측정은 장진석 주도, 자료 검토·시연 준비는 권기원 지원이라는 README 역할을 기준으로 제안하며 실제 세부 담당과 날짜는 팀이 확정한다. 공통 baseline 실행기는 필수 현장 검증을 막지 않는 추가 과제로 둔다.');
}
// 27
{
const s=slide('최종보고에서 제시할 결과물','7. 향후 개발 및 완성 계획',[src.readme,src.accept,'docs/paper/EXPERIMENT_GUIDE.md']);
 tx(s,'현재: 통합 프로토타입 구현과 기본 실물 흐름 확인',64,178,1152,62,33,true,C.teal);
 rows(s,[['실행 가능한 시스템','발표 장비에서 재시작 후 등록·이동·회수\n동일 ID와 관리자 처리 이력으로 확인'],['AI 평가 자료','정답·원본·응답을 묶어 지표와 사례 제시\n불확실·실패도 포함하고 평가 표본 수 명시'],['재현 가능한 배포본','고정한 코드·설정·패키지와 실행 안내\n점검표·원시 기록·남은 제한 사항을 함께 전달']],{y:287,gap:104,labelW:274});
 tx(s,'다음 단계의 초점: 새 기능 확대보다 실제 환경의 검증 근거 확보',64,618,1152,28,24,true,C.teal);
 note(s,'마무리에서 기능 구현 완료와 정량 성능 미측정을 동시에 설명한다. 제시한 산출물은 최종보고의 제안 완료 기준이며 이미 완성한 결과물 목록으로 읽지 않는다.');
}
// 28
{
 const s=slide('늦은 AI 응답을 적용하기 전 상태 확인','보충자료 A. 핵심 코드',['app/classification.py:70','app/main.py:432','app/item_policy.py']);
 tx(s,'app/classification.py  ·  process()의 실제 발췌',64,180,1152,36,25,true,C.teal);
 tx(s,'with self.mutation_lock:\n    current = self.store.get_item(item_id)\n    if not current or review_status(current) != "pending":\n        return',64,248,1152,174,28,false,C.ink,{typeface:'Consolas'});
 tx(s,'관리자가 검토를 완료한 기록에는 뒤늦은 분류를 적용하지 않는다.',64,444,1152,58,28,true,C.teal);
 tx(s,'모호한 제거 검증은 별도로 물리 추적 signature를 검사한다.\n이미 이동하거나 처리한 물품에 이전 제거 판정을 적용하지 않는다.',64,529,1152,99,27);
 note(s,'app/classification.py의 current 조회와 pending 검사 4줄을 그대로 발췌했다. signature와 revision은 이름·분류·기한의 단순 편집과 물리 추적 변경을 구분한다.');
}
// 29
{
const s=slide('시연 실행과 데이터 초기화 구분','보충자료 B. 시연 운영',[src.hotspot,src.check],'앱·카메라는 Pi에서 실행 / 상세 단계는 저장소의 Windows 핫스팟 가이드');
 rows(s,[['시작','노트북 Wi-Fi·핫스팟 실행 후 Pi 전원 연결\n2~3분 뒤 Windows에서 SSH 터널, 같은 노트북 웹 접속'],['정상 종료','Pi 정상 종료 명령 후 종료 점멸이 끝날 때까지 대기\nPi 전원 분리 후 핫스팟 종료'],['시연 초기화','확인 후 모든 물품·활동·알림·사진을 백업 없이 삭제\n설정·API 키·기존 백업은 유지'],['설정의 일반 초기화','자동 백업과 확인 문구 입력을 거쳐 실행\n시연 초기화와 보존 방식이 다름']],{y:183,gap:111,labelW:263});
 note(s,'시연을 다시 시작할 때마다 초기화할 필요는 없다. 필요한 기록이 있으면 보존하고, 초기화 전 물품을 카메라 범위에서 치운다. 실행 7단계·종료 4단계·이름 오류 5단계는 REFOUND_WINDOWS_HOTSPOT_GUIDE.md를 따른다. 현재 시연 연결 성공 보고와 새 구성 전원 재인가 성공은 별개다. 내부 접속 주소·키는 발표자료에 적지 않았다.');
}
// 30
{
const s=slide('AI 개선을 위한 파일럿과 재평가','보충자료 C. 평가 방법',['docs/paper/EXPERIMENT_GUIDE.md','AGENTS.md'],'아래는 제안 실험 설계 / 확보한 사건 수나 수행 결과가 아님');
 rows(s,[['1  기록 절차 점검','추가·이동·제거·변화 없음 각 10건, 약 40건 파일럿\n사건 ID로 원본·정답·응답·시각을 연결'],['2  오류 유형 분류','그림자·가림·저대비·다중 물품의 실패 조건 확인\n감지 실패, AI 오분류, 불확실·통신 실패를 구분'],['3  기준 보완·고정','입력 증거·프롬프트·판정 기준을 개발 자료에서 보완\n평가 전 코드·모델·설정을 고정'],['4  별도 자료 평가','새 평가 자료에서 지표·표본 수·실패 사례 보고\n연속 영상 Baseline 비교는 추가 실험으로 수행']],{y:184,gap:111,labelW:266});
 note(s,'파일럿 약 40건은 기록 절차·오류 유형 확인용 제안이며 최종 성능의 대표 표본이라고 주장하지 않는다. 개선에 사용한 자료와 최종 평가 자료를 분리한다. B0/B1/B2/P1 비교는 같은 영상·FPS·정답·워밍업으로 수행하고, 기존 pair runner로 시간당 오탐이나 종단간 지연을 주장하지 않는다. Accuracy의 분모에는 불확실·실패 처리를 명시하고 사건 Precision/Recall/F1과 분류 정확도를 구분한다.');
}

await fs.mkdir(BUILD,{recursive:true});
const candidatePath=path.join(BUILD,`candidate-${revision}.pptx`);
await(await PresentationFile.exportPptx(p)).save(candidatePath);
const {execFileSync}=await import('node:child_process');
execFileSync(path.join(RT,'dependencies/python/python.exe'),[path.join(BUILD,'korean_typography.py'),candidatePath],{stdio:'inherit'});
await fs.writeFile(path.join(BUILD,`typography-${revision}.json`),JSON.stringify(typography,null,2));
await fs.writeFile(path.join(BUILD,`deck-manifest-${revision}.json`),JSON.stringify({slides:meta,tableOwners,chartOwners,asOf:'2026-10-02',presentationDate:'2026-10-13',finalReportDate:'2026-11-03',fontPolicy:{basis:'design',families:[FONT,'Consolas']},screenshots:['development detail: 2026-09-18','development dashboard: 2026-09-22']},null,2));
await finalizePresentation({workspaceDir:ROOT,candidatePath,finalPath:FINAL,pythonExecutable:path.join(RT,'dependencies/python/python.exe'),integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--validate-bullet-geometry',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:30,requiredNativeTableOwnerSlides:tableOwners,requiredNativeChartOwnerSlides:chartOwners,materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT,'Consolas']},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation-${revision}.json`)});
if(process.env.SKIP_ARTIFACT_RENDER==='1'){console.log(JSON.stringify({final:FINAL,slides:30}));process.exit(0);}
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
