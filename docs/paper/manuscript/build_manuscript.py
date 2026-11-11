"""Build a PDF that approximates the official JDCS HWP template (2026-07 revision).

The submission itself must be the HWP template; this PDF is for checking the
page count, the one-page front matter and the placement of figures and tables
before the text is moved into HWP.  Values taken from the template file:

- paper 210 x 280 mm; margins 13 mm top/bottom plus 12 mm header/footer,
  20 mm left/right; two columns with an 8 mm gap from the introduction on
- page 1 holds only the titles, abstracts and keywords (one column)
- body Batang 9.1 pt, line spacing 150 %, first-line indent 10 pt
- chapter title 10 pt and section title 9.1 pt gothic, with two blank lines
  before a chapter and one blank line around section titles
- captions 8.5 pt gothic, left aligned, Korean line then English line
- table text 7.5 pt, line spacing 120 %; references Times 9 pt, 150 %
- figures and tables sit at the top of a column

HWP narrows the letter spacing (-5 to -8 %), which reportlab paragraphs cannot
do.  The same number of characters per line is reached by scaling the font
size instead (TRACK); line pitch is kept at the template value.
"""
from pathlib import Path
import json
import re
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / 'PAPER_DRAFT_JDCS.md'
OUT = HERE.parent / 'REFOUND_FULL_MANUSCRIPT.pdf'
FIG = HERE / 'figures'

PAGE = (210 * mm, 280 * mm)
MARGIN_X = 20 * mm
MARGIN_Y = 25 * mm          # 13 mm margin + 12 mm header/footer
GAP = 8 * mm
FULL_W = PAGE[0] - 2 * MARGIN_X
COL_W = (FULL_W - GAP) / 2
BODY_H = PAGE[1] - 2 * MARGIN_Y
BODY_PT = 9.1
LINE = BODY_PT * 1.5        # 150 % line spacing
TRACK = {'body': .92, 'abstract_ko': .95, 'abstract_en': .89, 'caption': .88, 'table': .95, 'ref': .85}
ABSTRACT_WORDS = (120, 170)


def _first(paths):
    for path, kwargs in paths:
        if Path(path).exists():
            return path, kwargs
    return None, None


