from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_pi_deployment import PI_SCRIPTS, available_bash


class RuntimeImportTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("pi_runtime_check", PI_SCRIPTS / "check-runtime.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_success_checks_camera_and_web_imports_without_importing_application(self):
        output = io.StringIO()
        with patch.object(self.module.importlib, "import_module", return_value=SimpleNamespace(__version__="test")) as load:
            with redirect_stdout(output):
                result = self.module.main()
        self.assertEqual(result, 0)
        self.assertEqual([call.args[0] for call in load.call_args_list], [entry[0] for entry in self.module.MODULES])
        self.assertNotIn("app.main", output.getvalue())

    def test_binary_import_failure_is_reported_and_does_not_hide_other_checks(self):
        def load(name):
            if name == "cv2":
                raise ImportError("synthetic NumPy ABI mismatch")
            return SimpleNamespace(__version__="test")
        output = io.StringIO()
        with patch.object(self.module.importlib, "import_module", side_effect=load):
            with redirect_stdout(output):
                result = self.module.main()
        self.assertEqual(result, 1)
        self.assertIn("FAIL: cv2", output.getvalue())
        self.assertIn("OK: httpx", output.getvalue())


@unittest.skipUnless(available_bash(), "Bash is required")
class SystemCheckTests(unittest.TestCase):
    def check(self, *, privacy=False, connected=True, healthy=True):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "lib").mkdir()
            (root / "runtime").mkdir()
            (root / "app/.venv/bin").mkdir(parents=True)
            source = (PI_SCRIPTS / "lib/common.sh").read_text(encoding="utf-8").replace(
                'readonly REFOUND_RUNTIME_DIR="/etc/refound"',
                'readonly REFOUND_RUNTIME_DIR="${PWD}/runtime"',
            )
            (root / "lib/common.sh").write_text(source, encoding="utf-8", newline="\n")
            (root / "check-system.sh").write_text((PI_SCRIPTS / "check-system.sh").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            (root / "runtime/runtime.env").write_text("HOST=10.42.0.1\nPORT=8100\n", encoding="utf-8")
            fake_python = root / "app/.venv/bin/python"
            fake_python.write_text("#!/bin/sh\necho 'OK: synthetic runtime'\n", encoding="utf-8", newline="\n")
            fake_python.chmod(0o755)
            (root / "health.json").write_text(json.dumps({
                "ok": healthy, "database": "connected" if healthy else "unavailable",
                "hardware_profile": "raspberry-pi", "camera": {
                    "camera_connected": connected, "privacy_enabled": privacy,
                    "inventory_connected": True, "pending_changes": 0, "phase": "monitoring",
                }, "provider": {"active": "offline"},
            }), encoding="utf-8")
            commands = r'''
export REFOUND_APP_DIR="${PWD}/app"
df() { printf 'synthetic storage\n'; }
free() { printf 'synthetic memory\n'; }
systemctl() { [[ "$1" == "is-active" ]] || return 90; printf 'active\n'; }
curl() { printf '%s\n' "$*" > curl.calls; cat health.json; }
vcgencmd() { printf 'synthetic sensor\n'; }
python3() { "${TEST_PYTHON}" "$@"; }
source ./check-system.sh
'''
            result = subprocess.run(
                [available_bash(), "--noprofile", "--norc", "-c", commands], cwd=root,
                env={**os.environ, "TEST_PYTHON": sys.executable.replace("\\", "/"), "REFOUND_PORT": "9999"},
                capture_output=True, text=True, timeout=15,
            )
            calls = (root / "curl.calls").read_text(encoding="utf-8")
        return result, calls

    def test_reads_saved_address_without_changing_services_or_calling_remote_ai(self):
        result, calls = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("http://10.42.0.1:8100/api/health", calls)
        self.assertIn("Local checks passed", result.stdout)
        self.assertIn("not a live API test", result.stdout)

    def test_privacy_camera_and_database_failures_need_attention(self):
        for values in ({"privacy": True}, {"connected": False}, {"healthy": False}):
            with self.subTest(values=values):
                result, _ = self.check(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("need attention", result.stderr)


if __name__ == "__main__":
    unittest.main()
