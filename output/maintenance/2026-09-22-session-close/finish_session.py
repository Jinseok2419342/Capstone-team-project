from pathlib import Path
from urllib.parse import unquote
import hashlib, json, re

audit=Path(__file__).resolve().parent
root=audit.parents[2]
plan=json.loads((audit/'cleanup-plan.json').read_text(encoding='utf-8'))
protected=json.loads((audit/'protected-before.json').read_text(encoding='utf-8'))
changed=[name for name,h in protected.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=h]
remaining=[t['relative_path'] for t in plan['targets'] if Path(t['absolute_path']).exists()]
assert not changed and not remaining, (changed,remaining)
docs=['START_HERE.md','AGENTS.md','docs/SESSION_HANDOFF_2026-09-18.md','docs/IMPROVEMENTS.md','output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md']
links=0
missing=[]
for rel in docs:
    p=root/rel
    for target in re.findall(r'\[[^\]]*\]\(([^\n)]+)\)',p.read_text(encoding='utf-8')):
        target=target.strip().strip('<>')
        if target.startswith(('https:','http:','#','mailto:')):continue
        target=unquote(target.split('#',1)[0])
        if not target:continue
        links+=1
        if not (p.parent/target).exists():missing.append({'file':rel,'target':target})
assert not missing,missing
runtime=Path('C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')
assert runtime.is_file()
checks=json.loads((root/'output/maintenance/2026-09-22-midterm-build/POST_CLEANUP_CHECKS.json').read_text(encoding='utf-8'))
assert checks['status']=='passed'
status={
 'record_date':'2026-09-22','status':'complete','user_request':'End work today after provisional acceptance of the midterm PPT; prepare next-session handoff and delete caches/unnecessary generated data.',
 'user_acceptance':'일단 좋아 (provisional draft acceptance, not completion of missing evidence)',
 'next_default':'Review existing v3 PPT and fill captures step by step using its guide; do not recreate or launch measurements automatically.',
 'read_order':['START_HERE.md','AGENTS.md latest session-close section','docs/SESSION_HANDOFF_2026-09-18.md sections 0 and 6','output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md'],
 'artifacts':{'pptx':'output/presentation/REFOUND_PROJECT_MIDTERM_2026-09-22_v3.pptx','sha256':checks['final_sha256'],'guide':'output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md','slides':30,'main':27,'appendix':3,'native_powerpoint_opened':False},
 'remaining_presentation_inputs':{'11':'S1 Git history and repository URL','14':'S2/S3/S4 same physical item registration, move and removal screenshots with separately verified ID captions','15':'S5 real Pi administrator screenshot','9':'Official progress percent after criteria agreement','19':'Measured accuracy/latency, N and actual cases'},
 'schedule':{'midterm_presentation':'2026-10-13','final_rehearsal':'2026-10-27','final_presentation':'2026-11-03'},
 'demo_state':'Friend share invitation sent, acceptance/laptop/hotspot unconfirmed; prior installation and owner-PC access already confirmed. Actual shutdown/power removal still unreported.',
 'cleanup':{'status':'complete','targets_removed':len(plan['targets']),'file_count_removed':plan['file_count'],'logical_bytes_removed':plan['bytes'],'MiB':round(plan['bytes']/2**20,2),'junctions_removed':1,'remaining_targets':remaining,'external_runtime_preserved':True,'browser_profiles_preserved':3,'browser_profile_reason':'Read-only process inventory through WMI returned access denied; active use not established, no profiles deleted.','installed_environments_preserved':['.venv','output/maintenance/2026-09-22-quick-reset/test-runtime']},
 'verification':{'protected_files':len(protected),'changed_protected_files':changed,'local_links_checked':links,'missing_local_links':missing,'final_artifact_post_cleanup_check':'passed','final_rendered_slides_preserved':30,'old_renders':'Removed v1/v2; saved pre-cleanup image hashes support historical comparisons.','app_tests_rerun':False,'new_pi_ai_smtp_experiments':False},
 'handoff_document_sha256':{r:hashlib.sha256((root/r).read_bytes()).hexdigest() for r in docs}
}
(audit/'SESSION_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cleanup':'complete','targets':len(plan['targets']),'files':plan['file_count'],'MiB':status['cleanup']['MiB'],'protected_unchanged':len(protected),'links_ok':links,'artifact':'passed'},ensure_ascii=False))
