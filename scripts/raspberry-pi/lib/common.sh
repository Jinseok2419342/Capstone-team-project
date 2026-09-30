#!/usr/bin/env bash

# Shared, non-interactive primitives for the Raspberry Pi administration scripts.
# This file is sourced by the entry-point scripts; do not run it directly.

set -Eeuo pipefail

readonly REFOUND_APP_DIR="${REFOUND_APP_DIR:-/opt/refound}"
readonly REFOUND_SERVICE="refound.service"
readonly REFOUND_RUNTIME_DIR="/etc/refound"
readonly REFOUND_RUNTIME_FILE="${REFOUND_RUNTIME_DIR}/runtime.env"
readonly REFOUND_DEFAULT_PORT="8000"
readonly REFOUND_HOTSPOT_ADDRESS="10.42.0.1"
readonly REFOUND_HOTSPOT_CIDR="${REFOUND_HOTSPOT_ADDRESS}/24"
readonly REFOUND_HOTSPOT_CONNECTION="refound-demo"

log() {
    printf '[Re:Found] %s\n' "$*"
}

warn() {
    printf '[Re:Found] WARNING: %s\n' "$*" >&2
}

die() {
    printf '[Re:Found] ERROR: %s\n' "$*" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        die "Run this script with sudo (example: sudo bash $0)."
    fi
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

confirm() {
    local prompt="$1"
    if [[ "${REFOUND_ASSUME_YES:-0}" == "1" ]]; then
        return 0
    fi
    local answer=""
    read -r -p "${prompt} [y/N] " answer
    [[ "${answer}" =~ ^[Yy]([Ee][Ss])?$ ]]
}

parse_yes_flag() {
    if [[ "${1:-}" == "--yes" ]]; then
        REFOUND_ASSUME_YES=1
        export REFOUND_ASSUME_YES
        shift
    fi
    if [[ "$#" -ne 0 ]]; then
        die "Unknown argument: $1"
    fi
}

runtime_port() {
    local port="${REFOUND_PORT:-}"
    if [[ -z "${port}" && -r "${REFOUND_RUNTIME_FILE}" ]]; then
        port="$(sed -n 's/^PORT=//p' "${REFOUND_RUNTIME_FILE}" | tail -n 1)"
    fi
    port="${port:-${REFOUND_DEFAULT_PORT}}"
    if [[ ! "${port}" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
        die "Invalid port '${port}'. Set REFOUND_PORT to a number from 1 to 65535."
    fi
    printf '%s\n' "${port}"
}

host_for_mode() {
    case "$1" in
        local|tailscale) printf '127.0.0.1\n' ;;
        hotspot) printf '%s\n' "${REFOUND_HOTSPOT_ADDRESS}" ;;
        *) die "Unknown access mode: $1" ;;
    esac
}

write_runtime_mode() {
    local mode="$1"
    local host port temp_file
    host="$(host_for_mode "${mode}")"
    port="$(runtime_port)"

    install -d -m 0755 -o root -g root "${REFOUND_RUNTIME_DIR}"
    temp_file="$(mktemp "${REFOUND_RUNTIME_DIR}/runtime.env.XXXXXX")"
    {
        printf '# Managed by /opt/refound/scripts/raspberry-pi/*.sh\n'
        printf '# Contains no API keys or passwords. Do not add secrets here.\n'
        printf 'REFOUND_ACCESS_MODE=%s\n' "${mode}"
        printf 'HARDWARE_PROFILE=raspberry-pi\n'
        printf 'HOST=%s\n' "${host}"
        printf 'PORT=%s\n' "${port}"
        printf 'RELOAD=false\n'
    } >"${temp_file}"
    chmod 0644 "${temp_file}"
    chown root:root "${temp_file}"
    mv -f "${temp_file}" "${REFOUND_RUNTIME_FILE}"
}