def _register_fonts():
    nanum = '/usr/share/fonts/truetype/nanum/'
    lib = '/usr/share/fonts/truetype/liberation/'
    faces = {
        # template: Batang (body), gothic faces (titles, captions), Times New Roman, Arial
        'Serif': [('C:/Windows/Fonts/batang.ttc', {'subfontIndex': 0}), (nanum + 'NanumMyeongjo_400Regular.ttf', {}),
                  (nanum + 'NanumMyeongjo.ttf', {}), ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', {'subfontIndex': 0})],
        'SerifBold': [(nanum + 'NanumMyeongjo_700Bold.ttf', {}), (nanum + 'NanumMyeongjoBold.ttf', {}),
                      ('C:/Windows/Fonts/malgunbd.ttf', {}), ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', {'subfontIndex': 0})],
        'Gothic': [('C:/Windows/Fonts/malgun.ttf', {}), (nanum + 'NanumGothic_400Regular.ttf', {}),
                   (nanum + 'NanumGothic.ttf', {}), ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', {'subfontIndex': 0})],
        'GothicBold': [('C:/Windows/Fonts/malgunbd.ttf', {}), (nanum + 'NanumGothic_700Bold.ttf', {}),
                       (nanum + 'NanumGothicBold.ttf', {}), ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', {'subfontIndex': 0})],
        'Times': [('C:/Windows/Fonts/times.ttf', {}), (lib + 'LiberationSerif-Regular.ttf', {}),
                  ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', {})],
        'TimesItalic': [('C:/Windows/Fonts/timesi.ttf', {}), (lib + 'LiberationSerif-Italic.ttf', {}),
                        ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', {})],
        'Arial': [('C:/Windows/Fonts/arial.ttf', {}), (lib + 'LiberationSans-Regular.ttf', {}),
                  ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', {})],
        'ArialBold': [('C:/Windows/Fonts/arialbd.ttf', {}), (lib + 'LiberationSans-Bold.ttf', {}),
                      ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', {})],
        'Equation': [('C:/Windows/Fonts/cambria.ttc', {'subfontIndex': 0}), ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', {})],
        'Fallback': [('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', {}), ('C:/Windows/Fonts/seguisym.ttf', {})],
    }
    for name, paths in faces.items():
        path, kwargs = _first(paths)
        if path is None:
            if name in ('Serif', 'Gothic'):
                raise SystemExit('Korean font not found (Batang/Malgun Gothic on Windows, Nanum Myeongjo/Gothic on Linux)')
            path, kwargs = _first(faces['Serif'])
        pdfmetrics.registerFont(TTFont(name, path, **kwargs))
    for family, bold in (('Serif', 'SerifBold'), ('Gothic', 'GothicBold'), ('Arial', 'ArialBold')):
        pdfmetrics.registerFontFamily(family, normal=family, bold=bold, italic=family, boldItalic=bold)
    pdfmetrics.registerFontFamily('Times', normal='Times', bold='Times', italic='TimesItalic', boldItalic='TimesItalic')


def has_glyph(font, ch):
    return ord(ch) in pdfmetrics.getFont(font).face.charToGlyph


def with_fallback(s, font):
    """Draw characters missing from `font` with a face that has them."""
    out = []
    for ch in s:
        if ch.isspace() or ord(ch) < 0x80 or has_glyph(font, ch):
            out.append(ch)
        else:
            alt = next((f for f in ('Serif', 'Gothic', 'Fallback', 'Equation') if f != font and has_glyph(f, ch)), None)
            out.append(f'<font name="{alt}">{ch}</font>' if alt else ch)
    return ''.join(out)


_register_fonts()
INK = colors.HexColor('#1F2A33')
MUTED = colors.HexColor('#5A6671')
RULE = colors.HexColor('#CAD3D9')


def S(name, font, size, leading, **kw):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, textColor=INK, **kw)


ST = {
    'title': S('title', 'GothicBold', 14 * .95, 14 * 1.6, wordWrap='CJK', spaceAfter=5),
    'en_title': S('en_title', 'Arial', 16.5, 16.5 * 1.3, spaceAfter=16),
    'abs_head': S('abs_head', 'GothicBold', 10, 15, spaceBefore=6),
    'abs_head_en': S('abs_head_en', 'ArialBold', 10, 15, spaceBefore=12),
    'abstract': S('abstract', 'Serif', BODY_PT * TRACK['abstract_ko'], LINE, wordWrap='CJK', alignment=TA_JUSTIFY, firstLineIndent=10),
    'abstract_en': S('abstract_en', 'Times', 9.2 * TRACK['abstract_en'], 9.2 * 1.5, alignment=TA_JUSTIFY, firstLineIndent=10),
    'keywords': S('keywords', 'Gothic', 8.7, 15, wordWrap='CJK', spaceBefore=12),
    'keywords_en': S('keywords_en', 'Arial', 8.7, 15, spaceBefore=4),
    'body': S('body', 'Serif', BODY_PT * TRACK['body'], LINE, wordWrap='CJK', alignment=TA_JUSTIFY, firstLineIndent=10),
    'h1': S('h1', 'GothicBold', 10, 15, wordWrap='CJK', spaceBefore=2 * LINE, spaceAfter=LINE),
    'h2': S('h2', 'GothicBold', BODY_PT * .95, LINE, wordWrap='CJK', spaceBefore=LINE, spaceAfter=LINE),
    'h2_after_h1': S('h2_after_h1', 'GothicBold', BODY_PT * .95, LINE, wordWrap='CJK', spaceAfter=LINE),
    'cap_ko': S('cap_ko', 'Gothic', 8.5 * TRACK['caption'], 8.5 * 1.3, wordWrap='CJK', alignment=TA_LEFT),
    'cap_en': S('cap_en', 'Arial', 8.5 * TRACK['caption'], 8.5 * 1.3, alignment=TA_LEFT),
    'table': S('table', 'Arial', 7.5 * TRACK['table'], 7.5 * 1.2),
    'table_head': S('table_head', 'ArialBold', 7.5 * TRACK['table'], 7.5 * 1.2),
    'fig_note': S('fig_note', 'Arial', 7.5 * TRACK['table'], 7.5 * 1.2),
    'ref': S('ref', 'Times', 9 * TRACK['ref'], 9 * 1.5, alignment=TA_LEFT, leftIndent=15, firstLineIndent=-15),  # ragged: long URLs
    'eq': S('eq', 'Equation', 8.6, 13, alignment=TA_CENTER),
    'eqno': S('eqno', 'Serif', BODY_PT * TRACK['body'], 13, alignment=TA_RIGHT),
}


def markup(s, font='Serif'):
    s = re.sub(r'\[\[[^\]]+\]\]', '[입력 대기]', s)
    s = re.sub(r'\\\((.*?)\\\)', lambda m: m[1], s)
    for src, dst in (('\\ell', 'ℓ'), ('\\tau', 'τ'), ('\\Delta', 'Δ')):
        s = s.replace(src, dst)
    s = re.sub(r'(?<=[a-z])-(?=t_)', ' − ', s)  # t_r-t_m reads as a difference
    s = s.replace('\\', '')
    s = escape(s)
    s = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    # Hangul counts as a word character, so end subscripts with an explicit lookahead.
    s = re.sub(r"\b(p|p')_i(?![A-Za-z0-9_])", r'\1<sub>i</sub>', s)
    s = re.sub(r'\bt_([mra])(?![A-Za-z0-9_])', r'<i>t</i><sub>\1</sub>', s)
    return ''.join(with_fallback(part, font) if not part.startswith('<') else part
                   for part in re.split(r'(<[^>]+>)', s))


class BodyParagraph(Paragraph):
    """Paragraph that keeps its spaces when it continues in the next column.

    reportlab's character-level (CJK) wrapping strips the space at the end of
    each line.  When the rest of a split paragraph is wrapped again, the lines
    are joined without those spaces ("JPEG (joint" + "photographic").  The
    continuation is therefore rebuilt from the original text.
    """

    @staticmethod
    def _plain(frag):
        return frag.text if hasattr(frag, 'text') else ''.join(frag.words)

    def split(self, aw, ah):
        single = len(self.frags) == 1 and not hasattr(self.frags[0], 'cbDefn')
        full = self._plain(self.frags[0]) if single else None
        parts = super().split(aw, ah)
        if single and len(parts) == 2:
            used = sum(len(re.sub(r'\s+', '', ''.join(line[1]))) for line in parts[0].blPara.lines)
            pos = 0
            while used and pos < len(full):
                used -= not full[pos].isspace()
                pos += 1
            rest = parts[1].frags[0]
            if hasattr(rest, 'text'):
                del rest.text
            rest.words = [full[pos:].lstrip()]
            if hasattr(parts[1], 'blPara'):
                del parts[1].blPara
            parts[1]._splitpara = 0
        return parts


def p(s, style='body'):
    cls = BodyParagraph if style == 'body' else Paragraph
    return cls(markup(s, ST[style].fontName), ST[style])


EQ = {
    1: 'F* = arg max<sub>F</sub> Σ<sub>i</sub> 1(‖p′<sub>i</sub> − Fp<sub>i</sub>‖<sub>2</sub> ≤ τ)',
    2: 'D(x) = max( min(|s(x) − m − ℓ(x)|, |s(x) − m|),<br/>|Δa(x)|, |Δb(x)| )',
}


def heading(text, style):
    st = ST[style]
    return [CondPageBreak(st.spaceBefore + st.leading + st.spaceAfter + 2 * LINE), p(text, style)]


def equation(n):
    """Equation with its number at the right margin and a blank line above and below."""
    formula = ''.join(with_fallback(part, 'Equation') if not part.startswith('<') else part
                      for part in re.split(r'(<[^>]+>)', EQ[n]))
    table = Table([[Paragraph(formula, ST['eq']), Paragraph(f'({n})', ST['eqno'])]],
                  colWidths=[COL_W - 22, 22], hAlign='CENTER', spaceBefore=LINE, spaceAfter=LINE)
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def captions(block, hang):
    """`**표 1. 국문**` / `**Table 1. English**` -> two left-aligned caption lines."""
    out = []
    for line, style in zip([x.strip() for x in block.splitlines()], ('cap_ko', 'cap_en')):
        m = re.fullmatch(r'\*\*((?:표|그림|알고리즘|Table|Fig\.|Algorithm) \d+\.)\s*(.*?)\*\*', line)
        assert m, line
        st = ParagraphStyle(style + str(hang), parent=ST[style], leftIndent=hang, firstLineIndent=-hang)
        out.append(Paragraph(f'<b>{markup(m[1], st.fontName)}</b> {markup(m[2], st.fontName)}', st))
    assert len(out) == 2, block
    return out


def table_flowable(block):
    rows = [[x.strip() for x in line.strip().strip('|').split('|')] for line in block.splitlines()]
    rows = [r for r in rows if not all(re.fullmatch(r'[-:]+', c) for c in r)]
    count = len(rows[0])

    def plain(text):
        return re.sub(r'<[^>]+>', '', markup(text, 'Arial'))

    def measure(text, row):
        return pdfmetrics.stringWidth(text, 'ArialBold' if row == 0 else 'Arial', ST['table'].fontSize)
    pad = 6.5
    natural = [max(measure(plain(r[i]), k) for k, r in enumerate(rows)) + pad for i in range(count)]
    narrow = [max(measure(word, k) for k, r in enumerate(rows) for word in plain(r[i]).split() or ['']) + pad
              for i in range(count)]
    if sum(natural) <= COL_W:
        widths = [n * COL_W / sum(natural) for n in natural]
    else:  # give every column its longest word, then share the rest by text length
        spare = COL_W - sum(narrow)
        assert spare >= 0, 'table is wider than the column'
        extra = [n - m for n, m in zip(natural, narrow)]
        widths = [m + spare * e / sum(extra) for m, e in zip(narrow, extra)]
    data = [[p(c, 'table_head' if i == 0 else 'table') for c in row] for i, row in enumerate(rows)]
    table = Table(data, colWidths=widths, hAlign='CENTER')
    table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, 0), (-1, 0), .5, INK),
        ('LINEBELOW', (0, -1), (-1, -1), .8, INK),
        ('INNERGRID', (0, 1), (-1, -1), .25, RULE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return table


def steps_flowable(block):
    rows = [[p(line, 'table')] for line in block.splitlines()]
    table = Table(rows, colWidths=[COL_W])
    table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, -1), (-1, -1), .8, INK),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return table


def figure_image(n):
    path = FIG / f'figure-{n}.jpg'
    if not path.exists():
        raise SystemExit(f'{path.name} is missing: run make_figures.py first')
    image = Image(str(path))
    image.drawWidth, image.drawHeight = COL_W, image.imageHeight * COL_W / image.imageWidth
    return image


class Float(Flowable):
    """Marker left where a figure or table is cited; the document places the
    group at the top of a column (JDCS: top or bottom of a page or column)."""

    def __init__(self, group):
        super().__init__()
        self.group = group
        self.height = sum(f.wrap(COL_W, BODY_H)[1] for f in group) + sum(f.getSpaceBefore() + f.getSpaceAfter() for f in group)

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        pass


class FlushFloats(Flowable):
    """At the end of the story: move to new columns until no float is waiting."""

    def __init__(self, doc):
        super().__init__()
        self.doc = doc

    def wrap(self, aw, ah):
        return (0, ah + 1) if self.doc.pending else (0, 0)

    def draw(self):
        pass


class Manuscript(BaseDocTemplate):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.pending = []
        self.text_in_frame = False
        self.float_pages = {}

    def _place(self, flt):
        frame = self.frame
        if flt.height > frame._y - frame._y1p:
            return False
        for f in flt.group:
            assert frame.add(f, self.canv, trySplit=0), 'float did not fit'
        self.float_pages[flt.label] = self.page
        return True

    def handle_frameBegin(self, *args, **kw):
        super().handle_frameBegin(*args, **kw)
        self.text_in_frame = False
        if self.frame.id == 'front':
            return
        while self.pending and self._place(self.pending[0]):
            del self.pending[0]

    def afterFlowable(self, flowable):
        if isinstance(flowable, Float):
            if self.pending or self.text_in_frame or not self._place(flowable):
                self.pending.append(flowable)
        elif not isinstance(flowable, (FlushFloats, Spacer)) and getattr(flowable, 'height', 1):
            self.text_in_frame = True


def parse():
    text = SOURCE.read_text(encoding='utf-8')
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    front, body, info = [], [], {'figures': 0, 'tables': 0, 'algorithms': 0}
    i, in_front, refs, prev_h1 = 0, True, False, False

    def float_group(label, parts):
        parts = parts + [Spacer(1, LINE)]
        flt = Float(parts)
        flt.label = label
        return flt

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
            elif b.startswith('## [요'):
                front.append(p(b[3:], 'abs_head'))
                info['abstract_ko'] = blocks[i]
                front.append(p(blocks[i], 'abstract'))
                i += 1
            elif b == '## [Abstract]':
                front.append(p(b[3:], 'abs_head_en'))
                info['abstract_en'] = blocks[i]
                front.append(p(blocks[i], 'abstract_en'))
                i += 1
            elif b.startswith('색인어 :'):
                front.append(Paragraph(f'<font name="GothicBold" size="10">색인어</font> : {markup(b[5:].strip(), "Gothic")}', ST['keywords']))
            elif b.startswith('Keyword :'):
                front.append(Paragraph(f'<font name="ArialBold" size="10">Keyword</font> : {markup(b[9:].strip(), "Arial")}', ST['keywords_en']))
            elif re.match(r'# [ⅠⅡⅢⅣⅤⅥⅦ]\.', b):
                in_front = False
                body += heading(b[2:], 'h1')
                prev_h1 = True
            else:
                raise SystemExit(f'unexpected front-matter block: {b[:40]}')
            continue
        was_h1, prev_h1 = prev_h1, False
        if b.startswith('![그림'):
            n = int(re.search(r'figure-(\d)', b)[1])
            parts = [figure_image(n), Spacer(1, 3)]
            if blocks[i].startswith('\\*'):
                parts += [p(blocks[i], 'fig_note'), Spacer(1, 2)]
                i += 1
            parts += captions(blocks[i], 28)
            i += 1
            info['figures'] += 1
            body.append(float_group(f'Fig. {n}', parts))
        elif b.startswith('\\['):
            body.append(equation(int(re.search(r'\\tag\{(\d+)\}', b)[1])))
        elif b.startswith('# '):
            refs = b[2:] == '참고문헌'
            body += heading(b[2:], 'h1')
            prev_h1 = True
        elif b.startswith('## '):
            body += heading(b[3:], 'h2_after_h1' if was_h1 else 'h2')
        elif b.startswith('**알고리즘 '):
            n = int(re.match(r'\*\*알고리즘 (\d+)', b)[1])
            parts = captions(b, 22) + [Spacer(1, 3), steps_flowable(blocks[i])]
            i += 1
            info['algorithms'] += 1
            body.append(float_group(f'Algorithm {n}', parts))
        elif b.startswith('**표 '):
            n = int(re.match(r'\*\*표 (\d+)', b)[1])
            parts = captions(b, 22) + [Spacer(1, 3), table_flowable(blocks[i])]
            i += 1
            info['tables'] += 1
            body.append(float_group(f'Table {n}', parts))
        elif refs:
            body.append(p(b, 'ref'))
        else:
            body.append(p(b))
    return text, front, body, info


def page_marks(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(MUTED)
    canvas.setStrokeColor(MUTED)
    canvas.setLineWidth(.4)
    canvas.setFont('Gothic', 7)
    top = PAGE[1] - 17 * mm
    if doc.page == 1:
        canvas.drawString(MARGIN_X, top + 9, '디지털콘텐츠학회논문지')
        canvas.setFont('Arial', 7)
        canvas.drawString(MARGIN_X, top, 'Journal of Digital Contents Society — review manuscript, author information removed')
        canvas.line(MARGIN_X, top - 5, PAGE[0] - MARGIN_X, top - 5)
        box_top = MARGIN_Y + 40 * mm
        canvas.line(MARGIN_X, box_top, PAGE[0] - MARGIN_X, box_top)
        canvas.setFont('Gothic', 7)
        canvas.drawString(MARGIN_X, box_top - 12, '학회 기재란(DOI, 접수·수정·게재확정일, 교신저자) — 양식의 이 영역은 수정하지 않는다')
    else:
        canvas.drawString(MARGIN_X, top, '디지털콘텐츠학회논문지(J. DCS) — 심사용 원고')
        canvas.line(MARGIN_X, top - 4, PAGE[0] - MARGIN_X, top - 4)
    canvas.setFont('Gothic', 7)
    canvas.drawString(MARGIN_X, 14 * mm, 'JDCS 공식 양식(2026.07)의 근사 조판 — 최종 투고는 학회 HWP 양식')
    canvas.drawCentredString(PAGE[0] / 2, 14 * mm, str(doc.page))
    canvas.restoreState()


def build():
    text, front, body, info = parse()
    words = len(info['abstract_en'].split())
    assert ABSTRACT_WORDS[0] <= words <= ABSTRACT_WORDS[1], f'English abstract has {words} words (template: 120-170)'
    pad = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    # the template keeps a 40 mm society box (DOI, dates, corresponding author) at the foot of page 1
    first = PageTemplate('first', frames=[Frame(MARGIN_X, MARGIN_Y + 42 * mm, FULL_W, BODY_H - 42 * mm, id='front', **pad)],
                         onPage=page_marks)
    later = PageTemplate('later', frames=[
        Frame(MARGIN_X, MARGIN_Y, COL_W, BODY_H, id='c1', **pad),
        Frame(MARGIN_X + COL_W + GAP, MARGIN_Y, COL_W, BODY_H, id='c2', **pad),
    ], onPage=page_marks)
    doc = Manuscript(str(OUT), pagesize=PAGE, pageTemplates=[first, later],
                     title=text.splitlines()[0][2:], author='', subject='JDCS 심사용 원고(공식 양식 근사 조판)')
    front_h = sum(f.wrap(FULL_W, BODY_H)[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in front)
    assert front_h <= BODY_H - 42 * mm, 'front matter does not fit on one page'
    doc.build(front + [NextPageTemplate('later'), PageBreak()] + body + [FlushFloats(doc)])
    texts = [page.extract_text() for page in PdfReader(OUT).pages]
    joined = '\n'.join(texts)
    assert '[[' not in joined and '입력 대기' not in joined
    assert not doc.pending
    ko = info['abstract_ko']
    report = {
        'pages': len(texts),
        'layout': 'approximation of the official JDCS HWP template (2026-07): 210 x 280 mm, one-column front page, two-column body',
        'margins_mm': {'top_bottom_incl_header_footer': 25, 'left_right': 20, 'column_gap': 8},
        'body_font_pt': BODY_PT, 'line_pitch_pt': round(LINE, 2),
        'abstract_en_words': words,
        'abstract_ko_chars': {'with_spaces': len(ko), 'without_spaces': len(ko.replace(' ', ''))},
        'figures': info['figures'], 'tables': info['tables'], 'algorithms': info['algorithms'],
        'equations': len(re.findall(r'\\tag\{\d+\}', text)),
        'references': len(re.findall(r'^\[\d+\] ', text, flags=re.M)),
        'float_pages': doc.float_pages,
        'placeholders_left': len(re.findall(r'\[\[[^\]]+\]\]', text)),
        'pdf': OUT.relative_to(ROOT).as_posix(),
    }
    (HERE / 'PDF_BUILD_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    build()
