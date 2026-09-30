"""Camera backends with an OpenCV-compatible capture contract.

``picamera2`` is deliberately imported only when that backend is requested.
This keeps the desktop application and its test environment independent from
Raspberry Pi packages while allowing the vision loop to consume CSI-camera
frames through the same ``read``/``release`` interface as ``VideoCapture``.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from inspect import getattr_static
import math
from typing import Any, Protocol

import cv2
import numpy as np


class CameraCapture(Protocol):
    """The small part of ``cv2.VideoCapture`` used by ``VisionMonitor``."""

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


class CameraSourceError(RuntimeError):
    """A camera backend could not be imported or initialised."""


def _load_picamera2_class() -> type[Any]:
    """Load Picamera2 lazily so desktop installs do not require it."""

    try:
        from picamera2 import Picamera2  # type: ignore[import-not-found]
    except (ImportError, OSError) as exc:
        raise CameraSourceError(f"Picamera2 is unavailable: {exc}") from exc
    return Picamera2


def _numeric_source(source: Any) -> Any:
    if isinstance(source, str) and source.strip().lstrip("-").isdigit():
        return int(source.strip())
    return source


def _camera_info(camera: Any, name: str) -> dict[str, Any]:
    """Optional diagnostics must not prevent a usable camera from opening."""

    try:
        value = getattr(camera, name, {})
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _has_capture_arrays(camera: Any) -> bool:
    """Do not mistake a dynamic mock/proxy attribute for a supported API."""

    try:
        getattr_static(camera, "capture_arrays")
        return callable(getattr(camera, "capture_arrays"))
    except Exception:
        return False


def _configure_flicker(
    camera: Any, frequency_hz: int, controls: dict[str, Any]
) -> tuple[int | None, list[str]]:
    """Request mains flicker avoidance while leaving automatic AE/AWB enabled.

    The libcamera control definition specifies FlickerManual=1, and periods of
    10000 us for 50 Hz mains and 8333 us for 60 Hz mains. Zero preserves the
    driver's existing behaviour; unsupported cameras keep working unchanged.
    """

    if frequency_hz == 0:
        return None, []
    requested = {
        "AeFlickerMode": 1,
        "AeFlickerPeriod": 10000 if frequency_hz == 50 else 8333,
    }
    for key, value in requested.items():
        info = controls.get(key)
        if not isinstance(info, (tuple, list)) or len(info) < 2:
            return None, [f"{frequency_hz} Hz flicker avoidance unavailable: {key} is not supported"]
        try:
            in_range = float(info[0]) <= value <= float(info[1])
        except (TypeError, ValueError, OverflowError):
            in_range = False
        if not in_range:
            return None, [f"{frequency_hz} Hz flicker avoidance unavailable: {key} does not accept {value}"]
    try:
        camera.set_controls(requested)
    except Exception as exc:
        return None, [f"Could not apply {frequency_hz} Hz flicker avoidance: {str(exc)[:300]}"]
    return frequency_hz, []


class Picamera2Capture:
    """Expose a Picamera2 CSI camera like an OpenCV capture object.

    Picamera2/libcamera's ``RGB888`` stream is byte-ordered as BGR for the
    NumPy/OpenCV view on Raspberry Pi, so frames must be returned unchanged.
    ``queue=False`` is important for change detection: it asks Picamera2 for a
    fresh completed request instead of an older queued frame.
    """

    def __init__(
        self,
        source: Any,
        width: int,
        height: int,
        fps: float,
        *,
        mains_frequency_hz: int = 0,
        picamera2_class: type[Any] | None = None,
    ) -> None:
        if isinstance(mains_frequency_hz, bool) or mains_frequency_hz not in {0, 50, 60}:
            raise CameraSourceError("Mains frequency must be 0, 50 or 60 Hz")
        camera_number = _numeric_source(source)
        if not isinstance(camera_number, int) or camera_number < 0:
            raise CameraSourceError(
                "Picamera2 camera source must be a non-negative camera number"
            )

        camera_type = picamera2_class or _load_picamera2_class()
        camera: Any | None = None
        try:
            camera = camera_type(camera_num=camera_number)
            video_config = camera.create_video_configuration(
                main={"format": "RGB888", "size": (int(width), int(height))},
                controls={"FrameRate": float(fps)},
                queue=False,
            )
            camera.configure(video_config)
            camera_controls = _camera_info(camera, "camera_controls")
            applied_mains, warnings = _configure_flicker(
                camera, mains_frequency_hz, camera_controls
            )
            camera.start()
        except Exception as exc:
            if camera is not None:
                # ``start`` can fail after libcamera has acquired resources,
                # so stop is worth attempting even if it did not return.
                try:
                    camera.stop()
                except Exception:
                    pass
                try:
                    camera.close()
                except Exception:
                    pass
            raise CameraSourceError(f"Unable to start Picamera2 camera: {exc}") from exc

        self._camera = camera
        self._opened = True
        camera_properties = _camera_info(camera, "camera_properties")
        self._diagnostics: dict[str, Any] = {
            "backend": "picamera2",
            "model": str(camera_properties.get("Model", "unknown"))[:128],
            "requested_mains_frequency_hz": mains_frequency_hz,
            "applied_mains_frequency_hz": applied_mains,
            "controls_supported": sorted(str(key)[:64] for key in camera_controls)[:128],
            "warnings": warnings,
            "metadata_supported": _has_capture_arrays(camera),
            "frame_sequence": 0,
            "frame_metadata": {},
            "last_read_ok": None,
            "last_read_error": None,
        }

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._opened:
            return False, None
        try:
            if self._diagnostics["metadata_supported"]:
                # A separate capture_metadata call would describe a different
                # frame and would double the number of blocking captures.
                arrays, metadata = self._camera.capture_arrays(["main"])
                frame = arrays[0]
            else:
                frame = self._camera.capture_array("main")
                metadata = {}
        except Exception as exc:
            self._diagnostics = {
                **self._diagnostics,
                "last_read_ok": False,
                "last_read_error": str(exc)[:300],
            }
            return False, None
        if (
            not isinstance(frame, np.ndarray)
            or frame.ndim != 3
            or frame.shape[2] != 3
            or frame.size == 0
            or frame.dtype != np.uint8
        ):
            self._diagnostics = {
                **self._diagnostics,
                "last_read_ok": False,
                "last_read_error": "Invalid RGB888 camera frame",
            }
            return False, None
        self._diagnostics = {
            **self._diagnostics,
            "frame_sequence": self._diagnostics["frame_sequence"] + 1,
            "frame_metadata": self._frame_metadata(metadata),
            "last_read_ok": True,
            "last_read_error": None,
        }
        return True, frame

    @staticmethod
    def _frame_metadata(metadata: Any) -> dict[str, Any]:
        """Expose only bounded, JSON-safe sensor values useful for diagnosis."""

        if not isinstance(metadata, dict):
            return {}
        result: dict[str, Any] = {}
        for key in (
            "ExposureTime", "AnalogueGain", "DigitalGain", "ColourGains",
            "ColourTemperature", "LensPosition", "AfMode", "AfState",
            "AeState", "AeLocked", "AwbLocked", "Lux", "FrameDuration",
            "SensorTimestamp", "AeFlickerMode", "AeFlickerPeriod", "AeFlickerDetected",
        ):
            value = metadata.get(key)
            if isinstance(value, (int, float, np.integer, np.floating, np.bool_)):
                number = value.item() if isinstance(value, np.generic) else value
                try:
                    finite = isinstance(number, bool) or math.isfinite(number)
                except (TypeError, ValueError, OverflowError):
                    finite = False
                if finite:
                    result[key] = number
            elif key == "ColourGains" and isinstance(value, (tuple, list)) and len(value) == 2:
                try:
                    gains = [float(part) for part in value]
                except (TypeError, ValueError, OverflowError):
                    continue
                if all(math.isfinite(part) for part in gains):
                    result[key] = gains
        return result

    def get_diagnostics(self) -> dict[str, Any]:
        """Return the latest frame's metadata without acquiring another frame."""

        return deepcopy(self._diagnostics)

    def isOpened(self) -> bool:  # noqa: N802 - matches cv2.VideoCapture
        return self._opened

    def release(self) -> None:
        if not self._opened:
            return
        self._opened = False
        try:
            self._camera.stop()
        except Exception:
            pass
        try:
            self._camera.close()
        except Exception:
            pass


