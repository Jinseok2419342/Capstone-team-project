"""Build a readable editorial PDF and four vector schematics from the paper source."""
from pathlib import Path
import re
import json
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderSVG
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=HERE.parent/'PAPER_DRAFT_JDCS.md'
OUT=ROOT/'output/pdf/REFOUND_FULL_MANUSCRIPT.pdf'
FIG=HERE/'figures'
FIG.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('Korean','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoreanBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFont(TTFont('Equation','C:/Windows/Fonts/cambria.ttc',subfontIndex=0))
pdfmetrics.registerFontFamily('Korean',normal='Korean',bold='KoreanBold',italic='Korean',boldItalic='KoreanBold')
INK=colors.HexColor('#243746'); MUTED=colors.HexColor('#5A6671'); LIGHT=colors.HexColor('#F0F4F6')
WIDTH=A4[0]-40*mm

def box(d,x,y,w,h,lines,accent=False,size=9):
    d.add(Rect(x,y,w,h,rx=2,ry=2,fillColor=INK if accent else LIGHT,strokeColor=colors.HexColor('#AEBBC4'),strokeWidth=.6))
    if isinstance(lines,str):lines=lines.split('\n')
    for i,line in enumerate(lines):
        d.add(String(x+w/2,y+h/2+(len(lines)-1)*6-i*12,line,fontName='KoreanBold' if i==0 else 'Korean',fontSize=size,textAnchor='middle',fillColor=colors.white if accent else INK))

def arrow(d,x1,y1,x2,y2):
    d.add(Line(x1,y1,x2,y2,strokeColor=MUTED,strokeWidth=.85))
    import math
    a=math.atan2(y2-y1,x2-x1);z=4
    pts=[x2,y2,x2-z*math.cos(a-.5),y2-z*math.sin(a-.5),x2-z*math.cos(a+.5),y2-z*math.sin(a+.5)]
    d.add(Polygon(pts,fillColor=MUTED,strokeColor=MUTED))

def label(d,x,y,txt,size=8):
    d.add(String(x,y,txt,fontName='Korean',fontSize=size,fillColor=MUTED,textAnchor='middle'))

def make_figures():
    figs={}
    d=Drawing(WIDTH,204)
    box(d,0,131,105,49,['CSI 카메라','Picamera2 입력'])
    box(d,140,131,166,49,['Raspberry Pi 4 · 2GB','움직임 감시 → 안정 장면','정합 · 보정 · 물품 대응'],True)
    box(d,342,131,140,49,['사건 callback','added / moved','removed / verify_removed'])
    arrow(d,105,155,140,155);arrow(d,306,155,342,155)
    box(d,342,28,140,55,['FastAPI · SQLite WAL','임시 등록 / 상태 / 이력','관리자 웹 화면'])
    arrow(d,412,131,412,83)
    box(d,140,28,166,55,['외부 시각언어모델','전체 장면 전후 + crop 전후','선택된 사건만 · 최대 4장'])
    arrow(d,342,63,306,63);arrow(d,306,41,342,41)
    label(d,239,9,'로컬 moved·removed는 외부 호출 없이 처리',8)
    figs[1]=d
    d=Drawing(WIDTH,168)
    labels=[['calibrating','카메라 준비'],['monitoring','움직임 감시'],['settling','마지막 움직임 후 대기'],['stabilizing','연속 안정 확인'],['analyzing','전후 장면 분석']]
    for i,l in enumerate(labels):box(d,i*99,82,86,52,l,i==4,7.8)
    for i in range(4):arrow(d,i*99+86,108,(i+1)*99,108)
    label(d,241,148,'일반 프레임 카메라의 처리 상태 전이',8)
    d.add(Line(439,82,439,30,strokeColor=MUTED,strokeWidth=.85));d.add(Line(439,30,142,30,strokeColor=MUTED,strokeWidth=.85));arrow(d,142,30,142,82)
    label(d,297,15,'분석 후 기준 갱신 → 감시 복귀 → callback 전달',8)
    label(d,288,61,'움직임 재발 시 안정 확인을 초기화',8)
    figs[2]=d
    d=Drawing(WIDTH,236)
    box(d,0,176,142,44,['안정 전후 영상','기준 B / 현재 I'])
    box(d,170,176,142,44,['기하 정합','부분 affine / 제한적 대체'])
    box(d,340,176,142,44,['휘도·색차 구성','전역·국소 조명 보정'])
    arrow(d,142,198,170,198);arrow(d,312,198,340,198)
    box(d,340,91,142,49,['경계·그림자 억제','형태학 처리 / 후보 병합'])
    box(d,170,91,142,49,['전역 변화 검사','광범위 변화는 사건 억제'])
    box(d,0,91,142,49,['활성 물품 대응','bbox + 물품·빈 배경 crop'])
    arrow(d,411,176,411,140);arrow(d,340,115,312,115);arrow(d,170,115,142,115)
    box(d,0,10,482,42,['사건 판정','added / moved / removed / verify_removed'],True)
    arrow(d,71,91,71,52)
    figs[3]=d
    d=Drawing(WIDTH,263)
    box(d,0,202,225,45,['added · callback 정상 접수','DB 저장 실패 시 오류 처리'],True)
    box(d,257,202,225,45,['verify_removed','기존 물품 유지 · 추적 signature 보관'],True)
    box(d,0,123,225,48,['임시 행 저장 성공','crop 저장 / provider=pending'])
    box(d,257,123,225,48,['선택적 VLM 요청','기존 물품의 제거 여부 검증'])
    arrow(d,112,202,112,171);arrow(d,369,202,369,171)
    box(d,0,34,225,53,['선택적 VLM 후 상태 확인','신뢰 결과: 정보 갱신 / 필요 시 취소','실패·불확실: 생성된 임시 행 보존'],False,8.4)
    box(d,257,34,225,53,['현재 signature 재검사','일치 + 신뢰 제거: recovered','불확실·오래된 응답: 상태 유지'],False,8.4)
    arrow(d,112,123,112,87);arrow(d,369,123,369,87)
    label(d,241,11,'임시 저장 이전 callback queue drop은 별도의 실패 경로',8)
    figs[4]=d
    for n,f in figs.items():
        renderSVG.drawToFile(f,str(FIG/f'figure-{n}.svg'))
        svg=(FIG/f'figure-{n}.svg').read_text(encoding='utf-8')
        svg=svg.replace("font-family: 'KoreanBold'","font-family: 'Malgun Gothic'; font-weight: bold").replace("font-family: 'Korean'","font-family: 'Malgun Gothic'")
        svg=svg.replace('font-family="KoreanBold"','font-family="Malgun Gothic" font-weight="bold"').replace('font-family="Korean"','font-family="Malgun Gothic"')
        svg=svg.replace('font-family: KoreanBold;', 'font-family: Malgun Gothic; font-weight: bold;').replace('font-family: Korean;', 'font-family: Malgun Gothic;')
        (FIG/f'figure-{n}.svg').write_text(svg,encoding='utf-8')
    return figs

ST={
 'title':ParagraphStyle('title',fontName='KoreanBold',fontSize=16,leading=24,alignment=TA_CENTER,wordWrap='CJK',spaceAfter=12),
 'en_title':ParagraphStyle('en_title',fontName='Korean',fontSize=10,leading=15,alignment=TA_CENTER,spaceAfter=12),
 'body':ParagraphStyle('body',fontName='Korean',fontSize=9.3,leading=14.5,wordWrap='CJK',alignment=TA_JUSTIFY,firstLineIndent=9.3,spaceAfter=7),
 'h1':ParagraphStyle('h1',fontName='KoreanBold',fontSize=13,leading=20,wordWrap='CJK',spaceBefore=13,spaceAfter=8,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='KoreanBold',fontSize=10.7,leading=16,wordWrap='CJK',spaceBefore=9,spaceAfter=6,keepWithNext=True),
 'note':ParagraphStyle('note',fontName='Korean',fontSize=8,leading=12,wordWrap='CJK',textColor=MUTED,spaceAfter=8),
 'caption':ParagraphStyle('caption',fontName='KoreanBold',fontSize=8.3,leading=12.3,wordWrap='CJK',spaceAfter=6,spaceBefore=5,keepWithNext=True),
 'figcaption':ParagraphStyle('figcaption',fontName='Korean',fontSize=8.3,leading=12,wordWrap='CJK',spaceAfter=10,alignment=TA_CENTER),
 'table':ParagraphStyle('table',fontName='Korean',fontSize=7.5,leading=11.2,wordWrap='CJK'),
 'ref':ParagraphStyle('ref',fontName='Korean',fontSize=8,leading=12,wordWrap='CJK',spaceAfter=6,leftIndent=18,firstLineIndent=-18),
 'eq':ParagraphStyle('eq',fontName='Equation',fontSize=10.5,leading=18,alignment=TA_CENTER,spaceBefore=6,spaceAfter=10),
 'list':ParagraphStyle('list',fontName='Korean',fontSize=9.1,leading=14,wordWrap='CJK',spaceAfter=5,leftIndent=13,firstLineIndent=-10),
}

def markup(s,short=True):
    s=re.sub(r'\[\[[^\]]+\]\]','[입력 대기]' if short else lambda m:m[0],s)
    math_items=[]
    def math_token(m):
        q=m[1].replace('\\hat I_t','Î_t').replace('\\leftarrow','←').replace('\\ell','ℓ').replace('\\tau','τ').replace('\\kappa','κ').replace('^{*}','*')
        q=q.replace('L_{Î_t}', 'L<sub>Î<sub>t</sub></sub>').replace('L_B','L<sub>B</sub>')
        q=re.sub(r'([A-Za-zÎ])_\{([^{}]+)\}',r'\1<sub>\2</sub>',q)
        q=re.sub(r"([A-Za-zÎ]')_([a-z])",r'\1<sub>\2</sub>',q)
        q=re.sub(r'([A-Za-zÎ])_([a-z])',r'\1<sub>\2</sub>',q)
        math_items.append('<font name="Equation">'+q+'</font>')
        return f'MATHITEM{len(math_items)-1}TOKEN'
    s=re.sub(r'\\\((.*?)\\\)',math_token,s)
    s=s.replace('\\(','').replace('\\)','').replace('\\leftarrow','←')
    s=s.replace('\\hat I_t','Î_t').replace('\\Delta','Δ').replace('\\tau','τ').replace('\\ell','ℓ')
    s=s.replace('\\(N\\)','N').replace('\\','')
    s=s.replace('^{*}','*')
    s=escape(s)
    s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'\1',s)
    # Only mathematical identifiers, not code names or profile names.
    s=re.sub(r'\b([BIDLTp])_\{?(stream|pair|vlm|fault|g|p|t)\}?',r'\1<sub>\2</sub>',s)
    for i,q in enumerate(math_items):s=s.replace(f'MATHITEM{i}TOKEN',q)
    return s

