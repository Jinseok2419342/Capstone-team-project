"""Threaded, fixed-camera change detection for the lost-and-found system.

The module deliberately has no dependencies on the rest of the application.  A
``VisionMonitor`` receives its configuration and active-item list through
callables, making it usable from Flask, FastAPI, a CLI demo, or tests.

Bounding boxes use the OpenCV convention ``(x, y, width, height)`` in source
frame pixels.  ``before_jpeg`` and ``after_jpeg`` are matching crops of the
same region.  ``crop_jpeg`` points to the useful object crop: the after crop
for an addition/relocation and the before crop for a removal.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Literal

import cv2
import numpy as np

from .camera_sources import CameraCapture, open_camera_capture


BBox = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class ChangeEvent:
    """A stable visual change relative to the previous stable baseline."""

    kind: Literal["added", "removed", "moved", "verify_removed"]
    bbox: BBox
    crop_jpeg: bytes | None
    before_jpeg: bytes | None
    after_jpeg: bytes | None
    confidence: float
    matched_item_id: Any | None = None
    # Downscaled, marked full-scene evidence is kept in memory only long
    # enough for multimodal classification.  Crops remain the high-detail
    # evidence while these frames preserve the before/after direction and
    # surrounding context.
    scene_before_jpeg: bytes | None = None
    scene_after_jpeg: bytes | None = None


@dataclass(slots=True)
class VisionStatus:
    """Small, JSON-serialisable snapshot of monitor health and progress."""

    running: bool = False
    camera_connected: bool = False
    using_fallback: bool = True
    privacy_enabled: bool = False
    phase: str = "stopped"
    baseline_ready: bool = False
    motion_detected: bool = False
    frame_width: int = 640
    frame_height: int = 480
    fps: float = 0.0
    frame_sequence: int = 0
    detected_changes: int = 0
    last_frame_at: float | None = None
    last_motion_at: float | None = None
    last_change_at: float | None = None
    last_baseline_at: float | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class _ActiveBox:
    item_id: Any
    bbox: BBox
    reference_jpeg: bytes | None = None
    background_jpeg: bytes | None = None


_CALLBACK_STOP = object()


class VisionMonitor:
    """Monitor a fixed camera and emit added/removed object events.

    Parameters
    ----------
    config_getter:
        Called periodically and expected to return a dictionary.  It may return
        vision keys directly or below a ``vision`` key.
    change_callback:
        Receives each :class:`ChangeEvent`.  It runs on a callback worker, not
        the capture thread, so an API or database operation cannot stall video.
    active_items_getter:
        Returns dictionaries containing ``id`` and ``bbox``.  A bbox can be a
        four-element sequence, a JSON string, or a mapping with x/y/w/h keys.
    event_callback:
        Optional operational callback receiving dictionaries such as
        ``{"type": "camera_connected", "timestamp": ...}``.
    """

    DEFAULTS: dict[str, Any] = {
        "camera_index": 0,
        "camera_width": 1280,
        "camera_height": 720,
        "camera_fps": 20,
        "monitor_fps": 12.0,
        "accumulated_check_fps": 4.0,
        "fallback_fps": 2.0,
        "camera_retry_seconds": 2.0,
        "camera_failures_before_retry": 4,
        # Many webcams keep hunting exposure/focus for a few seconds after
        # opening.  Do not freeze that transient image into the baseline.
        "camera_warmup_seconds": 3.0,
        "settle_seconds": 1.25,
        "stable_seconds": 1.0,
        "motion_threshold": 20,
        "motion_min_area": 420,
        "motion_min_ratio": 0.001,
        "change_threshold": 24,
        "min_change_area": 500,
        "min_change_area_ratio": 0.0007,
        "compact_change_area_factor": 0.28,
        "compact_change_min_density": 0.24,
        "elongated_change_area_factor": 0.035,
        "elongated_change_min_length": 28,
        "elongated_change_min_aspect": 3.0,
        "elongated_change_min_density": 0.08,
        "max_change_ratio": 0.42,
        "contour_merge_gap": 22,
        "bbox_padding": 10,
        "bbox_support_threshold_factor": 0.55,
        "bbox_support_max_scale": 3.0,
        "support_fallback_min_density": 0.55,
        "support_fallback_edge_factor": 0.10,
        "support_fallback_structure_similarity": 0.90,
        "illumination_structure_similarity": 0.65,
        "illumination_structure_min_energy": 0.20,
        "illumination_chroma_limit": 8.0,
        "removal_overlap": 0.18,
        "reference_match_min": 0.58,
        "removal_similarity_drop": 0.20,
        "background_match_min": 0.72,
        "background_similarity_gain": 0.15,
        "relocation_match_min": 0.72,
        "relocation_max_distance_ratio": 0.35,
        "relocation_min_shift": 8.0,
        # Fixed webcams still move by a few pixels because of desk vibration,
        # autofocus and inexpensive mounts.  Estimate the global translation
        # from the background and warp frames back onto the stable baseline
        # before looking for local object changes.
        "stabilize_camera": True,
        "stabilization_max_shift": 6.0,
        "stabilization_max_feature_shift": 24.0,
        "stabilization_min_response": 0.12,
        "stabilization_max_rotation": 0.75,
        # Autofocus on inexpensive webcams commonly changes the apparent
        # field of view by roughly one to three percent even when the mount is
        # perfectly still.  Distributed reference features and RANSAC make
        # this safe to correct without treating one moving object as a zoom.
        # Leave margin above the common 2% boundary: interpolation and JPEG
        # noise can make an actual 2% breath estimate a few ten-thousandths
        # larger and must not create an abrupt alignment cliff.
        "stabilization_max_scale_change": 0.03,
        "stabilization_analysis_width": 480,
        # Avoid resampling a genuinely still preview when feature estimates
        # merely fluctuate around the identity transform.
        "stabilization_translation_deadband": 0.25,
        "stabilization_rotation_deadband": 0.025,
        "stabilization_scale_deadband": 0.0005,
        # Residual lens breathing is not always a single affine transform:
        # different parts of a cheap lens can drift by a pixel or two.  Such
        # residuals form thin, matching bands around edges that exist in both
        # frames.  Suppress only those persistent-edge bands; new opaque
        # objects and hands still have unsupported interiors and remain
        # visible to motion/change detection.
        "micro_jitter_suppression": True,
        "micro_jitter_edge_threshold": 12.0,
        "micro_jitter_edge_radius": 1,
        "compensate_local_lighting": True,
        "motion_compensate_local_lighting": False,
        "lighting_blur_ratio": 0.04,
        "lighting_analysis_width": 320,
        # Unmatched changes touching the optical frame boundary are commonly
        # exposure/focus artefacts. Tracked items are still allowed to be
        # recovered there; this guard applies only to new-object candidates.
        "change_border_margin": 8,
        "change_border_margin_ratio": 0.04,
        "jpeg_quality": 88,
        "preview_jpeg_quality": 84,
        "ai_scene_max_width": 960,
        "ai_scene_jpeg_quality": 72,
        "compensate_lighting": True,
        "draw_active_boxes": True,
        "active_items_refresh_seconds": 1.0,
        "event_overlay_seconds": 4.0,
        "flip_horizontal": False,
        "rotate": 0,
    }

    def __init__(
        self,
        config_getter: Callable[[], dict[str, Any]],
        change_callback: Callable[[ChangeEvent], None],
        active_items_getter: Callable[[], list[dict[str, Any]]],
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._config_getter = config_getter
        self._change_callback = change_callback
        self._active_items_getter = active_items_getter
        self._event_callback = event_callback

        self._lock = threading.RLock()
        self._capture_lock = threading.Lock()
        self._status = VisionStatus()
        self._thread: threading.Thread | None = None
        self._dispatcher_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._callback_queue: queue.Queue[Any] | None = None
        self._capture: CameraCapture | None = None
        self._rebaseline_generation = 0
        self._manual_reconcile_generation: int | None = None
        self._recent_boxes: list[tuple[BBox, str, float]] = []

        initial = self._make_notice_frame(
            self.DEFAULTS["camera_width"],
            self.DEFAULTS["camera_height"],
            "CAMERA STARTING",
            "Waiting for the vision monitor",
        )
        self._latest_jpeg = self._encode_jpeg(initial, self.DEFAULTS["jpeg_quality"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start capture and callback workers.  Calling twice is harmless."""

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            stop_event = threading.Event()
            callback_queue: queue.Queue[Any] = queue.Queue(maxsize=128)
            self._stop_event = stop_event
            self._callback_queue = callback_queue
            self._status.running = True
            self._status.phase = "starting"
            self._status.last_error = None

            dispatcher = threading.Thread(
                target=self._dispatch_callbacks,
                args=(callback_queue,),
                name="vision-callbacks",
                daemon=True,
            )
            monitor = threading.Thread(
                target=self._run,
                args=(stop_event, callback_queue),
                name="vision-monitor",
                daemon=True,
            )
            self._dispatcher_thread = dispatcher
            self._thread = monitor

        dispatcher.start()
        monitor.start()
        self._enqueue_callback(
            callback_queue,
            "event",
            {"type": "monitor_started", "timestamp": time.time()},
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop capture, release the camera, and drain queued callbacks."""

        with self._lock:
            monitor = self._thread
            dispatcher = self._dispatcher_thread
            stop_event = self._stop_event
            callback_queue = self._callback_queue

        if stop_event is not None:
            stop_event.set()

        if monitor is not None and monitor.is_alive():
            monitor.join(max(0.1, timeout))
            if monitor.is_alive():
                # Some camera backends block inside read().  Releasing from the
                # outside is a best-effort escape hatch after the normal join.
                with self._capture_lock:
                    capture = self._capture
                    if capture is not None:
                        capture.release()
                monitor.join(1.0)

        if callback_queue is not None:
            try:
                callback_queue.put_nowait(_CALLBACK_STOP)
            except queue.Full:
                try:
                    callback_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    callback_queue.put_nowait(_CALLBACK_STOP)
                except queue.Full:
                    pass

        if dispatcher is not None and dispatcher.is_alive():
            dispatcher.join(min(max(0.1, timeout), 2.0))

        with self._lock:
            if self._thread is monitor:
                self._thread = None
                self._dispatcher_thread = None
                self._stop_event = None
                self._callback_queue = None
            self._status.running = False
            self._status.phase = "stopped"
            self._status.motion_detected = False

    def get_jpeg(self) -> bytes:
        """Return the latest complete JPEG, suitable for an MJPEG endpoint."""

        with self._lock:
            return bytes(self._latest_jpeg)

    def get_status(self) -> dict[str, Any]:
        """Return a thread-safe, JSON-compatible status dictionary."""

        with self._lock:
            return asdict(self._status)

    def rebaseline(self, *, reconcile_items: bool = False) -> None:
        """Discard the old scene baseline at the next live camera frame.

        ``reconcile_items`` is reserved for the administrator's explicit
        rebaseline action. Routine vision-setting changes must not silently
        recover stored rows merely because they also need a new baseline.
        """

        with self._lock:
            self._rebaseline_generation += 1
            if reconcile_items:
                self._manual_reconcile_generation = self._rebaseline_generation
            self._status.baseline_ready = False
            if self._status.running and not self._status.privacy_enabled:
                self._status.phase = "rebaseline_pending"
            callback_queue = self._callback_queue
        self._enqueue_callback(
            callback_queue,
            "event",
            {"type": "rebaseline_requested", "timestamp": time.time()},
        )

    def set_privacy(self, enabled: bool) -> None:
        """Hide camera imagery and suspend analysis until privacy is disabled."""

        enabled = bool(enabled)
        with self._lock:
            if self._status.privacy_enabled == enabled:
                return
            self._status.privacy_enabled = enabled
            self._status.baseline_ready = False
            self._status.motion_detected = False
            self._status.phase = "privacy" if enabled else "rebaseline_pending"
            self._rebaseline_generation += 1
            width = self._status.frame_width
            height = self._status.frame_height
            callback_queue = self._callback_queue
            if enabled:
                frame = self._make_notice_frame(
                    width,
                    height,
                    "PRIVACY MODE",
                    "Camera imagery and detection are paused",
                )
                self._latest_jpeg = self._encode_jpeg(frame, 88)

        self._enqueue_callback(
            callback_queue,
            "event",
            {
                "type": "privacy_changed",
                "enabled": enabled,
                "timestamp": time.time(),
            },
        )

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _run(
        self,
        stop_event: threading.Event,
        callback_queue: queue.Queue[Any],
    ) -> None:
        capture: CameraCapture | None = None
        capture_signature: tuple[Any, ...] | None = None
        next_open_attempt = 0.0
        read_failures = 0
        camera_was_connected = False
        camera_opened_mono: float | None = None
        offline_error_reported = False

        baseline_frame: np.ndarray | None = None
        previous_gray: np.ndarray | None = None
        calibration_still_since: float | None = None
        last_motion_mono = 0.0
        stable_since: float | None = None
        phase = "calibrating"
        observed_rebaseline = -1
        reconcile_on_baseline = False

        active_boxes: list[_ActiveBox] = []
        next_active_refresh = 0.0
        config = dict(self.DEFAULTS)
        next_config_refresh = 0.0
        last_processed_mono = 0.0
        last_accumulated_check_mono = 0.0
        last_fallback_mono = 0.0
        last_frame_mono: float | None = None
        smoothed_fps = 0.0

        try:
            while not stop_event.is_set():
                now_mono = time.monotonic()

                if now_mono >= next_config_refresh:
                    config = self._read_config()
                    next_config_refresh = now_mono + 0.5

                signature = self._camera_signature(config)
                if capture is not None and signature != capture_signature:
                    self._release_capture(capture)
                    capture = None
                    capture_signature = None
                    camera_opened_mono = None
                    next_open_attempt = now_mono
                    baseline_frame = None
                    previous_gray = None
                    phase = "calibrating"

                if capture is None and now_mono >= next_open_attempt:
                    capture, open_error = self._open_capture(config)
                    if capture is not None:
                        capture_signature = signature
                        camera_opened_mono = now_mono
                        read_failures = 0
                        baseline_frame = None
                        previous_gray = None
                        calibration_still_since = None
                        stable_since = None
                        phase = "calibrating"
                        observed_rebaseline = self._current_rebaseline_generation()
                        with self._capture_lock:
                            self._capture = capture
                        self._set_camera_status(True, None)
                        if not camera_was_connected:
                            self._emit_event(callback_queue, "camera_connected")
                        camera_was_connected = True
                        offline_error_reported = False
                    else:
                        retry = self._float_config(
                            config, "camera_retry_seconds", minimum=0.25
                        )
                        next_open_attempt = now_mono + retry
                        self._set_camera_status(False, open_error)
                        if camera_was_connected:
                            self._emit_event(
                                callback_queue,
                                "camera_disconnected",
                                error=open_error,
                            )
                        if not offline_error_reported:
                            self._emit_event(
                                callback_queue,
                                "camera_error",
                                error=open_error,
                                message=open_error,
                            )
                            offline_error_reported = True
                        camera_was_connected = False

                if capture is None:
                    fallback_fps = self._float_config(
                        config, "fallback_fps", minimum=0.2, maximum=10.0
                    )
                    if now_mono - last_fallback_mono >= 1.0 / fallback_fps:
                        self._publish_fallback(config)
                        last_fallback_mono = now_mono
                    stop_event.wait(0.05)
                    continue

                ok, frame = capture.read()
                if not ok or frame is None or frame.size == 0:
                    read_failures += 1
                    allowed_failures = self._int_config(
                        config,
                        "camera_failures_before_retry",
                        minimum=1,
                        maximum=30,
                    )
                    if read_failures >= allowed_failures:
                        error = "Camera stopped returning frames"
                        self._release_capture(capture)
                        capture = None
                        capture_signature = None
                        camera_opened_mono = None
                        with self._capture_lock:
                            self._capture = None
                        next_open_attempt = now_mono + self._float_config(
                            config, "camera_retry_seconds", minimum=0.25
                        )
                        self._set_camera_status(False, error)
                        if camera_was_connected:
                            self._emit_event(
                                callback_queue,
                                "camera_disconnected",
                                error=error,
                            )
                        if not offline_error_reported:
                            self._emit_event(
                                callback_queue,
                                "camera_error",
                                error=error,
                                message=error,
                            )
                            offline_error_reported = True
                        camera_was_connected = False
                        baseline_frame = None
                        previous_gray = None
                    else:
                        stop_event.wait(0.03)
                    continue

                read_failures = 0
                frame = self._transform_frame(frame, config)
                now_mono = time.monotonic()
                monitor_fps = self._float_config(
                    config, "monitor_fps", minimum=1.0, maximum=60.0
                )
                if now_mono - last_processed_mono < 1.0 / monitor_fps:
                    continue
                last_processed_mono = now_mono

                if last_frame_mono is not None and now_mono > last_frame_mono:
                    instant_fps = 1.0 / (now_mono - last_frame_mono)
                    smoothed_fps = (
                        instant_fps
                        if smoothed_fps <= 0.0
                        else smoothed_fps * 0.88 + instant_fps * 0.12
                    )
                last_frame_mono = now_mono
                self._mark_live_frame(frame, smoothed_fps)

                if self._privacy_enabled():
                    baseline_frame = None
                    previous_gray = None
                    calibration_still_since = None
                    stable_since = None
                    phase = "privacy"
                    self._set_detection_status(phase, False, False)
                    self._publish_privacy(frame.shape[1], frame.shape[0], config)
                    continue

                generation = self._current_rebaseline_generation()
                if generation != observed_rebaseline:
                    observed_rebaseline = generation
                    reconcile_on_baseline = self._should_reconcile_generation(
                        generation
                    )
                    baseline_frame = None
                    previous_gray = None
                    calibration_still_since = None
                    stable_since = None
                    phase = "calibrating"

                # Keep analysis in the baseline coordinate system.  Pairwise
                # motion compensation alone prevents false triggers, but
                # stabilising against the long-lived baseline also prevents a
                # one- or two-pixel camera wobble from slowly walking stored
                # object boxes away from their real location.
                analysis_frame = frame
                analysis_aligned = False
                gray = self._prepare_gray(frame)
                reference_gray: np.ndarray | None = None
                if (
                    baseline_frame is not None
                    and baseline_frame.shape[:2] == frame.shape[:2]
                    and self._bool_config(config, "stabilize_camera")
                ):
                    reference_gray = self._prepare_gray(baseline_frame)
                    euclidean = self._estimate_euclidean_alignment(
                        reference_gray, gray, config
                    )
                    minimum_response = self._float_config(
                        config,
                        "stabilization_min_response",
                        minimum=0.0,
                        maximum=1.0,
                    )
                    if euclidean is not None and euclidean[1] >= minimum_response:
                        analysis_frame, valid_mask = self._warp_affine(
                            frame, euclidean[0]
                        )
                        analysis_aligned = True
                    else:
                        translation = self._estimate_translation(
                            reference_gray, gray, config
                        )
                        if self._translation_is_usable(
                            translation, gray.shape, config
                        ):
                            analysis_frame, valid_mask = self._warp_translation(
                                frame, translation[0], translation[1]
                            )
                            analysis_aligned = True
                        else:
                            valid_mask = np.full(gray.shape, 255, dtype=np.uint8)

                    if analysis_frame is not frame:
                        # A translated image has a thin invalid strip at its
                        # edge. Filling it from the baseline prevents that
                        # synthetic border from becoming an object candidate.
                        analysis_frame[valid_mask == 0] = baseline_frame[
                            valid_mask == 0
                        ]
                        gray = self._prepare_gray(analysis_frame)
                if previous_gray is not None and previous_gray.shape != gray.shape:
                    baseline_frame = None
                    previous_gray = None
                    calibration_still_since = None
                    phase = "calibrating"

                if now_mono >= next_active_refresh:
                    active_boxes = self._fetch_active_boxes(
                        frame.shape[1], frame.shape[0], active_boxes
                    )
                    refresh = self._float_config(
                        config,
                        "active_items_refresh_seconds",
                        minimum=0.25,
                        maximum=60.0,
                    )
                    next_active_refresh = now_mono + refresh

                moving = False
                if previous_gray is not None:
                    moving, _ = self._has_motion(
                        previous_gray,
                        gray,
                        config,
                        already_aligned=analysis_aligned,
                    )

                # Very slow placement can change too little between adjacent
                # frames to trip motion detection.  While monitoring, compare
                # against the stable scene as well.  Once an accumulated local
                # change exists, the ordinary settle/stabilise state machine
                # takes over and waits for hands to leave before analysis.
                if phase == "monitoring" and not moving and reference_gray is not None:
                    accumulated_fps = self._float_config(
                        config,
                        "accumulated_check_fps",
                        minimum=1.0,
                        maximum=monitor_fps,
                    )
                    if (
                        now_mono - last_accumulated_check_mono
                        >= 1.0 / accumulated_fps
                    ):
                        last_accumulated_check_mono = now_mono
                        # Accumulation changes the comparison frame, not the
                        # user's sensitivity contract.  Lowering threshold,
                        # area and ratio here used to turn harmless autofocus
                        # residue into perpetual motion despite a deliberately
                        # less-sensitive camera setting.
                        moving, _ = self._has_motion(
                            reference_gray,
                            gray,
                            config,
                            already_aligned=analysis_aligned,
                        )

                if baseline_frame is None:
                    if previous_gray is None:
                        calibration_still_since = now_mono
                    elif moving:
                        calibration_still_since = None
                    elif calibration_still_since is None:
                        calibration_still_since = now_mono

                    stable_seconds = self._float_config(
                        config, "stable_seconds", minimum=0.0, maximum=30.0
                    )
                    calm_for = (
                        0.0
                        if calibration_still_since is None
                        else now_mono - calibration_still_since
                    )
                    camera_warmed_up = self._camera_warmup_complete(
                        camera_opened_mono,
                        now_mono,
                        config,
                    )
                    if (
                        calibration_still_since is not None
                        and calm_for >= stable_seconds
                        and camera_warmed_up
                    ):
                        baseline_frame = frame.copy()
                        phase = "monitoring"
                        self._set_baseline_ready()
                        self._emit_event(callback_queue, "baseline_ready")
                        if reconcile_on_baseline:
                            active_boxes = self._fetch_active_boxes(
                                frame.shape[1], frame.shape[0], active_boxes
                            )
                            reconciled = self._reconcile_absent_active_items(
                                frame,
                                active_boxes,
                                config,
                            )
                            reconcile_on_baseline = False
                            if reconciled:
                                self._record_events(reconciled, config)
                                for event in reconciled:
                                    self._enqueue_callback(
                                        callback_queue, "change", event
                                    )
                                    self._emit_event(
                                        callback_queue,
                                        "change_detected",
                                        kind=event.kind,
                                        bbox=list(event.bbox),
                                        confidence=event.confidence,
                                        matched_item_id=event.matched_item_id,
                                        source="manual_rebaseline",
                                    )
                    else:
                        phase = "calibrating"

                    self._set_detection_status(
                        phase, moving, baseline_frame is not None
                    )
                    output = self._draw_overlay(
                        analysis_frame, phase, moving, active_boxes, config
                    )
                    self._publish_frame(output, config, contains_camera_image=True)
                    previous_gray = gray
                    continue

                events: list[ChangeEvent] = []
                if phase == "monitoring":
                    if moving:
                        phase = "settling"
                        last_motion_mono = now_mono
                        stable_since = None
                        self._mark_motion()
                        self._emit_event(callback_queue, "motion_detected")
                else:
                    if moving:
                        phase = "settling"
                        last_motion_mono = now_mono
                        stable_since = None
                        self._mark_motion()
                    else:
                        settle_seconds = self._float_config(
                            config, "settle_seconds", minimum=0.0, maximum=60.0
                        )
                        if now_mono - last_motion_mono < settle_seconds:
                            phase = "settling"
                        else:
                            if stable_since is None:
                                stable_since = now_mono
                            phase = "stabilizing"
                            stable_seconds = self._float_config(
                                config,
                                "stable_seconds",
                                minimum=0.0,
                                maximum=30.0,
                            )
                            if now_mono - stable_since >= stable_seconds:
                                phase = "analyzing"
                                active_boxes = self._fetch_active_boxes(
                                    analysis_frame.shape[1],
                                    analysis_frame.shape[0],
                                    active_boxes,
                                )
                                events, globally_changed = self._detect_changes(
                                    baseline_frame,
                                    analysis_frame,
                                    active_boxes,
                                    config,
                                )
                                baseline_frame = analysis_frame.copy()
                                stable_since = None
                                phase = "monitoring"
                                self._set_baseline_ready()

                                if globally_changed:
                                    self._emit_event(
                                        callback_queue,
                                        "global_change_suppressed",
                                    )
                                elif events:
                                    self._record_events(events, config)
                                    for event in events:
                                        self._enqueue_callback(
                                            callback_queue,
                                            "change",
                                            event,
                                        )
                                        self._emit_event(
                                            callback_queue,
                                            "change_detected",
                                            kind=event.kind,
                                            bbox=list(event.bbox),
                                            confidence=event.confidence,
                                            matched_item_id=event.matched_item_id,
                                        )

                self._set_detection_status(phase, moving, True)
                output = self._draw_overlay(
                    analysis_frame, phase, moving, active_boxes, config
                )
                self._publish_frame(output, config, contains_camera_image=True)
                previous_gray = gray

        except Exception as exc:  # keep health information if a backend surprises us
            self._set_error(f"Vision monitor stopped unexpectedly: {exc}")
            self._emit_event(
                callback_queue,
                "monitor_error",
                error=str(exc),
            )
        finally:
            if capture is not None:
                self._release_capture(capture)
            with self._capture_lock:
                self._capture = None
            with self._lock:
                self._status.camera_connected = False
                self._status.using_fallback = True
                self._status.running = False
                self._status.motion_detected = False
                self._status.baseline_ready = False
                self._status.phase = "stopped"
            self._emit_event(callback_queue, "monitor_stopped")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare_gray(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            gray = frame
        elif frame.shape[2] == 4:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (9, 9), 0)

    def _estimate_translation(
        self,
        reference_gray: np.ndarray,
        current_gray: np.ndarray,
        config: dict[str, Any],
    ) -> tuple[float, float, float] | None:
        """Estimate global camera translation as ``(dx, dy, response)``.

        Existing corners are tracked forward and backward first, so a newly
        introduced object cannot become the feature that defines "camera
        movement". Phase correlation is only a small-shift fallback. This is
        important on a nearly plain table: there, an unrestricted phase peak
        can incorrectly describe the distance between an old object and a new
        object as a 50-100 px camera translation.
        """

        if (
            not self._bool_config(config, "stabilize_camera")
            or reference_gray.shape != current_gray.shape
            or reference_gray.ndim != 2
            or min(reference_gray.shape) < 32
        ):
            return None

        height, width = reference_gray.shape
        analysis_width = self._int_config(
            config,
            "stabilization_analysis_width",
            minimum=96,
            maximum=1920,
        )
        scale = min(1.0, analysis_width / float(width))
        if scale < 1.0:
            size = (max(32, int(round(width * scale))), max(32, int(round(height * scale))))
            reference = cv2.resize(reference_gray, size, interpolation=cv2.INTER_AREA)
            current = cv2.resize(current_gray, size, interpolation=cv2.INTER_AREA)
        else:
            reference = reference_gray
            current = current_gray

        inverse_scale = 1.0 / scale
        max_shift = self._float_config(
            config,
            "stabilization_max_shift",
            minimum=0.0,
            maximum=float(max(reference_gray.shape)),
        )
        scaled_limit = max_shift * scale

        # Lucas-Kanade features exist in the reference image, not in a newly
        # placed object. Forward/backward agreement rejects ambiguous tracks.
        try:
            points = cv2.goodFeaturesToTrack(
                reference,
                maxCorners=180,
                qualityLevel=0.01,
                minDistance=7,
                blockSize=7,
            )
            if points is not None and len(points) >= 4:
                lk_options = {
                    "winSize": (21, 21),
                    "maxLevel": 2,
                    "criteria": (
                        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                        20,
                        0.01,
                    ),
                }
                tracked, forward_status, _ = cv2.calcOpticalFlowPyrLK(
                    reference, current, points, None, **lk_options
                )
                if tracked is not None and forward_status is not None:
                    returned, backward_status, _ = cv2.calcOpticalFlowPyrLK(
                        current, reference, tracked, None, **lk_options
                    )
                    if returned is not None and backward_status is not None:
                        origin = points.reshape(-1, 2)
                        destination = tracked.reshape(-1, 2)
                        round_trip = returned.reshape(-1, 2)
                        good = (
                            (forward_status.reshape(-1) > 0)
                            & (backward_status.reshape(-1) > 0)
                            & np.all(np.isfinite(destination), axis=1)
                            & (np.linalg.norm(round_trip - origin, axis=1) <= 1.25)
                        )
                        displacement = destination[good] - origin[good]
                        if len(displacement) >= 4:
                            median = np.median(displacement, axis=0)
                            residual = np.linalg.norm(displacement - median, axis=1)
                            inliers = residual <= 1.5
                            inlier_count = int(np.count_nonzero(inliers))
                            inlier_ratio = inlier_count / len(displacement)
                            if inlier_count >= 4 and inlier_ratio >= 0.55:
                                robust_shift = np.median(
                                    displacement[inliers], axis=0
                                )
                                shift_x = float(robust_shift[0])
                                shift_y = float(robust_shift[1])
                                if (
                                    abs(shift_x) <= scaled_limit
                                    and abs(shift_y) <= scaled_limit
                                ):
                                    response = inlier_ratio * min(
                                        1.0, inlier_count / 8.0
                                    )
                                    result_x = shift_x * inverse_scale
                                    result_y = shift_y * inverse_scale
                                    deadband = self._float_config(
                                        config,
                                        "stabilization_translation_deadband",
                                        minimum=0.0,
                                        maximum=2.0,
                                    )
                                    if (
                                        abs(result_x) <= deadband
                                        and abs(result_y) <= deadband
                                    ):
                                        result_x = 0.0
                                        result_y = 0.0
                                    return (
                                        result_x,
                                        result_y,
                                        float(response),
                                    )
        except cv2.error:
            pass

        reference_float = reference.astype(np.float32)
        current_float = current.astype(np.float32)
        reference_float -= float(np.mean(reference_float))
        current_float -= float(np.mean(current_float))
        if min(float(np.std(reference_float)), float(np.std(current_float))) < 2.0:
            return None

        try:
            window = cv2.createHanningWindow(
                (reference_float.shape[1], reference_float.shape[0]), cv2.CV_32F
            )
            (shift_x, shift_y), response = cv2.phaseCorrelate(
                reference_float, current_float, window
            )
        except cv2.error:
            return None
        if not all(math.isfinite(value) for value in (shift_x, shift_y, response)):
            return None
        # Never use a large phase-only estimate.  It may be the distance
        # between two objects in a sparse scene, rather than camera movement.
        if abs(shift_x) > scaled_limit or abs(shift_y) > scaled_limit:
            return None
        result_x = float(shift_x) * inverse_scale
        result_y = float(shift_y) * inverse_scale
        deadband = self._float_config(
            config,
            "stabilization_translation_deadband",
            minimum=0.0,
            maximum=2.0,
        )
        if abs(result_x) <= deadband and abs(result_y) <= deadband:
            result_x = 0.0
            result_y = 0.0
        return (
            result_x,
            result_y,
            float(response),
        )

    def _estimate_euclidean_alignment(
        self,
        reference_gray: np.ndarray,
        current_gray: np.ndarray,
        config: dict[str, Any],
    ) -> tuple[np.ndarray, float] | None:
        """Return a conservative current-to-reference near-rigid transform.

        Rotation/scale correction is accepted only when reference features are
        distributed across the scene. A single object moving on a plain table
        must not be interpreted as the whole camera rotating or zooming.
        """

        if (
            not self._bool_config(config, "stabilize_camera")
            or reference_gray.shape != current_gray.shape
            or reference_gray.ndim != 2
            or min(reference_gray.shape) < 64
        ):
            return None
        height, width = reference_gray.shape
        analysis_width = self._int_config(
            config,
            "stabilization_analysis_width",
            minimum=96,
            maximum=1920,
        )
        resize_scale = min(1.0, analysis_width / float(width))
        if resize_scale < 1.0:
            size = (
                max(32, int(round(width * resize_scale))),
                max(32, int(round(height * resize_scale))),
            )
            reference = cv2.resize(reference_gray, size, interpolation=cv2.INTER_AREA)
            current = cv2.resize(current_gray, size, interpolation=cv2.INTER_AREA)
        else:
            reference = reference_gray
            current = current_gray

        try:
            points = cv2.goodFeaturesToTrack(
                reference,
                maxCorners=220,
                qualityLevel=0.01,
                minDistance=7,
                blockSize=7,
            )
            if points is None or len(points) < 8:
                return None
            lk_options = {
                "winSize": (21, 21),
                "maxLevel": 2,
                "criteria": (
                    cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                    20,
                    0.01,
                ),
            }
            tracked, forward_status, _ = cv2.calcOpticalFlowPyrLK(
                reference, current, points, None, **lk_options
            )
            if tracked is None or forward_status is None:
                return None
            returned, backward_status, _ = cv2.calcOpticalFlowPyrLK(
                current, reference, tracked, None, **lk_options
            )
            if returned is None or backward_status is None:
                return None
            origin = points.reshape(-1, 2)
            destination = tracked.reshape(-1, 2)
            round_trip = returned.reshape(-1, 2)
            good = (
                (forward_status.reshape(-1) > 0)
                & (backward_status.reshape(-1) > 0)
                & np.all(np.isfinite(destination), axis=1)
                & (np.linalg.norm(round_trip - origin, axis=1) <= 1.25)
            )
            origin = origin[good]
            destination = destination[good]
            if len(origin) < 8:
                return None

            span = np.ptp(origin, axis=0)
            if (
                span[0] < reference.shape[1] * 0.22
                or span[1] < reference.shape[0] * 0.22
            ):
                return None
            grid_x = np.clip(
                (origin[:, 0] * 3 / reference.shape[1]).astype(int), 0, 2
            )
            grid_y = np.clip(
                (origin[:, 1] * 3 / reference.shape[0]).astype(int), 0, 2
            )
            if len(set((grid_y * 3 + grid_x).tolist())) < 3:
                return None

            forward, inlier_mask = cv2.estimateAffinePartial2D(
                origin,
                destination,
                method=cv2.RANSAC,
                ransacReprojThreshold=1.5,
                maxIters=1000,
                confidence=0.99,
                refineIters=10,
            )
            if forward is None or inlier_mask is None:
                return None
            inlier_count = int(np.count_nonzero(inlier_mask))
            inlier_ratio = inlier_count / len(origin)
            if inlier_count < 6 or inlier_ratio < 0.45:
                return None

            a, b, shift_x = (float(value) for value in forward[0])
            c, d, shift_y = (float(value) for value in forward[1])
            scale = math.sqrt(max(0.0, a * a + c * c))
            angle = math.degrees(math.atan2(c, a))
            max_shift = self._float_config(
                config,
                "stabilization_max_feature_shift",
                minimum=0.0,
                maximum=float(max(reference_gray.shape)),
            )
            max_rotation = self._float_config(
                config,
                "stabilization_max_rotation",
                minimum=0.0,
                maximum=3.0,
            )
            max_scale_change = self._float_config(
                config,
                "stabilization_max_scale_change",
                minimum=0.0,
                maximum=0.05,
            )
            if (
                abs(shift_x / resize_scale) > max_shift
                or abs(shift_y / resize_scale) > max_shift
                or abs(angle) > max_rotation
                or abs(scale - 1.0) > max_scale_change
                or not all(math.isfinite(value) for value in (a, b, c, d, scale, angle))
            ):
                return None

            original_shift_x = shift_x / resize_scale
            original_shift_y = shift_y / resize_scale
            translation_deadband = self._float_config(
                config,
                "stabilization_translation_deadband",
                minimum=0.0,
                maximum=2.0,
            )
            rotation_deadband = self._float_config(
                config,
                "stabilization_rotation_deadband",
                minimum=0.0,
                maximum=0.25,
            )
            scale_deadband = self._float_config(
                config,
                "stabilization_scale_deadband",
                minimum=0.0,
                maximum=0.005,
            )
            if (
                abs(original_shift_x) <= translation_deadband
                and abs(original_shift_y) <= translation_deadband
                and abs(angle) <= rotation_deadband
                and abs(scale - 1.0) <= scale_deadband
            ):
                response = inlier_ratio * min(1.0, inlier_count / 12.0)
                return np.array(
                    [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
                ), float(response)

            forward_original = np.array(
                [
                    [a, b, original_shift_x],
                    [c, d, original_shift_y],
                ],
                dtype=np.float32,
            )
            current_to_reference = cv2.invertAffineTransform(forward_original)
            response = inlier_ratio * min(1.0, inlier_count / 12.0)
            return current_to_reference.astype(np.float32), float(response)
        except (cv2.error, ValueError, TypeError):
            return None

    def _translation_is_usable(
        self,
        translation: tuple[float, float, float] | None,
        shape: tuple[int, ...],
        config: dict[str, Any],
    ) -> bool:
        if translation is None:
            return False
        shift_x, shift_y, response = translation
        minimum_response = self._float_config(
            config, "stabilization_min_response", minimum=0.0, maximum=1.0
        )
        max_shift = self._float_config(
            config,
            "stabilization_max_shift",
            minimum=0.0,
            maximum=float(max(shape[:2])),
        )
        return bool(
            response >= minimum_response
            and abs(shift_x) <= max_shift
            and abs(shift_y) <= max_shift
        )

    @staticmethod
    def _warp_translation(
        image: np.ndarray, shift_x: float, shift_y: float
    ) -> tuple[np.ndarray, np.ndarray]:
        """Warp an image into its reference coordinate system.

        The second return value marks pixels backed by real camera data.  The
        reflected border makes the preview pleasant, while the mask makes sure
        those invented edge pixels never participate in detection.
        """

        height, width = image.shape[:2]
        matrix = np.array(
            [[1.0, 0.0, -float(shift_x)], [0.0, 1.0, -float(shift_y)]],
            dtype=np.float32,
        )
        return VisionMonitor._warp_affine(image, matrix)

    @staticmethod
    def _warp_affine(
        image: np.ndarray, current_to_reference: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        height, width = image.shape[:2]
        identity = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
        )
        if np.array_equal(current_to_reference, identity):
            return image, np.full((height, width), 255, dtype=np.uint8)
        aligned = cv2.warpAffine(
            image,
            current_to_reference,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        source_mask = np.full((height, width), 255, dtype=np.uint8)
        valid_mask = cv2.warpAffine(
            source_mask,
            current_to_reference,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        # Exclude the interpolation seam as well as the truly empty strip.
        valid_mask = cv2.erode(
            valid_mask, np.ones((3, 3), dtype=np.uint8), iterations=1
        )
        return aligned, valid_mask

    def _compensated_gray_difference(
        self,
        reference_gray: np.ndarray,
        current_gray: np.ndarray,
        valid_mask: np.ndarray,
        config: dict[str, Any],
        *,
        allow_local: bool = True,
    ) -> np.ndarray:
        """Return structural gray difference with exposure drift removed."""

        signed = current_gray.astype(np.float32) - reference_gray.astype(np.float32)
        valid = valid_mask > 0
        raw_magnitude: np.ndarray | None = None
        if self._bool_config(config, "compensate_lighting") and np.any(valid):
            sample_step = max(1, min(reference_gray.shape[:2]) // 180)
            sampled_valid = valid[::sample_step, ::sample_step]
            sampled_signed = signed[::sample_step, ::sample_step]
            if np.any(sampled_valid):
                signed -= float(np.median(sampled_signed[sampled_valid]))

            raw_magnitude = np.abs(signed)

            if allow_local and self._bool_config(config, "compensate_local_lighting"):
                blur_ratio = self._float_config(
                    config,
                    "lighting_blur_ratio",
                    minimum=0.005,
                    maximum=0.25,
                )
                sigma = max(2.0, min(reference_gray.shape[:2]) * blur_ratio)
                weights = valid.astype(np.float32)
                analysis_width = self._int_config(
                    config,
                    "lighting_analysis_width",
                    minimum=96,
                    maximum=1920,
                )
                lighting_scale = min(
                    1.0, analysis_width / float(reference_gray.shape[1])
                )
                if lighting_scale < 1.0:
                    lighting_size = (
                        max(32, int(round(reference_gray.shape[1] * lighting_scale))),
                        max(32, int(round(reference_gray.shape[0] * lighting_scale))),
                    )
                    lighting_signed = cv2.resize(
                        signed, lighting_size, interpolation=cv2.INTER_AREA
                    )
                    lighting_weights = cv2.resize(
                        weights, lighting_size, interpolation=cv2.INTER_AREA
                    )
                else:
                    lighting_signed = signed
                    lighting_weights = weights
                lighting_sigma = max(1.2, sigma * lighting_scale)
                numerator = cv2.GaussianBlur(
                    lighting_signed * lighting_weights,
                    (0, 0),
                    sigmaX=lighting_sigma,
                    sigmaY=lighting_sigma,
                    borderType=cv2.BORDER_REFLECT_101,
                )
                if np.all(lighting_weights >= 0.999):
                    illumination = numerator
                else:
                    denominator = cv2.GaussianBlur(
                        lighting_weights,
                        (0, 0),
                        sigmaX=lighting_sigma,
                        sigmaY=lighting_sigma,
                        borderType=cv2.BORDER_REFLECT_101,
                    )
                    illumination = numerator / np.maximum(denominator, 1e-3)
                if lighting_scale < 1.0:
                    illumination = cv2.resize(
                        illumination,
                        (reference_gray.shape[1], reference_gray.shape[0]),
                        interpolation=cv2.INTER_LINEAR,
                    )
                signed -= illumination

        magnitude = np.abs(signed)
        if raw_magnitude is not None:
            # Local normalisation must only remove evidence.  Without this
            # clamp, the blurred illumination estimate creates a bright halo
            # outside a dark object and inflates a 55 px item to a 125 px box.
            magnitude = np.minimum(magnitude, raw_magnitude)
        difference = np.clip(magnitude, 0, 255).astype(np.uint8)
        difference[~valid] = 0
        return difference

    def _persistent_edge_jitter_mask(
        self,
        reference_gray: np.ndarray,
        current_gray: np.ndarray,
        valid_mask: np.ndarray,
        config: dict[str, Any],
    ) -> np.ndarray | None:
        """Return pixels explained by tiny optical edge displacement.

        Autofocus breathing and sub-pixel lens distortion leave paired bands
        around scene edges after the best global alignment.  An edge must be
        present within a very small neighbourhood in *both* frames before its
        residual is ignored.  This is intentionally different from blurring
        the difference image: a newly introduced object's interior (and the
        silhouette where there was no prior edge) remains untouched.
        """

        if (
            not self._bool_config(config, "stabilize_camera")
            or not self._bool_config(config, "micro_jitter_suppression")
            or reference_gray.shape != current_gray.shape
            or reference_gray.ndim != 2
            or valid_mask.shape != reference_gray.shape
            or min(reference_gray.shape) < 32
        ):
            return None

        edge_threshold = self._float_config(
            config,
            "micro_jitter_edge_threshold",
            minimum=4.0,
            maximum=80.0,
        )
        radius = self._int_config(
            config,
            "micro_jitter_edge_radius",
            minimum=0,
            maximum=3,
        )
        try:
            reference_gradient = cv2.magnitude(
                cv2.Sobel(reference_gray, cv2.CV_32F, 1, 0, ksize=3),
                cv2.Sobel(reference_gray, cv2.CV_32F, 0, 1, ksize=3),
            )
            current_gradient = cv2.magnitude(
                cv2.Sobel(current_gray, cv2.CV_32F, 1, 0, ksize=3),
                cv2.Sobel(current_gray, cv2.CV_32F, 0, 1, ksize=3),
            )
            reference_edges = (reference_gradient >= edge_threshold).astype(
                np.uint8
            )
            current_edges = (current_gradient >= edge_threshold).astype(np.uint8)
            if radius > 0:
                kernel_size = radius * 2 + 1
                kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
                reference_edges = cv2.dilate(reference_edges, kernel)
                current_edges = cv2.dilate(current_edges, kernel)
            persistent = cv2.bitwise_and(reference_edges, current_edges)
            persistent[valid_mask == 0] = 0
            return persistent
        except cv2.error:
            return None

    def _has_motion(
        self,
        previous_gray: np.ndarray,
        current_gray: np.ndarray,
        config: dict[str, Any],
        *,
        already_aligned: bool = False,
    ) -> tuple[bool, float]:
        if previous_gray.shape != current_gray.shape:
            return True, 1.0

        aligned_current = current_gray
        valid_mask = np.full(previous_gray.shape, 255, dtype=np.uint8)
        if not already_aligned:
            euclidean = self._estimate_euclidean_alignment(
                previous_gray, current_gray, config
            )
            minimum_response = self._float_config(
                config, "stabilization_min_response", minimum=0.0, maximum=1.0
            )
            if euclidean is not None and euclidean[1] >= minimum_response:
                aligned_current, valid_mask = self._warp_affine(
                    current_gray, euclidean[0]
                )
            else:
                translation = self._estimate_translation(
                    previous_gray, current_gray, config
                )
                if self._translation_is_usable(
                    translation, previous_gray.shape, config
                ):
                    aligned_current, valid_mask = self._warp_translation(
                        current_gray, translation[0], translation[1]
                    )

        diff = self._compensated_gray_difference(
            previous_gray,
            aligned_current,
            valid_mask,
            config,
            allow_local=self._bool_config(
                config, "motion_compensate_local_lighting"
            ),
        )
        jitter_mask = self._persistent_edge_jitter_mask(
            previous_gray,
            aligned_current,
            valid_mask,
            config,
        )
        if jitter_mask is not None:
            diff[jitter_mask > 0] = 0
        threshold = self._int_config(
            config, "motion_threshold", minimum=2, maximum=100
        )
        _, mask = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(mask, valid_mask)
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
        )
        mask = cv2.dilate(mask, np.ones((5, 5), dtype=np.uint8), iterations=1)
        mask = cv2.bitwise_and(mask, valid_mask)
        changed_pixels = int(cv2.countNonZero(mask))
        frame_area = max(1, cv2.countNonZero(valid_mask))
        ratio = changed_pixels / frame_area
        min_ratio = self._float_config(
            config, "motion_min_ratio", minimum=0.0, maximum=1.0
        )
        min_area = self._float_config(
            config, "motion_min_area", minimum=1.0, maximum=float(frame_area)
        )

        largest = 0.0
        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        if contours:
            largest = max(cv2.contourArea(contour) for contour in contours)
        return bool(ratio >= min_ratio and largest >= min_area), ratio

    def _detect_changes(
        self,
        before: np.ndarray,
        after: np.ndarray,
        active_boxes: list[_ActiveBox],
        config: dict[str, Any],
    ) -> tuple[list[ChangeEvent], bool]:
        if before.shape[:2] != after.shape[:2]:
            return [], True

        before_gray = self._prepare_gray(before)
        after_gray = self._prepare_gray(after)
        aligned_after = after
        valid_mask = np.full(before_gray.shape, 255, dtype=np.uint8)
        euclidean = self._estimate_euclidean_alignment(
            before_gray, after_gray, config
        )
        minimum_response = self._float_config(
            config, "stabilization_min_response", minimum=0.0, maximum=1.0
        )
        if euclidean is not None and euclidean[1] >= minimum_response:
            aligned_after, valid_mask = self._warp_affine(after, euclidean[0])
        else:
            translation = self._estimate_translation(before_gray, after_gray, config)
            if self._translation_is_usable(
                translation, before_gray.shape, config
            ):
                aligned_after, valid_mask = self._warp_translation(
                    after, translation[0], translation[1]
                )

        if aligned_after is not after:
            if aligned_after.shape == before.shape:
                aligned_after[valid_mask == 0] = before[valid_mask == 0]
            after_gray = self._prepare_gray(aligned_after)

        diff = self._compensated_gray_difference(
            before_gray, after_gray, valid_mask, config
        )
        support_signed = after_gray.astype(np.float32) - before_gray.astype(np.float32)
        support_valid = valid_mask > 0
        if self._bool_config(config, "compensate_lighting") and np.any(support_valid):
            sample_step = max(1, min(before_gray.shape[:2]) // 180)
            sampled_valid = support_valid[::sample_step, ::sample_step]
            sampled_signed = support_signed[::sample_step, ::sample_step]
            if np.any(sampled_valid):
                support_signed -= float(np.median(sampled_signed[sampled_valid]))
        # A lower-frequency, globally exposure-corrected map is used only to
        # expand the final crop around a strong detection. It cannot create an
        # event on its own, so pale object bodies are included without turning
        # a soft lighting patch into a lost item.
        support_diff = np.clip(np.abs(support_signed), 0, 255).astype(np.uint8)
        support_diff[~support_valid] = 0
        # Grayscale alone misses objects whose luminance resembles the table
        # (for example a vivid red item on a mid-gray surface).  Add Lab chroma
        # differences while retaining the familiar pixel-threshold control.
        if (
            before.ndim == 3
            and aligned_after.ndim == 3
            and before.shape[2] in (3, 4)
            and aligned_after.shape[2] in (3, 4)
        ):
            before_bgr = (
                cv2.cvtColor(before, cv2.COLOR_BGRA2BGR)
                if before.shape[2] == 4
                else before
            )
            after_bgr = (
                cv2.cvtColor(aligned_after, cv2.COLOR_BGRA2BGR)
                if aligned_after.shape[2] == 4
                else aligned_after
            )
            before_lab = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2LAB)
            after_lab = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2LAB)
            chroma_diff = np.max(
                cv2.absdiff(before_lab[:, :, 1:3], after_lab[:, :, 1:3]),
                axis=2,
            ).astype(np.uint8)
            diff = np.maximum(diff, chroma_diff)
            support_diff = np.maximum(support_diff, chroma_diff)
        threshold = self._int_config(
            config, "change_threshold", minimum=2, maximum=120
        )
        # Keep the original mask for accurate silhouettes/crops, but require
        # every candidate to contain a small core that cannot be explained by
        # matching edges in the two frames.  This rejects autofocus bands
        # without eroding a real object's final bounding box.
        jitter_mask = self._persistent_edge_jitter_mask(
            before_gray,
            after_gray,
            valid_mask,
            config,
        )
        core_mask: np.ndarray | None = None
        if jitter_mask is not None:
            # The locally compensated map may intentionally remove a large
            # object's flat interior.  Its globally corrected support map is
            # still valid core evidence (and illumination-only candidates are
            # rejected later by the dedicated structure check).
            core_diff = np.maximum(diff, support_diff)
            core_diff[jitter_mask > 0] = 0
            _, core_mask = cv2.threshold(
                core_diff, threshold, 255, cv2.THRESH_BINARY
            )
            core_mask = cv2.bitwise_and(core_mask, valid_mask)
            core_mask = cv2.morphologyEx(
                core_mask,
                cv2.MORPH_OPEN,
                np.ones((3, 3), dtype=np.uint8),
            )
        _, mask = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(mask, valid_mask)
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
        )
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE, np.ones((9, 9), dtype=np.uint8)
        )
        mask = cv2.dilate(mask, np.ones((5, 5), dtype=np.uint8), iterations=1)
        mask = cv2.bitwise_and(mask, valid_mask)

        height, width = mask.shape[:2]
        frame_area = max(1, cv2.countNonZero(valid_mask))
        changed_ratio = cv2.countNonZero(mask) / frame_area
        max_ratio = self._float_config(
            config, "max_change_ratio", minimum=0.01, maximum=1.0
        )
        if changed_ratio > max_ratio:
            return [], True

        configured_min_area = self._float_config(
            config, "min_change_area", minimum=1.0, maximum=float(frame_area)
        )
        min_area_ratio = self._float_config(
            config, "min_change_area_ratio", minimum=0.0, maximum=1.0
        )
        min_area = max(configured_min_area, frame_area * min_area_ratio)
        compact_factor = self._float_config(
            config,
            "compact_change_area_factor",
            minimum=0.05,
            maximum=1.0,
        )
        compact_density = self._float_config(
            config,
            "compact_change_min_density",
            minimum=0.05,
            maximum=1.0,
        )
        compact_area = max(24.0, min_area * compact_factor)
        elongated_factor = self._float_config(
            config,
            "elongated_change_area_factor",
            minimum=0.005,
            maximum=0.25,
        )
        elongated_area = max(24.0, min_area * elongated_factor)
        elongated_length = self._int_config(
            config,
            "elongated_change_min_length",
            minimum=12,
            maximum=max(width, height),
        )
        elongated_aspect = self._float_config(
            config,
            "elongated_change_min_aspect",
            minimum=1.5,
            maximum=20.0,
        )
        elongated_density = self._float_config(
            config,
            "elongated_change_min_density",
            minimum=0.03,
            maximum=0.8,
        )

        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        raw_boxes: list[BBox] = []
        for contour in contours:
            contour_area = float(cv2.contourArea(contour))
            x, y, box_width, box_height = cv2.boundingRect(contour)
            box_area = max(1, box_width * box_height)
            if core_mask is not None:
                core_roi = core_mask[y : y + box_height, x : x + box_width]
                component_roi = mask[y : y + box_height, x : x + box_width]
                core_pixels = cv2.countNonZero(
                    cv2.bitwise_and(core_roi, component_roi)
                )
                required_core = max(
                    6,
                    min(48, int(round(max(1.0, contour_area) * 0.05))),
                )
                if core_pixels < required_core:
                    continue
            standard_candidate = contour_area >= min_area and box_area >= min_area
            compact_candidate = (
                contour_area >= compact_area
                and contour_area / box_area >= compact_density
            )
            long_side = max(box_width, box_height)
            short_side = max(1, min(box_width, box_height))
            elongated_candidate = (
                contour_area >= elongated_area
                and long_side >= elongated_length
                and long_side / short_side >= elongated_aspect
                and contour_area / box_area >= elongated_density
            )
            if (
                not standard_candidate
                and not compact_candidate
                and not elongated_candidate
            ):
                continue
            raw_boxes.append((int(x), int(y), int(box_width), int(box_height)))

        merge_gap = self._int_config(
            config, "contour_merge_gap", minimum=0, maximum=max(width, height)
        )
        if raw_boxes:
            support_factor = self._float_config(
                config,
                "bbox_support_threshold_factor",
                minimum=0.2,
                maximum=1.0,
            )
            support_threshold = max(2, int(round(threshold * support_factor)))
            _, support_mask = cv2.threshold(
                support_diff, support_threshold, 255, cv2.THRESH_BINARY
            )
            support_mask = cv2.bitwise_and(support_mask, valid_mask)
            support_mask = cv2.morphologyEx(
                support_mask,
                cv2.MORPH_OPEN,
                np.ones((3, 3), dtype=np.uint8),
            )
            support_mask = cv2.morphologyEx(
                support_mask,
                cv2.MORPH_CLOSE,
                np.ones((5, 5), dtype=np.uint8),
            )
            support_contours = cv2.findContours(
                support_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )[0]
            support_boxes = [
                tuple(int(value) for value in cv2.boundingRect(contour))
                for contour in support_contours
                if cv2.contourArea(contour) >= max(16.0, compact_area * 0.2)
            ]
            max_support_scale = self._float_config(
                config,
                "bbox_support_max_scale",
                minimum=1.0,
                maximum=8.0,
            )
            expanded_boxes: list[BBox] = []
            for raw_box in raw_boxes:
                expanded = raw_box
                base_width = max(1, raw_box[2])
                base_height = max(1, raw_box[3])
                for support_box in sorted(
                    support_boxes, key=lambda candidate: candidate[2] * candidate[3]
                ):
                    if not self._boxes_near(expanded, support_box, max(3, merge_gap // 3)):
                        continue
                    candidate = self._union_boxes([expanded, support_box])
                    if (
                        candidate[2] <= base_width * max_support_scale
                        and candidate[3] <= base_height * max_support_scale
                        and candidate[2] * candidate[3]
                        <= base_width
                        * base_height
                        * max_support_scale
                        * max_support_scale
                    ):
                        expanded = candidate
                expanded_boxes.append(expanded)
            raw_boxes = expanded_boxes

        # Local illumination compensation intentionally removes broad soft
        # shadows, but it can also leave only the four corners of a large,
        # low-contrast object.  Recover a support region only when the raw
        # globally-normalised difference forms a dense component with a sharp
        # boundary.  This both joins corner fragments into one item and avoids
        # promoting a smooth exposure gradient on its own.
        _, fallback_mask = cv2.threshold(
            support_diff, threshold, 255, cv2.THRESH_BINARY
        )
        fallback_mask = cv2.bitwise_and(fallback_mask, valid_mask)
        fallback_mask = cv2.morphologyEx(
            fallback_mask,
            cv2.MORPH_OPEN,
            np.ones((3, 3), dtype=np.uint8),
        )
        fallback_mask = cv2.morphologyEx(
            fallback_mask,
            cv2.MORPH_CLOSE,
            np.ones((7, 7), dtype=np.uint8),
        )
        gradient_x = cv2.Sobel(
            support_diff, cv2.CV_32F, 1, 0, ksize=3
        )
        gradient_y = cv2.Sobel(
            support_diff, cv2.CV_32F, 0, 1, ksize=3
        )
        edge_gradient = cv2.magnitude(gradient_x, gradient_y)
        fallback_density = self._float_config(
            config,
            "support_fallback_min_density",
            minimum=0.2,
            maximum=0.95,
        )
        fallback_edge = max(
            2.0,
            threshold
            * self._float_config(
                config,
                "support_fallback_edge_factor",
                minimum=0.03,
                maximum=0.5,
            ),
        )
        fallback_boxes: list[BBox] = []
        fallback_contours = cv2.findContours(
            fallback_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )[0]
        for contour in fallback_contours:
            contour_area = float(cv2.contourArea(contour))
            fx, fy, fw, fh = cv2.boundingRect(contour)
            fallback_area = max(1, fw * fh)
            if core_mask is not None:
                core_roi = core_mask[fy : fy + fh, fx : fx + fw]
                component_roi = fallback_mask[fy : fy + fh, fx : fx + fw]
                core_pixels = cv2.countNonZero(
                    cv2.bitwise_and(core_roi, component_roi)
                )
                required_core = max(
                    6,
                    min(48, int(round(max(1.0, contour_area) * 0.05))),
                )
                if core_pixels < required_core:
                    continue
            if (
                contour_area < min_area
                or contour_area / fallback_area < fallback_density
                or fallback_area / frame_area > max_ratio
            ):
                continue
            boundary = np.zeros_like(fallback_mask)
            cv2.drawContours(boundary, [contour], -1, 255, 3)
            boundary_values = edge_gradient[boundary > 0]
            if (
                boundary_values.size == 0
                or float(np.median(boundary_values)) < fallback_edge
            ):
                continue
            if self._is_illumination_only_change(
                before,
                aligned_after,
                (int(fx), int(fy), int(fw), int(fh)),
                config,
            ):
                continue
            fallback_boxes.append((int(fx), int(fy), int(fw), int(fh)))

        if fallback_boxes:
            consumed: set[int] = set()
            combined: list[BBox] = []
            for fallback_box in fallback_boxes:
                related = [
                    index
                    for index, raw_box in enumerate(raw_boxes)
                    if self._overlap_score(raw_box, fallback_box) >= 0.05
                    or self._box_contains(fallback_box, raw_box)
                ]
                if related:
                    consumed.update(related)
                combined.append(fallback_box)
            raw_boxes = [
                box for index, box in enumerate(raw_boxes) if index not in consumed
            ] + combined

        merged_boxes = self._merge_boxes(raw_boxes, merge_gap)
        padding = self._int_config(
            config, "bbox_padding", minimum=0, maximum=max(width, height) // 3
        )
        box_entries = [
            (box, self._pad_bbox(box, padding, width, height))
            for box in merged_boxes
        ]
        if not box_entries:
            return [], False

        border_pixels = self._int_config(
            config,
            "change_border_margin",
            minimum=0,
            maximum=max(0, min(width, height) // 4),
        )
        border_ratio = self._float_config(
            config,
            "change_border_margin_ratio",
            minimum=0.0,
            maximum=0.2,
        )
        border_margin = max(
            border_pixels, int(round(min(width, height) * border_ratio))
        )

        removal_threshold = self._float_config(
            config, "removal_overlap", minimum=0.01, maximum=1.0
        )
        removal_groups: dict[int, list[tuple[BBox, float]]] = {}
        verification_groups: dict[int, list[tuple[BBox, float]]] = {}
        relocation_sources: set[int] = set()
        added_boxes: list[BBox] = []

        def outside_active_candidate(
            box: BBox, overlapping_indices: list[int]
        ) -> BBox | None:
            x, y, box_width, box_height = box
            outside = mask[y : y + box_height, x : x + box_width].copy()
            for active_index in overlapping_indices:
                ax, ay, active_width, active_height = active_boxes[active_index].bbox
                ix1 = max(x, ax) - x
                iy1 = max(y, ay) - y
                ix2 = min(x + box_width, ax + active_width) - x
                iy2 = min(y + box_height, ay + active_height) - y
                if ix2 > ix1 and iy2 > iy1:
                    outside[
                        max(0, iy1 - 2) : min(box_height, iy2 + 2),
                        max(0, ix1 - 2) : min(box_width, ix2 + 2),
                    ] = 0
            outside_contours = cv2.findContours(
                outside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )[0]
            outside_parts: list[BBox] = []
            outside_area = 0.0
            for contour in outside_contours:
                area = float(cv2.contourArea(contour))
                if area < max(12.0, compact_area * 0.15):
                    continue
                ox, oy, ow, oh = cv2.boundingRect(contour)
                outside_parts.append((x + ox, y + oy, ow, oh))
                outside_area += area
            if not outside_parts or outside_area < compact_area:
                return None
            return self._pad_bbox(
                self._union_boxes(outside_parts), padding, width, height
            )

        for raw_box, box in box_entries:
            overlapping: list[tuple[int, float]] = []
            for index, active in enumerate(active_boxes):
                overlap = self._overlap_score(box, active.bbox)
                if overlap >= removal_threshold:
                    # A DB row can outlive the physical object after a restart
                    # or an older failed recovery. If BEFORE already matches
                    # the saved empty background, this stale box must not mask
                    # a genuinely new object placed in the same area. Recover
                    # the stale row and let the current change become added.
                    tracking_state = self._active_tracking_state(before, active)
                    if tracking_state == "absent":
                        removal_groups.setdefault(index, []).append(
                            (active.bbox, 1.0)
                        )
                        continue
                    if tracking_state == "unusable":
                        # Legacy rows may contain two effectively identical
                        # captures. They cannot prove presence or absence and
                        # therefore must not reserve a large blind rectangle.
                        # Keep the old row for AI/manual recovery review while
                        # allowing this physical change to be registered.
                        verification_groups.setdefault(index, []).append(
                            (box, overlap)
                        )
                        continue
                    overlapping.append((index, overlap))
            if overlapping:
                for active_index, overlap in overlapping:
                    relocation_sources.add(active_index)
                    active = active_boxes[active_index]
                    if self._looks_removed(before, aligned_after, active, config):
                        removal_groups.setdefault(active_index, []).append(
                            (box, overlap)
                        )
                    else:
                        verification_groups.setdefault(active_index, []).append(
                            (box, overlap)
                        )
                # A change contained by tracked items is an appearance change
                # and is suppressed. Any compact remainder outside every
                # overlapping active box is a real adjacent/new location
                # candidate (and can later be paired as a relocation).
                adjacent_box = outside_active_candidate(
                    box, [entry[0] for entry in overlapping]
                )
                if adjacent_box is not None:
                    added_boxes.append(adjacent_box)
            else:
                # A broad brightness-only patch preserves the desk's
                # high-frequency texture and is almost certainly a shadow or
                # exposure change, not a newly placed physical object. Apply
                # this only to additions: active-item recovery keeps its
                # conservative reference/background evidence.
                if self._is_illumination_only_change(
                    before, aligned_after, raw_box, config
                ):
                    continue
                x, y, box_width, box_height = box
                touches_border = border_margin > 0 and (
                    x <= border_margin
                    or y <= border_margin
                    or x + box_width >= width - border_margin
                    or y + box_height >= height - border_margin
                )
                if touches_border:
                    # Lens/exposure artefacts at the optical boundary tend to
                    # be sparse. A dense, sufficiently large object remains a
                    # valid lost item even when it is placed near the edge.
                    border_density = self._mask_density(mask, box)
                    edge_strip = (
                        box_width >= width * 0.8
                        and box_height <= max(12, border_margin * 2)
                    ) or (
                        box_height >= height * 0.8
                        and box_width <= max(12, border_margin * 2)
                    )
                    if (
                        edge_strip
                        or border_density < 0.18
                        or box_width * box_height < compact_area * 2.0
                    ):
                        continue
                added_boxes.append(box)

        # Pair a disappeared tracked object with a strongly matching new
        # location. This turns a desk nudge into one bbox update instead of a
        # recovered row plus a duplicate newly found row.
        addition_candidates = self._merge_boxes(added_boxes, merge_gap)
        relocation_pairs: dict[int, tuple[int, BBox, float]] = {}
        used_additions: set[int] = set()
        for active_index in relocation_sources:
            active = active_boxes[active_index]
            best_pair: tuple[int, BBox, float] | None = None
            for addition_index, candidate in enumerate(addition_candidates):
                if addition_index in used_additions:
                    continue
                match = self._match_relocated_item(
                    aligned_after,
                    candidate,
                    active,
                    config,
                    previous_frame=before,
                )
                if match is None:
                    continue
                moved_box, score = match
                if best_pair is None or score > best_pair[2]:
                    best_pair = (addition_index, moved_box, score)
            if best_pair is not None:
                relocation_pairs[active_index] = best_pair
                used_additions.add(best_pair[0])

        quality = self._int_config(config, "jpeg_quality", minimum=45, maximum=100)
        events: list[ChangeEvent] = []

        for active_index, (_, event_box, match_score) in relocation_pairs.items():
            active = active_boxes[active_index]
            clean_before = before.copy()
            if active.background_jpeg and clean_before.ndim == 3:
                saved_background = cv2.imdecode(
                    np.frombuffer(active.background_jpeg, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if saved_background is not None and saved_background.size > 0:
                    ax, ay, active_width, active_height = active.bbox
                    saved_background = cv2.resize(
                        saved_background,
                        (active_width, active_height),
                        interpolation=cv2.INTER_AREA,
                    )
                    clean_before[
                        ay : ay + active_height, ax : ax + active_width
                    ] = saved_background
            before_jpeg = self._encode_crop(clean_before, event_box, quality)
            after_jpeg = self._encode_crop(aligned_after, event_box, quality)
            events.append(
                ChangeEvent(
                    kind="moved",
                    bbox=event_box,
                    crop_jpeg=after_jpeg,
                    before_jpeg=before_jpeg,
                    after_jpeg=after_jpeg,
                    confidence=round(max(0.5, min(0.99, match_score)), 3),
                    matched_item_id=active.item_id,
                )
            )

        for active_index, matches in removal_groups.items():
            if active_index in relocation_pairs:
                continue
            active = active_boxes[active_index]
            changed_union = self._union_boxes([match[0] for match in matches])
            # The stored object box is normally the best removal crop. Include
            # changed pixels just outside it, then clamp to the source frame.
            event_box = self._clamp_bbox(
                self._union_boxes([active.bbox, changed_union]), width, height
            )
            before_jpeg = self._encode_crop(before, event_box, quality)
            after_jpeg = self._encode_crop(aligned_after, event_box, quality)
            max_overlap = max(match[1] for match in matches)
            density = self._mask_density(mask, event_box)
            confidence = self._confidence(event_box, frame_area, density, max_overlap)
            events.append(
                ChangeEvent(
                    kind="removed",
                    bbox=event_box,
                    crop_jpeg=before_jpeg,
                    before_jpeg=before_jpeg,
                    after_jpeg=after_jpeg,
                    confidence=confidence,
                    matched_item_id=active.item_id,
                )
            )

        # Appearance changes inside a tracked box are deliberately not enough
        # for local recovery (a phone display turning on is the classic false
        # positive). Send those ambiguous cases through the same full-scene AI
        # comparison; main.py only acts on a confident `removed` result.
        for active_index, matches in verification_groups.items():
            if active_index in relocation_pairs or active_index in removal_groups:
                continue
            active = active_boxes[active_index]
            changed_union = self._union_boxes([match[0] for match in matches])
            event_box = self._clamp_bbox(
                self._union_boxes([active.bbox, changed_union]), width, height
            )
            before_jpeg = self._encode_crop(before, event_box, quality)
            after_jpeg = self._encode_crop(aligned_after, event_box, quality)
            max_overlap = max(match[1] for match in matches)
            density = self._mask_density(mask, event_box)
            events.append(
                ChangeEvent(
                    kind="verify_removed",
                    bbox=event_box,
                    crop_jpeg=before_jpeg,
                    before_jpeg=before_jpeg,
                    after_jpeg=after_jpeg,
                    confidence=self._confidence(
                        event_box, frame_area, density, max_overlap
                    ),
                    matched_item_id=active.item_id,
                )
            )

        # Dilation can leave nearby pieces as separate boxes. Merging was done
        # before relocation matching; emit only candidates not consumed there.
        for addition_index, event_box in enumerate(addition_candidates):
            if addition_index in used_additions:
                continue
            event_box = self._clamp_bbox(event_box, width, height)
            before_jpeg = self._encode_crop(before, event_box, quality)
            after_jpeg = self._encode_crop(aligned_after, event_box, quality)
            density = self._mask_density(mask, event_box)
            confidence = self._confidence(event_box, frame_area, density, 0.0)
            events.append(
                ChangeEvent(
                    kind="added",
                    bbox=event_box,
                    crop_jpeg=after_jpeg,
                    before_jpeg=before_jpeg,
                    after_jpeg=after_jpeg,
                    confidence=confidence,
                    matched_item_id=None,
                )
            )

        if events:
            scene_max_width = self._int_config(
                config,
                "ai_scene_max_width",
                minimum=320,
                maximum=1920,
            )
            scene_quality = self._int_config(
                config,
                "ai_scene_jpeg_quality",
                minimum=45,
                maximum=92,
            )
            events = [
                replace(
                    event,
                    scene_before_jpeg=self._encode_scene_context(
                        before,
                        event.bbox,
                        scene_max_width,
                        scene_quality,
                    ),
                    scene_after_jpeg=self._encode_scene_context(
                        aligned_after,
                        event.bbox,
                        scene_max_width,
                        scene_quality,
                    ),
                )
                for event in events
            ]

        return events, False

    @staticmethod
    def _confidence(
        bbox: BBox, frame_area: int, density: float, overlap: float
    ) -> float:
        area = max(1, bbox[2] * bbox[3])
        useful_scale = min(1.0, area / max(1.0, frame_area * 0.08))
        value = 0.52 + 0.20 * min(1.0, density * 1.5) + 0.15 * math.sqrt(
            useful_scale
        )
        value += 0.12 * min(1.0, overlap)
        return round(max(0.5, min(0.99, value)), 3)

    @staticmethod
    def _mask_density(mask: np.ndarray, bbox: BBox) -> float:
        x, y, width, height = bbox
        roi = mask[y : y + height, x : x + width]
        if roi.size == 0:
            return 0.0
        return float(cv2.countNonZero(roi)) / float(roi.shape[0] * roi.shape[1])

    def _is_illumination_only_change(
        self,
        before: np.ndarray,
        after: np.ndarray,
        bbox: BBox,
        config: dict[str, Any],
    ) -> bool:
        """Recognise a shadow that preserves the surface under it.

        Mean brightness is discarded and the remaining high-frequency
        structure is compared. A shadow keeps the table grain in both frames,
        whereas an opaque object replaces it. Chroma changes veto the shadow
        decision so a real coloured item is not rejected for similar texture.
        """

        if before.shape[:2] != after.shape[:2] or before.ndim != after.ndim:
            return False
        frame_height, frame_width = before.shape[:2]
        x, y, width, height = self._clamp_bbox(bbox, frame_width, frame_height)
        if width < 12 or height < 12:
            return False

        # Stay inside the pre-padding contour. Otherwise its hard outer edge
        # dominates the correlation instead of the underlying surface.
        inset = max(1, int(round(min(width, height) * 0.025)))
        if width > inset * 2 + 8 and height > inset * 2 + 8:
            x += inset
            y += inset
            width -= inset * 2
            height -= inset * 2

        before_roi = before[y : y + height, x : x + width]
        after_roi = after[y : y + height, x : x + width]
        if before_roi.size == 0 or after_roi.size == 0:
            return False

        def raw_gray(image: np.ndarray) -> np.ndarray:
            if image.ndim == 2:
                return image
            if image.shape[2] == 4:
                return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        before_gray = raw_gray(before_roi).astype(np.float32)
        after_gray = raw_gray(after_roi).astype(np.float32)
        before_high = before_gray - cv2.GaussianBlur(before_gray, (0, 0), 2.0)
        after_high = after_gray - cv2.GaussianBlur(after_gray, (0, 0), 2.0)
        before_high = cv2.resize(
            before_high, (96, 96), interpolation=cv2.INTER_AREA
        )
        after_high = cv2.resize(
            after_high, (96, 96), interpolation=cv2.INTER_AREA
        )
        before_high -= float(np.mean(before_high))
        after_high -= float(np.mean(after_high))
        before_energy = float(np.sqrt(np.mean(before_high**2)))
        after_energy = float(np.sqrt(np.mean(after_high**2)))
        minimum_energy = self._float_config(
            config,
            "illumination_structure_min_energy",
            minimum=0.01,
            maximum=20.0,
        )
        if before_energy < minimum_energy or after_energy < minimum_energy:
            return False

        correlation = float(
            np.mean(before_high * after_high)
            / max(1e-6, before_energy * after_energy)
        )
        similarity_limit = self._float_config(
            config,
            "illumination_structure_similarity",
            minimum=0.4,
            maximum=0.999,
        )
        if correlation < similarity_limit:
            return False

        if before_roi.ndim == 3 and after_roi.ndim == 3:
            before_bgr = (
                cv2.cvtColor(before_roi, cv2.COLOR_BGRA2BGR)
                if before_roi.shape[2] == 4
                else before_roi
            )
            after_bgr = (
                cv2.cvtColor(after_roi, cv2.COLOR_BGRA2BGR)
                if after_roi.shape[2] == 4
                else after_roi
            )
            before_lab = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2LAB)
            after_lab = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2LAB)
            chroma_delta = np.max(
                cv2.absdiff(before_lab[:, :, 1:3], after_lab[:, :, 1:3]),
                axis=2,
            )
            chroma_limit = self._float_config(
                config,
                "illumination_chroma_limit",
                minimum=1.0,
                maximum=64.0,
            )
            if float(np.median(chroma_delta)) > chroma_limit:
                return False

        return True

    def _looks_removed(
        self,
        before: np.ndarray,
        after: np.ndarray,
        active: _ActiveBox,
        config: dict[str, Any],
    ) -> bool:
        """Require the stored item appearance to disappear before recovering it.

        Bbox overlap alone cannot tell a removed object from a display/color
        change. Real camera registrations always persist the detected crop and
        supply it as ``reference_jpeg``. If that evidence is unavailable we
        deliberately keep the item active; the dashboard still offers manual
        recovery and avoiding a false recovery is the safer outcome.
        """
        reference = active.reference_jpeg
        background = active.background_jpeg
        if not reference or not background:
            return False
        foreground_evidence = self._foreground_removal_evidence(
            before,
            after,
            active.bbox,
            reference,
            background,
        )
        if foreground_evidence is not None:
            return foreground_evidence
        before_similarity = self._reference_similarity(before, active.bbox, reference)
        after_similarity = self._reference_similarity(after, active.bbox, reference)
        before_background = self._reference_similarity(before, active.bbox, background)
        after_background = self._reference_similarity(after, active.bbox, background)
        if any(
            value is None
            for value in (
                before_similarity,
                after_similarity,
                before_background,
                after_background,
            )
        ):
            return False
        minimum = self._float_config(
            config, "reference_match_min", minimum=0.0, maximum=1.0
        )
        required_drop = self._float_config(
            config, "removal_similarity_drop", minimum=0.05, maximum=0.9
        )
        background_minimum = self._float_config(
            config, "background_match_min", minimum=0.0, maximum=1.0
        )
        background_gain = self._float_config(
            config, "background_similarity_gain", minimum=0.05, maximum=0.9
        )
        return bool(
            before_similarity >= minimum
            and before_similarity - after_similarity >= required_drop
            and after_background >= background_minimum
            and after_background - before_background >= background_gain
        )

    @staticmethod
    def _foreground_removal_evidence(
        before: np.ndarray,
        after: np.ndarray,
        bbox: BBox,
        reference_jpeg: bytes,
        background_jpeg: bytes,
    ) -> bool | None:
        """Compare removal only where the saved object differs from background.

        The event crop deliberately includes context for multimodal AI.  Whole
        crop similarity is therefore dominated by background for a small item.
        A support mask derived from the paired object/background snapshots
        makes a 30 px key fob as meaningful as a 200 px bag while preserving
        the phone-screen false-recovery protection.
        """
        before_metrics = VisionMonitor._foreground_background_distance(
            before, bbox, reference_jpeg, background_jpeg
        )
        after_metrics = VisionMonitor._foreground_background_distance(
            after, bbox, reference_jpeg, background_jpeg
        )
        if before_metrics is None or after_metrics is None:
            return None
        before_background, separation = before_metrics
        after_background, _ = after_metrics
        background_limit = max(7.0, separation * 0.12)
        required_presence = max(8.0, separation * 0.08)
        required_change = max(4.0, separation * 0.06)
        return bool(
            before_background >= required_presence
            and after_background <= background_limit
            and before_background - after_background >= required_change
            and after_background + required_change < before_background
        )

    @staticmethod
    def _tracking_pair_is_unusable(
        reference: np.ndarray,
        background: np.ndarray,
        *,
        legacy_edge_strip: bool = False,
    ) -> bool:
        """Reject legacy reference/background pairs that show the same scene.

        Older builds could save both JPEGs after the item was already present.
        JPEG noise and sub-pixel camera jitter make those files non-identical,
        so a byte/pixel equality check is insufficient.  A very small
        translation and exposure offset are removed before applying a strict
        structure-correlation gate.  The thresholds are deliberately narrow:
        a real opaque item/background pair remains usable even for compact
        objects, while near-duplicate captures cannot reserve a blind box.
        """

        try:
            if reference.shape[:2] != background.shape[:2]:
                return False
            reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(
                np.float32
            )
            background_gray = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY).astype(
                np.float32
            )
            reference_gray = cv2.GaussianBlur(reference_gray, (3, 3), 0)
            background_gray = cv2.GaussianBlur(background_gray, (3, 3), 0)
            shift, response = cv2.phaseCorrelate(reference_gray, background_gray)
            if (
                math.isfinite(shift[0])
                and math.isfinite(shift[1])
                and math.isfinite(response)
                and abs(shift[0]) <= 3.0
                and abs(shift[1]) <= 3.0
                and response >= 0.08
            ):
                matrix = np.float32(
                    [[1.0, 0.0, shift[0]], [0.0, 1.0, shift[1]]]
                )
                reference_gray = cv2.warpAffine(
                    reference_gray,
                    matrix,
                    (reference_gray.shape[1], reference_gray.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT,
                )

            if min(reference_gray.shape[:2]) > 12:
                reference_gray = reference_gray[3:-3, 3:-3]
                background_gray = background_gray[3:-3, 3:-3]
            reference_gray += float(
                np.median(background_gray - reference_gray)
            )
            reference_zero = reference_gray - float(np.mean(reference_gray))
            background_zero = background_gray - float(np.mean(background_gray))
            reference_scale = float(np.sqrt(np.mean(reference_zero**2)))
            background_scale = float(np.sqrt(np.mean(background_zero**2)))
            if reference_scale < 0.25 or background_scale < 0.25:
                correlation = 1.0 if float(
                    np.mean(np.abs(reference_gray - background_gray))
                ) <= 1.0 else 0.0
            else:
                correlation = float(
                    np.mean(reference_zero * background_zero)
                    / max(1e-6, reference_scale * background_scale)
                )
            residual = float(
                np.mean(np.abs(reference_gray - background_gray))
            )
            return bool(
                (correlation >= 0.985 and residual <= 8.0)
                # A legacy false detection at the optical boundary can be a
                # low-texture exposure band whose correlation is weakened by
                # JPEG gradients despite only a few levels of residual.  This
                # secondary gate is intentionally limited to elongated edge
                # boxes so a compact, real low-contrast item remains usable.
                or (legacy_edge_strip and residual <= 6.0)
            )
        except (cv2.error, ValueError, TypeError, IndexError):
            return False

    @staticmethod
    def _foreground_background_distance(
        frame: np.ndarray,
        bbox: BBox,
        reference_jpeg: bytes,
        background_jpeg: bytes,
    ) -> tuple[float, float] | None:
        """Return distance to saved background on object-only support pixels."""
        try:
            reference = cv2.imdecode(
                np.frombuffer(reference_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            background = cv2.imdecode(
                np.frombuffer(background_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            x, y, width, height = bbox
            current = frame[y : y + height, x : x + width]
            if (
                reference is None
                or background is None
                or reference.size == 0
                or background.size == 0
                or current.size == 0
            ):
                return None

            def as_bgr(image: np.ndarray) -> np.ndarray:
                if image.ndim == 2:
                    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                if image.shape[2] == 4:
                    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                return image

            size = (96, 96)
            reference = cv2.resize(
                as_bgr(reference), size, interpolation=cv2.INTER_AREA
            )
            background = cv2.resize(
                as_bgr(background), size, interpolation=cv2.INTER_AREA
            )
            current = cv2.resize(
                as_bgr(current), size, interpolation=cv2.INTER_AREA
            )
            frame_height, frame_width = frame.shape[:2]
            elongated = max(width, height) / max(1, min(width, height)) >= 3.0
            edge_margin_x = max(4, int(round(frame_width * 0.06)))
            edge_margin_y = max(4, int(round(frame_height * 0.06)))
            touches_edge = (
                x <= edge_margin_x
                or y <= edge_margin_y
                or x + width >= frame_width - edge_margin_x
                or y + height >= frame_height - edge_margin_y
            )
            if VisionMonitor._tracking_pair_is_unusable(
                reference,
                background,
                legacy_edge_strip=elongated and touches_edge,
            ):
                return None
            reference_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(
                np.float32
            )
            background_lab = cv2.cvtColor(background, cv2.COLOR_BGR2LAB).astype(
                np.float32
            )
            current_lab = cv2.cvtColor(current, cv2.COLOR_BGR2LAB).astype(
                np.float32
            )
            reference_delta = np.mean(
                np.abs(reference_lab - background_lab), axis=2
            )
            support = (reference_delta >= 8.0).astype(np.uint8) * 255
            support = cv2.morphologyEx(
                support,
                cv2.MORPH_OPEN,
                np.ones((3, 3), dtype=np.uint8),
            )
            support = cv2.morphologyEx(
                support,
                cv2.MORPH_CLOSE,
                np.ones((5, 5), dtype=np.uint8),
            )
            support = cv2.dilate(
                support, np.ones((3, 3), dtype=np.uint8), iterations=1
            )
            selected = support > 0
            if int(np.count_nonzero(selected)) < 40:
                return None
            separation = float(np.mean(reference_delta[selected]))
            if separation < 6.0:
                return None

            # Estimate exposure from context that was background in both saved
            # crops, never from the item itself.
            background_context = reference_delta < 5.0
            if int(np.count_nonzero(background_context)) >= 40:
                light_shift = float(
                    np.median(
                        current_lab[:, :, 0][background_context]
                        - background_lab[:, :, 0][background_context]
                    )
                )
                current_lab[:, :, 0] = np.clip(
                    current_lab[:, :, 0] - light_shift, 0, 255
                )
            distance = float(
                np.mean(np.abs(current_lab - background_lab)[selected])
            )
            return distance, separation
        except (cv2.error, ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _active_is_clearly_absent(
        frame: np.ndarray,
        active: _ActiveBox,
    ) -> bool:
        return VisionMonitor._active_tracking_state(frame, active) == "absent"

    @staticmethod
    def _active_tracking_state(
        frame: np.ndarray,
        active: _ActiveBox,
    ) -> Literal["present", "absent", "unusable"]:
        if not active.reference_jpeg or not active.background_jpeg:
            return "present"
        metrics = VisionMonitor._foreground_background_distance(
            frame,
            active.bbox,
            active.reference_jpeg,
            active.background_jpeg,
        )
        if metrics is None:
            return "unusable"
        distance, separation = metrics
        if distance <= max(7.0, separation * 0.12):
            return "absent"
        return "present"

    def _reconcile_absent_active_items(
        self,
        frame: np.ndarray,
        active_boxes: list[_ActiveBox],
        config: dict[str, Any],
    ) -> list[ChangeEvent]:
        """Recover only strong saved-background matches on manual rebaseline.

        Startup calibration never calls this path.  It is reserved for the
        administrator's explicit "use current scene" action so an item removed
        while the server was stopped cannot remain stored forever.
        """
        quality = self._int_config(config, "jpeg_quality", minimum=45, maximum=100)
        scene_width = self._int_config(
            config, "ai_scene_max_width", minimum=320, maximum=1920
        )
        scene_quality = self._int_config(
            config, "ai_scene_jpeg_quality", minimum=45, maximum=92
        )
        events: list[ChangeEvent] = []
        for active in active_boxes:
            if not self._active_is_clearly_absent(frame, active):
                continue
            current_crop = self._encode_crop(frame, active.bbox, quality)
            events.append(
                ChangeEvent(
                    kind="removed",
                    bbox=active.bbox,
                    crop_jpeg=active.reference_jpeg,
                    before_jpeg=active.reference_jpeg,
                    after_jpeg=current_crop,
                    confidence=0.96,
                    matched_item_id=active.item_id,
                    scene_after_jpeg=self._encode_scene_context(
                        frame,
                        active.bbox,
                        scene_width,
                        scene_quality,
                    ),
                )
            )
        return events

    def _match_relocated_item(
        self,
        frame: np.ndarray,
        candidate: BBox,
        active: _ActiveBox,
        config: dict[str, Any],
        *,
        previous_frame: np.ndarray | None = None,
    ) -> tuple[BBox, float] | None:
        """Locate a disappeared active item's reference near a new candidate.

        The fast path retains fixed-size template matching for the common case
        where an item is nudged on the same surface.  A second, deliberately
        conservative path compares only pixels that changed from saved/live
        background.  That path is independent of crop padding and tolerates a
        modest scale change, so an object moved from a dark mat to a pale desk
        is not recovered and immediately registered again as a duplicate.
        """

        if not active.reference_jpeg or not active.background_jpeg:
            return None
        try:
            reference = cv2.imdecode(
                np.frombuffer(active.reference_jpeg, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            background = cv2.imdecode(
                np.frombuffer(active.background_jpeg, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if reference is None or background is None:
                return None

            def as_bgr(image: np.ndarray) -> np.ndarray:
                if image.ndim == 2:
                    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                if image.shape[2] == 4:
                    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                return image

            frame_bgr = as_bgr(frame)
            _, _, template_width, template_height = active.bbox
            if template_width < 8 or template_height < 8:
                return None
            reference = cv2.resize(
                reference,
                (template_width, template_height),
                interpolation=cv2.INTER_AREA,
            )
            background = cv2.resize(
                background,
                (template_width, template_height),
                interpolation=cv2.INTER_AREA,
            )

            frame_height, frame_width = frame_bgr.shape[:2]
            candidate = self._clamp_bbox(candidate, frame_width, frame_height)
            cx, cy, candidate_width, candidate_height = candidate
            if candidate_width < 8 or candidate_height < 8:
                return None

            old_x, old_y, old_width, old_height = active.bbox
            old_center = (old_x + old_width / 2.0, old_y + old_height / 2.0)
            minimum_shift = self._float_config(
                config,
                "relocation_min_shift",
                minimum=1.0,
                maximum=float(max(frame_width, frame_height)),
            )
            max_distance_ratio = self._float_config(
                config,
                "relocation_max_distance_ratio",
                minimum=0.02,
                maximum=1.0,
            )

            def displacement_is_valid(box: BBox) -> bool:
                new_center = (
                    box[0] + box[2] / 2.0,
                    box[1] + box[3] / 2.0,
                )
                distance = math.hypot(
                    new_center[0] - old_center[0],
                    new_center[1] - old_center[1],
                )
                return bool(
                    distance >= minimum_shift
                    and distance
                    <= math.hypot(frame_width, frame_height)
                    * max_distance_ratio
                )

            minimum = self._float_config(
                config, "relocation_match_min", minimum=0.5, maximum=0.98
            )

            # Same-size, same-background moves are both cheap and reliable
            # with the original full-crop matcher, so try that first.
            search_x1 = max(0, cx - template_width)
            search_y1 = max(0, cy - template_height)
            search_x2 = min(
                frame_width, cx + candidate_width + template_width
            )
            search_y2 = min(
                frame_height, cy + candidate_height + template_height
            )
            search = frame_bgr[search_y1:search_y2, search_x1:search_x2]
            if not (
                search.shape[1] < template_width
                or search.shape[0] < template_height
            ):
                reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
                search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
                if float(np.std(reference_gray)) >= 3.0:
                    scores = cv2.matchTemplate(
                        search_gray, reference_gray, cv2.TM_CCOEFF_NORMED
                    )
                    _, template_score, _, location = cv2.minMaxLoc(scores)
                    moved_box = self._clamp_bbox(
                        (
                            search_x1 + int(location[0]),
                            search_y1 + int(location[1]),
                            template_width,
                            template_height,
                        ),
                        frame_width,
                        frame_height,
                    )
                    if displacement_is_valid(moved_box):
                        x, y, width, height = moved_box
                        current = frame_bgr[y : y + height, x : x + width]
                        current = cv2.resize(
                            current,
                            (template_width, template_height),
                            interpolation=cv2.INTER_AREA,
                        )
                        reference_lab = cv2.cvtColor(
                            reference, cv2.COLOR_BGR2LAB
                        ).astype(np.float32)
                        background_lab = cv2.cvtColor(
                            background, cv2.COLOR_BGR2LAB
                        ).astype(np.float32)
                        current_lab = cv2.cvtColor(
                            current, cv2.COLOR_BGR2LAB
                        ).astype(np.float32)
                        reference_delta = np.mean(
                            np.abs(reference_lab - background_lab), axis=2
                        )
                        support = reference_delta >= 8.0
                        if int(np.count_nonzero(support)) >= 20:
                            separation = float(
                                np.mean(reference_delta[support])
                            )
                            current_distance = float(
                                np.mean(
                                    np.abs(current_lab - reference_lab)[support]
                                )
                            )
                            appearance = 1.0 - min(
                                1.0,
                                current_distance
                                / max(10.0, separation * 1.5),
                            )
                            combined = max(
                                0.0, min(1.0, float(template_score))
                            ) * 0.55
                            combined += appearance * 0.45
                            if combined >= minimum:
                                return moved_box, float(combined)

            # A fixed template contains the old surface and assumes the old
            # crop size.  When either changes, compare the object-only regions
            # isolated by (reference - saved background) and
            # (current candidate - previous live frame) instead.
            if (
                previous_frame is None
                or previous_frame.shape[:2] != frame_bgr.shape[:2]
                or not displacement_is_valid(candidate)
            ):
                return None
            previous_bgr = as_bgr(previous_frame)
            current_candidate = frame_bgr[
                cy : cy + candidate_height,
                cx : cx + candidate_width,
            ]
            previous_candidate = previous_bgr[
                cy : cy + candidate_height,
                cx : cx + candidate_width,
            ]
            foreground_score = self._foreground_relocation_similarity(
                reference,
                background,
                current_candidate,
                previous_candidate,
            )
            if foreground_score is None or foreground_score < minimum:
                return None
            return candidate, float(foreground_score)
        except (cv2.error, ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _foreground_object_view(
        foreground: np.ndarray,
        background: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """Return a tight image/mask containing only changed foreground.

        Both inputs describe the same location.  Small JPEG and stabilisation
        residuals are removed before connected components are selected; the
        dominant component plus nearby meaningful parts retains buttons and
        markings without letting the surrounding surface drive matching.
        """

        try:
            if foreground.size == 0 or background.size == 0:
                return None

            def as_bgr(image: np.ndarray) -> np.ndarray:
                if image.ndim == 2:
                    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                if image.shape[2] == 4:
                    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                return image

            foreground = as_bgr(foreground)
            background = as_bgr(background)
            if background.shape[:2] != foreground.shape[:2]:
                background = cv2.resize(
                    background,
                    (foreground.shape[1], foreground.shape[0]),
                    interpolation=cv2.INTER_AREA,
                )

            longest = max(foreground.shape[:2])
            if longest > 480:
                scale = 480.0 / float(longest)
                size = (
                    max(8, int(round(foreground.shape[1] * scale))),
                    max(8, int(round(foreground.shape[0] * scale))),
                )
                foreground = cv2.resize(
                    foreground, size, interpolation=cv2.INTER_AREA
                )
                background = cv2.resize(
                    background, size, interpolation=cv2.INTER_AREA
                )

            foreground_lab = cv2.cvtColor(
                foreground, cv2.COLOR_BGR2LAB
            ).astype(np.float32)
            background_lab = cv2.cvtColor(
                background, cv2.COLOR_BGR2LAB
            ).astype(np.float32)
            difference = np.mean(
                np.abs(foreground_lab - background_lab), axis=2
            )
            support = (difference >= 8.0).astype(np.uint8) * 255
            if min(support.shape[:2]) >= 12:
                support = cv2.morphologyEx(
                    support,
                    cv2.MORPH_OPEN,
                    np.ones((3, 3), dtype=np.uint8),
                )
                support = cv2.morphologyEx(
                    support,
                    cv2.MORPH_CLOSE,
                    np.ones((7, 7), dtype=np.uint8),
                )
                support = cv2.dilate(
                    support,
                    np.ones((3, 3), dtype=np.uint8),
                    iterations=1,
                )

            component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
                support, connectivity=8
            )
            minimum_area = max(20, int(round(support.size * 0.001)))
            components = [
                (int(stats[index, cv2.CC_STAT_AREA]), index)
                for index in range(1, component_count)
                if int(stats[index, cv2.CC_STAT_AREA]) >= minimum_area
            ]
            if not components:
                return None
            largest_area = max(area for area, _ in components)
            selected = np.zeros_like(support)
            for area, index in components:
                if area >= max(minimum_area, int(round(largest_area * 0.03))):
                    selected[labels == index] = 255
            if int(cv2.countNonZero(selected)) < max(40, support.size // 100):
                return None
            x, y, width, height = cv2.boundingRect(selected)
            if width < 8 or height < 8:
                return None
            return (
                foreground[y : y + height, x : x + width],
                selected[y : y + height, x : x + width],
            )
        except (cv2.error, ValueError, TypeError, IndexError):
            return None

    @classmethod
    def _foreground_relocation_similarity(
        cls,
        reference: np.ndarray,
        saved_background: np.ndarray,
        current: np.ndarray,
        previous_background: np.ndarray,
    ) -> float | None:
        """Match two object-only views using scale-tolerant local features."""

        try:
            reference_view = cls._foreground_object_view(
                reference, saved_background
            )
            current_view = cls._foreground_object_view(
                current, previous_background
            )
            if reference_view is None or current_view is None:
                return None
            reference_object, reference_mask = reference_view
            current_object, current_mask = current_view

            reference_aspect = max(reference_object.shape[:2]) / max(
                1.0, float(min(reference_object.shape[:2]))
            )
            current_aspect = max(current_object.shape[:2]) / max(
                1.0, float(min(current_object.shape[:2]))
            )
            aspect_similarity = min(reference_aspect, current_aspect) / max(
                reference_aspect, current_aspect
            )
            if aspect_similarity < 0.55:
                return None

            def normalise(
                image: np.ndarray, mask: np.ndarray
            ) -> tuple[np.ndarray, np.ndarray]:
                longest = max(image.shape[:2])
                scale = min(3.0, 360.0 / max(1.0, float(longest)))
                size = (
                    max(16, int(round(image.shape[1] * scale))),
                    max(16, int(round(image.shape[0] * scale))),
                )
                resized = cv2.resize(
                    image,
                    size,
                    interpolation=(
                        cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
                    ),
                )
                resized_mask = cv2.resize(
                    mask, size, interpolation=cv2.INTER_NEAREST
                )
                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                return gray, resized_mask

            reference_gray, reference_mask = normalise(
                reference_object, reference_mask
            )
            current_gray, current_mask = normalise(
                current_object, current_mask
            )
            detector = cv2.ORB_create(
                nfeatures=800,
                scaleFactor=1.15,
                nlevels=10,
                edgeThreshold=7,
                patchSize=21,
                fastThreshold=8,
            )
            reference_points, reference_descriptors = detector.detectAndCompute(
                reference_gray, reference_mask
            )
            current_points, current_descriptors = detector.detectAndCompute(
                current_gray, current_mask
            )
            if (
                reference_descriptors is None
                or current_descriptors is None
                or len(reference_points) < 6
                or len(current_points) < 6
            ):
                return None

            matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
            forward = matcher.knnMatch(
                reference_descriptors, current_descriptors, k=2
            )
            reverse = matcher.knnMatch(
                current_descriptors, reference_descriptors, k=2
            )
            reverse_best = {
                first.queryIdx: first.trainIdx
                for pair in reverse
                if len(pair) >= 2
                for first, second in [pair]
                if first.distance < 0.80 * second.distance
                and first.distance <= 64.0
            }
            good = [
                first
                for pair in forward
                if len(pair) >= 2
                for first, second in [pair]
                if first.distance < 0.76 * second.distance
                and first.distance <= 64.0
                and reverse_best.get(first.trainIdx) == first.queryIdx
            ]
            if len(good) < 6:
                return None

            source = np.float32(
                [reference_points[match.queryIdx].pt for match in good]
            )
            target = np.float32(
                [current_points[match.trainIdx].pt for match in good]
            )
            transform, inlier_mask = cv2.estimateAffinePartial2D(
                source,
                target,
                method=cv2.RANSAC,
                ransacReprojThreshold=4.5,
                maxIters=2000,
                confidence=0.995,
                refineIters=10,
            )
            if transform is None or inlier_mask is None:
                return None
            inliers = inlier_mask.reshape(-1).astype(bool)
            inlier_count = int(np.count_nonzero(inliers))
            inlier_ratio = inlier_count / max(1.0, float(len(good)))
            if inlier_count < 6 or inlier_ratio < 0.50:
                return None

            scale = math.hypot(float(transform[0, 0]), float(transform[1, 0]))
            angle = abs(
                math.degrees(
                    math.atan2(float(transform[1, 0]), float(transform[0, 0]))
                )
            )
            if not (0.60 <= scale <= 1.70) or angle > 35.0:
                return None

            source_inliers = source[inliers]
            target_inliers = target[inliers]

            def feature_spread(points: np.ndarray, shape: tuple[int, int]) -> float:
                x_span = float(np.ptp(points[:, 0])) / max(1.0, float(shape[1]))
                y_span = float(np.ptp(points[:, 1])) / max(1.0, float(shape[0]))
                if x_span < 0.16 or y_span < 0.10:
                    return 0.0
                return min(1.0, (x_span + y_span) / 0.9)

            spread = min(
                feature_spread(source_inliers, reference_gray.shape[:2]),
                feature_spread(target_inliers, current_gray.shape[:2]),
            )
            if spread <= 0.0:
                return None

            reference_contours = cv2.findContours(
                reference_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )[0]
            current_contours = cv2.findContours(
                current_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )[0]
            shape_similarity = 0.5
            if reference_contours and current_contours:
                shape_distance = cv2.matchShapes(
                    max(reference_contours, key=cv2.contourArea),
                    max(current_contours, key=cv2.contourArea),
                    cv2.CONTOURS_MATCH_I1,
                    0.0,
                )
                shape_similarity = 1.0 / (1.0 + max(0.0, shape_distance) * 2.0)

            count_score = min(1.0, inlier_count / 18.0)
            score = (
                inlier_ratio * 0.50
                + count_score * 0.25
                + spread * 0.10
                + aspect_similarity * 0.10
                + shape_similarity * 0.05
            )
            return max(0.0, min(1.0, float(score)))
        except (cv2.error, ValueError, TypeError, IndexError):
            return None

    @classmethod
    def _reference_similarity(
        cls, frame: np.ndarray, bbox: BBox, reference_jpeg: bytes
    ) -> float | None:
        try:
            reference = cv2.imdecode(
                np.frombuffer(reference_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            x, y, width, height = bbox
            region = frame[y : y + height, x : x + width]
            if reference is None or reference.size == 0 or region.size == 0:
                return None
            size = (96, 96)
            reference = cv2.resize(reference, size, interpolation=cv2.INTER_AREA)
            region = cv2.resize(region, size, interpolation=cv2.INTER_AREA)

            ref_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(np.float32)
            region_lab = cv2.cvtColor(region, cv2.COLOR_BGR2LAB).astype(np.float32)
            color_similarity = 1.0 - min(
                1.0, float(np.mean(np.abs(ref_lab - region_lab))) / 100.0
            )

            ref_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
            region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            ref_gradient = cv2.Laplacian(ref_gray, cv2.CV_32F)
            region_gradient = cv2.Laplacian(region_gray, cv2.CV_32F)
            gradient_scale = max(
                20.0,
                float(np.mean(np.abs(ref_gradient)))
                + float(np.mean(np.abs(region_gradient))),
            )
            gradient_similarity = 1.0 - min(
                1.0,
                float(np.mean(np.abs(ref_gradient - region_gradient))) / gradient_scale,
            )

            ref_hist = cv2.calcHist([ref_gray], [0], None, [32], [0, 256])
            region_hist = cv2.calcHist([region_gray], [0], None, [32], [0, 256])
            cv2.normalize(ref_hist, ref_hist)
            cv2.normalize(region_hist, region_hist)
            histogram = float(
                cv2.compareHist(ref_hist, region_hist, cv2.HISTCMP_CORREL)
            )
            histogram_similarity = max(0.0, min(1.0, (histogram + 1.0) / 2.0))

            score = (
                color_similarity * 0.40
                + gradient_similarity * 0.35
                + histogram_similarity * 0.25
            )
            return max(0.0, min(1.0, float(score)))
        except (cv2.error, ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Active item/bbox helpers
    # ------------------------------------------------------------------

    def _fetch_active_boxes(
        self,
        frame_width: int,
        frame_height: int,
        previous: list[_ActiveBox],
    ) -> list[_ActiveBox]:
        try:
            values = self._active_items_getter() or []
            parsed: list[_ActiveBox] = []
            for item in values:
                if isinstance(item, dict):
                    item_id = item.get("id")
                    raw_bbox = item.get("bbox")
                    reference_jpeg = item.get("reference_jpeg")
                    background_jpeg = item.get("background_jpeg")
                    if raw_bbox is None:
                        raw_bbox = item
                else:
                    item_id = getattr(item, "id", None)
                    raw_bbox = getattr(item, "bbox", None)
                    reference_jpeg = getattr(item, "reference_jpeg", None)
                    background_jpeg = getattr(item, "background_jpeg", None)
                if isinstance(reference_jpeg, memoryview):
                    reference_jpeg = reference_jpeg.tobytes()
                if not isinstance(reference_jpeg, bytes):
                    reference_jpeg = None
                if isinstance(background_jpeg, memoryview):
                    background_jpeg = background_jpeg.tobytes()
                if not isinstance(background_jpeg, bytes):
                    background_jpeg = None
                bbox = self._parse_bbox(raw_bbox, frame_width, frame_height)
                if bbox is not None:
                    parsed.append(
                        _ActiveBox(
                            item_id=item_id,
                            bbox=bbox,
                            reference_jpeg=reference_jpeg,
                            background_jpeg=background_jpeg,
                        )
                    )
            return parsed
        except Exception as exc:
            self._set_error(f"Could not read active item boxes: {exc}")
            return previous

    @classmethod
    def _parse_bbox(
        cls, raw_bbox: Any, frame_width: int, frame_height: int
    ) -> BBox | None:
        if raw_bbox is None:
            return None
        if isinstance(raw_bbox, str):
            try:
                raw_bbox = json.loads(raw_bbox)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None

        if isinstance(raw_bbox, dict):
            if all(key in raw_bbox for key in ("x", "y", "w", "h")):
                values = (
                    raw_bbox["x"],
                    raw_bbox["y"],
                    raw_bbox["w"],
                    raw_bbox["h"],
                )
            elif all(key in raw_bbox for key in ("x", "y", "width", "height")):
                values = (
                    raw_bbox["x"],
                    raw_bbox["y"],
                    raw_bbox["width"],
                    raw_bbox["height"],
                )
            elif all(key in raw_bbox for key in ("x1", "y1", "x2", "y2")):
                values = (
                    raw_bbox["x1"],
                    raw_bbox["y1"],
                    float(raw_bbox["x2"]) - float(raw_bbox["x1"]),
                    float(raw_bbox["y2"]) - float(raw_bbox["y1"]),
                )
            else:
                return None
        elif isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
            values = tuple(raw_bbox)
        else:
            return None

        try:
            x, y, width, height = (float(value) for value in values)
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            return None

        # Normalised bboxes are convenient for clients and survive resolution
        # changes, so accept them in addition to pixel coordinates.
        if all(0.0 <= value <= 1.0 for value in (x, y, width, height)):
            x *= frame_width
            width *= frame_width
            y *= frame_height
            height *= frame_height

        if width <= 0 or height <= 0:
            return None
        if (
            x >= frame_width
            or y >= frame_height
            or x + width <= 0
            or y + height <= 0
        ):
            return None

        return cls._clamp_bbox(
            (round(x), round(y), round(width), round(height)),
            frame_width,
            frame_height,
        )

    @staticmethod
    def _clamp_bbox(bbox: BBox, frame_width: int, frame_height: int) -> BBox:
        x, y, width, height = bbox
        x1 = max(0, min(frame_width - 1, int(x)))
        y1 = max(0, min(frame_height - 1, int(y)))
        x2 = max(x1 + 1, min(frame_width, int(x + max(1, width))))
        y2 = max(y1 + 1, min(frame_height, int(y + max(1, height))))
        return x1, y1, x2 - x1, y2 - y1

    @classmethod
    def _pad_bbox(
        cls, bbox: BBox, padding: int, frame_width: int, frame_height: int
    ) -> BBox:
        x, y, width, height = bbox
        return cls._clamp_bbox(
            (x - padding, y - padding, width + padding * 2, height + padding * 2),
            frame_width,
            frame_height,
        )

    @staticmethod
    def _union_boxes(boxes: list[BBox]) -> BBox:
        x1 = min(box[0] for box in boxes)
        y1 = min(box[1] for box in boxes)
        x2 = max(box[0] + box[2] for box in boxes)
        y2 = max(box[1] + box[3] for box in boxes)
        return x1, y1, x2 - x1, y2 - y1

    @classmethod
    def _merge_boxes(cls, boxes: list[BBox], gap: int) -> list[BBox]:
        pending = list(boxes)
        merged: list[BBox] = []
        while pending:
            current = pending.pop()
            changed = True
            while changed:
                changed = False
                remaining: list[BBox] = []
                for candidate in pending:
                    if cls._boxes_near(current, candidate, gap):
                        current = cls._union_boxes([current, candidate])
                        changed = True
                    else:
                        remaining.append(candidate)
                pending = remaining
            merged.append(current)
        return merged

    @staticmethod
    def _boxes_near(first: BBox, second: BBox, gap: int) -> bool:
        ax1, ay1, aw, ah = first
        bx1, by1, bw, bh = second
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh
        return not (
            ax2 + gap < bx1
            or bx2 + gap < ax1
            or ay2 + gap < by1
            or by2 + gap < ay1
        )

    @staticmethod
    def _box_contains(outer: BBox, inner: BBox) -> bool:
        ox, oy, ow, oh = outer
        ix, iy, iw, ih = inner
        return (
            ix >= ox
            and iy >= oy
            and ix + iw <= ox + ow
            and iy + ih <= oy + oh
        )

    @staticmethod
    def _overlap_score(first: BBox, second: BBox) -> float:
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        intersection_width = max(0, min(ax + aw, bx + bw) - max(ax, bx))
        intersection_height = max(0, min(ay + ah, by + bh) - max(ay, by))
        intersection = intersection_width * intersection_height
        if intersection <= 0:
            return 0.0
        smaller_area = max(1, min(aw * ah, bw * bh))
        return min(1.0, intersection / smaller_area)

    # ------------------------------------------------------------------
    # Camera, config and image helpers
    # ------------------------------------------------------------------

    def _read_config(self) -> dict[str, Any]:
        merged = dict(self.DEFAULTS)
        try:
            supplied = self._config_getter() or {}
            if not isinstance(supplied, dict):
                raise TypeError("config_getter must return a dictionary")
            nested = supplied.get("vision")
            if isinstance(nested, dict):
                values = nested
            else:
                values = supplied
            merged.update(values)

            # Compatibility with the concise settings exposed by the web app:
            # ``motion_threshold`` is a changed-pixel ratio when <= 1,
            # ``pixel_threshold`` is the grayscale threshold, and ``min_area``
            # applies to both initial motion and the final scene comparison.
            raw_motion = values.get("motion_threshold")
            if raw_motion is not None:
                try:
                    numeric_motion = float(raw_motion)
                except (TypeError, ValueError, OverflowError):
                    numeric_motion = float(self.DEFAULTS["motion_threshold"])
                if 0.0 <= numeric_motion <= 1.0:
                    if "motion_min_ratio" not in values:
                        merged["motion_min_ratio"] = numeric_motion
                    merged["motion_threshold"] = values.get(
                        "pixel_threshold", self.DEFAULTS["motion_threshold"]
                    )
            if "pixel_threshold" in values:
                merged["motion_threshold"] = values["pixel_threshold"]
                if "change_threshold" not in values:
                    merged["change_threshold"] = values["pixel_threshold"]
            if "min_area" in values:
                if "motion_min_area" not in values:
                    merged["motion_min_area"] = values["min_area"]
                if "min_change_area" not in values:
                    merged["min_change_area"] = values["min_area"]
        except Exception as exc:
            self._set_error(f"Could not read vision configuration: {exc}")
        return merged

    @staticmethod
    def _camera_signature(config: dict[str, Any]) -> tuple[Any, ...]:
        source = config.get("camera_source", config.get("camera_index", 0))
        return (
            str(source),
            str(config.get("camera_backend", "")),
            config.get("camera_width"),
            config.get("camera_height"),
            config.get("camera_fps"),
        )

    def _open_capture(
        self, config: dict[str, Any]
    ) -> tuple[CameraCapture | None, str | None]:
        source: Any = config.get("camera_source", config.get("camera_index", 0))
        backend_name = str(config.get("camera_backend", "")).strip().lower()
        return open_camera_capture(
            source,
            backend_name,
            self._int_config(config, "camera_width", minimum=160, maximum=7680),
            self._int_config(config, "camera_height", minimum=120, maximum=4320),
            self._float_config(config, "camera_fps", minimum=1.0, maximum=120.0),
        )

    @staticmethod
    def _transform_frame(frame: np.ndarray, config: dict[str, Any]) -> np.ndarray:
        if VisionMonitor._bool_config(config, "flip_horizontal"):
            frame = cv2.flip(frame, 1)
        try:
            rotation = int(config.get("rotate", 0)) % 360
        except (TypeError, ValueError):
            rotation = 0
        if rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def _release_capture(self, capture: CameraCapture) -> None:
        try:
            capture.release()
        except Exception:
            pass
        with self._capture_lock:
            if self._capture is capture:
                self._capture = None

    @staticmethod
    def _encode_jpeg(frame: np.ndarray, quality: int) -> bytes:
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        )
        return encoded.tobytes() if ok else b""

    @classmethod
    def _encode_crop(
        cls, frame: np.ndarray, bbox: BBox, quality: int
    ) -> bytes | None:
        x, y, width, height = bbox
        crop = frame[y : y + height, x : x + width]
        if crop.size == 0:
            return None
        encoded = cls._encode_jpeg(crop, quality)
        return encoded or None

    @classmethod
    def _encode_scene_context(
        cls,
        frame: np.ndarray,
        bbox: BBox,
        max_width: int,
        quality: int,
    ) -> bytes | None:
        """Encode a bounded full-frame view with a thin candidate marker.

        The marker tells a multimodal model which local change belongs to this
        event without replacing the crop itself.  Resizing before drawing keeps
        the rectangle readable and bounds network latency and image-token use.
        """
        if frame.size == 0:
            return None
        if frame.ndim == 2:
            canvas = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            canvas = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        else:
            canvas = frame.copy()

        height, width = canvas.shape[:2]
        scale = min(1.0, float(max_width) / max(1.0, float(width)))
        if scale < 1.0:
            canvas = cv2.resize(
                canvas,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )

        x, y, box_width, box_height = bbox
        x1 = int(round(x * scale))
        y1 = int(round(y * scale))
        x2 = int(round((x + box_width) * scale))
        y2 = int(round((y + box_height) * scale))
        output_height, output_width = canvas.shape[:2]
        x1 = max(0, min(output_width - 1, x1))
        y1 = max(0, min(output_height - 1, y1))
        x2 = max(x1 + 1, min(output_width - 1, x2))
        y2 = max(y1 + 1, min(output_height - 1, y2))

        # A dark outline remains visible on pale desks; the orange inner line
        # remains visible on dark objects.  Both are deliberately thin so the
        # object pixels stay available to the model.
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (16, 16, 18), 5, cv2.LINE_AA)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 166, 255), 2, cv2.LINE_AA)
        label_y = y1 - 8 if y1 >= 28 else min(output_height - 8, y1 + 22)
        cv2.putText(
            canvas,
            "CHANGE AREA",
            (max(4, x1), max(16, label_y)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 166, 255),
            1,
            cv2.LINE_AA,
        )
        encoded = cls._encode_jpeg(canvas, quality)
        return encoded or None

    @staticmethod
    def _make_notice_frame(
        width: int, height: int, title: str, detail: str
    ) -> np.ndarray:
        width = max(320, int(width))
        height = max(240, int(height))
        y_gradient = np.linspace(31, 12, height, dtype=np.uint8)[:, None]
        frame = np.empty((height, width, 3), dtype=np.uint8)
        frame[:, :, 0] = y_gradient
        frame[:, :, 1] = np.clip(y_gradient + 5, 0, 255)
        frame[:, :, 2] = np.clip(y_gradient + 10, 0, 255)

        center_y = height // 2
        cv2.circle(frame, (width // 2, center_y - 70), 26, (93, 168, 255), 2)
        cv2.circle(frame, (width // 2, center_y - 70), 7, (93, 168, 255), -1)
        title_scale = max(0.65, min(1.05, width / 1000.0))
        detail_scale = max(0.45, min(0.7, width / 1500.0))
        title_size = cv2.getTextSize(
            title, cv2.FONT_HERSHEY_SIMPLEX, title_scale, 2
        )[0]
        detail_size = cv2.getTextSize(
            detail, cv2.FONT_HERSHEY_SIMPLEX, detail_scale, 1
        )[0]
        cv2.putText(
            frame,
            title,
            ((width - title_size[0]) // 2, center_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            title_scale,
            (245, 245, 247),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            detail,
            ((width - detail_size[0]) // 2, center_y + 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            detail_scale,
            (174, 174, 181),
            1,
            cv2.LINE_AA,
        )
        stamp = time.strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(
            frame,
            stamp,
            (24, height - 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (120, 120, 126),
            1,
            cv2.LINE_AA,
        )
        return frame

    def _draw_overlay(
        self,
        frame: np.ndarray,
        phase: str,
        moving: bool,
        active_boxes: list[_ActiveBox],
        config: dict[str, Any],
    ) -> np.ndarray:
        output = frame.copy()
        height, width = output.shape[:2]

        if self._bool_config(config, "draw_active_boxes"):
            for active in active_boxes:
                x, y, box_width, box_height = active.bbox
                cv2.rectangle(
                    output,
                    (x, y),
                    (x + box_width, y + box_height),
                    (255, 166, 64),
                    1,
                    cv2.LINE_AA,
                )
                label = f"#{active.item_id} active" if active.item_id is not None else "active"
                cv2.putText(
                    output,
                    label,
                    (x + 3, max(16, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (255, 196, 108),
                    1,
                    cv2.LINE_AA,
                )

        now = time.monotonic()
        with self._lock:
            recent = [entry for entry in self._recent_boxes if entry[2] > now]
            self._recent_boxes = recent
        for bbox, kind, _ in recent:
            x, y, box_width, box_height = bbox
            color = (
                (104, 211, 92)
                if kind == "added"
                else (64, 190, 255)
                if kind == "moved"
                else (0, 166, 255)
                if kind == "verify_removed"
                else (92, 92, 255)
            )
            cv2.rectangle(
                output,
                (x, y),
                (x + box_width, y + box_height),
                color,
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                output,
                "AI CHECK" if kind == "verify_removed" else kind.upper(),
                (x + 4, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        panel_width = min(width - 24, 330)
        overlay = output.copy()
        cv2.rectangle(overlay, (12, 12), (12 + panel_width, 76), (15, 15, 18), -1)
        output = cv2.addWeighted(overlay, 0.72, output, 0.28, 0)
        phase_label = phase.replace("_", " ").upper()
        color = (82, 210, 104) if phase == "monitoring" else (81, 174, 255)
        if moving:
            color = (64, 190, 255)
        cv2.circle(output, (32, 34), 6, color, -1, cv2.LINE_AA)
        cv2.putText(
            output,
            "VISION MONITOR",
            (48, 39),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.57,
            (247, 247, 250),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            output,
            phase_label,
            (28, 63),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (191, 191, 199),
            1,
            cv2.LINE_AA,
        )
        stamp = time.strftime("%Y-%m-%d  %H:%M:%S")
        size = cv2.getTextSize(stamp, cv2.FONT_HERSHEY_SIMPLEX, 0.43, 1)[0]
        cv2.putText(
            output,
            stamp,
            (max(12, width - size[0] - 18), height - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (232, 232, 236),
            1,
            cv2.LINE_AA,
        )
        return output

    def _publish_frame(
        self,
        frame: np.ndarray,
        config: dict[str, Any],
        *,
        contains_camera_image: bool = False,
    ) -> None:
        # The browser receives many preview frames, while item/background
        # evidence is encoded only when a change is analysed.  Keeping these
        # qualities separate lets a small Raspberry Pi reduce continuous JPEG
        # work without sacrificing the images sent to the multimodal model.
        quality = self._int_config(
            config,
            "preview_jpeg_quality",
            minimum=45,
            maximum=100,
        )
        jpeg = self._encode_jpeg(frame, quality)
        if not jpeg:
            return
        with self._lock:
            # Check under the same lock used by set_privacy(), preventing a
            # just-finished camera frame from replacing the privacy card.
            if contains_camera_image and self._status.privacy_enabled:
                return
            self._latest_jpeg = jpeg

    def _publish_fallback(self, config: dict[str, Any]) -> None:
        width = self._int_config(config, "camera_width", minimum=320, maximum=3840)
        height = self._int_config(config, "camera_height", minimum=240, maximum=2160)
        if self._privacy_enabled():
            title = "PRIVACY MODE"
            detail = "Camera imagery and detection are paused"
        else:
            title = "CAMERA OFFLINE"
            detail = "Retrying automatically - check camera connection"
        frame = self._make_notice_frame(width, height, title, detail)
        self._publish_frame(frame, config)
        with self._lock:
            self._status.frame_width = width
            self._status.frame_height = height
            self._status.using_fallback = True
            self._status.phase = "privacy" if self._status.privacy_enabled else "offline"

    def _publish_privacy(
        self, width: int, height: int, config: dict[str, Any]
    ) -> None:
        frame = self._make_notice_frame(
            width,
            height,
            "PRIVACY MODE",
            "Camera imagery and detection are paused",
        )
        self._publish_frame(frame, config)

    # ------------------------------------------------------------------
    # State and callbacks
    # ------------------------------------------------------------------

    def _mark_live_frame(self, frame: np.ndarray, fps: float) -> None:
        with self._lock:
            self._status.camera_connected = True
            self._status.using_fallback = False
            self._status.frame_width = int(frame.shape[1])
            self._status.frame_height = int(frame.shape[0])
            self._status.fps = round(float(fps), 1)
            self._status.frame_sequence += 1
            self._status.last_frame_at = time.time()

    def _set_camera_status(self, connected: bool, error: str | None) -> None:
        with self._lock:
            self._status.camera_connected = connected
            self._status.using_fallback = not connected
            self._status.baseline_ready = False if not connected else self._status.baseline_ready
            self._status.motion_detected = False if not connected else self._status.motion_detected
            self._status.phase = "calibrating" if connected else "offline"
            self._status.last_error = error

    def _set_detection_status(
        self, phase: str, moving: bool, baseline_ready: bool
    ) -> None:
        with self._lock:
            self._status.phase = phase
            self._status.motion_detected = bool(moving or phase in ("settling", "stabilizing"))
            self._status.baseline_ready = baseline_ready

    def _set_baseline_ready(self) -> None:
        with self._lock:
            self._status.baseline_ready = True
            self._status.last_baseline_at = time.time()

    def _mark_motion(self) -> None:
        with self._lock:
            self._status.motion_detected = True
            self._status.last_motion_at = time.time()

    def _record_events(
        self, events: list[ChangeEvent], config: dict[str, Any]
    ) -> None:
        now_wall = time.time()
        expires = time.monotonic() + self._float_config(
            config, "event_overlay_seconds", minimum=0.0, maximum=60.0
        )
        with self._lock:
            self._status.detected_changes += len(events)
            self._status.last_change_at = now_wall
            self._recent_boxes.extend((event.bbox, event.kind, expires) for event in events)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._status.last_error = str(message)

    def _privacy_enabled(self) -> bool:
        with self._lock:
            return self._status.privacy_enabled

    def _current_rebaseline_generation(self) -> int:
        with self._lock:
            return self._rebaseline_generation

    def _should_reconcile_generation(self, generation: int) -> bool:
        with self._lock:
            if self._manual_reconcile_generation != generation:
                return False
            self._manual_reconcile_generation = None
            return True

    def _emit_event(
        self,
        callback_queue: queue.Queue[Any] | None,
        event_type: str,
        **payload: Any,
    ) -> None:
        event = {"type": event_type, "timestamp": time.time(), **payload}
        self._enqueue_callback(callback_queue, "event", event)

    def _enqueue_callback(
        self,
        callback_queue: queue.Queue[Any] | None,
        callback_type: str,
        payload: Any,
    ) -> None:
        if callback_queue is None:
            return
        if callback_type == "change" and not callable(self._change_callback):
            return
        if callback_type == "event" and not callable(self._event_callback):
            return
        try:
            callback_queue.put_nowait((callback_type, payload))
        except queue.Full:
            self._set_error("Vision callback queue is full; an event was dropped")

    def _dispatch_callbacks(self, callback_queue: queue.Queue[Any]) -> None:
        while True:
            item = callback_queue.get()
            try:
                if item is _CALLBACK_STOP:
                    return
                callback_type, payload = item
                if callback_type == "change" and callable(self._change_callback):
                    self._change_callback(payload)
                elif callback_type == "event" and callable(self._event_callback):
                    self._event_callback(payload)
            except Exception as exc:
                self._set_error(f"Vision callback failed: {exc}")
            finally:
                callback_queue.task_done()

    def _camera_warmup_complete(
        self,
        opened_at: float | None,
        now: float,
        config: dict[str, Any],
    ) -> bool:
        """Whether initial autofocus/exposure hunting may enter the baseline."""

        if opened_at is None:
            return True
        warmup_seconds = self._float_config(
            config,
            "camera_warmup_seconds",
            minimum=0.0,
            maximum=30.0,
        )
        return now - opened_at >= warmup_seconds

    @staticmethod
    def _int_config(
        config: dict[str, Any],
        key: str,
        *,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        try:
            value = int(float(config.get(key, VisionMonitor.DEFAULTS.get(key, minimum))))
        except (TypeError, ValueError, OverflowError):
            value = int(VisionMonitor.DEFAULTS.get(key, minimum))
        value = max(minimum, value)
        return min(maximum, value) if maximum is not None else value

    @staticmethod
    def _float_config(
        config: dict[str, Any],
        key: str,
        *,
        minimum: float,
        maximum: float | None = None,
    ) -> float:
        try:
            value = float(config.get(key, VisionMonitor.DEFAULTS.get(key, minimum)))
        except (TypeError, ValueError, OverflowError):
            value = float(VisionMonitor.DEFAULTS.get(key, minimum))
        if not math.isfinite(value):
            value = float(VisionMonitor.DEFAULTS.get(key, minimum))
        value = max(minimum, value)
        return min(maximum, value) if maximum is not None else value

    @staticmethod
    def _bool_config(config: dict[str, Any], key: str) -> bool:
        value = config.get(key, VisionMonitor.DEFAULTS.get(key, False))
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", ""}
        return bool(value)


__all__ = ["BBox", "ChangeEvent", "VisionMonitor", "VisionStatus"]