def _open_picamera2_capture(
    source: Any,
    width: int,
    height: int,
    fps: float,
    *,
    mains_frequency_hz: int = 0,
) -> CameraCapture:
    return Picamera2Capture(source, width, height, fps, mains_frequency_hz=mains_frequency_hz)


def _open_opencv_capture(
    source: Any,
    backend_name: str,
    width: int,
    height: int,
    fps: float,
) -> tuple[CameraCapture | None, str | None]:
    backends = {
        "any": cv2.CAP_ANY,
        "dshow": getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),
        "msmf": getattr(cv2, "CAP_MSMF", cv2.CAP_ANY),
        "v4l2": getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),
        "avfoundation": getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY),
        "ffmpeg": getattr(cv2, "CAP_FFMPEG", cv2.CAP_ANY),
        "gstreamer": getattr(cv2, "CAP_GSTREAMER", cv2.CAP_ANY),
    }
    backend = backends.get(backend_name)
    capture: Any | None = None
    try:
        if backend is None or backend == cv2.CAP_ANY:
            capture = cv2.VideoCapture(source)
        else:
            capture = cv2.VideoCapture(source, backend)
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2500)
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2500)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        capture.set(cv2.CAP_PROP_FPS, float(fps))
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            capture.release()
            return None, f"Unable to open camera source {source!r}"
        return capture, None
    except Exception as exc:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        return None, f"Unable to open camera source {source!r}: {exc}"


def open_camera_capture(
    source: Any,
    backend_name: str,
    width: int,
    height: int,
    fps: float,
    *,
    mains_frequency_hz: int = 0,
) -> tuple[CameraCapture | None, str | None]:
    """Open the selected backend, optionally falling back to OpenCV.

    ``auto`` and ``picamera2`` both try the CSI-camera path first and then
    preserve demo availability by falling back to OpenCV. Other backend names,
    including the historical empty value, retain the old OpenCV-only path.
    """

    source = _numeric_source(source)
    backend_name = str(backend_name or "").strip().lower()
    picamera_error: str | None = None
    if backend_name in {"auto", "picamera2"}:
        try:
            if mains_frequency_hz:
                return _open_picamera2_capture(
                    source, width, height, fps, mains_frequency_hz=mains_frequency_hz
                ), None
            return _open_picamera2_capture(source, width, height, fps), None
        except Exception as exc:
            picamera_error = str(exc) or exc.__class__.__name__

    opencv_backend = "any" if backend_name in {"auto", "picamera2"} else backend_name
    capture, opencv_error = _open_opencv_capture(
        source,
        opencv_backend,
        width,
        height,
        fps,
    )
    if capture is not None:
        return capture, None
    if picamera_error:
        return None, f"Picamera2 failed ({picamera_error}); OpenCV failed ({opencv_error})"
    return None, opencv_error
