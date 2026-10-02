from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
before={r['path']:r['sha256'] for r in json.loads((out/'protected-before.json').read_text(encoding='utf-8'))}
files=['START_HERE.md','AGENTS.md','docs/SESSION_HANDOFF_2026-09-18.md','docs/IMPROVEMENTS.md','output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md']
records=[{'path':rel,'before_sha256':before[rel],'after_sha256':hashlib.sha256((root/rel).read_bytes()).hexdigest()} for rel in files]
(out/'documentation-changes.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
