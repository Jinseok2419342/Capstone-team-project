#!/usr/bin/env bash

# Internal detached transition. setup-hotspot.sh launches this through systemd
# so dropping the current Wi-Fi SSH session cannot interrupt the mode switch.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root
require_command nmcli

transition_succeeded=0
rollback_network() {
    local exit_code=$?
    if (( transition_succeeded == 0 )); then
        warn "Hotspot transition failed; closing the AP so saved Wi-Fi can reconnect."
        nmcli connection modify "${REFOUND_HOTSPOT_CONNECTION}" \
            connection.autoconnect no >/dev/null 2>&1 || true
        nmcli connection down "${REFOUND_HOTSPOT_CONNECTION}" >/dev/null 2>&1 || true
        nmcli radio wifi on >/dev/null 2>&1 || true
    fi
    exit "${exit_code}"
}
trap rollback_network EXIT

nmcli connection up "${REFOUND_HOTSPOT_CONNECTION}"
interface="$(nmcli -g connection.interface-name connection show \
    "${REFOUND_HOTSPOT_CONNECTION}" | head -n 1)"
if [[ -z "${interface}" ]]; then
    interface="$(detect_wifi_interface)"
fi
active_address="$(nmcli -g IP4.ADDRESS device show "${interface}" | head -n 1)"
[[ "${active_address}" == "${REFOUND_HOTSPOT_CIDR}" ]] \
    || die "The AP received '${active_address}', expected '${REFOUND_HOTSPOT_CIDR}'."

switch_runtime_mode hotspot
transition_succeeded=1
log "Detached hotspot transition completed successfully."
