"""Build a JDCS-like two-column review PDF and the column-width schematics.

The official submission is the JDCS HWP template (A4, two columns, 9.1 pt
body).  This PDF approximates that layout so the page count can be checked
before moving the text into HWP; it is not the HWP file itself.
"""
from pathlib import Path
import json
import math
import re
import sys
from xml.sax.saxutils import escape

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / 'PAPER_DRAFT_JDCS.md'
OUT = ROOT / 'output/paper/REFOUND_FULL_MANUSCRIPT.pdf'
FIG = HERE / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

# JDCS template: A4, top/bottom 13 mm + 12 mm header/footer, left/right 20 mm,
# 8 mm column gap, 9.1 pt body.  Line pitch approximates HWP 160 %.
MARGIN_X = 20 * mm
MARGIN_Y = 25 * mm
GAP = 8 * mm
BODY_PT = 9.1
LEADING = 14.5
FULL_W = A4[0] - 2 * MARGIN_X
COL_W = (FULL_W - GAP) / 2
BODY_H = A4[1] - 2 * MARGIN_Y


def _register_fonts():
    candidates = [
        ('C:/Windows/Fonts/batang.ttc', 'C:/Windows/Fonts/malgunbd.ttf', 0),
        ('C:/Windows/Fonts/malgun.ttf', 'C:/Windows/Fonts/malgunbd.ttf', None),
        ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 0),
    ]
    for regular, bold, index in candidates:
        if Path(regular).exists() and Path(bold).exists():
            kwargs = {'subfontIndex': index} if index is not None else {}
            pdfmetrics.registerFont(TTFont('Korean', regular, **kwargs))
            bold_kwargs = {'subfontIndex': 0} if bold.endswith('.ttc') else {}
            pdfmetrics.registerFont(TTFont('KoreanBold', bold, **bold_kwargs))
            break
    else:
        raise SystemExit('Korean font not found (Batang/Malgun Gothic or WenQuanYi Zen Hei)')
    for path, kwargs in (('C:/Windows/Fonts/cambria.ttc', {'subfontIndex': 0}),
                         ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', {})):
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont('Equation', path, **kwargs))
            break
    else:
        pdfmetrics.registerFont(TTFont('Equation', regular, **kwargs))
    pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='KoreanBold', italic='Korean', boldItalic='KoreanBold')


_register_fonts()
INK = colors.HexColor('#243746')
MUTED = colors.HexColor('#5A6671')
LIGHT = colors.HexColor('#F0F4F6')
EDGE = colors.HexColor('#AEBBC4')


def box(d, x, y, w, h, lines, accent=False, size=7.2):
    d.add(Rect(x, y, w, h, rx=2, ry=2, fillColor=INK if accent else LIGHT, strokeColor=EDGE, strokeWidth=.6))
    if isinstance(lines, str):
        lines = lines.split('\n')
    pitch = size + 2.6
    for i, line in enumerate(lines):
        d.add(String(x + w / 2, y + h / 2 + (len(lines) - 1) * pitch / 2 - i * pitch - size * .35, line,
                     fontName='KoreanBold' if i == 0 else 'Korean', fontSize=size, textAnchor='middle',
                     fillColor=colors.white if accent else INK))


def arrow(d, x1, y1, x2, y2):
    d.add(Line(x1, y1, x2, y2, strokeColor=MUTED, strokeWidth=.8))
    a = math.atan2(y2 - y1, x2 - x1)
    z = 3.6
    d.add(Polygon([x2, y2, x2 - z * math.cos(a - .5), y2 - z * math.sin(a - .5),
                   x2 - z * math.cos(a + .5), y2 - z * math.sin(a + .5)], fillColor=MUTED, strokeColor=MUTED))


def label(d, x, y, txt, size=6.6):
    d.add(String(x, y, txt, fontName='Korean', fontSize=size, fillColor=MUTED, textAnchor='middle'))


