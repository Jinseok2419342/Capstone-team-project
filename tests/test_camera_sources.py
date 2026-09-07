from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from app.camera_sources import (
    CameraSourceError,
    Picamera2Capture,
    open_camera_capture,
)


class FakePicamera2:
    instances: list["FakePicamera2"] = []

    def __init__(self, camera_num: int = 0) -> None:
        self.camera_num = camera_num
        self.configuration_kwargs: dict[str, object] | None = None
        self.configured: object | None = None
        self.started = 0
        self.stopped = 0
        self.closed = 0
        self.capture_name: str | None = None
        # Deliberately asymmetric BGR values catch accidental RGB conversion.
        self.frame = np.full((6, 8, 3), (7, 31, 223), dtype=np.uint8)
        self.instances.append(self)

    def create_video_configuration(self, **kwargs: object) -> object:
        self.configuration_kwargs = kwargs
        return {"created": True}

    def configure(self, configuration: object) -> None:
        self.configured = configuration

    def start(self) -> None:
        self.started += 1

    def capture_array(self, name: str) -> np.ndarray:
        self.capture_name = name
        return self.frame

    def stop(self) -> None:
        self.stopped += 1

    def close(self) -> None:
        self.closed += 1


class Picamera2CaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        FakePicamera2.instances.clear()

    def test_configures_fresh_rgb888_stream_and_returns_bgr_unchanged(self) -> None:
        capture = Picamera2Capture(
            "1", 1280, 720, 12.0, picamera2_class=FakePicamera2
        )
        camera = FakePicamera2.instances[-1]

        self.assertEqual(camera.camera_num, 1)
        self.assertEqual(
            camera.configuration_kwargs,
            {
                "main": {"format": "RGB888", "size": (1280, 720)},
                "controls": {"FrameRate": 12.0},
                "queue": False,
            },
        )
        self.assertEqual(camera.configured, {"created": True})
        self.assertEqual(camera.started, 1)

        ok, frame = capture.read()
        self.assertTrue(ok)
        self.assertIs(frame, camera.frame)
        self.assertEqual(camera.capture_name, "main")
        self.assertEqual(frame[0, 0].tolist(), [7, 31, 223])

        capture.release()
        capture.release()
        self.assertFalse(capture.isOpened())
        self.assertEqual(camera.stopped, 1)
        self.assertEqual(camera.closed, 1)
        self.assertEqual(capture.read(), (False, None))

    def test_rejects_non_numeric_picamera_source(self) -> None:
        with self.assertRaisesRegex(CameraSourceError, "camera number"):
            Picamera2Capture(
                "rtsp://camera/live",
                640,
                360,
                8.0,
                picamera2_class=FakePicamera2,
            )

    def test_capture_error_becomes_failed_read_for_monitor_retry(self) -> None:
        class FailingReadPicamera2(FakePicamera2):
            def capture_array(self, name: str) -> np.ndarray:
                raise RuntimeError("camera request failed")

        capture = Picamera2Capture(
            0, 640, 360, 8.0, picamera2_class=FailingReadPicamera2
        )

        self.assertEqual(capture.read(), (False, None))
        capture.release()

    def test_start_error_releases_partially_opened_camera(self) -> None:
        class FailingStartPicamera2(FakePicamera2):
            def start(self) -> None:
                self.started += 1
                raise RuntimeError("libcamera busy")

        with self.assertRaisesRegex(CameraSourceError, "libcamera busy"):
            Picamera2Capture(
                0, 640, 360, 8.0, picamera2_class=FailingStartPicamera2
            )

        camera = FailingStartPicamera2.instances[-1]
        self.assertEqual(camera.stopped, 1)
        self.assertEqual(camera.closed, 1)

    @patch("app.camera_sources._open_opencv_capture")
    @patch("app.camera_sources._open_picamera2_capture")
    def test_auto_prefers_picamera2_without_opening_opencv(
        self, open_picamera: Mock, open_opencv: Mock
    ) -> None:
        expected = Mock()
        open_picamera.return_value = expected

        capture, error = open_camera_capture("0", "auto", 640, 360, 8.0)

        self.assertIs(capture, expected)
        self.assertIsNone(error)
        open_picamera.assert_called_once_with(0, 640, 360, 8.0)
        open_opencv.assert_not_called()

    @patch("app.camera_sources._open_opencv_capture")
    @patch("app.camera_sources._open_picamera2_capture")
    def test_auto_falls_back_to_opencv_when_picamera2_is_unavailable(
        self, open_picamera: Mock, open_opencv: Mock
    ) -> None:
        expected = Mock()
        open_picamera.side_effect = CameraSourceError("package missing")
        open_opencv.return_value = (expected, None)

        capture, error = open_camera_capture(0, "auto", 640, 360, 8.0)

        self.assertIs(capture, expected)
        self.assertIsNone(error)
        open_opencv.assert_called_once_with(0, "any", 640, 360, 8.0)

    @patch("app.camera_sources._open_opencv_capture")
    @patch("app.camera_sources._open_picamera2_capture")
    def test_explicit_picamera2_also_falls_back_and_combines_open_errors(
        self, open_picamera: Mock, open_opencv: Mock
    ) -> None:
        open_picamera.side_effect = CameraSourceError("no CSI camera")
        open_opencv.return_value = (None, "no V4L2 device")

        capture, error = open_camera_capture(0, "picamera2", 640, 360, 8.0)

        self.assertIsNone(capture)
        self.assertIn("Picamera2 failed (no CSI camera)", error or "")
        self.assertIn("OpenCV failed (no V4L2 device)", error or "")
        open_opencv.assert_called_once_with(0, "any", 640, 360, 8.0)

    @patch("app.camera_sources.cv2.VideoCapture")
    def test_desktop_backend_keeps_existing_opencv_configuration(
        self, video_capture: Mock
    ) -> None:
        fake_capture = Mock()
        fake_capture.isOpened.return_value = True
        video_capture.return_value = fake_capture

        capture, error = open_camera_capture(2, "v4l2", 800, 600, 15.0)

        self.assertIs(capture, fake_capture)
        self.assertIsNone(error)
        video_capture.assert_called_once_with(2, cv2.CAP_V4L2)
        fake_capture.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 800)
        fake_capture.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        fake_capture.set.assert_any_call(cv2.CAP_PROP_FPS, 15.0)


if __name__ == "__main__":
    unittest.main()
