#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/raspberry-pi/setup-hotspot.sh [--yes]

Creates an offline WPA2 hotspot and binds Re:Found only to 10.42.0.1. The Wi-Fi
password is read silently, or from REFOUND_HOTSPOT_PASSWORD. Optional variables:
  REFOUND_HOTSPOT_SSID       default: ReFound-Demo
  REFOUND_WIFI_INTERFACE     auto-detected (usually wlan0)

The hotspot replaces the Pi's current Wi-Fi connection. It does not require a
school router or internet connection.
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

ssid="${REFOUND_HOTSPOT_SSID:-ReFound-Demo}"
ssid_bytes="$(printf '%s' "${ssid}" | wc -c)"
if (( ssid_bytes < 1 || ssid_bytes > 32 )) || [[ "${ssid}" == *$'\n'* ]]; then
    die "The hotspot SSID must be 1-32 bytes and contain no newline."
fi

interface="$(detect_wifi_interface)"
password="${REFOUND_HOTSPOT_PASSWORD:-}"
if [[ -z "${password}" ]]; then
    read -r -s -p "New hotspot password (8-63 characters): " password
    printf '\n'
    read -r -s -p "Enter it again: " password_again
    printf '\n'
    [[ "${password}" == "${password_again}" ]] || die "The passwords did not match."
    unset password_again
fi

password_bytes="$(printf '%s' "${password}" | wc -c)"
if (( password_bytes < 8 || password_bytes > 63 )) || [[ "${password}" == *$'\n'* ]]; then
    die "The WPA2 password must be 8-63 bytes and contain no newline."
fi

warn "This will disconnect '${interface}' from its current Wi-Fi network."
warn "Anyone who knows the hotspot password can open the admin screen; use a unique password."
confirm "Create/start the offline '${ssid}' hotspot?" || die "Hotspot setup cancelled."

nmcli radio wifi on
if nmcli -t -f NAME connection show | grep -Fxq "${REFOUND_HOTSPOT_CONNECTION}"; then
    log "Updating the existing NetworkManager hotspot profile."
else
    nmcli connection add type wifi ifname "${interface}" \
        con-name "${REFOUND_HOTSPOT_CONNECTION}" ssid "${ssid}"
fi

# NetworkManager stores the PSK in its root-owned connection profile. Passing
# it by argument is unavoidable for non-interactive nmcli; clear our shell copy
# immediately after the profile is updated.
nmcli connection modify "${REFOUND_HOTSPOT_CONNECTION}" \
    connection.interface-name "${interface}" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.ssid "${ssid}" \
    802-11-wireless-security.key-mgmt wpa-psk \
    802-11-wireless-security.proto rsn \
    802-11-wireless-security.psk "${password}" \
    ipv4.method shared \
    ipv4.addresses "${REFOUND_HOTSPOT_CIDR}" \
    ipv6.method disabled
unset password REFOUND_HOTSPOT_PASSWORD

port="$(runtime_port)"
log "The Wi-Fi switch will start in 2 seconds and may close this SSH session."
log "After about 10 seconds:"
log "1) On the presentation PC, join Wi-Fi: ${ssid}"
log "2) Open: http://${REFOUND_HOTSPOT_ADDRESS}:${port}"
log "When finished: sudo bash ${SCRIPT_DIR}/remove-hotspot.sh"
log "If it does not appear, reconnect normally and inspect: sudo journalctl -u refound-hotspot-switch.service -n 80 --no-pager"

# A transient systemd unit survives the expected loss of the current Wi-Fi SSH
# connection. The helper activates and verifies the AP before changing HOST; on
# any failure it closes the AP so a saved Wi-Fi connection can return.
systemctl stop refound-hotspot-switch.timer refound-hotspot-switch.service \
    >/dev/null 2>&1 || true
systemctl reset-failed refound-hotspot-switch.service >/dev/null 2>&1 || true
systemd-run --unit=refound-hotspot-switch --collect --no-block --on-active=2s \
    /bin/bash "${SCRIPT_DIR}/activate-hotspot.sh"
