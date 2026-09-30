import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,'../../..');
const RUNTIME='C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime';
const SKILL='C:/Users/pppp/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.61513/skills/presentations';
process.env.RUNTIME_NODE_MODULES=path.join(RUNTIME,'dependencies/node/node_modules');
process.env.RUNTIME_NODE=path.join(RUNTIME,'dependencies/node/bin/node.exe');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(process.env.RUNTIME_NODE_MODULES,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const TMP=path.join(ROOT,'tmp/paper-capture-slides');
const OUT=path.join(ROOT,'output/presentation/REFOUND_PDF_CAPTURE_BRIEFING.pptx');
const data=[
 ['제목·요약',[
  ['연구 주제','보관대 물품의 추가·이동·제거를\n기록하는 분실물 관리 시스템'],
  ['역할 분담','Pi가 변화를 먼저 찾고,\n필요한 사건의 의미만 외부 AI에 질문'],
  ['현재 단계','구현과 실험 설계까지 진행\n성능 수치는 실측 후 제시']]],
 ['서론',[
  ['풀려는 문제','조명이나 그림자의 변화를\n새 물품으로 오인하지 않아야 함'],
  ['관리 업무와 연결','같은 물건을 옮기면\n기존 기록의 위치를 갱신'],
  ['연구 질문','정확도·지연·자원·외부 호출량을\n함께 평가']]],
 ['이론적 배경',[
  ['안정 장면','손이 빠지고 물품이 멈춘 뒤\n전후 모습을 비교'],
  ['엣지 컴퓨팅','카메라 가까운 Pi에서\n기초 영상 분석을 수행'],
  ['멀티모달 추론','전체 장면과 확대 영역의 전후를\n최대 네 장으로 전달']]],
 ['관련 연구',[
  ['선행연구의 역할','사진 등록·소유 관계 추적·\n전후 비교 등 기존 접근을 참고'],
  ['본 연구의 초점','사건 선별 → 의미 추론 →\n보관 관리 이력까지 연결'],
  ['검증할 내용','같은 영상의 비교 실험으로\n설계의 효과와 부담을 확인']]],
];
const p=Presentation.create({slideSize:{width:1280,height:960}});
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const imageHashes=[];
function text(s,value,x,y,w,h,fontSize,bold=false,color='#263D4B'){
 const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 t.text=value;t.text.style={typeface:'Malgun Gothic',fontSize,bold,color,lineSpacing:1.12,autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0}};return t;
}
for(let i=0;i<4;i++){
 const s=p.slides.add();s.background.fill='#FFFFFF';
 const bytes=await fs.readFile(path.join(HERE,'pdf_pages',`page-${i+1}.png`));
 imageHashes.push(hash(bytes));
 s.images.add({blob:bytes,contentType:'image/png',alt:`전반부 논문 PDF ${i+1}쪽 전체`,fit:'contain',position:{left:28,top:18,width:652,height:924}});
 s.shapes.add({geometry:'rect',position:{left:708,top:70,width:1,height:814},fill:'#D7E0E5',line:{fill:'none',width:0}});
 text(s,'Re:Found',756,94,450,32,22,false,'#637986');
 text(s,data[i][0],752,145,460,75,43,true);
 for(let j=0;j<3;j++){
   text(s,data[i][1][j][0],756,278+j*178,450,45,29,true,'#166A75');
   text(s,data[i][1][j][1],756,330+j*178,452,116,27,false);
 }
 text(s,`${i+1} / 4`,756,884,450,30,20,false,'#637986');
 s.speakerNotes.textFrame.setText(`출처: RESEARCH_FRONT_MATTER.pdf ${i+1}쪽. 관련 연구의 번호와 서지는 원고의 참고문헌 [1]–[8]을 따른다.`);
}
await fs.mkdir(TMP,{recursive:true});
const candidatePath=path.join(TMP,'candidate.pptx');
await(await PresentationFile.exportPptx(p)).save(candidatePath);
await finalizePresentation({workspaceDir:ROOT,candidatePath,finalPath:OUT,
 pythonExecutable:path.join(RUNTIME,'dependencies/python/python.exe'),
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,9144000','--validate-heading-fit'],
 explicitTotalSlideCount:4,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],
 fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,
 receiptPath:path.join(TMP,'validation.json')});
const result=await PresentationFile.importPptx(await FileBlob.load(OUT));
for(let i=0;i<4;i++){
 const png=await result.export({slide:result.slides.items[i],format:'png',scale:1.25});
 await fs.writeFile(path.join(TMP,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const source=await fs.readFile(path.join(ROOT,'output/pdf/RESEARCH_FRONT_MATTER.pdf'));
await fs.writeFile(path.join(HERE,'PDF_CAPTURE_SLIDES_CHECK.json'),JSON.stringify({slides:4,pdfPages:4,layout:'4:3; full PDF page on left, three brief explanations on right',pdfSha256:hash(source),pngSha256:imageHashes,pdfPageImageEditable:false,explanationsEditable:true,final:OUT},null,2));
console.log(JSON.stringify({final:OUT,slides:4}));
