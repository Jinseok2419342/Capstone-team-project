from pathlib import Path
import hashlib, json, os

audit = Path(__file__).resolve().parent
root = audit.parents[2]
build = root/'output/maintenance/2026-09-22-midterm-build'
quick = root/'output/maintenance/2026-09-22-quick-reset'
targets = []
def add(p, reason):
    if not p.exists(): return
    assert p.is_relative_to(root)
    kind = 'junction' if p.is_junction() else ('directory' if p.is_dir() else 'file')
    files = [] if kind == 'junction' else ([p] if kind == 'file' else [f for f in p.rglob('*') if f.is_file()])
    if kind == 'directory':
        assert not any(f.is_symlink() or f.is_junction() for f in p.rglob('*')), str(p)
    targets.append({'relative_path':p.relative_to(root).as_posix(),'absolute_path':str(p),'kind':kind,'reason':reason,'files':len(files),'bytes':sum(f.stat().st_size for f in files)})

for p in sorted(root.glob('.chart-data-*')): add(p,'PPT chart workbook packaging scratch, final values already embedded')
for rel in ['app/__pycache__','experiments/__pycache__','scripts/raspberry-pi/__pycache__','tests/__pycache__','output/maintenance/2026-09-18-live-flow-review/__pycache__']:
    add(root/rel,'Regenerable Python bytecode cache')
add(quick/'uv-cache','Package download cache; installed test-runtime preserved')
for p in sorted(quick.glob('browser-fixture-*')): add(p,'Isolated synthetic browser test DB/images, not operational data')
# Browser profiles are left alone because active process inventory could not be read.
for name in ['render-v1','render-v2']: add(build/name,'Superseded slide previews; final render-v3 and all validation receipts preserved')
for pat in ['candidate-*.pptx','candidate-*.pptx.inspect.ndjson','superseded-*.pptx']:
    for p in sorted(build.glob(pat)): add(p,'Intermediate generated deck or inspection dump, final v3 and authoring source preserved')
add(build/'node_modules','Remove junction only; external bundled runtime must stay untouched')
plan={'workspace':str(root),'authorized_by':'User explicitly requested end-of-session cache and unnecessary data cleanup, 2026-09-22','targets':targets,'file_count':sum(t['files'] for t in targets),'bytes':sum(t['bytes'] for t in targets),'preserve':['data','dist','app source','paper artifacts','final PPT and guide','render-v3','validation logs and source backups','.venv','installed test-runtime','browser profiles (active-process status unavailable)']}
(audit/'cleanup-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
excluded={Path(t['absolute_path']) for t in targets}
editing={root/s for s in ['START_HERE.md','AGENTS.md','docs/SESSION_HANDOFF_2026-09-18.md','docs/IMPROVEMENTS.md', 'output/maintenance/2026-09-22-midterm-build/check_delivery.py']}
skip={root/'.venv',quick/'test-runtime',audit,*[p for p in quick.glob('browser-profile-*')]}
protected={}
for base, dirs, files in os.walk(root,followlinks=False):
    dirs[:]=[d for d in dirs if Path(base,d) not in excluded|skip and not Path(base,d).is_junction() and not Path(base,d).is_symlink()]
    for name in files:
        p=Path(base,name)
        if p not in excluded|editing:
            protected[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
(audit/'protected-before.json').write_text(json.dumps(protected,indent=2),encoding='utf-8')
render_hashes={f'{r}/{p.name}':hashlib.sha256(p.read_bytes()).hexdigest() for r in ['render-v1','render-v2','render-v3'] for p in (build/r).glob('*.png')}
(audit/'render-hashes-before.json').write_text(json.dumps(render_hashes,indent=2),encoding='utf-8')
print(json.dumps({'targets':len(targets),'files':plan['file_count'],'MiB':round(plan['bytes']/2**20,2),'protected':len(protected)}))
