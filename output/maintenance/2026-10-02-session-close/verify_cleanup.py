from pathlib import Path
import hashlib,json,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((out/'cleanup-plan.json').read_text(encoding='utf-8'))
before=json.loads((out/'protected-before.json').read_text(encoding='utf-8'))
assert all(not (root/t['path']).exists() for t in plan['targets'])
modified=[]
for item in before:
    path=root/item['path']
    assert path.is_file(),item['path']
    if sha(path)!=item['sha256']:modified.append(item['path'])
assert not modified,modified
result={'status':'complete','removed_targets':plan['target_count'],'removed_files':plan['file_count'],'removed_bytes':plan['bytes'],'removed_MiB':round(plan['bytes']/2**20,2),'protected_files_verified_unchanged':len(before),'all_targets_absent':True,'app_or_pi_tests_rerun':False}
(out/'POST_CLEANUP_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
