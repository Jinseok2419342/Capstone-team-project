from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PI_SCRIPTS = ROOT / "scripts" / "raspberry-pi"


def available_bash() -> str | None:
    if os.name == "nt":
        # Windows' System32/bash.exe invokes WSL, not the current filesystem.
        for folder in ("ProgramFiles", "ProgramW6432"):
            candidate = Path(os.environ.get(folder, "C:/Program Files")) / "Git/bin/bash.exe"
            if candidate.is_file():
                return str(candidate)
        return None
    return shutil.which("bash")


@unittest.skipUnless(available_bash(), "Bash is required for isolated deployment checks")
class PiServiceInstallationTests(unittest.TestCase):
    def run_install_completion(
        self, runtime: str | None, *, unchanged_pid: bool = False, health_ok: bool = True
    ) -> tuple[subprocess.CompletedProcess, str, list[str], list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            # The production helper is executed against one managed temp tree.
            # Every systemd, curl, ownership, and sleep command is a shell fake.
            source = (PI_SCRIPTS / "lib/common.sh").read_text(encoding="utf-8")
            source = source.replace(
                'readonly REFOUND_RUNTIME_DIR="/etc/refound"',
                'readonly REFOUND_RUNTIME_DIR="${PWD}/runtime"',
            )
            (sandbox / "common.sh").write_text(source, encoding="utf-8", newline="\n")
            (sandbox / "runtime").mkdir()
            if runtime is not None:
                (sandbox / "runtime/runtime.env").write_text(runtime, encoding="utf-8", newline="\n")
            (sandbox / "service.pid").write_text("123\n", encoding="ascii")
            fake_commands = r'''
source ./common.sh
install() { [[ "$1" == "-d" ]] || return 91; mkdir -p "${@: -1}"; }
chown() { :; }
chmod() { :; }
sleep() { :; }
systemctl() {
    printf '%s\n' "$*" >> service.calls
    case "$1" in
        show) cat service.pid ;;
        daemon-reload|enable|status) return 0 ;;
        restart)
            if [[ "${UNCHANGED_PID}" != "1" ]]; then printf '456\n' > service.pid; fi ;;
        is-active) [[ "$(cat service.pid)" != "0" ]] ;;
        *) return 92 ;;
    esac
}
curl() {
    printf '%s\n' "$*" >> health.calls
    [[ "${HEALTH_OK}" == "1" ]]
}
prepare_install_runtime
restart_installed_service
'''
            result = subprocess.run(
                [available_bash(), "--noprofile", "--norc", "-c", fake_commands],
                cwd=sandbox,
                env={
                    **os.environ, "UNCHANGED_PID": "1" if unchanged_pid else "0",
                    "HEALTH_OK": "1" if health_ok else "0", "REFOUND_PORT": "9876",
                },
                capture_output=True, text=True, timeout=20,
            )
            persisted = (sandbox / "runtime/runtime.env").read_text(encoding="utf-8")
            service_calls = (sandbox / "service.calls").read_text(encoding="utf-8").splitlines()
            health_calls = (sandbox / "health.calls").read_text(encoding="utf-8").splitlines()
        return result, persisted, service_calls, health_calls

    def test_reinstall_preserves_each_access_mode_and_checks_a_new_process(self) -> None:
        for mode, address in (("local", "127.0.0.1"), ("tailscale", "127.0.0.1"), ("hotspot", "10.42.0.1")):
            with self.subTest(mode=mode):
                original = (
                    f"REFOUND_ACCESS_MODE={mode}\nHARDWARE_PROFILE=raspberry-pi\n"
                    f"HOST={address}\nPORT=8100\nRELOAD=false\n# Preserve other local choices\n"
                )
                result, persisted, calls, health = self.run_install_completion(original)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(persisted, original)
                self.assertIn("enable refound.service", calls)
                self.assertEqual(calls.count("restart refound.service"), 1)
                self.assertLess(calls.index("daemon-reload"), calls.index("restart refound.service"))
                self.assertTrue(any(f"http://{address}:8100/api/health" in call for call in health))
                self.assertIn("New service process 456", result.stdout)

    def test_first_install_creates_local_runtime_and_restarts(self) -> None:
        result, persisted, calls, health = self.run_install_completion(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REFOUND_ACCESS_MODE=local\n", persisted)
        self.assertIn("HOST=127.0.0.1\n", persisted)
        self.assertIn("PORT=9876\n", persisted)
        self.assertIn("restart refound.service", calls)
        self.assertTrue(any("http://127.0.0.1:9876/api/health" in call for call in health))

    def test_old_health_response_cannot_certify_an_unchanged_process(self) -> None:
        result, _, _, _ = self.run_install_completion("HOST=127.0.0.1\nPORT=8000\n", unchanged_pid=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("new running service process was not confirmed", result.stderr)

    def test_health_failure_does_not_report_installation_success(self) -> None:
        result, _, _, health = self.run_install_completion("HOST=10.42.0.1\nPORT=8000\n", health_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(health), 20)
        self.assertIn("restarted service did not become healthy", result.stderr)

    def test_all_pi_shell_scripts_parse(self) -> None:
        for script in PI_SCRIPTS.rglob("*.sh"):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [available_bash(), "-n", script.as_posix()],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(os.name == "nt", "The release packaging script runs on Windows")
class PiPackageTests(unittest.TestCase):
    def test_release_contains_school_guide_and_no_runtime_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "release.tar.gz"
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(PI_SCRIPTS / "package-for-pi.ps1"), "-OutputPath", str(archive)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with tarfile.open(archive, "r:gz") as package:
                entries = set(package.getnames())
            self.assertIn("docs/guides/SCHOOL_DEMO_GUIDE.md", entries)
            self.assertIn("docs/guides/PI_MONITOR_WIFI_GUIDE.md", entries)
            self.assertIn("docs/guides/FRESH_SD_START.md", entries)
            self.assertIn("docs/guides/PI_ACCEPTANCE_CHECKLIST.md", entries)
            self.assertIn("scripts/raspberry-pi/check-system.sh", entries)
            self.assertIn("scripts/raspberry-pi/check-runtime.py", entries)
            self.assertIn("scripts/raspberry-pi/lib/common.sh", entries)
            self.assertIn("app/classification.py", entries)
            self.assertIn("requirements-pi.txt", entries)
            self.assertFalse(any(name == ".env" or name.startswith("data/") for name in entries))
            self.assertTrue(Path(str(archive) + ".sha256").is_file())


if __name__ == "__main__":
    unittest.main()
