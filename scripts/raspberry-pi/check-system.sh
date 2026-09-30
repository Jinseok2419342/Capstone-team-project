#!/usr/bin/env bash

# Read-only summary: no service restart, camera capture, VLM/SMTP call or .env read.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "${SCRIPT_DIR}/lib/common.sh"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    printf 'Usage: bash scripts/raspberry-pi/check-system.sh\nRead-only OS, storage, Python, service and camera-status checks.\n'
    exit 0
fi
[[ "$#" == 0 ]] || die "Unknown argument: $1"
issues=0
log "OS / architecture / clock"
grep '^PRETTY_NAME=' /etc/os-release || true
uname -m
date --iso-8601=seconds
log "Storage and memory"
df -h "${REFOUND_APP_DIR}"
free -h
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp || true
    vcgencmd get_throttled || true
fi
log "Service Python environment"
if [[ -x "${REFOUND_APP_DIR}/.venv/bin/python" ]]; then
    if ! "${REFOUND_APP_DIR}/.venv/bin/python" "${SCRIPT_DIR}/check-runtime.py"; then
        issues=$((issues + 1))
    fi
else
    warn "Service virtual environment is missing. Run install.sh first."
    issues=$((issues + 1))
fi
log "Service state"
if ! systemctl is-active "${REFOUND_SERVICE}"; then
    issues=$((issues + 1))
fi
if [[ ! -r "${REFOUND_RUNTIME_FILE}" ]]; then
    die "Runtime settings are missing. Run install.sh first."
fi
port="$(unset REFOUND_PORT; runtime_port)"
host="$(sed -n 's/^HOST=//p' "${REFOUND_RUNTIME_FILE}" | tail -n 1)"
host="${host:-127.0.0.1}"
case "${host}" in
    0.0.0.0) host="127.0.0.1" ;;
    ::|::1) host="[::1]" ;;
esac
log "Application status at http://${host}:${port}"
if ! curl --fail --silent --show-error --max-time 8 "http://${host}:${port}/api/health" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except (ValueError, OSError):
    raise SystemExit("FAIL: no readable health response")
camera = data.get("camera") or {}
provider = data.get("provider") or {}
connected = camera.get("camera_connected", camera.get("connected", False))
privacy = camera.get("privacy_enabled", camera.get("privacy_mode", False))
print("Database:", data.get("database"))
print("Hardware profile:", data.get("hardware_profile"))
print("Camera connected:", connected, "| phase:", camera.get("phase"), "| privacy:", privacy)
print("Pending changes:", camera.get("pending_changes"), "| inventory connected:", camera.get("inventory_connected"))
print("Configured AI:", provider.get("active"), "| model:", provider.get("model"))
print("AI key presence is not a live API test. SMTP delivery is not tested here.")
if not data.get("ok") or not connected or privacy or camera.get("inventory_connected") is False:
    raise SystemExit("ATTENTION: check the database, camera connection or privacy setting")
'; then
    issues=$((issues + 1))
fi
if (( issues > 0 )); then
    warn "${issues} check(s) need attention. For service failures: sudo journalctl -u refound.service -n 60 --no-pager"
    exit 1
fi
log "Local checks passed. Continue with a real-item test and test email in the browser."
