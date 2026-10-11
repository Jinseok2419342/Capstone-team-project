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
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.live_session import HEALTH_FIELDS as FIELDS, Api, ApiError, health_row  # noqa: E402


def sample(url: str, timeout: float) -> dict[str, object]:
    try:
        return health_row(Api(url, timeout=timeout).get(""))
    except ApiError as exc:
        return health_row(None, str(exc))


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
