#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/raspberry-pi/remove-hotspot.sh [--yes]

First makes Re:Found local-only, then removes the refound-demo NetworkManager
profile. NetworkManager can reconnect to a previously saved Wi-Fi network.
Your SSH/browser connection through the hotspot will disconnect at the end.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
parse_yes_flag "$@"
require_root
require_command nmcli
require_command systemctl
require_command systemd-run

if ! nmcli -t -f NAME connection show | grep -Fxq "${REFOUND_HOTSPOT_CONNECTION}"; then
    log "No '${REFOUND_HOTSPOT_CONNECTION}' profile exists. Ensuring local-only bind."
    switch_runtime_mode local
    exit 0
fi

warn "Devices connected through the Re:Found hotspot will disconnect."
confirm "Remove the offline hotspot?" || die "Hotspot removal cancelled."

# Close the application listener before reconnecting this Wi-Fi interface to a
# school or home network. This order prevents even a brief unauthenticated LAN
# exposure.
switch_runtime_mode local
log "Re:Found is local-only. The AP will close in 2 seconds; this SSH session may end."
log "NetworkManager will then try saved Wi-Fi profiles. Run setup-tailscale.sh after internet reconnects."

systemctl stop refound-hotspot-remove.timer refound-hotspot-remove.service \
    >/dev/null 2>&1 || true
systemctl reset-failed refound-hotspot-remove.service >/dev/null 2>&1 || true
systemd-run --unit=refound-hotspot-remove --collect --no-block --on-active=2s \
    /bin/bash "${SCRIPT_DIR}/deactivate-hotspot.sh"
