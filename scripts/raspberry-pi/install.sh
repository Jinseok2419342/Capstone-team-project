#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/raspberry-pi/install.sh [--yes]

Installs Raspberry Pi OS packages, creates a system-package-aware virtual
environment, and installs/enables refound.service. Run it from the project that
has already been unpacked at /opt/refound. Existing Pi-side .env values are
preserved on upgrades; the first install only accepts a blank template.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
parse_yes_flag "$@"
require_root

[[ -f "${REFOUND_APP_DIR}/run.py" ]] \
    || die "run.py was not found at ${REFOUND_APP_DIR}. Unpack the Pi package there first."
[[ -f "${REFOUND_APP_DIR}/requirements.txt" ]] \
    || die "requirements.txt was not found at ${REFOUND_APP_DIR}."
source_root="$(readlink -f "${SCRIPT_DIR}/../..")"
installed_root="$(readlink -f "${REFOUND_APP_DIR}")"
[[ "${source_root}" == "${installed_root}" ]] \
    || die "This installer belongs to ${source_root}, but the app contract is ${installed_root}. Unpack the package at /opt/refound and run that copy."

service_user="${REFOUND_USER:-${SUDO_USER:-}}"
if [[ -z "${service_user}" || "${service_user}" == "root" ]]; then
    die "Run from a normal login with sudo, or set REFOUND_USER to the intended service account."
fi
id "${service_user}" >/dev/null 2>&1 || die "User does not exist: ${service_user}"
service_group="$(id -gn "${service_user}")"
[[ "${service_user}" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || die "Unsafe service user name."
[[ "${service_group}" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || die "Unsafe service group name."

if [[ -r /proc/device-tree/model ]]; then
    model="$(tr -d '\0' </proc/device-tree/model)"
    if [[ "${model}" != *"Raspberry Pi"* ]]; then
        warn "Detected '${model}', not a Raspberry Pi."
        confirm "Continue anyway?" || die "Installation cancelled."
    fi
else
    warn "Could not verify Raspberry Pi hardware."
    confirm "Continue anyway?" || die "Installation cancelled."
fi

first_install=0
if [[ ! -f "${REFOUND_RUNTIME_DIR}/installed" ]]; then
    first_install=1
fi

if (( first_install == 1 )) && [[ -d "${REFOUND_APP_DIR}/data" ]] \
    && find "${REFOUND_APP_DIR}/data" \( -type f -o -type l \) -print -quit | grep -q .; then
    die "Existing data was found before first Pi install. Do not transfer the PC database or captures; remove /opt/refound/data and rerun."
fi

if (( first_install == 1 )) && [[ -f "${REFOUND_APP_DIR}/.env" ]]; then
    if grep -Eq '^[[:space:]]*(OPENAI_API_KEY|GEMINI_API_KEY|SMTP_PASSWORD)[[:space:]]*=[[:space:]]*[^[:space:]#]' \
        "${REFOUND_APP_DIR}/.env"; then
        die "A populated .env exists before first Pi install. Keep a secure backup, remove the transferred file, rerun install, then enter valid keys directly on the Pi."
    fi
fi

log "Installing Raspberry Pi camera, OpenCV, NetworkManager, and runtime packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates curl dnsmasq-base network-manager python3-opencv python3-picamera2 \
    python3-pip python3-venv rpicam-apps
systemctl enable --now NetworkManager

if getent group video >/dev/null 2>&1; then
    usermod -a -G video "${service_user}"
fi
if getent group render >/dev/null 2>&1; then
    usermod -a -G render "${service_user}"
fi

install -d -m 0755 -o "${service_user}" -g "${service_group}" \
    "${REFOUND_APP_DIR}/.venv"
install -d -m 0700 -o "${service_user}" -g "${service_group}" \
    "${REFOUND_APP_DIR}/data" "${REFOUND_APP_DIR}/data/captures"

if [[ ! -f "${REFOUND_APP_DIR}/.env" ]]; then
    [[ -f "${REFOUND_APP_DIR}/.env.example" ]] \
        || die ".env.example is missing; refusing to invent a secrets file."
    install -m 0600 -o "${service_user}" -g "${service_group}" \
        "${REFOUND_APP_DIR}/.env.example" "${REFOUND_APP_DIR}/.env"
    log "Created a blank, Pi-local .env (mode 600). No key was copied from the PC."
else
    chown "${service_user}:${service_group}" "${REFOUND_APP_DIR}/.env"
    chmod 0600 "${REFOUND_APP_DIR}/.env"
    log "Preserved the existing Pi-local .env and enforced mode 600."
fi

log "Creating the Python environment with Raspberry Pi system camera packages..."
runuser -u "${service_user}" -- python3 -m venv --system-site-packages \
    "${REFOUND_APP_DIR}/.venv"
runuser -u "${service_user}" -- "${REFOUND_APP_DIR}/.venv/bin/python" \
    -m pip install --upgrade pip wheel

requirements_file="${REFOUND_APP_DIR}/requirements.txt"
if [[ -f "${REFOUND_APP_DIR}/requirements-pi.txt" ]]; then
    requirements_file="${REFOUND_APP_DIR}/requirements-pi.txt"
fi
runuser -u "${service_user}" -- "${REFOUND_APP_DIR}/.venv/bin/python" \
    -m pip install -r "${requirements_file}"

log "Checking the actual service user's Python imports before starting the app..."
runuser -u "${service_user}" -- "${REFOUND_APP_DIR}/.venv/bin/python" \
    "${SCRIPT_DIR}/check-runtime.py"

service_temp="$(mktemp /run/refound.service.XXXXXX)"
trap 'rm -f "${service_temp:-}"' EXIT
sed \
    -e "s/@@SERVICE_USER@@/${service_user}/g" \
    -e "s/@@SERVICE_GROUP@@/${service_group}/g" \
    "${SCRIPT_DIR}/refound.service" >"${service_temp}"
install -m 0644 -o root -g root "${service_temp}" \
    "/etc/systemd/system/${REFOUND_SERVICE}"

prepare_install_runtime
install -m 0644 -o root -g root /dev/null "${REFOUND_RUNTIME_DIR}/installed"
restart_installed_service

log "Installation complete. Existing access settings were retained; a first install is local-only."
if (( first_install == 1 )); then
    log "Next: run check-camera.sh and follow docs/guides/FRESH_SD_START.md. Verify the app through an SSH tunnel before optional Tailscale setup."
else
    log "Continue using the existing access address. Check the camera and finish one real-item rehearsal before presenting."
fi
log "Edit Pi-only secrets with: sudo -u ${service_user} nano ${REFOUND_APP_DIR}/.env"