def make_figures():
    w = COL_W
    figs = {}

    d = Drawing(w, 214)
    box(d, 30, 184, w - 60, 26, ['CSI 카메라', 'Picamera2 영상 입력'])
    arrow(d, w / 2, 184, w / 2, 170)
    box(d, 0, 122, w, 48, ['Raspberry Pi 4 (2GB)', '안정 장면 확인 → 영상 정합·조명 보정', '기존 물품 대응 → 사건 판정'], True)
    arrow(d, w * .25, 122, w * .25, 106)
    arrow(d, w * .75, 122, w * .75, 106)
    box(d, 0, 66, w * .47, 40, ['이동 · 제거', '장치에서 처리', '외부 호출 없음'])
    box(d, w * .53, 66, w * .47, 40, ['등록 · 제거 검증', '외부 시각언어모델', '전후 이미지 최대 4장'])
    arrow(d, w * .25, 66, w * .25, 50)
    arrow(d, w * .75, 66, w * .75, 50)
    box(d, 0, 6, w, 44, ['FastAPI · SQLite WAL', '임시 등록 · 보관 기한 · 처리 이력', '관리자 웹 화면 · 알림'])
    figs[1] = d

    d = Drawing(w, 132)
    bw, bh = 64, 32  # figure 3: state machine
    xs = (0, (w - bw) / 2, w - bw)
    top, low = 82, 26
    box(d, xs[0], top, bw, bh, ['카메라 준비', '기준 장면 설정'])
    box(d, xs[1], top, bw, bh, ['감시', '움직임·누적 변화'])
    box(d, xs[2], top, bw, bh, ['대기', '마지막 움직임 후 3.0 s'])
    box(d, xs[2], low, bw, bh, ['안정 확인', '1.2 s 무동작'])
    box(d, xs[1], low, bw, bh, ['분석', '전후 장면 비교'], True)
    arrow(d, xs[0] + bw, top + bh / 2, xs[1], top + bh / 2)
    arrow(d, xs[1] + bw, top + bh / 2, xs[2], top + bh / 2)
    arrow(d, xs[2] + bw / 2, top, xs[2] + bw / 2, low + bh)
    arrow(d, xs[2], low + bh / 2, xs[1] + bw, low + bh / 2)
    arrow(d, xs[1] + bw / 2, low + bh, xs[1] + bw / 2, top)
    label(d, xs[0] + bw / 2, low + bh / 2 + 3, 'DB 반영 확인 후')
    label(d, xs[0] + bw / 2, low + bh / 2 - 6, '기준 갱신 → 감시')
    label(d, w / 2, 8, '안정 확인 중 움직임이 생기면 대기로 돌아간다')
    figs[3] = d

    steps = [
        (['안정 전후 영상', '기준 영상 B / 현재 영상 I'], False),
        (['기하 정합', '광류 추적 + RANSAC 부분 아핀'], False),
        (['차이 영상 구성', '노출·국소 조명 보정, Lab 색차'], False),
        (['후보 정리', '공통 경계·그림자 억제, 형태학 연산'], False),
        (['전역 변화 검사', '변화 42% 초과 시 사건 억제'], False),
        (['기존 물품 대응 → 사건 판정', '등록 / 이동 / 제거 / 제거 검증'], True),
    ]
    bh, gap = 26, 9
    height = len(steps) * bh + (len(steps) - 1) * gap + 4
    d = Drawing(w, height)
    for i, (lines, accent) in enumerate(steps):
        y = height - 2 - (i + 1) * bh - i * gap
        box(d, 18, y, w - 36, bh, lines, accent)
        if i:
            arrow(d, w / 2, y + bh + gap, w / 2, y + bh)
    figs[4] = d

    for n, f in figs.items():
        target = FIG / f'figure-{n}.svg'
        renderSVG.drawToFile(f, str(target))
        svg = target.read_text(encoding='utf-8')
        svg = svg.replace("font-family: 'KoreanBold'", "font-family: 'Malgun Gothic'; font-weight: bold").replace("font-family: 'Korean'", "font-family: 'Malgun Gothic'")
        svg = svg.replace('font-family="KoreanBold"', 'font-family="Malgun Gothic" font-weight="bold"').replace('font-family="Korean"', 'font-family="Malgun Gothic"')
        svg = svg.replace('font-family: KoreanBold;', 'font-family: Malgun Gothic; font-weight: bold;').replace('font-family: Korean;', 'font-family: Malgun Gothic;')
        target.write_text(svg, encoding='utf-8')
    return figs


def photo_or_placeholder(n, caption_hint):
    path = FIG / f'figure-{n}.png'
    if path.exists():
        image = Image(str(path))
        scale = COL_W / image.imageWidth
        image.drawWidth, image.drawHeight = COL_W, image.imageHeight * scale
        return image, True
    d = Drawing(COL_W, 118)
    d.add(Rect(0, 0, COL_W, 118, fillColor=colors.white, strokeColor=EDGE, strokeWidth=.8, strokeDashArray=[3, 2]))
    label(d, COL_W / 2, 64, f'그림 {n}: 사진 입력 예정', 8)
    label(d, COL_W / 2, 50, caption_hint, 7)
    return d, False


