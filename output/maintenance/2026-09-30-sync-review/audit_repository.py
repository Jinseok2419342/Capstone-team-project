"""Read-only source/import review; never imports the application or reads secrets."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def digest(data):
    return hashlib.sha256(data).hexdigest()

tracked = git('ls-files', '-z').decode().split('\0')[:-1]
changes = git('diff', 'HEAD^', 'HEAD', '--name-status').decode().splitlines()
report = {
    'date': '2026-09-30', 'head': git('rev-parse', 'HEAD').decode().strip(),
    'parent': git('rev-parse', 'HEAD^').decode().strip(),
    'tracked_files': len(tracked), 'commit_changes': len(changes),
    'deleted_in_commit': [x for x in changes if x.startswith('D\t')],
    'tracked_browser_profile_files': sum('/browser-profile-' in p for p in tracked),
    'tracked_runtime_or_secret_paths': [p for p in tracked if p == '.env' or p.startswith(('data/', '.venv/', 'dist/'))],
    'missing_tracked_files': [p for p in tracked if not (ROOT / p).exists()],
    'python_syntax_errors': [], 'conflict_markers': [],
    'archive_comparison': {},
}
for base in ('app', 'experiments', 'scripts', 'tests'):
    for path in (ROOT / base).rglob('*.py'):
        try:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            report['python_syntax_errors'].append([path.relative_to(ROOT).as_posix(), str(exc)])
for p in tracked:
    if p.startswith(('app/', 'static/', 'templates/', 'scripts/', 'tests/', 'experiments/')) and Path(p).suffix in ('.py', '.js', '.cjs', '.html', '.css', '.sh', '.ps1'):
        for line_no, line in enumerate((ROOT / p).read_text(encoding='utf-8-sig').splitlines(), 1):
            if line.startswith(('<<<<<<< ', '>>>>>>> ')) or line == '=======':
                report['conflict_markers'].append([p, line_no])
archive = ROOT / 'dist/refound-pi.tar.gz'
if archive.exists():
    ar = report['archive_comparison']
    ar['sha256'] = digest(archive.read_bytes())
    ar['matches_install_record'] = ar['sha256'] == '92007237f6cf4ee5fdeb2e099961153893012e8f9c0ad8f1be7596c2127cf4ae'
    ar['missing'] = []; ar['different'] = []; ar['newline_only'] = []; ar['same'] = []
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name.removeprefix('./')
            local = ROOT / name
            if not local.is_file():
                ar['missing'].append(name); continue
            old = tar.extractfile(member).read(); new = local.read_bytes()
            if old == new:
                ar['same'].append(name)
            elif old.replace(b'\r\n', b'\n') == new.replace(b'\r\n', b'\n'):
                ar['newline_only'].append(name)
            else:
                ar['different'].append(name)
    for k in ('same', 'newline_only'):
        ar[k + '_count'] = len(ar[k])
else:
    report['archive_comparison']['present'] = False
ledger = json.loads((ROOT / 'output/maintenance/2026-09-22-session-close/protected-before.json').read_text(encoding='utf-8-sig'))
report['protected_ledger_shape'] = list(ledger)[:8] if isinstance(ledger, dict) else {'list_length': len(ledger)}
(OUT / 'repository-before.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
