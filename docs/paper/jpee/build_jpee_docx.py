"""Build the JPEE submission file (MS Word) from PAPER_DRAFT_JPEE.md.

The Journal of Practical Engineering Education accepts MS Word or HWP in its
own template: one column, 10 pt, 1.5 line spacing, chapter numbers I./A./1),
figures and tables after the references.  The publisher typesets the accepted
paper again, so this file only has to follow the template.

The official Korean template (template/JPEE_TEMPLATE_KO.docx) is opened and
its body replaced, so the page setup and base styles are the journal's own.
"""
from pathlib import Path
import copy
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE / 'PAPER_DRAFT_JPEE.md'
TEMPLATE = HERE / 'template' / 'JPEE_TEMPLATE_KO.docx'
OUT = HERE.parent / 'REFOUND_JPEE_MANUSCRIPT.docx'
KOREAN_FONT = '휴먼명조'       # template: Korean text in Human Myeongjo
LATIN_FONT = 'Times New Roman'
BODY_PT = 10
ABSTRACT_KO_MAX, ABSTRACT_EN_MAX, KEYWORDS = 500, 200, 5
MATH_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


def set_fonts(run, size=BODY_PT, bold=None, italic=None):
    run.font.name = LATIN_FONT
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn('w:rFonts'))
    if fonts is None:
        fonts = OxmlElement('w:rFonts')
        rpr.insert(0, fonts)
    fonts.set(qn('w:eastAsia'), KOREAN_FONT)
    fonts.set(qn('w:ascii'), LATIN_FONT)
    fonts.set(qn('w:hAnsi'), LATIN_FONT)
    return run


MATH_WORDS = {'\\ell': 'ℓ', '\\Delta': 'Δ', '\\tau': 'τ'}


def add_math(par, expr, size):
    """Inline symbols such as t_r-t_m: italic letters with subscripts."""
    for src, dst in MATH_WORDS.items():
        expr = expr.replace(src, dst)
    expr = expr.replace('-', ' − ')
    for token in re.findall(r'[A-Za-zℓΔτ]_[A-Za-z0-9]|.', expr):
        if len(token) == 3 and token[1] == '_':
            set_fonts(par.add_run(token[0]), size, italic=True)
            set_fonts(par.add_run(token[2]), size, italic=True).font.subscript = True
        else:
            set_fonts(par.add_run(token), size, italic=token.isalpha())


def add_text(par, text, size=BODY_PT, bold=None):
    """Markdown-lite: \\( math \\), *italic*, **bold**."""
    text = text.replace('\\*', '*')
    for part in re.split(r'(\\\(.*?\\\)|\*\*.*?\*\*|\*[^*]+\*)', text):
        if not part:
            continue
        if part.startswith('\\('):
            add_math(par, part[2:-2], size)
        elif part.startswith('**'):
            set_fonts(par.add_run(part[2:-2]), size, bold=True)
        elif part.startswith('*') and part.endswith('*') and len(part) > 2:
            set_fonts(par.add_run(part[1:-1]), size, bold=bold, italic=True)
        else:
            set_fonts(par.add_run(part), size, bold=bold)
    return par


def m_run(text, upright=False):
    style = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ''
    return f'<m:r>{style}<m:t xml:space="preserve">{text}</m:t></m:r>'


def m_group(parts, begin='(', end=')'):
    """Delimited group; several parts are separated by commas."""
    parts = parts if isinstance(parts, list) else [parts]
    body = ''.join(f'<m:e>{part}</m:e>' for part in parts)
    return (f'<m:d><m:dPr><m:begChr m:val="{begin}"/><m:sepChr m:val=","/><m:endChr m:val="{end}"/></m:dPr>'
            f'{body}</m:d>')


def m_abs(inner):
    return m_group(inner, '|', '|')


