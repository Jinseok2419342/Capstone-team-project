from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile

root = Path(__file__).resolve().parents[3]
build = Path(__file__).resolve().parent
final = root / 'output/presentation/REFOUND_PROJECT_MIDTERM_2026-09-22_v3.pptx'
ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart'}
with zipfile.ZipFile(final) as z:
    slides = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)), key=lambda s: int(re.search(r'slide(\d+)\.xml', s).group(1)))
    texts = ['\n'.join(ET.fromstring(z.read(n)).itertext()) for n in slides]
    notes = [n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml', n)]
    note_text = '\n'.join(' '.join(ET.fromstring(z.read(n)).itertext()) for n in notes)
    assert len(slides) == len(notes) == 30
    assert 'undefined' not in note_text
    assert '2026-09-22' in note_text
    assert all(f'S{i}' in '\n'.join(texts) for i in range(1, 6))
    assert '[입력]' in texts[8] and '[입력]' in texts[18]
    assert 'gpt-5.6-luna' in texts[17]
    assert all(v in texts[20] for v in ('272', '37', '7'))
    charts = [n for n in z.namelist() if re.fullmatch(r'ppt/slides/charts/chart\d+\.xml', n)]
    assert len(charts) == 1
    chart = ET.fromstring(z.read(charts[0]))
    chart_vals = [float(n.text) for n in chart.findall('.//c:numCache/c:pt/c:v', ns)]
    assert chart_vals == [27.756, 13.212], chart_vals
    assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')]) == 1
    fulltext = '\n'.join(texts) + note_text
    for sensitive in ('tail7a1a61', '192.168.0.2', 'fe80::', 'sk-proj-'):
        assert sensitive not in fulltext

guide = (root/'output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md').read_text(encoding='utf-8')
topics = set(re.findall(r'^\| ([1-7]\.\d) ', guide, re.M))
assert len(topics) == 34, len(topics)
assert '/api/items?sort=newest&limit=10' in guide
render = build/'render-v3'
assert len(list(render.glob('*.png'))) == 30
historical_comparison_reused = not ((build/'render-v1').is_dir() and (build/'render-v2').is_dir())
if historical_comparison_reused:
    # The user authorized removal of obsolete renders after visual inspection.
    # Reuse their saved hashes; do not claim a new visual review of deleted images.
    ledger = json.loads((build.parent/'2026-09-22-session-close/render-hashes-before.json').read_text(encoding='utf-8'))
    names = [f'slide-{i:02}.png' for i in range(1,31)]
    assert all(hashlib.sha256((render/n).read_bytes()).hexdigest() == ledger[f'render-v3/{n}'] for n in names)
    changed_v1_v2 = [n for n in names if ledger[f'render-v1/{n}'] != ledger[f'render-v2/{n}']]
    changed_v2_v3 = [n for n in names if ledger[f'render-v2/{n}'] != ledger[f'render-v3/{n}']]
else:
    changed_v1_v2 = [f.name for f in (build/'render-v1').glob('*.png') if f.read_bytes() != (build/'render-v2'/f.name).read_bytes()]
    changed_v2_v3 = [f.name for f in (build/'render-v2').glob('*.png') if f.read_bytes() != (render/f.name).read_bytes()]
assert set(changed_v1_v2) == {f'slide-{n:02}.png' for n in [5,9,13,21,24]}
assert set(changed_v2_v3) == {'slide-05.png','slide-21.png'}
quick = json.loads((root/'output/maintenance/2026-09-22-quick-reset/VALIDATION.json').read_text(encoding='utf-8-sig'))
protected = {}
for file in ['app/main.py','static/app.js']:
    protected[file] = hashlib.sha256((root/file).read_bytes()).hexdigest()
    assert protected[file] == quick['hashes'][file]
state = json.loads((root/'output/maintenance/2026-09-22-network-plan/SESSION_STATUS.json').read_text(encoding='utf-8-sig'))
protected['dist/refound-pi.tar.gz'] = hashlib.sha256((root/'dist/refound-pi.tar.gz').read_bytes()).hexdigest()
assert protected['dist/refound-pi.tar.gz'] == state['deployment']['sha256']
receipt = json.loads((build/'validation-v3.json').read_text(encoding='utf-8'))
assert receipt['packageIntegrity']['status'] == 'pass'
assert receipt['presentationLayout']['finding_count'] == 0
assert receipt['firstPartyImport']['passed']
assert receipt['nativeChartValidation']['passed']
result = {
    'status': 'passed', 'final': str(final.relative_to(root)),
    'final_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
    'slides':30, 'main_slides':27, 'appendix_slides':3,
    'source_outline_subtopics':len(topics), 'notes_with_source_references':30,
    'editable_tables':receipt['nativeTableArithmetic']['native_table_count'],
    'editable_charts':1, 'chart_values_ms':chart_vals,
    'intentional_screenshot_slots':['S1','S2','S3','S4','S5'],
    'intentional_missing_values':['official progress percent','field AI evaluation','individual success/error samples'],
    'visual_review':'All v1 slides individually inspected at 1280x720; all changed v2 and v3 slides inspected. Unchanged render hashes matched. Final deck rendered on all 30 slides.',
    'historical_render_comparison_reused':historical_comparison_reused,
    'native_powerpoint_opened':False, 'app_tests_rerun':False, 'actual_pi_or_remote_api_experiments':False,
    'verified_protected_hashes':protected,
    'data_basis':'2026-09-22 current code and prior development/acceptance records',
    'schedule_source':'User-provided class schedule: midterm 2026-10-13, rehearsal 2026-10-27, final 2026-11-03'
}
report_name = 'POST_CLEANUP_CHECKS.json' if historical_comparison_reused else 'FINAL_CHECKS.json'
(build/report_name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'slides':30,'coverage':len(topics),'sha256':result['final_sha256']}))
