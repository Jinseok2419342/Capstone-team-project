#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/raspberry-pi/setup-tailscale.sh [--yes]

Installs Tailscale from its official Linux installer when needed, opens the
interactive browser sign-in, binds Re:Found to 127.0.0.1, and publishes it only
inside your private tailnet with Tailscale Serve. Existing Serve/Funnel routes
on this Pi are cleared first. No auth key is stored here.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
parse_yes_flag "$@"
require_root
require_command curl
require_command nmcli
require_command python3
require_command systemctl

if nmcli -t -f NAME,TYPE,DEVICE connection show --active 2>/dev/null \
    | grep -Eq "^${REFOUND_HOTSPOT_CONNECTION}:802-11-wireless:"; then
    die "The offline Re:Found hotspot is active. Run remove-hotspot.sh, connect the Pi to internet Wi-Fi, then retry."
fi

if ! command -v tailscale >/dev/null 2>&1; then
    log "Tailscale is not installed."
    confirm "Download and run Tailscale's official HTTPS installer?" \
        || die "Tailscale setup cancelled."
    installer="$(mktemp /tmp/tailscale-install.XXXXXX.sh)"
    trap 'rm -f "${installer:-}"' EXIT
    curl --fail --silent --show-error --location \
        --proto '=https' --tlsv1.2 https://tailscale.com/install.sh \
        --output "${installer}"
    chmod 0700 "${installer}"
    sh "${installer}"
fi

require_command tailscale
systemctl enable --now tailscaled

if ! tailscale status >/dev/null 2>&1; then
    log "Tailscale sign-in is required. Open the URL printed below on your phone or PC."
    tailscale up
fi

tailscale status >/dev/null 2>&1 \
    || die "Tailscale is not connected. Complete sign-in, then rerun this script."

# Funnel and Serve share one node-local publishing configuration. Reset it so
# this dedicated Pi cannot retain an older public Funnel route. The private
# Re:Found Serve route is recreated below.
log "Clearing any previous Tailscale Serve or Funnel routes on this Pi..."
if ! tailscale funnel reset; then
    die "Could not clear the previous Tailscale Serve/Funnel configuration."
fi

# Loopback is applied before Serve so the unauthenticated app never listens on
# the school LAN. switch_runtime_mode rolls back if the service fails.
switch_runtime_mode tailscale

port="$(runtime_port)"
log "Publishing the loopback service privately through Tailscale Serve..."
log "On first use, Tailscale may print a consent URL below and wait here."
log "Keep this terminal open, approve HTTPS/Serve in the browser, and do not enable Funnel."
if ! tailscale serve --bg "http://127.0.0.1:${port}"; then
    die "Tailscale Serve was not enabled. If a consent URL was printed, open it, enable Serve without Funnel, then rerun this script."
fi

if ! tailscale serve status; then
    die "Could not verify the Tailscale Serve configuration."
fi

if ! serve_config="$(tailscale serve status --json 2>&1)"; then
    printf '%s\n' "${serve_config}" >&2
    die "Could not read the Tailscale Serve configuration as JSON."
fi

if ! printf '%s' "${serve_config}" | python3 -c '
import json
import sys

expected_proxy = sys.argv[1]
config = json.load(sys.stdin)

def has_active_funnel(serve_config):
    if not isinstance(serve_config, dict):
        return False
    if any((serve_config.get("AllowFunnel") or {}).values()):
        return True
    return any(
        has_active_funnel(foreground_config)
        for foreground_config in (serve_config.get("Foreground") or {}).values()
    )

if has_active_funnel(config):
    raise SystemExit("an active public Funnel route was found")

tcp_443 = (config.get("TCP") or {}).get("443") or {}
if tcp_443.get("HTTPS") is not True:
    raise SystemExit("the private HTTPS listener on port 443 is missing")

root_proxies = []
for authority, web_server in (config.get("Web") or {}).items():
    if not authority.endswith(":443") or not isinstance(web_server, dict):
        continue
    root_handler = (web_server.get("Handlers") or {}).get("/") or {}
    if isinstance(root_handler, dict):
        root_proxies.append(root_handler.get("Proxy"))

if expected_proxy not in root_proxies:
    raise SystemExit("the expected loopback proxy is missing")
' "http://127.0.0.1:${port}"; then
    warn "The Tailscale publishing configuration failed its private-only safety check."
    if ! tailscale funnel reset; then
        die "The unsafe or incomplete publishing configuration could not be cleared. Run: sudo tailscale funnel reset"
    fi
    die "The unsafe or incomplete publishing configuration was cleared. Complete any consent flow, then rerun this script."
fi

log "Tailscale access is ready. Devices must be signed into the same tailnet."
