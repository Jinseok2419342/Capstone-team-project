#!/usr/bin/env python3
"""Record Re:Found Raspberry Pi resources to a bounded, append-free CSV.

This is intentionally a separate process: experiment instrumentation neither
writes to the operational SQLite database nor contends with the camera thread.
Power is not inferred from software counters.  Record input watts with an
external, timestamped USB-C/DC meter and merge those observations afterwards.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.resources import POWER_SOURCE_NOTE, ResourceSample, ResourceSampler


DEFAULT_SERVICE = "refound.service"
DEFAULT_DISK_PATH = Path("/opt/refound/data")


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def resolve_service_main_pid(service: str) -> int | None:
    """Resolve systemd's current MainPID without shell interpolation."""

    try:
        result = subprocess.run(
            ["systemctl", "show", "--property=MainPID", "--value", service],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        pid = int(result.stdout.strip())
    except ValueError:
        return None
    return pid if pid > 0 else None


def open_new_private_csv(path: Path) -> TextIO:
    """Create a new mode-0600 file and refuse overwrites or final symlinks."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8", newline="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record CPU, RSS, load, memory, Pi temperature, and disk capacity. "
            "Power requires a separate external input meter."
        )
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--pid", type=positive_int, help="fixed Re:Found process PID")
    target.add_argument(
        "--service",
        default=None,
        help=f"systemd unit to follow (default: {DEFAULT_SERVICE})",
    )
    parser.add_argument("--output", required=True, type=Path, help="new .csv path")
    parser.add_argument(
        "--disk-path",
        type=Path,
        default=DEFAULT_DISK_PATH,
        help="filesystem path whose capacity is recorded",
    )
    parser.add_argument("--trial-id", default="", help="non-secret experiment label")
    parser.add_argument(
        "--interval",
        type=positive_float,
        default=1.0,
        help="sampling interval in seconds (default: 1)",
    )
    parser.add_argument(
        "--duration",
        type=positive_float,
        default=900.0,
        help="bounded recording duration in seconds (default: 900)",
    )
    parser.add_argument(
        "--flush-every",
        type=positive_int,
        default=10,
        help="flush after this many rows (default: 10)",
    )
    parser.add_argument(
        "--max-file-mib",
        type=positive_float,
        default=64.0,
        help="stop before the CSV grows beyond this size (default: 64)",
    )
    parser.add_argument(
        "--min-free-mib",
        type=positive_float,
        default=256.0,
        help="stop if the output filesystem has less free space (default: 256)",
    )
    return parser


def output_has_space(path: Path, minimum_free_mib: float) -> bool:
    try:
        free = shutil.disk_usage(path.parent).free
    except OSError:
        return False
    return free >= minimum_free_mib * 1024**2


def run(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    if output.suffix.casefold() != ".csv":
        raise ValueError("--output must end in .csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output_has_space(output, args.min_free_mib):
        raise OSError("output filesystem does not have the required free space")

    service = args.service
    if args.pid is None and service is None:
        service = DEFAULT_SERVICE
    current_pid = args.pid if args.pid is not None else resolve_service_main_pid(service)

    started = time.monotonic()
    sampler = ResourceSampler(
        current_pid,
        args.disk_path,
        started_monotonic=started,
    )
    stop_requested = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    rows_written = 0
    next_sample = started
    next_service_refresh = started
    fieldnames = ("trial_id",) + ResourceSample.csv_fieldnames()

    print(f"Recording resource samples to {output}")
    print(f"Power boundary: {POWER_SOURCE_NOTE}")
    try:
        with open_new_private_csv(output) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            while not stop_requested.is_set():
                now = time.monotonic()
                if now - started >= args.duration:
                    break

                if service is not None and (
                    now >= next_service_refresh or not sampler.process_exists()
                ):
                    sampler.set_pid(resolve_service_main_pid(service))
                    # Avoid making systemctl itself a meaningful part of a 1 Hz load.
                    next_service_refresh = now + 30.0

                sample = sampler.sample(now_monotonic=now)
                row = {"trial_id": args.trial_id, **sample.to_csv_row()}
                writer.writerow(row)
                rows_written += 1

                if rows_written % args.flush_every == 0:
                    handle.flush()
                    if handle.tell() >= args.max_file_mib * 1024**2:
                        print("Stopped at --max-file-mib safety limit", file=sys.stderr)
                        break
                    if not output_has_space(output, args.min_free_mib):
                        print("Stopped at --min-free-mib safety limit", file=sys.stderr)
                        break

                next_sample = max(next_sample + args.interval, time.monotonic())
                stop_requested.wait(max(0.0, next_sample - time.monotonic()))

            handle.flush()
            os.fsync(handle.fileno())
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)

    print(f"Finished: {rows_written} rows")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
