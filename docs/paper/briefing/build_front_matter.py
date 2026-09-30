"""Build the four-page research briefing from its editable Markdown source."""
from pathlib import Path
import html
import json
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = HERE / 'RESEARCH_FRONT_MATTER.md'
DEST = OUT / 'RESEARCH_FRONT_MATTER.pdf'
text = SOURCE.read_text(encoding='utf-8')
pages = text.split('<!-- PAGEBREAK -->')
assert len(pages) == 4

pdfmetrics.registerFont(TTFont('Korean', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoreanBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='KoreanBold', italic='Korean', boldItalic='KoreanBold')

styles = {
    'body': ParagraphStyle('body', fontName='Korean', fontSize=10.2, leading=16.1,
                           alignment=TA_JUSTIFY, wordWrap='CJK', spaceAfter=7, firstLineIndent=10.2),
    'title': ParagraphStyle('title', fontName='KoreanBold', fontSize=16, leading=24,
                            alignment=TA_CENTER, wordWrap='CJK', spaceAfter=12),
    'en_title': ParagraphStyle('en_title', fontName='Korean', fontSize=10.3, leading=15.5,
                               alignment=TA_CENTER, spaceAfter=17),
    'h2': ParagraphStyle('h2', fontName='KoreanBold', fontSize=12.6, leading=18,
                         spaceBefore=10, spaceAfter=9, keepWithNext=True),
    'h3': ParagraphStyle('h3', fontName='KoreanBold', fontSize=10.8, leading=16.5,
                         spaceBefore=7, spaceAfter=7, keepWithNext=True),
    'abstract': ParagraphStyle('abstract', fontName='Korean', fontSize=9.8, leading=15.7,
                               alignment=TA_JUSTIFY, wordWrap='CJK', spaceAfter=8),
    'en_abstract': ParagraphStyle('en_abstract', fontName='Korean', fontSize=9.2, leading=14.9,
                                  alignment=TA_JUSTIFY, spaceAfter=8),
    'keywords': ParagraphStyle('keywords', fontName='Korean', fontSize=8.3, leading=12.5,
                               wordWrap='CJK', spaceAfter=9),
    'caption': ParagraphStyle('caption', fontName='KoreanBold', fontSize=8.5, leading=12,
                              wordWrap='CJK', spaceBefore=3, spaceAfter=3, keepWithNext=True),
    'table': ParagraphStyle('table', fontName='Korean', fontSize=8.15, leading=12.3,
                            wordWrap='CJK'),
    'reference': ParagraphStyle('reference', fontName='Korean', fontSize=7.8, leading=10.8,
                                wordWrap='CJK', spaceAfter=5, leftIndent=15, firstLineIndent=-15),
    'compact': ParagraphStyle('compact', fontName='Korean', fontSize=9.1, leading=14,
                              alignment=TA_JUSTIFY, wordWrap='CJK', spaceAfter=6, firstLineIndent=9.1),
}

def paragraph(value, style):
    return Paragraph(escape(value), styles[style])

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Korean', 8)
    canvas.setFillColor(colors.HexColor('#555555'))
    canvas.drawCentredString(A4[0]/2, 12*mm, str(doc.page))
    canvas.restoreState()

story = []
reference_mode = False
for page_index, content in enumerate(pages):
    if page_index:
        story.append(PageBreak())
    blocks = content.strip().split('\n\n')
    english_abstract = False
    for block_index, block in enumerate(blocks):
        block = block.strip()
        if block.startswith('# '):
            # Break the long Korean title at semantic boundaries.
            title = block[2:].replace('사건 기반 장면 변화 감지와 ', '사건 기반 장면 변화 감지와<br/>')
            story.append(Paragraph(title, styles['title']))
        elif page_index == 0 and block_index == 1:
            story.append(paragraph(block, 'en_title'))
        elif block.startswith('## '):
            label = block[3:]
            reference_mode = label == '참고문헌'
            english_abstract = label == 'Abstract'
            story.append(paragraph(label, 'h2'))
        elif block.startswith('### '):
            story.append(paragraph(block[4:], 'h3'))
        elif block.startswith('주제어:') or block.startswith('Keywords:'):
            story.append(paragraph(block, 'keywords'))
        elif block.startswith('표 1.'):
            for line in block.splitlines():
                story.append(paragraph(line, 'caption'))
        elif block.startswith('|'):
            rows = [[c.strip() for c in line.strip('|').split('|')] for line in block.splitlines()]
            rows = [row for row in rows if not all(re.fullmatch(r'[-:]+', c) for c in row)]
            cells = [[paragraph(c, 'table') for c in row] for row in rows]
            table = Table(cells, colWidths=[38*mm, 64*mm, 68*mm], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0),(-1,0), colors.HexColor('#EAEAEA')),
                ('GRID', (0,0),(-1,-1), 0.45, colors.HexColor('#D9D9D9')),
                ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0),(-1,-1), 7), ('RIGHTPADDING', (0,0),(-1,-1), 7),
                ('TOPPADDING', (0,0),(-1,-1), 6), ('BOTTOMPADDING', (0,0),(-1,-1), 6),
            ]))
            story.extend([table, Spacer(1,9)])
        elif reference_mode:
            match = re.search(r'\s+(https?://\S+)\s*$',block)
            if match:
                # Preserve a clickable primary/DOI link without a long printed URL.
                body, url = block[:match.start()], match.group(1)
                story.append(Paragraph(f'<link href="{escape(url)}" color="#000000">{escape(body)}</link>',styles['reference']))
            else:
                story.append(paragraph(block, 'reference'))
        elif page_index == 0:
            story.append(paragraph(block, 'en_abstract' if english_abstract else 'abstract'))
        else:
            story.append(paragraph(block, 'compact' if page_index == 3 else 'body'))

