import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../../..');
const RUNTIME='C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime';
process.env.RUNTIME_NODE_MODULES=path.join(RUNTIME,'dependencies/node/node_modules');
process.env.RUNTIME_NODE=path.join(RUNTIME,'dependencies/node/bin/node.exe');
const SKILL='C:/Users/pppp/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.61513/skills/presentations';
const TMP=path.join(ROOT,'tmp/paper-revision');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(RUNTIME,'dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,resolvePresentationFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const source=(await fs.readFile(path.join(HERE,'RESEARCH_FRONT_MATTER.md'),'utf8')).replace(/\r\n/g,'\n');
const title=source.split('\n')[0].slice(2);
const refs=source.split('## 참고문헌')[1].trim();
const abstract=source.split('## 요약')[1].split('주제어:')[0].trim();
const sections={};
for(const m of source.matchAll(/^### (\d-\d) ([^\n]+)\n\n([\s\S]*?)(?=\n### |\n## |\n<!-- PAGEBREAK -->|(?![\s\S]))/gm)){
  sections[m[1]]={title:m[2],paragraphs:m[3].trim().split('\n\n')};
}
const tableBlock=source.split('\n\n').find(b=>b.startsWith('| 연구 |'));
const tableValues=tableBlock.split('\n').filter(l=>!l.startsWith('|---')).map(l=>l.split('|').slice(1,-1).map(s=>s.trim()));
const relatedConclusion=source.split('본 연구의 기여는')[1].split('\n\n')[0];
const slidesData=[
  {title:title.replace('감지와 ','감지와\n'),label:'요약 · 원문',page:1,font:23,
   excerpts:[abstract],
   notes:[['어떤 시스템인가','물품의 상태 변화는 Pi에서 찾고, 필요한 의미만 외부 AI에 묻습니다.'],['무엇을 연구하나','오탐·처리 지연·외부 호출·관리 기록의 연결을 평가합니다.'],['현재 단계','시스템 구현과 실험 설계. 정량 성능은 아직 측정 전입니다.']]},
  {title:'1-1  연구 배경과 필요성',label:'서론 · 원문 발췌',page:2,font:24,
   excerpts:[sections['1-1'].paragraphs[0],sections['1-1'].paragraphs[2]],
   notes:[['보관대에서 필요한 일','물품명뿐 아니라 들어옴·이동·사라짐을 기록해야 합니다.'],['예를 들면','같은 물건을 옆으로 옮겼다면 새로 등록하기보다 기존 위치를 바꿔야 합니다.'],['인용의 역할','[1]은 기존 연구의 근거입니다. 우리가 그 연구를 수행했다는 뜻이 아닙니다.']]},
  {title:'1-2 · 1-3  문제 정의와 연구 질문',label:'서론 · 원문 발췌',page:2,font:23,
   excerpts:[sections['1-2'].paragraphs[0],sections['1-3'].paragraphs[0]],
   notes:[['영상 차이 ≠ 물품 변화','조명·그림자·흔들림도 차이를 만듭니다.'],['함께 확인할 관계','오탐 억제와 대기시간, 호출 감소와 사건 누락을 같이 봅니다.'],['논문의 중심','왜 이렇게 설계했는지 설명하고, 비교 실험으로 효과와 부담을 확인합니다.']]},
  {title:'2-1 · 2-2  안정 장면과 엣지의 역할',label:'이론적 배경 · 원문 발췌',page:3,font:24,
   excerpts:[sections['2-1'].paragraphs[2],sections['2-2'].paragraphs[2]],
   notes:[['안정 장면','손이 빠지고 물품이 제자리에 머문 전후 모습을 비교합니다.'],['엣지 장치','카메라 가까이 있는 Raspberry Pi가 기초 분석을 맡습니다.'],['설계의 부담','기다리는 시간이 생기고, 영상 보정에도 연산이 필요합니다.']]},
  {title:'2-3  멀티모달 추론과 전후 시각 증거',label:'이론적 배경 · 원문',page:3,font:24,
   excerpts:sections['2-3'].paragraphs,
   notes:[['시각언어모델','이미지를 보고 물품의 특징이나 변화의 의미를 설명하는 AI입니다.'],['최대 네 장','전체 장면 전·후와 변화 영역 전·후를 함께 제공합니다.'],['검증할 부분','네 장이 더 좋은지는 같은 사건의 1장·2장·4장 비교로 확인합니다.']]},
  {title:'2-4  관련 연구와 본 연구의 위치',label:'관련 연구 · 표와 원문',page:4,font:23,
   table:tableValues,excerpts:['본 연구의 기여는'+relatedConclusion],
   notes:[['표를 읽는 방법','정확도 순위가 아니라 각 연구가 다루는 문제를 비교합니다.'],['우리 연구의 초점','사건 선별 → 의미 추론 → 보관 관리 이력을 연결합니다.'],['다음 본론','설계·알고리즘·실험 방법을 설명하고 실측 결과로 검증합니다.']]},
];

const family=resolvePresentationFont({fontFamily:'Malgun Gothic'});
const C={ink:'#223848',body:'#202B34',muted:'#657581',line:'#CDD7DE',accent:'#186D78',pale:'#F3F6F8'};
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
const excerptAudit=[];
function rect(slide,x,y,w,h,fill){return slide.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}})}
function textbox(slide,text,x,y,w,h,size=24,color=C.body,bold=false,lineSpacing=1.38){
  const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  s.text=text;s.text.style={typeface:family,fontSize:size,color,bold,lineSpacing,wrap:'square',autoFit:'none',verticalAlignment:'top',insets:{left:0,right:0,top:0,bottom:0}};
  return s;
}
for(let i=0;i<slidesData.length;i++){
  const data=slidesData[i];const slide=presentation.slides.add();slide.background.fill='#FFFFFF';
  rect(slide,56,34,30,4,C.accent);
  textbox(slide,'Re:Found  /  연구방법 이전 원고',99,23,950,26,16,C.muted);
  textbox(slide,data.title,56,68,1168,i===0?86:60,i===0?30:34,C.ink,true,1.2);
  const top=i===0?184:155;
  textbox(slide,data.label,56,top-10,800,25,16,C.muted);
  rect(slide,923,top-8,1,474,C.line);
  textbox(slide,'이해를 돕는 설명',956,top-10,268,26,17,C.accent,true);
  for(let j=0;j<data.notes.length;j++){
    const y=top+45+j*137;
    textbox(slide,data.notes[j][0],956,y,267,30,21,C.ink,true);
    textbox(slide,data.notes[j][1],956,y+38,267,91,20,C.body,false,1.08);
  }
  if(data.table){
    const tableDisplay=data.table.map(row=>row.map(value=>value.replace('NoScope[6]·Reducto[7]','NoScope[6]·\nReducto[7]')));
    const table=slide.tables.add({rows:data.table.length,columns:3,left:56,top:192,width:828,height:300,columnWidths:[172,326,330],values:tableDisplay});
    table.styleOptions={headerRow:true,bandedRows:false};
    table.borders.assign({style:'solid',fill:C.line,width:.75});
    table.cells.block({row:0,column:0,rowCount:data.table.length,columnCount:3}).assign({fill:'#FFFFFF',textStyle:{typeface:family,fontSize:19,color:C.body},margins:{left:10,right:10,top:10,bottom:10},anchor:'center'});
    table.cells.block({row:0,column:0,rowCount:1,columnCount:3}).assign({fill:C.pale,textStyle:{typeface:family,fontSize:19,bold:true,color:C.ink}});
    textbox(slide,data.excerpts[0],56,520,828,134,21.5,C.body,false,1.06);
  }else{
    const joined=data.excerpts.join('\n\n');
    textbox(slide,joined,56,top+33,828,466-(i===0?22:0),data.font,C.body,false,1.06);
  }
  rect(slide,56,668,1168,1,C.line);
  textbox(slide,`전반부 원고 ${data.page}쪽 · 본문은 원문 그대로${data.label.includes('발췌')?' 발췌':''}`,56,682,995,22,14,C.muted);
  textbox(slide,`${i+1} / ${slidesData.length}`,1160,680,64,23,15,C.muted);
  slide.speakerNotes.textFrame.setText(`대본 없음. 왼쪽은 RESEARCH_FRONT_MATTER.md의 원문이며 오른쪽만 이해를 돕는 설명입니다.\n원고 ${data.page}쪽.\n\n참고문헌\n${refs}`);
  for(const excerpt of data.excerpts){
    if(!source.includes(excerpt))throw new Error(`Source mismatch on slide ${i+1}`);
    excerptAudit.push({slide:i+1,characters:excerpt.length,verbatim:true});
  }
}
await fs.mkdir(TMP,{recursive:true});
const candidatePath=path.join(TMP,'front-paper-candidate.pptx');
await(await PresentationFile.exportPptx(presentation)).save(candidatePath);
const finalPath=path.join(ROOT,'output/presentation/REFOUND_EARLY_PAPER_FINAL.pptx');
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath,finalPath,
 pythonExecutable:path.join(RUNTIME,'dependencies/python/python.exe'),
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','6'],
 requiredNativeTableOwnerSlides:[6],requiredNativeChartOwnerSlides:[],explicitTotalSlideCount:6,
 fontPolicy:{basis:'design',families:[family]},verifyArtifactToolImport:true,
 receiptPath:path.join(TMP,path.basename(finalPath)+'.validation.json')});
const imported=await PresentationFile.importPptx(await FileBlob.load(finalPath));
const rendered=[];
for(let i=0;i<imported.slides.items.length;i++){
  const slide=imported.slides.items[i];
  const png=await imported.export({slide,format:'png',scale:1.25});
  const f=path.join(TMP,`slide-${i+1}.png`);await fs.writeFile(f,new Uint8Array(await png.arrayBuffer()));rendered.push(f);
  const layout=await slide.export({format:'layout'});await fs.writeFile(path.join(TMP,`slide-${i+1}.layout.json`),await layout.text());
}
await fs.writeFile(path.join(HERE,'SLIDES_SOURCE_CHECK.json'),JSON.stringify({slides:6,editable:true,sourceManuscript:'RESEARCH_FRONT_MATTER.md',excerpts:excerptAudit,tableSourceExact:true,speechScript:false,final:finalPath},null,2));
console.log(JSON.stringify({final:finalPath,slides:6,rendered,validation:result},null,2));
