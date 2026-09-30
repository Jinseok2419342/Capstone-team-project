"""Check consistency of the delivered manuscript, handout and native slide content."""
from pathlib import Path
import json
import re
import hashlib
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
PAPER=ROOT/'docs/paper'
read=lambda p:p.read_text(encoding='utf-8')
norm=lambda s:re.sub(r'\s+','',s)
draft=read(PAPER/'PAPER_DRAFT_JDCS.md')
front=read(PAPER/'briefing/RESEARCH_FRONT_MATTER.md')
sheet=read(PAPER/'RESULTS_FILL_SHEET.md')
keys=lambda s:set(re.findall(r'\[\[[^\]]+\]\]',s))
assert keys(draft)==keys(sheet) and len(keys(draft))==297
body,refs=draft.split('# 참고문헌')
first=list(dict.fromkeys(re.findall(r'(?<!\[)\[(\d+)\](?!\])',body)))
assert first==re.findall(r'^\[(\d+)\]',refs,re.M)==list(map(str,range(1,18)))
front_paragraphs=[]
for b in front.split('## 참고문헌')[0].split('\n\n'):
    if b and not b.startswith(('#','<!--','|','표 1.')):
        assert norm(b) in norm(draft),b[:60]
        front_paragraphs.append(b)
for n in range(1,5):
    fig=PAPER/f'manuscript/figures/figure-{n}.svg'
    assert fig.is_file() and 'font-family: Korean' not in read(fig)

ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
deck=ROOT/'output/presentation/REFOUND_EARLY_PAPER_FINAL.pptx'
verified_paragraphs=0
with zipfile.ZipFile(deck) as z:
    slide_names=sorted(n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n))
    assert len(slide_names)==6
    for name in slide_names:
        xml=ET.fromstring(z.read(name))
        for shape in xml.findall('.//p:sp',ns):
            pos=shape.find('./p:spPr/a:xfrm/a:off',ns)
            if pos is None or int(pos.get('x'))!=56*9525:continue
            for paragraph in shape.findall('./p:txBody/a:p',ns):
                text=''.join(t.text or '' for t in paragraph.findall('.//a:t',ns))
                if len(text)>85:
                    assert norm(text) in norm(front), (name,text[:50])
                    verified_paragraphs+=1
    native=ET.fromstring(z.read('ppt/slides/slide6.xml')).find('.//a:tbl',ns)
    assert native is not None
    cells=[norm(''.join(t.text or '' for t in cell.findall('.//a:t',ns))) for cell in native.findall('./a:tr/a:tc',ns)]
    table=next(b for b in front.split('\n\n') if b.startswith('| 연구 |'))
    expected=[norm(c.strip()) for line in table.splitlines() if not line.startswith('|---') for c in line.strip('|').split('|')]
    assert cells==expected
assert verified_paragraphs==10,verified_paragraphs

files={}
for name,count in [('REFOUND_FULL_MANUSCRIPT.pdf',19),('RESEARCH_FRONT_MATTER.pdf',4)]:
    f=ROOT/'output/pdf'/name;r=PdfReader(f)
    assert len(r.pages)==count
    text='\n'.join(p.extract_text() for p in r.pages)
    assert '\ufffd' not in text and '[[' not in text
    files[name]={'pages':count,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
files[deck.name]={'slides':6,'bytes':deck.stat().st_size,'sha256':hashlib.sha256(deck.read_bytes()).hexdigest()}
report={'status':'pass','placeholder_count':297,'reference_count':17,'front_paragraphs_synchronized':len(front_paragraphs),'slide_manuscript_paragraphs_verified_in_pptx':verified_paragraphs,'native_table_cells_verified':len(cells),'figures':4,'visual_qa':'All final PDF pages and six final slides inspected; see REVISION_STATUS.md for limits.','files':files}
(PAPER/'manuscript/FINAL_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