doc = SimpleDocTemplate(str(DEST), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                         topMargin=18*mm, bottomMargin=18*mm,
                         title=text.splitlines()[0][2:], author='', subject='연구방법 이전 논문 원고')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
reader = PdfReader(DEST)
page_texts = [page.extract_text() or '' for page in reader.pages]
body = text.split('## 참고문헌')[0]
citations = list(dict.fromkeys(re.findall(r'\[(\d+)\]', body)))
references = re.findall(r'^\[(\d+)\]',text.split('## 참고문헌')[1],re.M)
ko_abstract = pages[0].split('## 요약')[1].split('주제어:')[0].strip()
en_abstract = pages[0].split('## Abstract')[1].split('Keywords:')[0].strip()
report = {
    'page_count': len(reader.pages),
    'page_text_characters': [len(x) for x in page_texts],
    'first_citation_order': citations, 'references': references,
    'korean_abstract_characters_without_spaces':len(re.sub(r'\s','',ko_abstract)),
    'english_abstract_words':len(en_abstract.split()),
    'has_placeholders':bool(re.search(r'\[\[.*?\]\]',text)),
    'pdf':str(DEST),
}
print(json.dumps(report,ensure_ascii=False,indent=2))
assert len(reader.pages) == 4, 'Adjust layout to restore the four-page budget.'
assert citations == references == list(map(str,range(1,9)))
assert not report['has_placeholders']
for i, heading in enumerate(['요약','1. 서론','2. 이론적 배경','2-4 관련 연구']):
    assert heading in page_texts[i], (i, heading)