def difference_equation():
    """D(x) = max(min(|s(x) - m - l(x)|, |s(x) - m|), |Da(x)|, |Db(x)|) as Office Math."""
    x = m_group(m_run('x'))
    first = m_abs(m_run('s') + x + m_run('−m−ℓ') + x)
    second = m_abs(m_run('s') + x + m_run('−m'))
    inner = m_run('min', True) + m_group([first, second])
    return (m_run('D') + x + m_run('=') + m_run('max', True)
            + m_group([inner, m_abs(m_run('Δa') + x), m_abs(m_run('Δb') + x)]))


class Builder:
    def __init__(self):
        self.doc = Document(str(TEMPLATE))
        body = self.doc.element.body
        for child in list(body):
            if child.tag != qn('w:sectPr'):
                body.remove(child)
        self.text_width = self.doc.sections[0].page_width - self.doc.sections[0].left_margin - self.doc.sections[0].right_margin

    def par(self, text='', align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=BODY_PT, bold=None, indent=0, spacing=1.5,
            keep_next=False, style=None):
        p = self.doc.add_paragraph(style=style)
        p.alignment = align
        fmt = p.paragraph_format
        fmt.line_spacing = spacing
        fmt.space_before = fmt.space_after = Pt(0)
        if indent:
            fmt.first_line_indent = Pt(indent)
        fmt.keep_with_next = keep_next
        if text:
            add_text(p, text, size, bold)
        return p

    def blank(self):
        return self.par()

    def heading1(self, text):
        self.blank()
        self.par(text, WD_ALIGN_PARAGRAPH.CENTER, bold=True, keep_next=True)

    def heading2(self, text):
        self.par(text, WD_ALIGN_PARAGRAPH.JUSTIFY, bold=True, keep_next=True)

    def equation(self, omml, number):
        p = self.par(align=WD_ALIGN_PARAGRAPH.RIGHT)
        math = parse_xml(f'<m:oMath xmlns:m="{MATH_NS}">{omml}</m:oMath>')
        p._element.append(math)
        set_fonts(p.add_run(f'               ({number})'))

    def reference(self, text):
        m = re.match(r'\[(\d+)\]\s+(.*)', text, flags=re.S)
        p = self.par(align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.left_indent = Pt(21.3)
        p.paragraph_format.first_line_indent = Pt(-21.3)
        add_text(p, f'[{m[1]}] {m[2]}')

    def captions(self, block, align, keep_last):
        lines = block.splitlines()
        for k, line in enumerate(lines):
            m = re.fullmatch(r'\*\*(.*?)\*\*', line.strip())
            self.par(m[1], align, keep_next=keep_last or k < len(lines) - 1)

    def figure(self, path, caption):
        p = self.par(align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True, spacing=1.0)
        shape = p.add_run().add_picture(str(path), width=self.text_width)
        limit = Mm(105)  # keep a figure and its two caption lines on one page
        if shape.height > limit:
            shape.width, shape.height = int(shape.width * limit / shape.height), limit
        self.captions(caption, WD_ALIGN_PARAGRAPH.CENTER, keep_last=False)
        self.blank()

    def table(self, caption, block):
        self.captions(caption, WD_ALIGN_PARAGRAPH.LEFT, keep_last=True)
        rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in block.splitlines()]
        rows = [r for r in rows if not all(re.fullmatch(r'[-:]+', c) for c in r)]
        table = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        borders = parse_xml(
            '<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            + ''.join(f'<w:{side} w:val="single" w:sz="{size}" w:space="0" w:color="000000"/>'
                      for side, size in (('top', 8), ('bottom', 8), ('insideH', 4), ('insideV', 4)))
            + '</w:tblBorders>')
        table._element.tblPr.append(borders)
        table.autofit = False
        plain = [[re.sub(r'\\[()]|_', '', c) for c in row] for row in rows]
        longest = [max(max(len(w) for w in r[j].split() or ['']) for r in plain) + 2 for j in range(len(rows[0]))]
        total = [max(len(r[j]) for r in plain) + 2 for j in range(len(rows[0]))]
        weight = [max(lo, min(to, 34)) for lo, to in zip(longest, total)]
        widths = [int(self.text_width * w / sum(weight)) for w in weight]
        for j, column in enumerate(table.columns):
            column.width = widths[j]
        for i, row in enumerate(rows):
            tr_pr = table.rows[i]._tr.get_or_add_trPr()
            tr_pr.append(OxmlElement('w:cantSplit'))
            for j, cell_text in enumerate(row):
                cell = table.cell(i, j)
                cell.width = widths[j]
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.keep_with_next = i < len(rows) - 1
                add_text(p, cell_text, 9, bold=True if i == 0 else None)
        self.blank()


