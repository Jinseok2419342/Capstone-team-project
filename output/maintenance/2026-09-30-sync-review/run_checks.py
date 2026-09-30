"""Run existing regressions with all runtime paths redirected away from real data."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def protected():
    files = list((ROOT / 'data').rglob('*')) + list((ROOT / 'dist').rglob('*'))
    files += list((ROOT / 'output/presentation').glob('*.pptx')) + list((ROOT / 'output/pdf').glob('*.pdf'))
    files += [ROOT / '.env']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}

before = protected()
(OUT / 'protected-before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
env = os.environ.copy()
data = OUT / 'isolated-data'
env.update(DATA_DIR=str(data), DB_PATH=str(data / 'tests.sqlite3'), CAPTURE_DIR=str(data / 'captures'),
           OPENAI_API_KEY='', GEMINI_API_KEY='', SMTP_PASSWORD='', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
node = Path('C:/Users/pppp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
commands = {
    'python-tests': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
    'frontend-tests': [str(node), '--test', 'tests/frontend/app.test.cjs'],
    'frontend-syntax': [str(node), '--check', 'static/app.js'],
    'dependencies': [sys.executable, '-m', 'pip', 'check'],
}
results = {}
for name, command in commands.items():
    with (OUT / (name + '.log')).open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    results[name] = result.returncode
    print(name, result.returncode, flush=True)
versions = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], env=env, text=True)
(OUT / 'test-environment.txt').write_text(versions, encoding='utf-8')
after = protected()
results['protected_file_count'] = len(before)
results['protected_unchanged'] = before == after
(OUT / 'checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results), flush=True)
sys.exit(0 if all(v == 0 for k, v in results.items() if k in commands) and before == after else 1)