ST = {
    'title': ParagraphStyle('title', fontName='KoreanBold', fontSize=15, leading=21, alignment=TA_CENTER, wordWrap='CJK', spaceAfter=6),
    'en_title': ParagraphStyle('en_title', fontName='KoreanBold', fontSize=10.5, leading=14, alignment=TA_CENTER, spaceAfter=10),
    'abs_head': ParagraphStyle('abs_head', fontName='KoreanBold', fontSize=9, leading=13, spaceBefore=4, spaceAfter=2),
    'abstract': ParagraphStyle('abstract', fontName='Korean', fontSize=8.6, leading=13, wordWrap='CJK', alignment=TA_JUSTIFY, leftIndent=12, rightIndent=12, spaceAfter=3),
    'keywords': ParagraphStyle('keywords', fontName='Korean', fontSize=8.4, leading=12, wordWrap='CJK', leftIndent=12, rightIndent=12, spaceAfter=6),
    'body': ParagraphStyle('body', fontName='Korean', fontSize=BODY_PT, leading=LEADING, wordWrap='CJK', alignment=TA_JUSTIFY, firstLineIndent=BODY_PT, spaceAfter=0),
    'h1': ParagraphStyle('h1', fontName='KoreanBold', fontSize=10.5, leading=15, wordWrap='CJK', spaceBefore=10, spaceAfter=4, keepWithNext=True),
    'h2': ParagraphStyle('h2', fontName='KoreanBold', fontSize=9.4, leading=14, wordWrap='CJK', spaceBefore=6, spaceAfter=2, keepWithNext=True),
    'caption': ParagraphStyle('caption', fontName='KoreanBold', fontSize=8, leading=11, wordWrap='CJK', alignment=TA_CENTER, spaceBefore=6, spaceAfter=3, keepWithNext=True),
    'figcaption': ParagraphStyle('figcaption', fontName='KoreanBold', fontSize=8, leading=11, wordWrap='CJK', alignment=TA_CENTER, spaceBefore=3, spaceAfter=8),
    'table': ParagraphStyle('table', fontName='Korean', fontSize=7.4, leading=10, wordWrap='CJK'),
    'ref': ParagraphStyle('ref', fontName='Korean', fontSize=7.6, leading=10.6, wordWrap='CJK', spaceAfter=3, leftIndent=14, firstLineIndent=-14),
    'eq': ParagraphStyle('eq', fontName='Equation', fontSize=8.6, leading=14, alignment=TA_CENTER, spaceBefore=4, spaceAfter=6),
    'alg': ParagraphStyle('alg', fontName='Korean', fontSize=8, leading=11.2, wordWrap='CJK', leftIndent=11, firstLineIndent=-11),
    'note': ParagraphStyle('note', fontName='Korean', fontSize=7.4, leading=10.5, wordWrap='CJK', textColor=MUTED, alignment=TA_CENTER, spaceAfter=6),
}


def markup(s):
    s = re.sub(r'\[\[[^\]]+\]\]', '[입력 대기]', s)
    s = re.sub(r'\\\((.*?)\\\)', lambda m: m[1], s)
    for src, dst in (('\\hat I_t', 'Î_t'), ('\\ell', 'ℓ'), ('\\tau', 'τ'), ('\\Delta', 'Δ'), ("p'_i", 'p′_i')):
        s = s.replace(src, dst)
    s = s.replace('\\', '')
    s = escape(s)
    s = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'\b(p|p′)_i\b', r'\1<sub>i</sub>', s)
    return s


def p(s, style='body'):
    return Paragraph(markup(s), ST[style])


EQ = {
    1: 'F* = arg max<sub>F</sub> Σ<sub>i</sub> 1(‖p′<sub>i</sub> − Fp<sub>i</sub>‖ ≤ τ)　　(1)',
    2: 'D(x)=max(min(|s(x)−m−ℓ(x)|,|s(x)−m|),|Δa(x)|,|Δb(x)|)　(2)',
}


