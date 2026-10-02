from pathlib import Path
import hashlib,json,os,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
targets=[]
for folder,files in {
 '2026-10-02-midterm-review':['.chart-data-b4i5w2','.chart-data-Gbbrsh','powerpoint-v4','candidate-v4.pptx','candidate-v4_reviewed.pptx','review-first-pass.pptx'],
 '2026-10-02-midterm-content-review':['.chart-data-aPFu0F','.chart-data-tp7vmG','powerpoint-v5','candidate-v5_content.pptx','candidate-v5_improved.pptx','REFOUND_PROJECT_MIDTERM_2026-10-02_v5_content.pptx','update_handoff.py'],
}.items():
    for name in files:
        path=root/'output/maintenance'/folder/name
        assert path.exists(),path
        assert path.resolve().is_relative_to(root.resolve()) and not path.is_symlink()
        members=list(path.rglob('*')) if path.is_dir() else [path]
        assert not any(p.is_symlink() or (getattr(p.stat(),'st_file_attributes',0)&0x400) for p in members)
        entries=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in members if p.is_file()]
        targets.append({'path':path.relative_to(root).as_posix(),'absolute':str(path.resolve()),'kind':'directory' if path.is_dir() else 'file','reason':'Temporary chart export' if name.startswith('.chart-') else 'Superseded first-pass rendering' if name.startswith('powerpoint-') else 'One-time documentation updater' if name=='update_handoff.py' else 'Superseded draft presentation','files':entries,'count':len(entries),'bytes':sum(e['bytes'] for e in entries)})
plan={'date':'2026-10-02','authorization':'User explicitly requested session handoff updates and removal of unnecessary caches/dummy data.','root':str(root),'targets':targets,'target_count':len(targets),'file_count':sum(t['count'] for t in targets),'bytes':sum(t['bytes'] for t in targets),'excluded':['.git','all final PPTX/PDF','final PowerPoint renders','app/source/tests','actual data and deployments','original screenshots and builder dependencies','historical validation logs'],'process_check':'Get-Process python*,node,POWERPNT returned no matching processes. CIM command-line query was denied; no process-dependent runtime/profile paths are deletion targets.'}
(out/'cleanup-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
excluded=[Path(t['absolute']) for t in targets]
protected=[]
for current,dirs,files in os.walk(root,followlinks=False):
    here=Path(current)
    dirs[:]=[d for d in dirs if d!='.git' and not (here/d).is_symlink() and here/d!=out and not any(here/d==x or (here/d).is_relative_to(x) for x in excluded)]
    for name in files:
        p=here/name
        if p.is_symlink() or any(p==x or p.is_relative_to(x) for x in excluded):continue
        protected.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
(out/'protected-before.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'targets':plan['target_count'],'files':plan['file_count'],'MiB':round(plan['bytes']/2**20,2),'protected':len(protected)},ensure_ascii=False))