def p(s,style='body'):return Paragraph(markup(s),ST[style])

EQ={
1:'F* = arg max<sub>F</sub> Σ<sub>i</sub> 1(||p′<sub>i</sub> − Fp<sub>i</sub>|| ≤ τ)<br/>T* = (F*)<super>−1</super>,　Î<sub>t</sub> = W(I<sub>t</sub>, T*)　　(1)',
2:'D<sub>L</sub>(x) = min(|s(x) − m − ℓ(x)|, |s(x) − m|)　　(2)',
3:'D(x) = max(D<sub>L</sub>(x), |Δa(x)|, |Δb(x)|)　　(3)',
4:'IoU(B<sub>g</sub>, B<sub>p</sub>) = |B<sub>g</sub> ∩ B<sub>p</sub>| / |B<sub>g</sub> ∪ B<sub>p</sub>|　　(4)',
5:'P = TP / (TP + FP),　R = TP / (TP + FN)<br/>F1 = 2TP / (2TP + FP + FN)　　(5)',
6:'False events/hour = N<sub>FP,none</sub> / T<sub>eligible,h</sub>　　(6)',
}

def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#D8DFE4'));canvas.line(20*mm,17*mm,A4[0]-20*mm,17*mm)
    canvas.setFont('Korean',7.2);canvas.setFillColor(MUTED)
    canvas.drawString(20*mm,12*mm,'Re:Found · 실측 전 연구 원고 · 2026-09-16')
    canvas.drawRightString(A4[0]-20*mm,12*mm,str(doc.page));canvas.restoreState()