def table_flowable(block):
    rows = [[x.strip() for x in line.strip().strip('|').split('|')] for line in block.splitlines()]
    rows = [r for r in rows if not all(re.fullmatch(r'[-:]+', c) for c in r)]
    count = len(rows[0])
    def width(text):
        return sum(2 if ord(ch) > 0x1100 else 1 for ch in re.sub(r'<[^>]+>', '', markup(text)))
    weights = [min(40, max(7, max(width(r[i]) for r in rows))) for i in range(count)]
    total = sum(weights)
    widths = [COL_W * w / total for w in weights]
    table = Table([[p(c, 'table') for c in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='CENTER')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, 0), (-1, 0), .5, INK),
        ('LINEBELOW', (0, -1), (-1, -1), .8, INK),
        ('INNERGRID', (0, 1), (-1, -1), .25, colors.HexColor('#CAD3D9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    return table


def reference(b):
    m = re.search(r'\s+(https?://\S+)', b)
    if not m:
        return p(b, 'ref')
    rendered = escape(b[:m.start()]) + f' <link href="{escape(m[1])}" color="#243746">{escape(m[1])}</link>'
    tail = b[m.end():].strip()
    if tail:
        rendered += ' ' + escape(tail)
    return Paragraph(rendered, ST['ref'])


def parse():
    figs = make_figures()
    text = SOURCE.read_text(encoding='utf-8')
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    front, body, photos = [], [], {}
    i, in_front, refs = 0, True, False
    while i < len(blocks):
        b = blocks[i]
        i += 1
        if b.startswith('> '):
            continue  # editorial note, not part of the paper
        if in_front:
            if b.startswith('# ') and '저사양' in b:
                front.append(p(b[2:], 'title'))
            elif b.startswith('An Event-'):
                front.append(p(b, 'en_title'))
            elif b in ('## 요약', '## Abstract'):
                front.append(p(b[3:], 'abs_head'))
            elif b.startswith('주제어:') or b.startswith('Keywords:'):
                front.append(p(b, 'keywords'))
            elif b.startswith('# 1.'):
                in_front = False
                body.append(p(b[2:], 'h1'))
            else:
                front.append(p(b, 'abstract'))
            continue
        if b.startswith('![그림'):
            n = int(re.search(r'figure-(\d)', b)[1])
            caption = blocks[i]
            i += 1
            if n in figs:
                graphic = figs[n]
            else:
                hint = {2: '관리자 웹 화면 캡처', 5: '보관대와 카메라 설치 사진'}.get(n, '판정 성공 예와 실패 예')
                graphic, photos[n] = photo_or_placeholder(n, hint)
            body.append(KeepTogether([Spacer(1, 4), graphic, p(caption, 'figcaption')]))
        elif b.startswith('\\['):
            n = int(re.search(r'\\tag\{(\d+)\}', b)[1])
            body.append(Paragraph(EQ[n], ST['eq']))
        elif b.startswith('# '):
            refs = b[2:] == '참고문헌'
            body.append(p(b[2:], 'h1'))
        elif b.startswith('## '):
            body.append(p(b[3:], 'h2'))
        elif b.startswith('**알고리즘 '):
            caption = p(b, 'caption')
            steps = [p(line, 'alg') for line in blocks[i].splitlines()]
            i += 1
            frame = Table([[x] for x in steps], colWidths=[COL_W])
            frame.setStyle(TableStyle([
                ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, -1), (-1, -1), .8, INK),
                ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
            ]))
            body.append(KeepTogether([caption, frame, Spacer(1, 7)]))
        elif b.startswith('**표 '):
            caption = p(b, 'caption')
            table = table_flowable(blocks[i])
            i += 1
            body.append(KeepTogether([caption, table, Spacer(1, 7)]))
        elif refs:
            body.append(reference(b))
        else:
            body.append(p(b))
    return text, front, body, photos


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Korean', 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, 14 * mm, 'Re:Found 심사용 원고 초안 · JDCS 2단 근사 조판(최종 투고는 학회 HWP 양식)')
    canvas.drawRightString(A4[0] - MARGIN_X, 14 * mm, str(doc.page))
    canvas.restoreState()


def build():
    text, front, body, photos = parse()
    front_h = sum(f.wrap(FULL_W, BODY_H)[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in front) + 14
    col_h = BODY_H - front_h
    first = PageTemplate('first', frames=[
        Frame(MARGIN_X, MARGIN_Y + col_h, FULL_W, front_h, id='front', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(MARGIN_X, MARGIN_Y, COL_W, col_h, id='c1', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(MARGIN_X + COL_W + GAP, MARGIN_Y, COL_W, col_h, id='c2', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
    ], onPage=footer)
    later = PageTemplate('later', frames=[
        Frame(MARGIN_X, MARGIN_Y, COL_W, BODY_H, id='l1', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(MARGIN_X + COL_W + GAP, MARGIN_Y, COL_W, BODY_H, id='l2', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
    ], onPage=footer)
    doc = BaseDocTemplate(str(OUT), pagesize=A4, pageTemplates=[first, later],
                          title=text.splitlines()[0][2:], author='', subject='JDCS 심사용 원고 초안(실측 전)')
    from reportlab.platypus import FrameBreak
    doc.build(front + [FrameBreak(), NextPageTemplate('later')] + body)
    texts = [page.extract_text() for page in PdfReader(OUT).pages]
    assert '[[' not in '\n'.join(texts)
    report = {
        'pages': len(texts),
        'layout': 'A4 two-column approximation of the JDCS HWP template',
        'margins_mm': {'top_bottom_incl_header_footer': 25, 'left_right': 20, 'column_gap': 8},
        'body_font_pt': BODY_PT, 'leading_pt': LEADING,
        'figures': 6, 'tables': 8, 'algorithms': 1, 'equations': 2, 'references': 18,
        'photo_figures_present': photos,
        'unmeasured_display': '[입력 대기]',
        'pdf': OUT.relative_to(ROOT).as_posix(),
    }
    (HERE / 'PDF_BUILD_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    if '--figures-only' in sys.argv:
        make_figures()
    else:
        build()
