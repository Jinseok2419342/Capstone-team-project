from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import hashlib, json, re, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

root=Path(__file__).resolve().parents[3]
build=Path(__file__).resolve().parent
final=root/'output/presentation/REFOUND_PROJECT_MIDTERM_2026-10-02_v5_improved.pptx'
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected={}
for rel in ['output/presentation/REFOUND_PROJECT_MIDTERM_2026-09-22_v3.pptx','docs/presentation/midterm/build_midterm.mjs']:
    prior=subprocess.run(['git','show',f'HEAD:{rel}'],cwd=root,capture_output=True,check=True).stdout
    current=(root/rel).read_bytes()
    assert (prior==current) if rel.endswith('.pptx') else (prior.replace(b'\r\n',b'\n')==current.replace(b'\r\n',b'\n'))
    protected[rel]=sha(root/rel)
v4=root/'output/presentation/REFOUND_PROJECT_MIDTERM_2026-10-02_v4_reviewed.pptx'
assert sha(v4)=='aff59e8440b89bd8f4b9d21c00b1e790b4df69ea2a997188db6815dbbdce721c'
protected[str(v4.relative_to(root))]=sha(v4)
with ZipFile(final) as z:
    parts=sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda n:int(re.search(r'slide(\d+)',n)[1]))
    assert len(parts)==30
    slides=[E.fromstring(z.read(n)) for n in parts]
    texts=[' '.join(s.xpath('//a:t/text()',namespaces=ns)) for s in slides]
    alltext='\n'.join(texts)
    assert '[입력]' not in alltext and 'FILL_S' not in alltext
    assert '산정 기준 미확정' in texts[8] and '미측정' in texts[18]
    assert all(s in texts[10] for s in ['258efc1','956b346','69eb6ff'])
    assert all(s in texts[20] for s in ['272','37','7','9/30','9/22'])
    assert '당일 모델명은 미수집' in texts[17]
    assert '합성' in texts[13] and '합성' in texts[14]
    assert '실제 측정 결과가 아님' in texts[2]
    assert '앞으로 수행할' in texts[24] and '제안 실험 설계' in texts[29]
    paragraphs=[p for s in slides for p in s.findall('.//a:pPr',ns)]
    assert all(p.get('eaLnBrk')=='0' and p.get('latinLnBrk')=='0' for p in paragraphs)
    tables=sum(len(s.findall('.//a:tbl',ns)) for s in slides)
    charts=[n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n)]
    assert len(charts)==1
    values=[float(v) for v in E.fromstring(z.read(charts[0])).xpath('//c:numCache/c:pt/c:v/text()',namespaces=ns)]
    assert values==[27.756,13.212]
    assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')])==1
    notes=[n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n)]
    assert len(notes)==30
    for forbidden in ['tail7a1a61','192.168.137.243','sk-proj-']:
        assert forbidden not in alltext

guide=(root/'output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md').read_text(encoding='utf-8')
outline=(root/'docs/presentation/midterm/OUTLINE_REFERENCE.md').read_text(encoding='utf-8')
expected=set(re.findall(r'^#### ([1-7]\.\d)',outline,re.M))
mapping=[]
for line in guide.splitlines():
    m=re.match(r'^\| ([1-7]\.\d) (.*?) \| (.*?) \| (.*?) \|$',line)
    if m: mapping.append({'topic':m[1],'name':m[2],'slides':m[3],'treatment':m[4]})
assert {m['topic'] for m in mapping}==expected and len(mapping)==34
(build/'outline-coverage.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')

native=json.loads((build/'powerpoint-final/text-layout.json').read_text(encoding='utf-8-sig'))
assert len(native)==511
assert not [r for r in native if r['overflowW'] or r['overflowH']]
boundaries=0
for r in native:
    assert '\ufffd' not in r['text']
    for a,b in zip(r['lines'],r['lines'][1:]):
        boundaries+=1
        assert a['text'].endswith(('\r','\n','\v',' ')),(r['slide'],a,b)
        assert not (re.search('[가-힣]$',a['text']) and re.match('[가-힣]',b['text']))
assert len(list((build/'powerpoint-final').glob('slide-*.png')))==30
changed=[i for i in range(1,31) if sha(build/'powerpoint-v5'/f'slide-{i:02}.png')!=sha(build/'powerpoint-final'/f'slide-{i:02}.png')]
assert changed==[5,15,17,18,26],changed
receipt=json.loads((build/'validation-v5_improved.json').read_text(encoding='utf-8'))
assert receipt['finalSha256']==sha(final)
assert receipt['packageIntegrity']['status']=='pass'
assert receipt['presentationLayout']['finding_count']==0
assert receipt['nativeChartValidation']['passed'] and receipt['firstPartyImport']['passed']

# Evidence traceability: compare source assertions to the preserved complete suite run.
cases={
 'tests/test_app_resilience.py':['test_executor_rejection_preserves_item_and_releases_slot','test_late_classification_preserves_manual_extension'],
 'tests/test_reset.py':['test_quick_reset_skips_backup_and_preserves_settings_and_existing_backups'],
 'tests/test_services.py':['test_scheduler_lock_prevents_concurrent_duplicate_email'],
}
for rel,names in cases.items():
    current=(root/rel).read_text(encoding='utf-8')
    assert all('def '+name+'(' in current for name in names)
log=(root/'output/maintenance/2026-09-30-sync-review/python-tests.log').read_text(encoding='utf-8')
assert 'Ran 272 tests' in log and '\nOK' in log
assert not subprocess.run(['git','diff','--name-only','--','app','static','templates','tests','dist','data'],cwd=root,capture_output=True,check=True).stdout.strip()
for rel in ['START_HERE.md','AGENTS.md','docs/IMPROVEMENTS.md','docs/SESSION_HANDOFF_2026-09-18.md','output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md']:
    content=(root/rel).read_text(encoding='utf-8')
    assert final.name in content
    assert '\ufffd' not in content

result={'status':'passed','date':'2026-10-02','final':str(final.relative_to(root)),'sha256':sha(final),'slide_count':30,'outline_topics':34,'outline_scope':'Topic coverage only; missing actual measurements and official progress are explicitly disclosed.','editable_tables':tables,'editable_charts':1,'chart_source_ms':values,'native_powerpoint_opened':True,'native_rendered_slides':30,'native_text_areas':len(native),'text_overflow_findings':0,'checked_line_boundaries':boundaries,'unexpected_line_breaks':0,'korean_paragraph_protection_count':len(paragraphs),'visual_review':'All 30 first-pass native PowerPoint renders individually inspected; final changed slides 5,15,17,18,26 re-inspected; other 25 final renders byte-identical.','protected_originals':protected,'app_or_pi_tests_rerun':False,'test_case_sources':cases,'limitations':['Official project/function percentages need agreed completion criteria.','Quantitative AI results, individual evidence and actual Pi screenshots remain uncollected.','Slides 14–15 use disclosed synthetic development screenshots.','Three rehearsals and approximately forty pilot cases are proposed future targets, not completed trials.']}
(build/'FINAL_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
