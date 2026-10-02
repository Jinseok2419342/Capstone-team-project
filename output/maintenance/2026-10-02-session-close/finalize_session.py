from pathlib import Path
from zipfile import ZipFile
import hashlib,json,re,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((out/'protected-before.json').read_text(encoding='utf-8'))
doc_changes=json.loads((out/'documentation-changes.json').read_text(encoding='utf-8'))
approved={d['path']:d['after_sha256'] for d in doc_changes}
for item in before:
    p=root/item['path']
    assert p.is_file(),item['path']
    assert sha(p)==approved.get(item['path'],item['sha256']),item['path']
checks=json.loads((out/'POST_CLEANUP_CHECKS.json').read_text(encoding='utf-8'))
plan=json.loads((out/'cleanup-plan.json').read_text(encoding='utf-8'))
assert all(not (root/t['path']).exists() for t in plan['targets'])
final=root/'output/presentation/REFOUND_PROJECT_MIDTERM_2026-10-02_v5_improved.pptx'
assert sha(final)=='d0ca0d989993f7367839e23e23dd3542ab426bdd90bcdddc9aea76388bb9c52f'
with ZipFile(final) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==30
for name in ['2026-10-02-midterm-review','2026-10-02-midterm-content-review']:
    assert len(list((root/'output/maintenance'/name/'powerpoint-final').glob('slide-*.png')))==30
    assert (root/'output/maintenance'/name/'korean_typography.py').is_file()
assert (root/'output/maintenance/2026-10-02-midterm-review/assets/detail.png').is_file()
assert (root/'output/maintenance/2026-09-22-quick-reset/browser-dashboard-1440.png').is_file()
assert (root/'docs/presentation/midterm/build_midterm_v5.mjs').is_file()
for rel in approved:
    text=(root/rel).read_text(encoding='utf-8')
    assert '\ufffd' not in text
    assert '다음 세션' in text and 'v5' in text,rel
subprocess.run(['git','diff','--check'],cwd=root,check=True)
assert not subprocess.run(['git','diff','--name-only','--','app','static','templates','tests','data','dist'],cwd=root,capture_output=True,check=True).stdout.strip()
status={'status':'complete','date':'2026-10-02','next_session_task':'Continue completing the existing v5 midterm PPT; review content, fill supported evidence and check all slides for Korean wrapping.','latest_ppt':final.relative_to(root).as_posix(),'latest_ppt_sha256':sha(final),'slides':30,'outline_topics':34,'source':'docs/presentation/midterm/build_midterm_v5.mjs','cleanup':checks,'handoff_documents_updated':list(approved),'protected_non_document_files_unchanged':len(before)-len(approved),'updated_document_hashes_verified':len(approved),'final_render_slides_preserved':{'v4':30,'v5':30},'original_build_reports_preserved':True,'post_cleanup_validation':'Package integrity, final hash, protected file hashes, builder assets, latest document pointers, Git whitespace and unchanged app paths verified. Historical check_final.py first-pass comparisons reference intentionally deleted intermediate renders.','app_pi_ai_smtp_tests_rerun':False,'committed_or_pushed':False,'remaining':['Actual Pi screenshots for slides 14–15','Agreed progress criteria and percentage for slide 9','Actual labeled AI responses and latency evidence for slide 19','Team confirmation of proposed detailed schedule and roles'],'proposed_not_completed':['Three consecutive demonstration rehearsals','Approximately forty pilot cases']}
(out/'SESSION_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':status['status'],'removed_files':checks['removed_files'],'removed_MiB':checks['removed_MiB'],'preserved':len(before),'documents':len(approved),'next':'v5 PPT completion'},ensure_ascii=False))
