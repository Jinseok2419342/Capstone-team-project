"""Desktop synthetic microbenchmark; values are not Raspberry Pi measurements."""
from pathlib import Path
import json
import statistics
import sys
import time
import types
from zipfile import ZipFile

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.vision import VisionMonitor
from alignment_probe import scene, changed


def measure(callable_, count=25):
    for _ in range(3):
        callable_()
    elapsed = []
    result = None
    for _ in range(count):
        start = time.perf_counter()
        result = callable_()
        elapsed.append((time.perf_counter() - start) * 1000)
    return {"median_ms": statistics.median(elapsed),
            "p95_ms": float(np.percentile(elapsed, 95)), "result": result}


def main():
    root = Path(__file__).resolve().parent
    before_module = types.ModuleType("app._vision_probe_before")
    before_module.__package__ = "app"
    sys.modules[before_module.__name__] = before_module
    with ZipFile(root / "source-before.zip") as z:
        exec(compile(z.read("app/vision.py"), "vision-before.py", "exec"), before_module.__dict__)
    baseline_monitor = before_module.VisionMonitor(lambda: {}, lambda e: None, lambda: [])
    current_monitor = VisionMonitor(lambda: {}, lambda e: None, lambda: [])
    config = dict(VisionMonitor.DEFAULTS, stabilization_analysis_width=360)
    frame = scene("rich")
    gray = current_monitor._prepare_gray(frame)
    object_frame = frame.copy()
    object_frame[300:344, 650:682] = (25, 35, 45)
    cases = {"identical": frame, "global_brightness": changed(frame, "add8"),
             "sensor_noise": changed(frame, "noise2"), "compact_object": object_frame}
    benchmarks = []
    for name, image in cases.items():
        current = current_monitor._prepare_gray(image)
        before = measure(lambda: baseline_monitor._has_motion(gray, current, config, already_aligned=True))
        after = measure(lambda: current_monitor._has_motion(gray, current, config, already_aligned=True))
        benchmarks.append({"case": name, "before": before, "after": after,
                           "speed_ratio": before["median_ms"] / after["median_ms"]})
    lighting = []
    plain = np.full((720, 1280, 3), 180, np.uint8)
    plain_gray = current_monitor._prepare_gray(plain)
    for width, height in ((32, 44), (12, 130), (200, 180), (400, 280)):
        for value in (25, 150):
            after = plain.copy()
            after[200:200 + height, 500:500 + width] = value
            current = current_monitor._prepare_gray(after)
            off = current_monitor._has_motion(plain_gray, current, config, already_aligned=True)
            on = current_monitor._has_motion(plain_gray, current,
                dict(config, motion_compensate_local_lighting=True), already_aligned=True)
            lighting.append({"size": [width, height], "object_value": value,
                             "local_compensation_off": off, "local_compensation_on": on})
    result = {"warning": "Synthetic desktop diagnostics, not camera accuracy or Raspberry Pi performance",
              "frame_size": [1280, 720], "opencv_threads": cv2.getNumThreads(), "iterations": 25,
              "benchmarks": benchmarks, "lighting_tradeoff": lighting}
    (root / "motion_probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
