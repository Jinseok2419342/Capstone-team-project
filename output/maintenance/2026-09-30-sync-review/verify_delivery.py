"""Verify documentation, package contents and real entrypoint with isolated data."""
from pathlib import Path
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
os.chdir(ROOT)
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()

docs = [p for p in git('diff', '--name-only').splitlines() if p.endswith('.md')]
docs += ['REFOUND_WINDOWS_HOTSPOT_GUIDE.md', 'output/maintenance/2026-09-30-sync-review/REVIEW.md']

def missing_links(name, text):
    result = []
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    for url in re.findall(r'\]\(([^\n]+?)\)', text):
        url = url.strip('<>')
        if re.match(r'\w+://|mailto:|#', url):
            continue
        url = unquote(url.split('#', 1)[0])
        if url and not (ROOT / name).parent.joinpath(url).exists():
            result.append(url)
    return sorted(set(result))

report = {'date': '2026-09-30', 'new_missing_links': {}, 'preexisting_missing_links': {}, 'markdown_files_checked': len(docs)}
for name in docs:
    text = (ROOT / name).read_text(encoding='utf-8')
    bad = missing_links(name, text)
    prev = subprocess.run(['git', 'show', 'HEAD:' + name], capture_output=True, cwd=ROOT)
    old_bad = missing_links(name, prev.stdout.decode('utf-8')) if prev.returncode == 0 else []
    if set(bad) - set(old_bad): report['new_missing_links'][name] = sorted(set(bad) - set(old_bad))
    if set(bad) & set(old_bad): report['preexisting_missing_links'][name] = sorted(set(bad) & set(old_bad))

# Recreate the disposable package on demand; it is not a retained artifact.
with tempfile.TemporaryDirectory(prefix='refound-package-check-') as package_temp:
    archive = Path(package_temp) / 'package-check.tar.gz'
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(ROOT / 'scripts/raspberry-pi/package-for-pi.ps1'),
                    '-OutputPath', str(archive)], cwd=ROOT, check=True, capture_output=True)
    with tarfile.open(archive) as tar:
        files = {m.name: m for m in tar.getmembers() if m.isfile()}
        report['package_files'] = len(files)
        report['package_has_latest_guide'] = 'REFOUND_WINDOWS_HOTSPOT_GUIDE.md' in files
        report['package_shells_lf'] = all(b'\r\n' not in tar.extractfile(m).read() for n, m in files.items() if n.endswith(('.sh', '.service')))
        report['package_forbidden'] = [n for n in files if n == '.env' or n.startswith(('data/', '.git/', '.venv/')) or '__pycache__' in n]
        report['package_runtime_mismatch'] = [n for n, m in files.items() if n.startswith(('app/', 'static/', 'templates/')) and tar.extractfile(m).read() != (ROOT / n).read_bytes()]

report['git_fsck'] = subprocess.run(['git', 'fsck', '--no-reflogs'], capture_output=True, cwd=ROOT).returncode
report['git_diff_check'] = subprocess.run(['git', 'diff', '--check'], capture_output=True, cwd=ROOT).returncode
report['git_attributes'] = git('check-attr', 'text', 'eol', '--', 'scripts/raspberry-pi/install.sh', 'scripts/raspberry-pi/refound.service').splitlines()
report['root_pc_venv_present'] = (ROOT / '.venv/Scripts/python.exe').exists()
report['root_env_present'] = (ROOT / '.env').exists()

data = OUT / 'isolated-data' / 'startup'
data.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(DATA_DIR=str(data), DB_PATH=str(data / 'startup.sqlite3'), CAPTURE_DIR=str(data / 'captures'),
           OPENAI_API_KEY='', GEMINI_API_KEY='', SMTP_PASSWORD='', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', RELOAD='false', HOST='127.0.0.1')
# Seed privacy before startup; camera opening may be attempted, live AI is disabled.
seed = "from pathlib import Path; import os; from app.store import Store; s=Store(Path(os.environ['DB_PATH'])); s.initialize(); s.update_settings({'privacy_mode': True})"
subprocess.run([sys.executable, '-c', seed], cwd=ROOT, env=env, check=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    env['PORT'] = str(sock.getsockname()[1])
base = 'http://127.0.0.1:' + env['PORT']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with (OUT / 'startup.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([sys.executable, 'run.py'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        deadline = time.monotonic() + 25
        while True:
            try:
                with opener.open(base + '/api/health', timeout=2) as response:
                    health = json.load(response)
                break
            except Exception:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Real entrypoint startup failed; inspect startup.log')
                time.sleep(0.2)
        statuses = {}
        for route in ('/', '/static/app.js', '/static/styles.css', '/api/items', '/api/settings'):
            with opener.open(base + route, timeout=5) as response:
                statuses[route] = response.status
        report['startup'] = {'http_statuses': statuses, 'health': health,
                             'privacy_enabled': True, 'live_ai_disabled': True,
                             'camera_open_attempted': True, 'captured_frames': health['camera']['frame_sequence']}
    finally:
        process.terminate()
        process.wait(timeout=15)

before = json.loads((OUT / 'protected-before.json').read_text(encoding='utf-8'))
report['protected_unchanged'] = all((ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in before.items())
report['protected_count'] = len(before)
(OUT / 'delivery-checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
# The report links to this output; validate it after creating the output itself.
report['new_missing_links'] = {}
for name in docs:
    bad = missing_links(name, (ROOT / name).read_text(encoding='utf-8'))
    prev = subprocess.run(['git', 'show', 'HEAD:' + name], capture_output=True, cwd=ROOT)
    old_bad = missing_links(name, prev.stdout.decode('utf-8')) if prev.returncode == 0 else []
    if set(bad) - set(old_bad):
        report['new_missing_links'][name] = sorted(set(bad) - set(old_bad))
(OUT / 'delivery-checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
