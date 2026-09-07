#!/usr/bin/env bash

# Internal detached transition. remove-hotspot.sh has already made the web app
# local-only before this script disconnects the SSH-carrying AP interface.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root
require_command nmcli

nmcli connection down "${REFOUND_HOTSPOT_CONNECTION}" >/dev/null 2>&1 || true
if nmcli -t -f NAME connection show | grep -Fxq "${REFOUND_HOTSPOT_CONNECTION}"; then
    nmcli connection delete "${REFOUND_HOTSPOT_CONNECTION}"
fi
nmcli radio wifi on
log "Detached hotspot removal completed; saved Wi-Fi profiles may reconnect."

