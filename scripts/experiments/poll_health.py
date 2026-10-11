#!/usr/bin/env python3
"""Record Re:Found's analysis frame rate and per-frame processing time.

Run it on the laptop while the SSH tunnel is open; it only reads
``/api/health`` once per interval and needs nothing beyond the Python
standard library.  Stop it with Ctrl+C.

    python scripts/experiments/poll_health.py --output health.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FIELDS = (
    "timestamp_utc", "ok", "phase", "camera_connected", "fps", "processing_ms",
    "frame_sequence", "detected_changes", "pending_changes", "error",
)


def sample(url: str, timeout: float) -> dict[str, object]:
    row: dict[str, object] = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        row.update(ok=0, error=str(exc)[:200])
        return row
    camera = payload.get("camera") or {}
    row.update(
        ok=int(bool(payload.get("ok"))),
        phase=camera.get("phase", ""),
        camera_connected=int(bool(camera.get("camera_connected"))),
        fps=camera.get("fps", ""),
        processing_ms=camera.get("processing_ms", ""),
        frame_sequence=camera.get("frame_sequence", ""),
        detected_changes=camera.get("detected_changes", ""),
        pending_changes=camera.get("pending_changes", ""),
        error="",
    )
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re:Found 처리 속도 기록")
    parser.add_argument("--url", default="http://127.0.0.1:18000", help="웹 화면 주소")
    parser.add_argument("--output", required=True, type=Path, help="새로 만들 CSV 경로")
    parser.add_argument("--interval", type=float, default=1.0, help="기록 간격(초)")
    parser.add_argument("--duration", type=float, default=0.0, help="기록 시간(초), 0이면 Ctrl+C까지")
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"{args.output} 파일이 이미 있습니다. 다른 이름을 쓰세요.", file=sys.stderr)
        return 2
    health_url = args.url.rstrip("/") + "/api/health"
    started = time.monotonic()
    written = 0
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        print(f"기록 시작: {health_url} → {args.output} (Ctrl+C로 종료)")
        try:
            while not args.duration or time.monotonic() - started < args.duration:
                tick = time.monotonic()
                row = sample(health_url, timeout=max(0.5, args.interval))
                writer.writerow(row)
                handle.flush()
                written += 1
                if written == 1 or written % 60 == 0:
                    status = row.get("error") or f"fps={row.get('fps')} phase={row.get('phase')}"
                    print(f"[{written}] {status}")
                time.sleep(max(0.0, args.interval - (time.monotonic() - tick)))
        except KeyboardInterrupt:
            pass
    print(f"종료: {written}행 저장")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
