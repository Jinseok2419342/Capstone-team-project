"""Deterministic desktop-only synthetic alignment probe; no camera access."""
from pathlib import Path
import json
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.vision import VisionMonitor


def scene(kind):
    y, x = np.indices((720, 1280))
    plane = (180 + 5 * np.sin(x / 31) + 4 * np.cos(y / 27)).astype(np.uint8)
    frame = np.repeat(plane[:, :, None], 3, axis=2)
    if kind == "rich":
        for row in range(4):
            for col in range(6):
                left, top = 40 + col * 210, 40 + row * 175
                cv2.rectangle(frame, (left, top), (left + 100, top + 75),
                              (60 + (col * 17) % 70, 85, 110), 3)
                cv2.circle(frame, (left + 50, top + 35), 12, (95, 105, 135), -1)
    elif kind == "sparse":
        cv2.rectangle(frame, (490, 280), (730, 420), (35, 45, 55), -1)
        for row in range(4):
            for col in range(6):
                cv2.circle(frame, (510 + col * 38, 300 + row * 30), 5,
                           (140, 150, 160), -1)
    elif kind == "weak":
        for row in range(4):
            for col in range(6):
                cv2.rectangle(frame, (40 + col * 210, 40 + row * 175),
                              (140 + col * 210, 115 + row * 175), (165, 165, 165), 2)
    return frame


def changed(frame, mode, seed=20260918):
    rng = np.random.default_rng(seed)
    y, x = np.indices(frame.shape[:2])
    out = frame.astype(np.float32)
    if mode.startswith("noise"):
        out += rng.normal(0, int(mode[5:]), frame.shape)
    elif mode.startswith("add"):
        out += int(mode[3:])
    elif mode.startswith("gain"):
        out *= float(mode[4:])
    elif mode.startswith("spot"):
        out += int(mode[4:]) * np.exp(-((x - 540) ** 2 / 320 ** 2 + (y - 290) ** 2 / 220 ** 2))[:, :, None]
    elif mode.startswith("gradient"):
        out += (int(mode[8:]) * (x / 1280 - 0.5))[:, :, None]
    elif mode.startswith("blur"):
        out = cv2.GaussianBlur(frame, (0, 0), float(mode[4:]))
    elif mode.startswith("jpeg"):
        out = cv2.imdecode(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(mode[4:])])[1], cv2.IMREAD_COLOR)
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    monitor = VisionMonitor(lambda: {}, lambda event: None, lambda: [])
    config = dict(monitor.DEFAULTS, stabilization_analysis_width=360)
    records = []
    modes = ["noise2", "noise5", "noise10", "add8", "add20", "gain1.06", "gain1.15",
             "spot20", "spot40", "gradient20", "gradient40", "blur1.2", "blur2.5", "jpeg60"]
    for kind in ("rich", "sparse", "weak"):
        baseline = scene(kind)
        gray = monitor._prepare_gray(baseline)
        for mode in modes:
            after = changed(baseline, mode)
            current = monitor._prepare_gray(after)
            started = time.perf_counter()
            affine = monitor._estimate_euclidean_alignment(gray, current, config)
            affine_ms = 1000 * (time.perf_counter() - started)
            started = time.perf_counter()
            translation = monitor._estimate_translation(gray, current, config)
            translation_ms = 1000 * (time.perf_counter() - started)
            moving, ratio = monitor._has_motion(gray, current, config)
            row = {"scene": kind, "mode": mode, "affine_ms": round(affine_ms, 3),
                   "translation_ms": round(translation_ms, 3), "translation": translation,
                   "motion": moving, "motion_ratio": ratio}
            if affine is not None:
                matrix = affine[0]
                corners = np.float32([[0, 0, 1], [1280, 0, 1], [0, 720, 1], [1280, 720, 1]])
                offsets = corners @ matrix.T - corners[:, :2]
                row.update(affine=matrix.tolist(), response=affine[1], max_corner_shift=float(np.linalg.norm(offsets, axis=1).max()))
            else:
                row.update(affine=None, response=None, max_corner_shift=None)
            if moving or (row["max_corner_shift"] or 0) >= 0.25:
                events, global_change = monitor._detect_changes(baseline, after, [], config)
                row.update(events=[(event.kind, event.bbox) for event in events], global_change=global_change)
            records.append(row)
    output = {"frame_size": [1280, 720], "analysis_width": 360, "opencv_threads": cv2.getNumThreads(),
              "warning": "Synthetic desktop diagnostics, not camera accuracy or Raspberry Pi performance", "records": records}
    path = Path(__file__).with_name("alignment_probe.json")
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(path), "cases": len(records), "motion_cases": [row for row in records if row["motion"]],
                      "artificial_warp_cases": [row for row in records if (row["max_corner_shift"] or 0) >= 0.25]}, indent=2))


if __name__ == "__main__":
    main()
