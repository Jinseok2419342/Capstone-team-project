"""Camera backends with an OpenCV-compatible capture contract.

``picamera2`` is deliberately imported only when that backend is requested.
This keeps the desktop application and its test environment independent from
Raspberry Pi packages while allowing the vision loop to consume CSI-camera
frames through the same ``read``/``release`` interface as ``VideoCapture``.
"""

from __future__ import annotations

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
        picamera2_class: type[Any] | None = None,
    ) -> None:
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

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._opened:
            return False, None
        try:
            frame = self._camera.capture_array("main")
        except Exception:
            return False, None
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.size == 0:
            return False, None
        return True, frame

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
) -> CameraCapture:
    return Picamera2Capture(source, width, height, fps)


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
