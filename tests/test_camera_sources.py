from __future__ import annotations

import json
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

    def test_flicker_defaults_preserve_controls_and_do_not_guess_capabilities(self) -> None:
        capture = Picamera2Capture(0, 640, 360, 8.0, picamera2_class=FakePicamera2)
        diagnostics = capture.get_diagnostics()
        self.assertEqual(diagnostics["requested_mains_frequency_hz"], 0)
        self.assertIsNone(diagnostics["applied_mains_frequency_hz"])
        self.assertEqual(diagnostics["controls_supported"], [])
        self.assertFalse(diagnostics["metadata_supported"])
        self.assertEqual(diagnostics["frame_metadata"], {})
        capture.release()

    def test_dynamic_mock_attributes_are_not_treated_as_metadata_support(self) -> None:
        class DynamicCamera(FakePicamera2):
            def __getattr__(self, name: str) -> Mock:
                return Mock()

        capture = Picamera2Capture(0, 640, 360, 8.0, picamera2_class=DynamicCamera)
        self.assertFalse(capture.get_diagnostics()["metadata_supported"])
        self.assertEqual(capture.get_diagnostics()["controls_supported"], [])
        self.assertTrue(capture.read()[0])
        capture.release()

    def test_supported_flicker_is_applied_without_locking_ae_awb_or_focus(self) -> None:
        class ControlledCamera(FakePicamera2):
            camera_controls = {
                "AeFlickerMode": (0, 1, 0),
                "AeFlickerPeriod": (100, 100000, 0),
                "AeEnable": (False, True, True),
                "AwbEnable": (False, True, True),
                "AfMode": (0, 2, 0),
            }
            camera_properties = {"Model": "test-camera"}

            def set_controls(self, controls: dict[str, object]) -> None:
                self.control_updates = controls
                # Controls must be queued after configure and before start.
                assert self.configured is not None
                assert self.started == 0

        for frequency, period in ((50, 10000), (60, 8333)):
            with self.subTest(frequency=frequency):
                capture = Picamera2Capture(
                    0, 640, 360, 8.0,
                    mains_frequency_hz=frequency, picamera2_class=ControlledCamera,
                )
                camera = FakePicamera2.instances[-1]
                self.assertEqual(camera.control_updates, {"AeFlickerMode": 1, "AeFlickerPeriod": period})
                self.assertEqual(capture.get_diagnostics()["applied_mains_frequency_hz"], frequency)
                self.assertEqual(capture.get_diagnostics()["model"], "test-camera")
                self.assertEqual(capture.get_diagnostics()["warnings"], [])
                capture.release()

    def test_unsupported_or_rejected_flicker_keeps_csi_camera_running(self) -> None:
        class MissingPeriodCamera(FakePicamera2):
            camera_controls = {"AeFlickerMode": (0, 1, 0)}

            def set_controls(self, controls: dict[str, object]) -> None:
                raise AssertionError("Must not send unsupported controls")

        class OutOfRangeCamera(MissingPeriodCamera):
            camera_controls = {"AeFlickerMode": (0, 0, 0), "AeFlickerPeriod": (100, 100000, 0)}

        class RejectingCamera(FakePicamera2):
            camera_controls = {"AeFlickerMode": (0, 1, 0), "AeFlickerPeriod": (100, 100000, 0)}

            def set_controls(self, controls: dict[str, object]) -> None:
                raise RuntimeError("control was rejected")

        for camera_type in (MissingPeriodCamera, OutOfRangeCamera, RejectingCamera):
            with self.subTest(camera_type=camera_type):
                capture = Picamera2Capture(
                    0, 640, 360, 8.0,
                    mains_frequency_hz=60, picamera2_class=camera_type,
                )
                self.assertTrue(capture.isOpened())
                self.assertIsNone(capture.get_diagnostics()["applied_mains_frequency_hz"])
                self.assertEqual(capture.get_diagnostics()["requested_mains_frequency_hz"], 60)
                self.assertEqual(len(capture.get_diagnostics()["warnings"]), 1)
                self.assertTrue(capture.read()[0])
                capture.release()

    def test_diagnostic_properties_failure_does_not_lose_an_open_camera(self) -> None:
        class UnavailableInfoCamera(FakePicamera2):
            @property
            def camera_controls(self) -> dict[str, object]:
                raise RuntimeError("optional camera information unavailable")

            @property
            def camera_properties(self) -> dict[str, object]:
                raise RuntimeError("optional camera information unavailable")

        capture = Picamera2Capture(0, 640, 360, 8.0, picamera2_class=UnavailableInfoCamera)
        self.assertEqual(capture.get_diagnostics()["model"], "unknown")
        self.assertTrue(capture.read()[0])
        capture.release()
        self.assertEqual(FakePicamera2.instances[-1].closed, 1)

    def test_frame_and_metadata_are_captured_together_once_and_are_json_safe(self) -> None:
        class MetadataCamera(FakePicamera2):
            def capture_array(self, name: str) -> np.ndarray:
                raise AssertionError("Must not acquire a second frame")

            def capture_metadata(self) -> dict[str, object]:
                raise AssertionError("Must not acquire metadata from another frame")

            def capture_arrays(self, names: list[str]) -> tuple[list[np.ndarray], dict[str, object]]:
                self.calls = getattr(self, "calls", 0) + 1
                assert names == ["main"]
                return [self.frame], {
                    "ExposureTime": np.int64(8333), "AnalogueGain": np.float32(2.0),
                    "ColourGains": (1.3, 1.7), "AfState": 2, "LensPosition": 1.2,
                    "SensorTimestamp": 1234567890, "AwbLocked": True,
                    "Lux": float("nan"), "DigitalGain": float("inf"),
                    "ColourTemperature": 10 ** 1000,
                    "UnrelatedBlob": np.zeros((200, 200)),
                }

        capture = Picamera2Capture(0, 640, 360, 8.0, picamera2_class=MetadataCamera)
        camera = FakePicamera2.instances[-1]
        ok, frame = capture.read()
        self.assertTrue(ok)
        self.assertIs(frame, camera.frame)
        self.assertEqual(camera.calls, 1)
        diagnostics = capture.get_diagnostics()
        self.assertEqual(diagnostics["frame_sequence"], 1)
        self.assertEqual(diagnostics["frame_metadata"], {
            "ExposureTime": 8333, "AnalogueGain": 2.0, "ColourGains": [1.3, 1.7],
            "AfState": 2, "LensPosition": 1.2, "SensorTimestamp": 1234567890, "AwbLocked": True,
        })
        json.dumps(diagnostics, allow_nan=False)
        diagnostics["frame_metadata"]["ColourGains"][0] = 99
        self.assertEqual(capture.get_diagnostics()["frame_metadata"]["ColourGains"], [1.3, 1.7])
        capture.release()
        capture.release()
        self.assertEqual(camera.stopped, 1)
        self.assertEqual(camera.closed, 1)

    def test_failed_read_marks_old_metadata_as_stale_and_invalid_frames_are_rejected(self) -> None:
        capture = Picamera2Capture(0, 640, 360, 8.0, picamera2_class=FakePicamera2)
        camera = FakePicamera2.instances[-1]
        self.assertTrue(capture.read()[0])
        for frame in (np.zeros((8, 8, 4), np.uint8), np.zeros((8, 8, 3), np.float32), np.zeros((0, 8, 3), np.uint8)):
            camera.frame = frame
            self.assertEqual(capture.read(), (False, None))
            self.assertFalse(capture.get_diagnostics()["last_read_ok"])
            self.assertEqual(capture.get_diagnostics()["frame_sequence"], 1)
        capture.release()

    def test_invalid_flicker_frequency_is_rejected_before_acquiring_camera(self) -> None:
        for value in (True, 45, -60, "60"):
            with self.subTest(value=value), self.assertRaisesRegex(CameraSourceError, "frequency"):
                Picamera2Capture(0, 640, 360, 8.0, mains_frequency_hz=value, picamera2_class=FakePicamera2)
        self.assertEqual(FakePicamera2.instances, [])

    @patch("app.camera_sources._open_opencv_capture")
    @patch("app.camera_sources._open_picamera2_capture")
    def test_requested_flicker_is_forwarded_only_to_picamera_backend(
        self, open_picamera: Mock, open_opencv: Mock
    ) -> None:
        expected = Mock()
        open_picamera.return_value = expected
        capture, error = open_camera_capture(0, "picamera2", 640, 360, 8.0, mains_frequency_hz=60)
        self.assertIs(capture, expected)
        self.assertIsNone(error)
        open_picamera.assert_called_once_with(0, 640, 360, 8.0, mains_frequency_hz=60)
        open_opencv.assert_not_called()

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
