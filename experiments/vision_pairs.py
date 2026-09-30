"""Offline evaluation of stable before/after image pairs.

The live monitor contains a motion/settling state machine.  This module tests
the stable-pair detector beneath that state machine, which makes all ablation
profiles consume exactly the same pixels.  It therefore measures local scene
change accuracy and compute time, not end-to-end camera or VLM latency.
"""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.vision import BBox, ChangeEvent, VisionMonitor, _ActiveBox

from .ablation import build_vision_config


PAIR_MANIFEST_FIELDS = (
    "trial_id",
    "scenario",
    "lighting",
    "nuisance",
    "before_image",
    "after_image",
    "event_ground_truth",
    "bbox_ground_truth",
    "active_item_id",
    "active_bbox",
    "active_reference_image",
    "active_background_image",
    "source_segment_seconds",
    "notes",
)

GROUND_TRUTH_KINDS = {"added", "moved", "removed", "none"}


@dataclass(frozen=True, slots=True)
class PairTrial:
    trial_id: str
    before_image: str
    after_image: str
    event_ground_truth: str
    scenario: str = ""
    lighting: str = ""
    nuisance: str = ""
    bbox_ground_truth: BBox | None = None
    active_item_id: str | None = None
    active_bbox: BBox | None = None
    active_reference_image: str | None = None
    active_background_image: str | None = None
    source_segment_seconds: float = 0.0
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PairDetectionResult:
    trial: PairTrial
    profile: str
    frame_width: int
    frame_height: int
    events: tuple[ChangeEvent, ...]
    global_change_suppressed: bool
    detection_latency_ms: float
    process_cpu_ms: float
    process_cpu_percent: float

    def as_row(self) -> dict[str, Any]:
        """Return a flat row while preserving every prediction as JSON."""

        return {
            "trial_id": self.trial.trial_id,
            "profile": self.profile,
            "scenario": self.trial.scenario,
            "lighting": self.trial.lighting,
            "nuisance": self.trial.nuisance,
            "event_ground_truth": self.trial.event_ground_truth,
            "bbox_ground_truth": format_bbox(self.trial.bbox_ground_truth),
            "active_item_id": self.trial.active_item_id or "",
            "active_bbox": format_bbox(self.trial.active_bbox),
            "source_segment_seconds": self.trial.source_segment_seconds,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "prediction_count": len(self.events),
            "predicted_events_json": json.dumps(
                [
                    {
                        "kind": event.kind,
                        "bbox": list(event.bbox),
                        "confidence": round(float(event.confidence), 8),
                        "matched_item_id": event.matched_item_id,
                    }
                    for event in self.events
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "global_change_suppressed": int(self.global_change_suppressed),
            "detection_latency_ms": round(self.detection_latency_ms, 6),
            "process_cpu_ms": round(self.process_cpu_ms, 6),
            "process_cpu_percent": round(self.process_cpu_percent, 3),
            "notes": self.trial.notes,
        }


def parse_bbox(value: str | None) -> BBox | None:
    """Parse ``x;y;w;h``, comma-separated, or JSON-array bboxes."""

    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("["):
        try:
            values = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid bbox JSON: {text!r}") from exc
    else:
        separator = ";" if ";" in text else ","
        values = [part.strip() for part in text.split(separator)]
    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise ValueError(f"bbox must have four values: {text!r}")
    try:
        x, y, width, height = (int(float(part)) for part in values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"bbox contains a non-numeric value: {text!r}") from exc
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError(f"bbox must use non-negative x/y and positive width/height: {text!r}")
    return x, y, width, height


def format_bbox(bbox: BBox | None) -> str:
    return "" if bbox is None else ";".join(str(value) for value in bbox)


def read_pair_manifest(path: Path) -> list[PairTrial]:
    """Read and validate a stable-pair CSV manifest."""

    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        required = {"trial_id", "before_image", "after_image", "event_ground_truth"}
        missing = sorted(required.difference(fieldnames))
        if missing:
            raise ValueError(f"pair manifest is missing columns: {', '.join(missing)}")

        trials: list[PairTrial] = []
        seen: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            trial_id = str(row.get("trial_id") or "").strip()
            if not trial_id:
                raise ValueError(f"line {line_number}: trial_id is required")
            if trial_id in seen:
                raise ValueError(f"line {line_number}: duplicate trial_id {trial_id!r}")
            seen.add(trial_id)

            kind = str(row.get("event_ground_truth") or "").strip().lower()
            if kind not in GROUND_TRUTH_KINDS:
                raise ValueError(
                    f"line {line_number}: event_ground_truth must be one of "
                    f"{', '.join(sorted(GROUND_TRUTH_KINDS))}"
                )
            before_image = str(row.get("before_image") or "").strip()
            after_image = str(row.get("after_image") or "").strip()
            if not before_image or not after_image:
                raise ValueError(
                    f"line {line_number}: before_image and after_image are required"
                )

            try:
                seconds = float(row.get("source_segment_seconds") or 0.0)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"line {line_number}: source_segment_seconds is invalid"
                ) from exc
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError(
                    f"line {line_number}: source_segment_seconds must be finite and non-negative"
                )

            bbox = parse_bbox(row.get("bbox_ground_truth"))
            if kind != "none" and bbox is None:
                raise ValueError(
                    f"line {line_number}: {kind} ground truth requires bbox_ground_truth"
                )
            if kind == "none" and bbox is not None:
                raise ValueError(
                    f"line {line_number}: none ground truth must not have bbox_ground_truth"
                )
            active_bbox = parse_bbox(row.get("active_bbox"))
            active_item_id = str(row.get("active_item_id") or "").strip() or None
            if (active_bbox is None) != (active_item_id is None):
                raise ValueError(
                    f"line {line_number}: active_item_id and active_bbox must be provided together"
                )
            if kind in {"moved", "removed"} and active_bbox is None:
                raise ValueError(
                    f"line {line_number}: {kind} trials require active_item_id and active_bbox"
                )

            trials.append(
                PairTrial(
                    trial_id=trial_id,
                    before_image=before_image,
                    after_image=after_image,
                    event_ground_truth=kind,
                    scenario=str(row.get("scenario") or "").strip(),
                    lighting=str(row.get("lighting") or "").strip(),
                    nuisance=str(row.get("nuisance") or "").strip(),
                    bbox_ground_truth=bbox,
                    active_item_id=active_item_id,
                    active_bbox=active_bbox,
                    active_reference_image=(
                        str(row.get("active_reference_image") or "").strip() or None
                    ),
                    active_background_image=(
                        str(row.get("active_background_image") or "").strip() or None
                    ),
                    source_segment_seconds=seconds,
                    notes=str(row.get("notes") or ""),
                )
            )
    return trials


def detect_stable_pair(
    trial: PairTrial,
    *,
    manifest_dir: Path,
    profile: str,
    config_overrides: dict[str, Any] | None = None,
    monitor: VisionMonitor | None = None,
) -> PairDetectionResult:
    """Run one stable image pair through the production change detector."""

    base_dir = Path(manifest_dir)
    before = _read_image(_resolve_image(base_dir, trial.before_image))
    after = _read_image(_resolve_image(base_dir, trial.after_image))
    if before.shape[:2] != after.shape[:2]:
        raise ValueError(
            f"trial {trial.trial_id!r}: before/after dimensions differ "
            f"({before.shape[1]}x{before.shape[0]} vs {after.shape[1]}x{after.shape[0]})"
        )
    if trial.bbox_ground_truth is not None:
        _ensure_bbox_inside(
            trial.bbox_ground_truth,
            before.shape[1],
            before.shape[0],
            trial.trial_id,
            label="bbox_ground_truth",
        )

    active_boxes: list[_ActiveBox] = []
    if trial.active_bbox is not None and trial.active_item_id is not None:
        _ensure_bbox_inside(
            trial.active_bbox,
            before.shape[1],
            before.shape[0],
            trial.trial_id,
            label="active_bbox",
        )
        reference = _evidence_jpeg(
            base_dir,
            trial.active_reference_image,
            before,
            trial.active_bbox,
        )
        background = _evidence_jpeg(
            base_dir,
            trial.active_background_image,
            after,
            trial.active_bbox,
        )
        active_boxes.append(
            _ActiveBox(
                item_id=trial.active_item_id,
                bbox=trial.active_bbox,
                reference_jpeg=reference,
                background_jpeg=background,
            )
        )

    detector = monitor or VisionMonitor(lambda: {}, lambda _: None, lambda: [])
    config = build_vision_config(profile, config_overrides)
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    events, global_change = detector._detect_changes(  # noqa: SLF001 - exact production core
        before,
        after,
        active_boxes,
        config,
    )
    elapsed = max(0.0, time.perf_counter() - wall_start)
    cpu_elapsed = max(0.0, time.process_time() - cpu_start)
    cpu_percent = 0.0 if elapsed <= 0.0 else cpu_elapsed / elapsed * 100.0
    return PairDetectionResult(
        trial=trial,
        profile=profile,
        frame_width=before.shape[1],
        frame_height=before.shape[0],
        events=tuple(events),
        global_change_suppressed=bool(global_change),
        detection_latency_ms=elapsed * 1000.0,
        process_cpu_ms=cpu_elapsed * 1000.0,
        process_cpu_percent=cpu_percent,
    )


def _resolve_image(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValueError(f"could not read image: {path}")
    return image


def _ensure_bbox_inside(
    bbox: BBox,
    width: int,
    height: int,
    trial_id: str,
    *,
    label: str,
) -> None:
    x, y, box_width, box_height = bbox
    if x + box_width > width or y + box_height > height:
        raise ValueError(
            f"trial {trial_id!r}: {label} {bbox!r} exceeds {width}x{height} frame"
        )


def _evidence_jpeg(
    base_dir: Path,
    configured_path: str | None,
    fallback_frame: np.ndarray,
    bbox: BBox,
) -> bytes:
    if configured_path:
        evidence = _read_image(_resolve_image(base_dir, configured_path))
        if evidence.shape[:2] == fallback_frame.shape[:2]:
            x, y, width, height = bbox
            evidence = evidence[y : y + height, x : x + width]
    else:
        x, y, width, height = bbox
        evidence = fallback_frame[y : y + height, x : x + width]
    if evidence.size == 0:
        raise ValueError("active-item evidence crop is empty")
    ok, encoded = cv2.imencode(".jpg", evidence, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise ValueError("could not encode active-item evidence")
    return encoded.tobytes()