wait_for_health() {
    local port="$1"
    local host="${2:-127.0.0.1}"
    local attempt
    if ! command -v curl >/dev/null 2>&1; then
        systemctl is-active --quiet "${REFOUND_SERVICE}"
        return
    fi
    for attempt in {1..20}; do
        if curl --fail --silent --show-error --max-time 2 \
            "http://${host}:${port}/api/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

prepare_install_runtime() {
    if [[ -f "${REFOUND_RUNTIME_FILE}" ]]; then
        log "Preserved the existing access mode, bind address, and port."
    else
        write_runtime_mode local
    fi
}

restart_installed_service() {
    local previous_pid current_pid port host
    previous_pid="$(systemctl show "${REFOUND_SERVICE}" --property=MainPID --value 2>/dev/null || true)"
    systemctl daemon-reload
    systemctl enable "${REFOUND_SERVICE}"
    # enable --now leaves an already-running process on the previous code and
    # schema. A real restart is required after installing either one.
    systemctl restart "${REFOUND_SERVICE}"

    # Read the preserved file, rather than a one-off REFOUND_PORT shell value.
    # systemd also reads this file when launching the new process.
    port="$(unset REFOUND_PORT; runtime_port)"
    host="$(sed -n 's/^HOST=//p' "${REFOUND_RUNTIME_FILE}" | tail -n 1)"
    host="${host:-127.0.0.1}"
    case "${host}" in
        0.0.0.0) host="127.0.0.1" ;;
        ::|::1) host="[::1]" ;;
    esac
    if ! wait_for_health "${port}" "${host}"; then
        systemctl status "${REFOUND_SERVICE}" --no-pager || true
        die "The restarted service did not become healthy. Inspect: sudo journalctl -u ${REFOUND_SERVICE} -n 80 --no-pager"
    fi
    current_pid="$(systemctl show "${REFOUND_SERVICE}" --property=MainPID --value 2>/dev/null || true)"
    if [[ ! "${current_pid}" =~ ^[1-9][0-9]*$ ]] \
        || [[ "${current_pid}" == "${previous_pid}" ]] \
        || ! systemctl is-active --quiet "${REFOUND_SERVICE}"; then
        die "A new running service process was not confirmed; refusing to report an upgrade success."
    fi
    log "New service process ${current_pid} is responding at http://${host}:${port}."
}

switch_runtime_mode() {
    local mode="$1"
    local backup_file=""
    local had_runtime=0
    local port
    port="$(runtime_port)"

    systemctl cat "${REFOUND_SERVICE}" >/dev/null 2>&1 \
        || die "${REFOUND_SERVICE} is not installed. Run install.sh first."

    if [[ -f "${REFOUND_RUNTIME_FILE}" ]]; then
        backup_file="$(mktemp /run/refound-runtime.XXXXXX)"
        cp --preserve=mode,ownership "${REFOUND_RUNTIME_FILE}" "${backup_file}"
        had_runtime=1
    fi

    write_runtime_mode "${mode}"
    if systemctl restart "${REFOUND_SERVICE}" \
        && wait_for_health "${port}" "$(host_for_mode "${mode}")"; then
        [[ -z "${backup_file}" ]] || rm -f "${backup_file}"
        log "Access mode is now '${mode}' (HOST=$(host_for_mode "${mode}"), PORT=${port})."
        return 0
    fi

    warn "The service failed after switching to '${mode}'. Restoring the previous bind setting."
    if (( had_runtime == 1 )); then
        mv -f "${backup_file}" "${REFOUND_RUNTIME_FILE}"
    else
        rm -f "${REFOUND_RUNTIME_FILE}"
    fi
    systemctl restart "${REFOUND_SERVICE}" >/dev/null 2>&1 || true
    die "Mode switch failed. Inspect: sudo journalctl -u ${REFOUND_SERVICE} -n 80 --no-pager"
}

detect_wifi_interface() {
    local interface="${REFOUND_WIFI_INTERFACE:-}"
    if [[ -z "${interface}" ]]; then
        interface="$(nmcli -t -f DEVICE,TYPE device status \
            | awk -F: '$2 == "wifi" {print $1; exit}')"
    fi
    [[ -n "${interface}" ]] || die "No Wi-Fi interface found. Set REFOUND_WIFI_INTERFACE (usually wlan0)."
    [[ "${interface}" =~ ^[a-zA-Z0-9_.-]+$ ]] \
        || die "Unsafe Wi-Fi interface name: ${interface}"
    printf '%s\n' "${interface}"
}
