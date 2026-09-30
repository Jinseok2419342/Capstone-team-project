"""Synthetic developer benchmark, never a Raspberry Pi or paper result.

Examples (from the repository root)::

    python scripts/benchmarks/vision_pipeline.py --threads 1 --output output/vision-current.json
    python scripts/benchmarks/vision_pipeline.py --source-zip output/maintenance/2026-09-18-vision-review/source-before.zip

The loop cases run the actual VisionMonitor._run with a generated camera and a
virtual camera clock. Real CPU work is timed; capture blocking, DB, HTTP, remote
AI, a browser and callback consumers are absent. Configured camera/monitor rates
are scheduling inputs, not measured hardware FPS. The pair cases exercise only
_detect_changes, including evidence JPEG encoding for an added object.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
import platform
import pstats
import queue
import sys
import threading
import time
import types
import zipfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CASES = ("static", "sensor_noise", "pair_none", "pair_added")


def load_vision(source_zip: Path | None) -> tuple[types.ModuleType, str]:
    """Import the selected vision source without importing app.main or config."""

    if source_zip is None:
        from app import vision

        return vision, hashlib.sha256((ROOT / "app/vision.py").read_bytes()).hexdigest()
    with zipfile.ZipFile(source_zip) as archive:
        source = archive.read("app/vision.py")
    name = "app._benchmark_archived_vision"
    spec = importlib.util.spec_from_loader(name, loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(source_zip.resolve()) + "!/app/vision.py"
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module, hashlib.sha256(source).hexdigest()


def scenes(width: int, height: int) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    rng = np.random.default_rng(1842)
    y, x = np.indices((height, width))
    gray = (178 + 9 * ((x // 100 + y // 90) % 2)).astype(np.uint8)
    before = np.dstack((gray, gray + 5, gray + 9))
    for _ in range(36):
        center = (int(rng.integers(30, width - 30)), int(rng.integers(30, height - 30)))
        cv2.circle(before, center, int(rng.integers(4, 13)), (80, 104, 127), -1)
    cv2.line(before, (40, height // 3), (width - 40, height // 3 + 18), (121, 140, 159), 3)
    after = before.copy()
    left, top = int(width * 0.42), int(height * 0.38)
    right, bottom = int(width * 0.60), int(height * 0.65)
    cv2.rectangle(after, (left, top), (right, bottom), (30, 48, 74), -1)
    cv2.line(after, (left + 15, top + 12), (right - 15, bottom - 12), (117, 137, 164), 5)
    noisy = [
        np.clip(before.astype(np.int16) + rng.integers(-2, 3, before.shape, dtype=np.int16) + index % 3, 0, 255).astype(np.uint8)
        for index in range(6)
    ]
    return before, after, noisy


def profile_rows(profile: cProfile.Profile, limit: int = 12) -> dict[str, Any]:
    stats = pstats.Stats(profile)
    rows = [
        {"function": f"{Path(file).name}:{line}:{name}", "calls": total,
         "self_ms": round(own * 1000, 3), "cumulative_ms": round(cumulative * 1000, 3)}
        for (file, line, name), (_primitive, total, own, cumulative, _callers) in stats.stats.items()
    ]
    return {
        "total_profiled_seconds": round(stats.total_tt, 6),
        "top_self": sorted(rows, key=lambda row: row["self_ms"], reverse=True)[:limit],
        "top_cumulative": sorted(rows, key=lambda row: row["cumulative_ms"], reverse=True)[:limit],
    }


class VirtualTime:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return 1_800_000_000.0 + self.now

    def perf_counter(self) -> float:
        return time.perf_counter()

    def strftime(self, fmt: str) -> str:
        return time.strftime(fmt, time.gmtime(self.time()))


def loop_pass(
    module: types.ModuleType, config: dict[str, Any], frames: list[np.ndarray],
    frame_count: int, warmup: int, *, profiled: bool,
) -> dict[str, Any]:
    monitor = module.VisionMonitor(lambda: config, lambda _: None, lambda: [])
    clock = VirtualTime()
    stop = threading.Event()
    callback_queue: queue.Queue[Any] = queue.Queue()
    done = threading.Event()
    profile = cProfile.Profile()
    frame_start = 0
    preview_start = preview_count = 0
    preview_shape: list[int] | None = None
    start = end = 0.0
    profiled_phase = ""
    original_publish = monitor._publish_frame

    def publish(frame: np.ndarray, settings: dict[str, Any], **kwargs: Any) -> None:
        nonlocal preview_count, preview_shape
        original_publish(frame, settings, **kwargs)
        if kwargs.get("contains_camera_image"):
            preview_count += 1
            preview_shape = [int(frame.shape[1]), int(frame.shape[0])]

    monitor._publish_frame = publish

    class SyntheticCapture:
        index = 0

        def read(self) -> tuple[bool, np.ndarray | None]:
            nonlocal frame_start, preview_start, start, end, profiled_phase
            if self.index == warmup:
                frame_start = monitor._status.frame_sequence
                preview_start = preview_count
                profiled_phase = monitor._status.phase
                start = time.perf_counter()
                if profiled:
                    profile.enable()
            if self.index >= warmup + frame_count:
                end = time.perf_counter()
                if profiled:
                    profile.disable()
                stop.set()
                return False, None
            clock.now += 1.0 / float(config["camera_fps"]) + 1e-9
            self.index += 1
            return True, frames[(self.index - 1) % len(frames)]

        def release(self) -> None:
            pass

    capture = SyntheticCapture()
    monitor._open_capture = lambda _: (capture, None)
    original_time = module.time
    try:
        module.time = clock
        monitor._run(stop, callback_queue, done)
    finally:
        profile.disable()
        module.time = original_time
    if not end or monitor._status.last_error:
        raise RuntimeError(monitor._status.last_error or "Synthetic loop terminated prematurely")
    processed = monitor._status.frame_sequence - frame_start
    result = {
        "camera_frames": frame_count, "processed_frames": processed,
        "published_preview_frames": preview_count - preview_start,
        "preview_size_last": preview_shape,
        "phase_after_warmup": profiled_phase,
        "virtual_camera_seconds": frame_count / float(config["camera_fps"]),
        "processed_per_virtual_second": processed / (frame_count / float(config["camera_fps"])),
        "previews_per_virtual_second": (preview_count - preview_start) / (frame_count / float(config["camera_fps"])),
        "real_work_seconds": round(end - start, 6),
        "work_ms_per_processed_frame": round((end - start) * 1000 / max(1, processed), 3),
        "synthetic_change_events": monitor._status.detected_changes,
        "profiled": profiled,
    }
    if profiled:
        result["profile"] = profile_rows(profile)
    return result


def pair_pass(
    module: types.ModuleType, config: dict[str, Any], before: np.ndarray,
    after: np.ndarray, iterations: int, *, profiled: bool,
) -> dict[str, Any]:
    monitor = module.VisionMonitor(lambda: config, lambda _: None, lambda: [])
    # Initialize OpenCV's Lab/JPEG machinery before collecting timings.
    monitor._detect_changes(before, after, [], config)
    samples = []
    events: list[Any] = []
    suppressed = False
    profile = cProfile.Profile()
    if profiled:
        profile.enable()
    try:
        for _ in range(iterations):
            start = time.perf_counter()
            events, suppressed = monitor._detect_changes(before, after, [], config)
            samples.append((time.perf_counter() - start) * 1000)
    finally:
        profile.disable()
    result = {
        "iterations": iterations, "median_ms": round(float(np.median(samples)), 3),
        "p95_ms": round(float(np.percentile(samples, 95)), 3),
        "event_kinds_last_iteration": [event.kind for event in events],
        "events_last_iteration": [
            {"kind": event.kind, "bbox": list(event.bbox), "confidence": round(event.confidence, 6),
             "evidence_sha256": {
                 field: hashlib.sha256(payload).hexdigest() if payload else None
                 for field in ("before_jpeg", "after_jpeg", "scene_before_jpeg", "scene_after_jpeg")
                 for payload in (getattr(event, field),)
             }}
            for event in events
        ],
        "globally_suppressed_last_iteration": suppressed, "profiled": profiled,
    }
    if profiled:
        result["profile"] = profile_rows(profile)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-zip", type=Path, help="Optional trusted source snapshot containing app/vision.py")
    parser.add_argument("--threads", type=int, default=1, help="Explicit OpenCV CPU thread count (default: 1)")
    parser.add_argument("--frames", type=int, default=80, help="Synthetic camera frames per loop sample")
    parser.add_argument("--warmup-frames", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=10, help="Stable pair iterations")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--case", choices=CASES, action="append", dest="cases")
    parser.add_argument("--output", type=Path, help="Optional JSON report; no application data is written")
    args = parser.parse_args()
    if min(args.threads, args.frames, args.iterations) < 1 or args.warmup_frames < 1:
        parser.error("thread/frame/iteration/warmup counts must be positive")
    if args.width < 320 or args.height < 240:
        parser.error("minimum image dimensions are 320x240")

    cv2.setNumThreads(args.threads)
    cv2.ocl.setUseOpenCL(False)
    cv2.setRNGSeed(1842)
    module, source_sha256 = load_vision(args.source_zip)
    config = dict(module.VisionMonitor.DEFAULTS)
    config.update({
        "camera_width": args.width, "camera_height": args.height,
        "camera_fps": 10.0, "monitor_fps": 7.0, "accumulated_check_fps": 2.0,
        "preview_stream_fps": 5.0, "preview_max_width": 800, "preview_jpeg_quality": 78,
        "stabilization_analysis_width": 360, "min_change_area": 1800,
        "settle_seconds": 3.0, "stable_seconds": 1.2,
    })
    before, after, noisy = scenes(args.width, args.height)
    report: dict[str, Any] = {
        "scope": "Synthetic developer CPU benchmark on the executing host; not Pi FPS, paper results, or accuracy evaluation.",
        "limitations": "Virtual capture clock; no camera blocking, DB, callback consumer, network, browser, power or thermal measurement. Zero active tracked items.",
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "processor": platform.processor(), "python": platform.python_version(),
                 "opencv": cv2.__version__, "numpy": np.__version__,
                 "opencv_threads": cv2.getNumThreads(), "opencl": cv2.ocl.useOpenCL()},
        "source": str(args.source_zip) if args.source_zip else "app/vision.py",
        "vision_sha256": source_sha256, "config": config,
        "warmup_camera_frames": args.warmup_frames,
        "scene_seed": 1842, "cases": {},
    }
    for case in args.cases or CASES:
        if case in ("static", "sensor_noise"):
            frames = [before] if case == "static" else noisy
            unprofiled = loop_pass(module, config, frames, args.frames, args.warmup_frames, profiled=False)
            profiled = loop_pass(module, config, frames, args.frames, args.warmup_frames, profiled=True)
        else:
            target = before if case == "pair_none" else after
            unprofiled = pair_pass(module, config, before, target, args.iterations, profiled=False)
            profiled = pair_pass(module, config, before, target, args.iterations, profiled=True)
        report["cases"][case] = {"timing": unprofiled, "profile_run": profiled}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        summary = {case: data["timing"] for case, data in report["cases"].items()}
        print(json.dumps({"output": str(args.output), "host": report["host"], "cases": summary}, indent=2))
    else:
        print(rendered)


if __name__ == "__main__":
    main()
