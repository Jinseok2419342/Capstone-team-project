from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class CameraProfileTests(unittest.TestCase):
    def test_pi_preview_budget_preserves_capture_and_evidence_resolution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, HARDWARE_PROFILE="raspberry-pi")
        result = subprocess.run(
            [sys.executable, "-c", "import json; from app.config import DEFAULT_SETTINGS; "
             "print(json.dumps({k:DEFAULT_SETTINGS[k] for k in "
             "('camera_width','camera_height','jpeg_quality','preview_max_width',"
             "'monitor_fps','preview_stream_fps','camera_mains_frequency_hz')}))"],
            cwd=root, env=environment, text=True, capture_output=True, check=True, timeout=10,
        )
        settings = json.loads(result.stdout)
        self.assertEqual((settings["camera_width"], settings["camera_height"]), (1280, 720))
        self.assertEqual(settings["jpeg_quality"], 88)
        self.assertEqual(settings["preview_max_width"], 800)
        self.assertEqual(settings["monitor_fps"], 7)
        self.assertEqual(settings["preview_stream_fps"], 5)
        self.assertEqual(settings["camera_mains_frequency_hz"], 0)


if __name__ == "__main__":
    unittest.main()
