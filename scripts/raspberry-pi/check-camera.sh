#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/raspberry-pi/check-camera.sh [--yes]

Lists attached cameras, takes one temporary JPEG, and captures one Picamera2
array. If refound.service owns the camera, it is stopped temporarily and is
always restarted on exit.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
parse_yes_flag "$@"
require_root

camera_list_command=""
camera_still_command=""
if command -v rpicam-hello >/dev/null 2>&1; then
    camera_list_command="rpicam-hello"
elif command -v libcamera-hello >/dev/null 2>&1; then
    camera_list_command="libcamera-hello"
else
    die "Neither rpicam-hello nor libcamera-hello is installed. Run install.sh first."
fi

if command -v rpicam-still >/dev/null 2>&1; then
    camera_still_command="rpicam-still"
elif command -v libcamera-still >/dev/null 2>&1; then
    camera_still_command="libcamera-still"
else
    die "Neither rpicam-still nor libcamera-still is installed. Run install.sh first."
fi

service_was_active=0
capture_file="$(mktemp --suffix=.jpg /tmp/refound-camera-check.XXXXXX)"

cleanup() {
    local exit_code=$?
    rm -f "${capture_file:-}"
    if (( service_was_active == 1 )); then
        log "Restarting ${REFOUND_SERVICE}..."
        systemctl start "${REFOUND_SERVICE}" || true
    fi
    exit "${exit_code}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if systemctl is-active --quiet "${REFOUND_SERVICE}" 2>/dev/null; then
    warn "${REFOUND_SERVICE} is currently using the camera."
    confirm "Stop it briefly for a camera self-test?" || die "Camera check cancelled."
    systemctl stop "${REFOUND_SERVICE}"
    service_was_active=1
fi

log "Cameras reported by the Raspberry Pi camera stack:"
"${camera_list_command}" --list-cameras

log "Taking a short, non-preview test image..."
"${camera_still_command}" --nopreview --timeout 2000 --output "${capture_file}"
[[ -s "${capture_file}" ]] || die "The camera command created no image. Recheck the ribbon cable orientation."
log "JPEG capture succeeded ($(stat -c '%s' "${capture_file}") bytes)."

python_bin="python3"
if [[ -x "${REFOUND_APP_DIR}/.venv/bin/python" ]]; then
    python_bin="${REFOUND_APP_DIR}/.venv/bin/python"
fi

log "Checking Picamera2 from the same Python environment used by Re:Found..."
"${python_bin}" - <<'PY'
from picamera2 import Picamera2

camera = Picamera2()
try:
    config = camera.create_preview_configuration(main={"size": (640, 360), "format": "RGB888"})
    camera.configure(config)
    camera.start()
    frame = camera.capture_array()
    print(f"[Re:Found] Picamera2 capture succeeded: shape={frame.shape}, dtype={frame.dtype}")
finally:
    camera.stop()
    camera.close()
PY

log "Camera check passed. The temporary image has been removed."
