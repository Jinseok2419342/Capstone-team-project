import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../../..');
const RT='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime';
const SKILL='C:/Users/USER/.codex/plugins/cache/openai-primary-runtime/presentations/26.930.11008/skills/presentations';
process.env.RUNTIME_NODE_MODULES=path.join(RT,'dependencies/node/node_modules');
process.env.RUNTIME_NODE=path.join(RT,'dependencies/node/bin/node.exe');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const BUILD=path.join(ROOT,'output/maintenance/2026-10-02-midterm-review');
const revision=process.env.DECK_REVISION||'v4_reviewed';
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
 const s=slide('초기 계획과 실제 구현의 차이','3. 프로젝트 개발 진행 현황',[src.readme],'전체 진행률(%)은 팀의 작업 가중치·완료 기준 합의 후 산정');
 tab(s,[['초기 계획','현재 구현','변경 이유'],['Pi 5 / USB 카메라','Pi 4 2GB / CSI 카메라','보유 장비에 맞춘 배포'],['YOLO·CNN·로컬 LLM','OpenCV + 외부 VLM','저사양 장치·다양한 물품 대응'],['클라우드 DB','SQLite WAL + 사진 파일','단일 장치 운영 단순화'],['AI 응답 후 등록','관찰 우선 저장 후 비동기 추론','API 장애 때에도 기록 보존'],['React·복수 백엔드 검토','Vanilla JS + FastAPI','배포·유지보수 구조 단순화']],[370,420,362],{h:393,size:23});
 tx(s,'전체 진행률: 산정 기준 미확정',64,600,1152,38,28,true,C.teal);
 note(s,'공식 진행률의 분모·가중치·완료 기준이 제공되지 않았으므로 수치를 만들지 않았다. 작성 가이드의 가중 작업 산식으로 산정 후 입력한다. 초기 계획 대비 빠름/지연은 기존 예정 완료일이 없어 단정하지 않는다.');
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

 const s=slide('물품 상세 화면과 처리 흐름','4. 핵심 기능 구현 결과',[src.accept,src.live,'output/maintenance/2026-09-18-live-flow-review/browser-classified-detail.png'],'9/18 개발 검사 화면 / 합성 물품·모의 AI 사용. 화면의 97%는 실제 모델 정확도가 아님');
 await screenshot(s,'output/maintenance/2026-10-02-midterm-review/assets/detail.png',64,171,399,466,'합성 데이터 개발 검사에서 저장된 물품 상세 화면');
 rows(s,[['등록','물품을 놓고 손을 뺀 뒤 임시 기록 생성\nAI 분석 후 이름·분류를 확정하거나 검토 대기'],['이동','같은 물품의 위치·사진 갱신\n새 기록을 만들지 않고 기존 ID 유지'],['회수','화면에서 사라지면 같은 기록의 상태 전환\n활동 이력에 처리 결과 저장']],{x:515,y:195,w:701,gap:125,labelW:95});
 tx(s,'실물 흐름은 9/22 성공 보고. 동일 ID의 실제 Pi 캡처는 미확보.',515,595,701,49,22,false,C.muted);
 note(s,'왼쪽은 기존 개발 검사 PNG의 상세 창 영역만 비율을 유지해 잘랐다. 실제 카메라·원격 모델 결과로 해석하지 않는다. 오른쪽은 구현 흐름이다. 사용자 보고에서는 실물 등록·이동 시 중복 방지·제거 후 회수 확인에 성공했다고 했으나 개별 ID·사진은 수집하지 않았다.');

}
// 15
{

 const s=slide('관리자 대시보드와 운영 기능','4. 핵심 기능 구현 결과',['templates/index.html','static/app.js',src.check,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png'],'9/22 개발 검사 화면 / 물품 수·사진·영상은 합성 테스트 데이터');
 await screenshot(s,'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png',64,178,740,455,'합성 카메라·임시 DB를 사용한 관리자 대시보드');
 tx(s,'대시보드',850,180,366,42,29,true,C.teal);
 tx(s,'실시간 카메라와 보관 현황\n기한 도래·확인 필요 항목\n물품 검색과 상세 편집',850,237,366,144,25);
 tx(s,'시연 초기화',850,414,366,42,29,true,C.teal);
 tx(s,'확인 후 모든 물품·기록 삭제\n백업 없이 실행\n설정과 API 키는 유지',850,471,366,124,25);
 note(s,'실제 Pi 관리자 화면은 추가 확보 대상이다. 이 슬라이드는 보존된 개발 검사 캡처로 구현된 UI를 설명한다. 일반 초기화는 자동 백업을 유지하며, 시연 초기화는 사진까지 백업 없이 삭제한다. 실물은 초기화 전에 카메라 범위에서 치운다.');

}
// 16
{
 const s=slide('통합된 기능과 남은 개발 범위','4. 핵심 기능 구현 결과',[src.live,src.accept,'experiments/pair_runner.py',src.arch]);
 para(s,'연동 구현 완료','카메라·사건 처리·SQLite·API·웹 연결\n임시 저장 후 비동기 AI 반영\n기한 검사와 알림, 상태·활동 이력 연결',64,192,552);
 para(s,'현장 확인 대기','새 네트워크의 전원 재인가와 자동 연결\n개별 AI 응답 기록과 실제 SMTP 수신\n여러 물품과 장시간 운영',679,192,537);
 tx(s,'정량 평가를 위해 추가할 부분',64,456,1152,44,29,true,C.teal);
 tx(s,'종단간 사건·API 호출의 영속 측정 원장\n공통 영상으로 B0/B1/B2를 비교할 스트림 실행기\n정답 라벨 데이터와 반복 측정 결과',64,518,1152,117,27);
}
// 17
{

 const s=slide('데이터 수집과 AI 입력 구성','5. AI 모델 및 데이터 개발 현황',['app/vision.py','app/ai.py','app/config.py',src.readme],'운영 사진의 전체 수량은 미집계 / 정답 라벨이 있는 평가 세트는 미확보');
 tab(s,[['단계','현재 처리와 확보 수준'],['원시 데이터','고정 CSI 카메라의 연속 영상과 사건별 사진'],['로컬 전처리','움직임 종료·장면 안정화, 기하 정합과 조명 보정'],['전체 장면 전후 2장','변화 방향과 주변 문맥 확인, JPEG 품질 72'],['후보 영역 전후 2장','물품의 세부 특징 확인, JPEG 품질 88'],['평가 데이터','정답 라벨·AI 응답을 연결한 평가 자료 수집 예정']],[290,862],{h:393,size:24});
 tx(s,'요청당 최대 4장. 자체 학습·데이터 증강·파인튜닝은 수행하지 않았다.',64,597,1152,40,25,true,C.teal);
 note(s,'통계형 결측치 대치나 학습 데이터 정규화는 적용 대상이 아니다. 프레임 읽기 실패는 연결 복구 흐름에서 처리한다. 사진 수량과 평가 사건 수를 근거 없이 만들지 않았다.');

}
// 18
{

 const s=slide('적용 모델과 구조화 추론 방법','5. AI 모델 및 데이터 개발 현황',['app/ai.py','app/config.py',src.state,src.hotspot],'모델별 정확도·비용 비교는 미실시 / RAG·자체 학습·파인튜닝은 미적용');
 rows(s,[['모델·선정 이유','OpenAI 사용, Gemini 연동 경로도 구현\n다양한 물품을 전후 이미지와 문맥으로 해석'],['설정 확인 범위','9/22 설정: gpt-5.6-luna\n9/29 OpenAI 동작 성공 보고, 당일 모델명은 미수집'],['프롬프트·출력','전후 증거와 판단 지침, JSON schema를 함께 전달\naction·물품명·분류·확신도·근거를 해석'],['응답 검증','기본 모델의 reasoning low, 출력 상한 2,048토큰\n완료 상태와 내용을 검사하고 오류·불확실 기록 보존']],{y:181,gap:111,labelW:239});
 note(s,'모델은 Pi 설정 로그의 문자열을 날짜와 함께 표시했다. 학습 조건이 아니라 추론 요청 설정이다. OpenAI strict schema와 기본 모델의 낮은 추론 강도 설정은 app/ai.py 근거다. 특정 모델의 우수성이 비교 실험으로 확인됐다는 뜻은 아니다.');

}
// 19
{

 const s=slide('현재 성능 확인 범위와 평가 지표','5. AI 모델 및 데이터 개발 현황',[src.hotspot,src.accept,'docs/paper/EXPERIMENT_GUIDE.md'],'9/29 OpenAI 동작 성공 보고 확보 / 정답·개별 응답·표본 수를 연결한 정량 결과는 없음');
 tab(s,[['평가 항목','현재 상태','수집할 근거'],['사건 Precision / Recall / F1','미측정','추가·이동·제거별 TP·FP·FN'],['물품 분류 정확도','미측정','정답 분류와 AI 응답, 표본 수 N'],['불확실 판정 비율','미측정','전체 사건 수와 uncertain 건수'],['종단간 지연 p50 / p95','미측정','행동 종료와 DB 반영 시각'],['성공·실패 사례 분석','원본 미수집','같은 사건의 사진·정답·응답']],[410,210,532],{h:397,size:25});
 tx(s,'다음 평가: 사건별 정답과 응답을 함께 저장하고 지표를 계산한다.',64,603,1152,40,26,true,C.teal);

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

 const s=slide('자동화 테스트와 통합 검사','6. 테스트 결과 및 문제점 분석',[src.check,src.live,src.sync],'합성 카메라·임시 DB·모의 AI·SMTP를 사용한 개발 검사');
 [['272','Python 검사','9/30 재실행 통과'],['37','Node 검사','9/30 재실행 통과'],['7','Chromium 검사','9/22 검사 통과']].forEach(([n,l,d],i)=>{tx(s,n,64+i*402,165,360,100,76,true,C.teal);tx(s,l,67+i*402,264,360,39,27,true);tx(s,d,67+i*402,310,360,35,23,false,C.muted);});
 tab(s,[['검사 조건','예상 결과와 실제 결과'],['합성 사건·관리 흐름','등록·이동·상태 변경·활동 이력 연결 검사 통과'],['초기화·반응형 화면','확인·취소·설정 보존·후속 등록 검사 통과'],['9/30 격리 서버 시작','화면·정적 파일·주요 API의 HTTP 200 확인']],[350,802],{y:382,h:238,size:24});
 note(s,'Python 272개·Node 37개는 9월 30일 재실행 기록이다. Chromium 7개는 9월 22일 기록이며 9월 30일에 재실행하지 않았다. 10월 2일에는 슬라이드 검토만 수행했다. 개수를 서로 합산하거나 AI 정확도로 해석하지 않는다.');

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

 const s=slide('최종보고 전 개발·검증 우선순위','7. 향후 개발 및 완성 계획',[src.accept,src.hotspot,'docs/paper/EXPERIMENT_GUIDE.md','사용자 제공 수업 일정'],'제안 계획 / 성능 목표 수치는 파일럿 결과와 운영 허용 오차를 바탕으로 확정');
 rows(s,[['우선 1  시연 안정화','핫스팟 자동 연결과 전원 재인가 후 영상·AI 복귀\n완료 근거: 같은 발표 장비의 반복 실행 기록'],['우선 2  운영 검증','다중 물품, 편집·메일, privacy 복원, 장시간 감시\n완료 근거: 조건·예상·실제 결과를 연결한 점검표'],['우선 3  평가 구현','사건·API 시각 원장, 정답 라벨, 공통 비교 실행기\n완료 근거: 원시 CSV와 동일 입력의 비교 결과'],['AI 개선 반복','약 40건 파일럿으로 오류 유형과 기록 절차 확인\n입력·판정 기준을 고정한 뒤 별도 자료로 재평가']],{y:181,gap:111,labelW:267});
 note(s,'약 40건은 추가·이동·제거·none 각 10건의 제안 구성이며 확보한 데이터나 최종 표본 수가 아니다. 기존 모델 학습은 없으므로 입력 증거·프롬프트·판정 기준의 조정과 필요한 경우 모델 변경을 비교한다.');

}
// 26
{

 const s=slide('11월 3일 최종보고까지의 일정','7. 향후 개발 및 완성 계획',['사용자 제공 수업 일정',src.hotspot],'발표일은 수업 확정 일정 / 개발 작업과 완료 목표는 제안 일정');
 tab(s,[['기간','개발·검증 계획','완료 산출물'],['10/02~10/12','실제 캡처, 연결 리허설, 평가 설계','중간보고 자료·시연 기록'],['10/13 중간보고','구현·검증 범위와 남은 계획 발표','피드백과 수정 우선순위'],['10/14~10/20','측정 원장·비교 실행기, 파일럿','원시 CSV·정답 라벨·오류 목록'],['10/21~10/26','동일 입력 비교, 운영 안정화','평가표·실패 사례·반복 검사'],['10/27 발표 연습','전체 시연과 결과·화면 점검','최종 수정 목록'],['10/28~11/03','자료 보완, 배포 고정, 최종보고','최종 PPT·패키지·검증 기록']],[255,510,387],{h:431,size:23});
 note(s,'10/20은 중간고사 일정이므로 실제 팀 작업량에 맞춰 10/14~10/20의 범위를 조정한다. 구현·계측은 팀장 주도, 자료 검토·시연 준비는 팀원 지원이라는 현재 역할을 기준으로 협업하며 세부 담당과 마감은 팀 합의가 필요하다.');

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
 tx(s,'관리자가 검토를 완료한 기록에는 뒤늦은 분류를 적용하지 않는다.',64,444,1152,58,28,true,C.teal);
 tx(s,'모호한 제거 검증은 별도로 물리 추적 signature를 검사한다.\n이미 이동하거나 처리한 물품에 이전 제거 판정을 적용하지 않는다.',64,529,1152,99,27);
 note(s,'app/classification.py의 current 조회와 pending 검사 4줄을 그대로 발췌했다. signature와 revision은 이름·분류·기한의 단순 편집과 물리 추적 변경을 구분한다.');
}
// 29
{

 const s=slide('현재 시연 연결 구조','보충자료 B. 시연 운영',[src.hotspot],'앱·카메라는 Pi에서 실행 / 시연 노트북은 핫스팟과 웹 접속을 담당');
 rows(s,[['인터넷 연결','노트북을 인터넷 Wi-Fi에 연결한 뒤 모바일 핫스팟 실행'],['Pi 시작','핫스팟을 먼저 켜고 Pi 전원 연결, 약 2~3분 대기'],['웹 접속','Windows PowerShell에서 SSH 터널 시작\n같은 노트북 브라우저에서 관리자 화면 접속'],['종료·재실행','작업 완료 후 Pi 정상 종료, 종료 점멸이 끝나면 전원 분리\n다음 실행 때 핫스팟과 SSH 터널을 다시 시작']],{y:185,gap:106,labelW:232});
 note(s,'상세 실행 7단계·종료 4단계·이름 오류 대응 5단계는 REFOUND_WINDOWS_HOTSPOT_GUIDE.md를 따른다. 공개 발표자료에는 내부 접속 주소·비밀번호·키를 적지 않았다. 이 사용 순서의 확정과 새 구성의 실제 전원 재인가 성공은 별개다.');

}
// 30
{

 const s=slide('정량 평가의 설계와 해석 기준','보충자료 C. 평가 방법',['docs/paper/EXPERIMENT_GUIDE.md','AGENTS.md']);
 rows(s,[['평가 자료','안정 이미지 쌍, 연속 영상, 동일 사건의 VLM 증거를 구분\n그림자·가림·저대비·다중 물품 조건을 기록'],['공통 비교 조건','같은 영상·FPS·정답 라벨로 B0/B1/B2/P1 비교\n개발 자료에서 기준을 정한 뒤 별도 자료로 평가'],['정확도와 지연','사건별 TP·FP·FN, 분류 정답, 불확실·실패 응답 기록\n지연에는 표본 수·검출률·시각 누락률을 함께 제시'],['운영 검증','동일 물품 ID, 상태·사진·활동 이력을 함께 확인\n실패 시 조건·실제 결과·복구 과정을 보존']],{y:184,gap:111,labelW:255});
 note(s,'평가 설계이며 수행 결과가 아니다. pair runner는 detector core만 평가한다. FP/hour와 실제 DB 중복 방지, 종단간 지연은 연속 입력과 영속 기록이 필요하다. 공식 진행률은 팀이 합의한 전체 작업 가중치와 완료 기준으로 별도 산정한다.');

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