def build():
    figs=make_figures();text=SOURCE.read_text(encoding='utf-8');blocks=text.split('\n\n');story=[];ref=False;i=0
    while i<len(blocks):
        b=blocks[i].strip();i+=1
        if not b:continue
        if b.startswith('![그림'):
            n=int(re.search(r'figure-(\d)',b)[1]);cap=blocks[i].strip();i+=1
            story.append(KeepTogether([Spacer(1,5),figs[n],p(cap,'figcaption')]))
        elif b.startswith('\\['):
            n=int(re.search(r'\\tag\{(\d+)\}',b)[1]);story.append(KeepTogether([Paragraph(EQ[n],ST['eq'])]))
        elif b.startswith('# '):
            label=b[2:]
            if '저사양' in label:story.append(Paragraph(markup(label).replace('감지와 ','감지와<br/>'),ST['title']))
            else:
                if label.startswith('1. 서론'):story.append(PageBreak())
                if label=='참고문헌':ref=True
                story.append(p(label,'h1'))
        elif b.startswith('## '):story.append(p(b[3:],'h2'))
        elif b.startswith('An Event-'):story.append(p(b,'en_title'))
        elif b.startswith('> '):story.append(p(b[2:],'note'))
        elif b.startswith('**표 ') or b.startswith('**알고리즘 '):story.append(p(b,'caption'))
        elif b.startswith('|'):
            rows=[[x.strip() for x in l.strip('|').split('|')] for l in b.splitlines()]
            rows=[r for r in rows if not all(re.fullmatch('[-:]+',c) for c in r)]
            count=len(rows[0]);ratios={2:[.40,.60],3:[.24,.38,.38],4:[.19,.33,.24,.24],5:[.24,.19,.19,.19,.19],6:[.22,.12,.16,.17,.17,.16],7:[.22,.15,.12,.13,.13,.12,.13]}[count]
            cells=[[p(c,'table') for c in row] for row in rows]
            table=Table(cells,colWidths=[WIDTH*r for r in ratios],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('TEXTCOLOR',(0,0),(-1,0),INK),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#CAD3D9')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.extend([table,Spacer(1,9)])
        elif ref:
            m=re.search(r'\s+(https?://\S+)',b)
            if m:
                rendered=f'<link href="{escape(m[1])}" color="#243746">{escape(b[:m.start()])}</link>'
                if '[Online]' in b:
                    rendered=escape(b[:m.start()])+f'<br/><link href="{escape(m[1])}" color="#243746">{escape(m[1])}</link>'
                # Retain access dates after URLs for documentation references.
                tail=b[m.end():].strip()
                if tail:rendered+=' '+escape(tail)
                story.append(Paragraph(rendered,ST['ref']))
            else:story.append(p(b,'ref'))
        elif re.match(r'^(\d+\. |- )',b):
            for line in b.splitlines():story.append(p(line,'list'))
        elif b.startswith('주제어:') or b.startswith('Keywords:'):story.append(p(b,'note'))
        else:story.append(p(b))
    doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=18*mm,bottomMargin=22*mm,title=text.splitlines()[0][2:],author='',subject='실측 전 전체 논문 편집 원고')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(OUT);texts=[x.extract_text() for x in reader.pages]
    report={'pages':len(texts),'page_text_characters':[len(x) for x in texts],'figures':4,'equations':6,'references':17,'tables':13,'pdf':str(OUT),'rendering':'single-column editorial reading copy; not final JDCS HWP layout','unmeasured_display':'[입력 대기]'}
    assert all(len(x)>50 for x in texts)
    assert '[[' not in '\n'.join(texts)
    (HERE/'PDF_BUILD_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    import sys
    if '--figures-only' in sys.argv:make_figures()
    else:build()
