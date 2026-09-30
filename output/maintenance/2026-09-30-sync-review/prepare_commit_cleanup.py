"""Inventory explicit disposable paths and fingerprint all other workspace files."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TARGETS = [
    'output/maintenance/2026-09-22-quick-reset/browser-profile-1790066635655224500',
    'output/maintenance/2026-09-22-quick-reset/browser-profile-1790066672484512100',
    'output/maintenance/2026-09-22-quick-reset/browser-profile-1790066733549901400',
    'output/maintenance/2026-09-22-quick-reset/test-runtime',
    'output/maintenance/2026-09-30-sync-review/runtime',
    'output/maintenance/2026-09-30-sync-review/isolated-data',
    'output/maintenance/2026-09-30-sync-review/package-check.tar.gz',
    'output/maintenance/2026-09-30-sync-review/package-check.tar.gz.sha256',
    'output/maintenance/2026-09-30-sync-review/sync_docs.py',
    'output/maintenance/2026-09-30-sync-review/frontend-syntax.log',
]
tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
plan = []
for name in TARGETS:
    target = ROOT / name
    assert target.resolve().is_relative_to(ROOT)
    assert target.exists(), name
    assert not target.is_symlink(), name
    files = [p for p in target.rglob('*') if p.is_file()] if target.is_dir() else [target]
    plan.append({'path': name, 'kind': 'directory' if target.is_dir() else 'file',
                 'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
                 'tracked_files': sum(p.relative_to(ROOT).as_posix() in tracked for p in files)})
protected = {}
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d != '.git' and (Path(base)/d).relative_to(ROOT).as_posix() not in TARGETS]
    for name in files:
        p = Path(base)/name
        rel = p.relative_to(ROOT).as_posix()
        if rel in TARGETS or p.name.startswith('commit-cleanup-'):
            continue
        protected[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
record = {'date': '2026-09-30', 'workspace': str(ROOT),
          'authorization': 'User requested unnecessary files/caches cleanup before their full commit.',
          'process_check': 'Read-only elevated Win32_Process query found no matching browser or verification runtime process.',
          'targets': plan, 'total_files': sum(x['files'] for x in plan),
          'total_bytes': sum(x['bytes'] for x in plan), 'tracked_deletions_expected': sum(x['tracked_files'] for x in plan)}
(OUT/'commit-cleanup-plan.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT/'commit-cleanup-protected.json').write_text(json.dumps(protected, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'targets':len(plan), 'files':record['total_files'], 'MiB':round(record['total_bytes']/1024**2,2),
                  'tracked_deletions':record['tracked_deletions_expected'], 'protected_files':len(protected)}))