notes = [
    ('연구 주제', '저사양 장치가 상태 변화를 먼저 찾고, 필요한 사건의 의미만 외부 AI에 묻는 시스템입니다.',
     [('사건 기반', '영상 한 장마다 물품명을 묻기보다, 추가·이동·제거가 일어난 시점을 처리 단위로 삼습니다.'),
      ('선택적 추론', '신규 물품과 모호한 제거에만 전후 증거를 전송합니다.'),
      ('현재 단계', '시스템 구현은 되어 있습니다. 정확도와 비용 등의 정량 평가는 앞으로 수행합니다.')]),
    ('연구가 필요한 이유', '보관대에서는 물품의 이름만큼, 언제 들어오고 이동하고 사라졌는지를 기록하는 일이 중요합니다.',
     [('구체적인 문제', '같은 물건을 옮겼는데 새 물품으로 등록하거나, 조명이 바뀌었는데 물건이 생겼다고 판단하면 안 됩니다.'),
      ('연구 범위', '보관대 물품의 상태를 관리합니다. 소유자를 추적하거나 실제 인계를 증명하는 연구는 아닙니다.'),
      ('설명할 흐름', '업무의 필요 → 기존 접근 → 영상 차이의 어려움 → 연구 목적 순서로 읽으면 됩니다.')]),
    ('세 가지 배경 개념', '변화 감지는 무엇이 달라졌는지, 엣지는 어디서 처리할지, 멀티모달 추론은 그 변화가 무엇을 뜻하는지와 연결됩니다.',
     [('안정 장면', '손이 물건을 놓는 중간 모습과 손이 빠진 뒤의 최종 배치를 구분합니다.'),
      ('엣지 컴퓨팅', '카메라 가까운 Raspberry Pi에서 기초 분석을 수행합니다.'),
      ('시각 증거', '전체 장면은 위치와 맥락을, 확대 영역은 물품의 특징을 제공할 수 있습니다. 네 장의 우수성은 아직 실험할 내용입니다.')]),
    ('기존 연구와의 관계', '관련 연구의 정확도 순위를 만드는 표가 아닙니다. 각 연구가 풀려는 문제와 우리의 초점을 비교합니다.',
     [('가까운 선행연구', '차량의 전후 이미지를 비교한 연구와 입력을 먼저 선별하는 영상 분석 연구가 중요한 출발점입니다.'),
      ('우리 연구의 초점', '로컬 사건 선별, 외부 의미 추론, 보관 관리 기록을 하나의 과정으로 연결합니다.'),
      ('다음 본론으로 연결', '구체적인 알고리즘과 실험 설계는 이번 범위 이후의 연구방법에서 설명합니다.')]),
]
notes_json = json.dumps(notes,ensure_ascii=False).replace('</','<\\/')
viewer = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Re:Found 논문 원고 보기</title><style>
*{box-sizing:border-box}body{margin:0;background:#f0f1f3;color:#202124;font-family:"Malgun Gothic",sans-serif}
header{padding:17px 24px;background:white;border-bottom:1px solid #d5d7da;display:flex;gap:22px;align-items:center;flex-wrap:wrap}
header strong{font-size:17px}nav{display:flex;gap:7px}button,a{font:inherit}button{border:1px solid #b8bdc5;background:white;color:#202124;padding:7px 12px;border-radius:5px;cursor:pointer}
button[aria-pressed="true"]{background:#253950;color:white;border-color:#253950}a{color:#284d79}main{display:grid;grid-template-columns:minmax(560px,1fr) 310px;gap:22px;padding:20px 24px;height:calc(100vh - 78px)}
iframe{width:100%;height:100%;background:white;border:1px solid #d5d7da}aside{background:white;padding:24px;overflow:auto}aside h1{font-size:20px;line-height:1.5;margin:0 0 16px}aside p{font-size:14px;line-height:1.9;margin:0 0 22px}aside h2{font-size:14px;margin:24px 0 6px}small{display:block;color:#616775;line-height:1.8;font-size:12px;margin-top:30px}.links{margin-left:auto;font-size:13px;display:flex;gap:15px}
@media(max-width:950px){main{grid-template-columns:1fr;height:auto}iframe{height:80vh}aside{min-height:300px}}@media print{header,aside{display:none}main{display:block;padding:0}}
</style><header><strong>Re:Found 논문 원고</strong><nav aria-label="원고 페이지">NAV</nav><div class="links"><a href="../../../output/pdf/RESEARCH_FRONT_MATTER.pdf" target="_blank">PDF 열기</a><a href="RESEARCH_FRONT_MATTER.md">편집용 원문</a></div></header>
<main><iframe id="paper" title="논문 원고 PDF" src="../../../output/pdf/RESEARCH_FRONT_MATTER.pdf#page=1&view=FitH"></iframe><aside id="note"></aside></main>
<script>const notes=NOTES;function show(i){const n=notes[i];document.getElementById('paper').src='../../../output/pdf/RESEARCH_FRONT_MATTER.pdf#page='+(i+1)+'&view=FitH';const aside=document.getElementById('note');aside.replaceChildren();function add(tag,txt){const e=document.createElement(tag);e.textContent=txt;aside.appendChild(e)}add('h1',n[0]);add('p',n[1]);n[2].forEach(x=>{add('h2',x[0]);add('p',x[1])});add('small','오른쪽은 이해를 돕는 설명입니다. 제출·공유용 원고는 왼쪽의 4쪽 PDF를 사용하세요.');document.querySelectorAll('button').forEach((b,j)=>b.setAttribute('aria-pressed',i===j?'true':'false'))}document.querySelectorAll('button').forEach((b,i)=>b.addEventListener('click',()=>show(i)));show(0)</script></html>'''
viewer = viewer.replace('NAV',''.join(f'<button aria-pressed="false">{i+1}쪽 {label}</button>' for i,label in enumerate(['요약','서론','배경','관련 연구'])))
viewer = viewer.replace('NOTES',notes_json)
(HERE/'RESEARCH_FRONT_MATTER_VIEW.html').write_text(viewer,encoding='utf-8')
(HERE/'BUILD_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
