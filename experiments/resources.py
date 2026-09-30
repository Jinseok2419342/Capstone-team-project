"""Dependency-free Linux resource sampling for reproducible Pi experiments.

The collector deliberately reads only kernel-exported ``/proc`` and ``/sys``
files.  Missing or unsupported metrics are represented by ``None`` so a CSV
writer can leave those cells empty instead of inventing platform values.

Input power is outside the Raspberry Pi process boundary.  ``power_w`` is
therefore always ``None``; publishable wattage must come from a timestamped
external meter placed at the board's power input.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIB = 1024**2
GIB = 1024**3
POWER_SOURCE_NOTE = "not_measured_in_software; external_input_meter_required"


@dataclass(frozen=True)
class CpuTimes:
    """Aggregate CPU counters expressed in kernel clock ticks."""

    total: int
    idle: int


@dataclass(frozen=True)
class ResourceSample:
    """One JSON/CSV-safe snapshot of host and Re:Found process resources."""

    timestamp_utc: str
    elapsed_seconds: float
    pid: int | None
    process_alive: bool
    raspberry_pi: bool
    device_model: str | None
    system_cpu_percent: float | None
    process_cpu_percent: float | None
    process_cpu_percent_of_device: float | None
    rss_mib: float | None
    peak_rss_mib: float | None
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    memory_available_mib: float | None
    memory_total_mib: float | None
    temperature_c: float | None
    temperature_source: str | None
    disk_used_percent: float | None
    disk_free_gib: float | None
    power_w: float | None
    power_source: str

    @classmethod
    def csv_fieldnames(cls) -> tuple[str, ...]:
        return tuple(field.name for field in fields(cls))

    def to_csv_row(self) -> dict[str, Any]:
        """Return a row where unavailable numeric values become empty cells."""

        row = asdict(self)
        return {
            key: "" if value is None else int(value) if isinstance(value, bool) else value
            for key, value in row.items()
        }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def read_device_model(proc_root: Path = Path("/proc")) -> str | None:
    """Read the device-tree model without requiring ``vcgencmd``."""

    path = proc_root / "device-tree" / "model"
    try:
        value = path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    return value.strip() or None


def is_raspberry_pi_model(model: str | None) -> bool:
    return bool(model and "raspberry pi" in model.casefold())


def parse_system_cpu_times(text: str) -> CpuTimes | None:
    """Parse the aggregate ``cpu`` line from ``/proc/stat``.

    Guest counters are excluded because Linux already includes them in the
    user and nice counters.  Idle follows the common ``idle + iowait``
    convention.  Raspberry Pi experiments do not normally involve guests,
    but excluding them keeps the formula correct on other Linux hosts.
    """

    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0] != "cpu":
            continue
        try:
            values = [int(value) for value in parts[1:]]
        except ValueError:
            return None
        if len(values) < 4:
            return None
        padded = values + [0] * (8 - len(values))
        total = sum(padded[:8])
        idle = padded[3] + padded[4]
        return CpuTimes(total=total, idle=idle)
    return None


def read_system_cpu_times(proc_root: Path = Path("/proc")) -> CpuTimes | None:
    text = _read_text(proc_root / "stat")
    return parse_system_cpu_times(text) if text is not None else None


def cpu_percent(previous: CpuTimes | None, current: CpuTimes | None) -> float | None:
    """Calculate aggregate busy percentage from two cumulative samples."""

    if previous is None or current is None:
        return None
    total_delta = current.total - previous.total
    idle_delta = current.idle - previous.idle
    if total_delta <= 0 or idle_delta < 0:
        return None
    busy_delta = max(0, total_delta - idle_delta)
    return round(min(100.0, 100.0 * busy_delta / total_delta), 3)


def parse_process_cpu_ticks(text: str) -> int | None:
    """Return ``utime + stime`` from ``/proc/<pid>/stat``.

    The command name is enclosed in parentheses and may itself contain spaces
    or parentheses, so splitting is safe only after the final closing one.
    """

    closing_parenthesis = text.rfind(")")
    if closing_parenthesis < 0:
        return None
    remaining = text[closing_parenthesis + 1 :].split()
    # remaining[0] is field 3 (state); utime/stime are fields 14 and 15.
    if len(remaining) <= 12:
        return None
    try:
        return int(remaining[11]) + int(remaining[12])
    except ValueError:
        return None


def read_process_cpu_ticks(pid: int, proc_root: Path = Path("/proc")) -> int | None:
    text = _read_text(proc_root / str(pid) / "stat")
    return parse_process_cpu_ticks(text) if text is not None else None


def _parse_kib_fields(text: str, requested: set[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for line in text.splitlines():
        key, separator, remainder = line.partition(":")
        if not separator or key not in requested:
            continue
        parts = remainder.split()
        if not parts:
            continue
        try:
            parsed[key] = float(parts[0])
        except ValueError:
            continue
    return parsed


def read_process_memory(
    pid: int, proc_root: Path = Path("/proc")
) -> tuple[float | None, float | None]:
    """Return current and high-water RSS in MiB."""

    text = _read_text(proc_root / str(pid) / "status")
    if text is None:
        return None, None
    values = _parse_kib_fields(text, {"VmRSS", "VmHWM"})
    rss = values.get("VmRSS")
    peak = values.get("VmHWM")
    return (
        round(rss / 1024.0, 3) if rss is not None else None,
        round(peak / 1024.0, 3) if peak is not None else None,
    )


def read_load_average(
    proc_root: Path = Path("/proc"),
) -> tuple[float | None, float | None, float | None]:
    text = _read_text(proc_root / "loadavg")
    if text is None:
        return None, None, None
    parts = text.split()
    if len(parts) < 3:
        return None, None, None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None, None, None


def read_system_memory(
    proc_root: Path = Path("/proc"),
) -> tuple[float | None, float | None]:
    """Return MemAvailable and MemTotal in MiB."""

    text = _read_text(proc_root / "meminfo")
    if text is None:
        return None, None
    values = _parse_kib_fields(text, {"MemAvailable", "MemTotal"})
    available = values.get("MemAvailable")
    total = values.get("MemTotal")
    return (
        round(available / 1024.0, 3) if available is not None else None,
        round(total / 1024.0, 3) if total is not None else None,
    )


def _parse_temperature(text: str) -> float | None:
    try:
        value = float(text.strip())
    except (TypeError, ValueError):
        return None
    # Linux thermal zones normally expose millidegrees Celsius.
    if abs(value) >= 1000.0:
        value /= 1000.0
    if not -40.0 <= value <= 150.0:
        return None
    return round(value, 3)


def read_pi_temperature(
    sys_root: Path = Path("/sys"),
) -> tuple[float | None, str | None]:
    """Read the Pi CPU/SoC thermal zone, preferring explicitly named zones."""

    thermal_root = sys_root / "class" / "thermal"
    try:
        zones = sorted(thermal_root.glob("thermal_zone*"))
    except (OSError, ValueError):
        return None, None
    if not zones:
        return None, None

    preferred_names = {"cpu-thermal", "cpu_thermal", "soc-thermal", "soc_thermal"}
    ranked: list[tuple[int, Path, str]] = []
    for zone in zones:
        zone_type = (_read_text(zone / "type") or "").strip()
        rank = 0 if zone_type.casefold() in preferred_names else 1
        if zone.name == "thermal_zone0":
            rank = min(rank, 1)
        ranked.append((rank, zone, zone_type))

    for _, zone, zone_type in sorted(ranked, key=lambda item: (item[0], item[1].name)):
        text = _read_text(zone / "temp")
        temperature = _parse_temperature(text) if text is not None else None
        if temperature is not None:
            label = zone_type or zone.name
            return temperature, f"sysfs:{label}"
    return None, None


def read_disk_usage(path: Path) -> tuple[float | None, float | None]:
    """Return filesystem used percentage and free GiB for the data path."""

    try:
        usage = shutil.disk_usage(path)
    except (OSError, ValueError):
        return None, None
    used_percent = 100.0 * usage.used / usage.total if usage.total else 0.0
    return round(used_percent, 3), round(usage.free / GIB, 3)


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class ResourceSampler:
    """Stateful sampler that calculates CPU percentages from counter deltas."""

    def __init__(
        self,
        pid: int | None,
        disk_path: Path,
        *,
        proc_root: Path = Path("/proc"),
        sys_root: Path = Path("/sys"),
        clock_ticks_per_second: int | None = None,
        cpu_count: int | None = None,
        started_monotonic: float | None = None,
    ) -> None:
        self.pid = pid if pid is not None and pid > 0 else None
        self.disk_path = Path(disk_path)
        self.proc_root = Path(proc_root)
        self.sys_root = Path(sys_root)
        self.device_model = read_device_model(self.proc_root)
        self.raspberry_pi = is_raspberry_pi_model(self.device_model)
        self.cpu_count = max(1, cpu_count or os.cpu_count() or 1)
        self.clock_ticks_per_second = clock_ticks_per_second or self._clock_ticks()
        self.started_monotonic = (
            time.monotonic() if started_monotonic is None else started_monotonic
        )
        self._previous_system_cpu: CpuTimes | None = None
        self._previous_process_ticks: int | None = None
        self._previous_process_monotonic: float | None = None

    @staticmethod
    def _clock_ticks() -> int:
        try:
            value = int(os.sysconf("SC_CLK_TCK"))
        except (AttributeError, OSError, TypeError, ValueError):
            return 100
        return value if value > 0 else 100

    def set_pid(self, pid: int | None) -> None:
        """Follow a restarted service without mixing two processes' deltas."""

        normalized = pid if pid is not None and pid > 0 else None
        if normalized == self.pid:
            return
        self.pid = normalized
        self._previous_process_ticks = None
        self._previous_process_monotonic = None

    def process_exists(self) -> bool:
        return bool(self.pid and (self.proc_root / str(self.pid)).is_dir())

    def sample(
        self,
        *,
        now_monotonic: float | None = None,
        timestamp_utc: str | None = None,
    ) -> ResourceSample:
        now = time.monotonic() if now_monotonic is None else now_monotonic

        system_times = read_system_cpu_times(self.proc_root)
        system_percent = cpu_percent(self._previous_system_cpu, system_times)
        self._previous_system_cpu = system_times

        process_ticks = (
            read_process_cpu_ticks(self.pid, self.proc_root) if self.pid is not None else None
        )
        process_percent: float | None = None
        if (
            process_ticks is not None
            and self._previous_process_ticks is not None
            and self._previous_process_monotonic is not None
        ):
            wall_delta = now - self._previous_process_monotonic
            tick_delta = process_ticks - self._previous_process_ticks
            if wall_delta > 0 and tick_delta >= 0:
                process_percent = round(
                    100.0
                    * tick_delta
                    / self.clock_ticks_per_second
                    / wall_delta,
                    3,
                )
        self._previous_process_ticks = process_ticks
        self._previous_process_monotonic = now if process_ticks is not None else None

        if self.pid is not None:
            rss_mib, peak_rss_mib = read_process_memory(self.pid, self.proc_root)
        else:
            rss_mib, peak_rss_mib = None, None

        load_1m, load_5m, load_15m = read_load_average(self.proc_root)
        memory_available_mib, memory_total_mib = read_system_memory(self.proc_root)
        if self.raspberry_pi:
            temperature_c, temperature_source = read_pi_temperature(self.sys_root)
        else:
            temperature_c, temperature_source = None, None
        disk_used_percent, disk_free_gib = read_disk_usage(self.disk_path)

        return ResourceSample(
            timestamp_utc=timestamp_utc or utc_timestamp(),
            elapsed_seconds=round(max(0.0, now - self.started_monotonic), 3),
            pid=self.pid,
            process_alive=self.process_exists(),
            raspberry_pi=self.raspberry_pi,
            device_model=self.device_model,
            system_cpu_percent=system_percent,
            process_cpu_percent=process_percent,
            process_cpu_percent_of_device=(
                round(process_percent / self.cpu_count, 3)
                if process_percent is not None
                else None
            ),
            rss_mib=rss_mib,
            peak_rss_mib=peak_rss_mib,
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            memory_available_mib=memory_available_mib,
            memory_total_mib=memory_total_mib,
            temperature_c=temperature_c,
            temperature_source=temperature_source,
            disk_used_percent=disk_used_percent,
            disk_free_gib=disk_free_gib,
            power_w=None,
            power_source=POWER_SOURCE_NOTE,
        )