def build():
    text = SOURCE.read_text(encoding='utf-8')
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    blocks = [x for x in blocks if not x.startswith('> ')]  # editorial notes are not part of the paper
    b = Builder()
    info = {'figures': 0, 'tables': 0, 'references': 0}
    i, tail = 0, False
    while i < len(blocks):
        blk = blocks[i]
        i += 1
        if blk.startswith('# ') and not re.match(r'# ([IVX]+\.|참 고 문 헌|그림과 표)', blk):
            b.blank()
            b.par(blk[2:], WD_ALIGN_PARAGRAPH.CENTER, size=16, bold=True)
            b.blank()
            b.par(blocks[i], WD_ALIGN_PARAGRAPH.CENTER, size=14)   # English title
            i += 1
            b.blank()
            b.blank()  # author names and affiliations are added only in the final version
        elif blk == '## 요 약':
            info['abstract_ko'] = blocks[i]
            b.par('요 약', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
            b.par(blocks[i])
            i += 1
            b.blank()
        elif blk == '## ABSTRACT':
            info['abstract_en'] = blocks[i]
            b.par('ABSTRACT', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
            b.par(blocks[i])
            i += 1
            b.blank()
        elif blk.startswith('Key Words :'):
            info['keywords'] = [k.strip(' .') for k in blk.split(':', 1)[1].split(';')]
            p = b.par(align=WD_ALIGN_PARAGRAPH.LEFT)
            add_text(p, 'Key Words : ', bold=True)
            add_text(p, blk.split(':', 1)[1].strip())
        elif blk == '# 참 고 문 헌':
            b.heading1('참 고 문 헌')
            tail = 'refs'
        elif blk == '# 그림과 표':
            b.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            b.par('그림과 표', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
            b.blank()
            tail = 'floats'
        elif blk.startswith('# '):
            b.heading1(blk[2:])
        elif blk.startswith('## '):
            b.heading2(blk[3:])
        elif blk.startswith('\\['):
            n = int(re.search(r'\\tag\{(\d+)\}', blk)[1])
            b.equation(difference_equation(), n)
        elif blk.startswith('![그림'):
            path = HERE / re.search(r'\((.*?)\)', blk)[1]
            b.figure(path, blocks[i])
            i += 1
            info['figures'] += 1
        elif blk.startswith('**표 '):
            b.table(blk, blocks[i])
            i += 1
            info['tables'] += 1
        elif tail == 'refs':
            b.reference(blk)
            info['references'] += 1
        else:
            b.par(blk, indent=10)
    ko, en = info['abstract_ko'], info['abstract_en']
    assert len(ko) <= ABSTRACT_KO_MAX, f'Korean abstract has {len(ko)} characters (limit {ABSTRACT_KO_MAX})'
    assert len(en.split()) <= ABSTRACT_EN_MAX, f'English abstract has {len(en.split())} words (limit {ABSTRACT_EN_MAX})'
    assert len(info['keywords']) == KEYWORDS and info['keywords'] == sorted(info['keywords'], key=str.lower)
    assert info['references'] >= 10
    b.doc.core_properties.author = ''
    b.doc.core_properties.last_modified_by = ''
    b.doc.core_properties.title = ''
    b.doc.save(str(OUT))
    print({'docx': OUT.relative_to(ROOT).as_posix(), 'abstract_ko_chars': len(ko), 'abstract_en_words': len(en.split()),
           'keywords': info['keywords'], 'figures': info['figures'], 'tables': info['tables'], 'references': info['references']})


if __name__ == '__main__':
    build()
