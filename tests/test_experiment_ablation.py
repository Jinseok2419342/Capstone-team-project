from __future__ import annotations

import unittest

from experiments.ablation import ABLATION_PROFILES, build_vision_config, profile_names


class ExperimentAblationTests(unittest.TestCase):
    def test_profiles_add_defences_in_declared_order(self) -> None:
        self.assertEqual(
            profile_names(),
            (
                "plain",
                "aligned",
                "aligned_global",
                "aligned_global_jitter",
                "full",
            ),
        )
        self.assertFalse(ABLATION_PROFILES["plain"]["stabilize_camera"])
        self.assertTrue(ABLATION_PROFILES["aligned"]["stabilize_camera"])
        self.assertTrue(ABLATION_PROFILES["aligned_global"]["compensate_lighting"])
        self.assertTrue(
            ABLATION_PROFILES["aligned_global_jitter"]["micro_jitter_suppression"]
        )
        self.assertTrue(ABLATION_PROFILES["full"]["compensate_local_lighting"])

    def test_config_combines_monitor_operational_profile_and_explicit_values(self) -> None:
        config = build_vision_config(
            "plain",
            {"change_threshold": 31, "custom_experiment_label": "R001"},
        )
        self.assertIn("relocation_match_min", config)
        self.assertIn("camera_width", config)
        self.assertFalse(config["stabilize_camera"])
        self.assertEqual(config["change_threshold"], 31)
        self.assertEqual(config["custom_experiment_label"], "R001")

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown ablation profile"):
            build_vision_config("mystery")


if __name__ == "__main__":
    unittest.main()
