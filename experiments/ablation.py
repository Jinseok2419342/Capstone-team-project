"""Named, ordered ablation profiles for the local vision pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.config import DEFAULT_SETTINGS
from app.vision import VisionMonitor


ABLATION_PROFILES: dict[str, dict[str, bool]] = {
    # The contour and event logic remains identical in every profile.  Only
    # nuisance defences are added in order, so comparisons isolate the value
    # of alignment, lighting correction, and edge-jitter suppression.
    "plain": {
        "stabilize_camera": False,
        "compensate_lighting": False,
        "compensate_local_lighting": False,
        "micro_jitter_suppression": False,
    },
    "aligned": {
        "stabilize_camera": True,
        "compensate_lighting": False,
        "compensate_local_lighting": False,
        "micro_jitter_suppression": False,
    },
    "aligned_global": {
        "stabilize_camera": True,
        "compensate_lighting": True,
        "compensate_local_lighting": False,
        "micro_jitter_suppression": False,
    },
    "aligned_global_jitter": {
        "stabilize_camera": True,
        "compensate_lighting": True,
        "compensate_local_lighting": False,
        "micro_jitter_suppression": True,
    },
    "full": {
        "stabilize_camera": True,
        "compensate_lighting": True,
        "compensate_local_lighting": True,
        "micro_jitter_suppression": True,
    },
}

PROFILE_CONTROLLED_KEYS = frozenset(
    {
        "stabilize_camera",
        "compensate_lighting",
        "compensate_local_lighting",
        "micro_jitter_suppression",
    }
)


PROFILE_DESCRIPTIONS: dict[str, str] = {
    "plain": "No camera, lighting, or persistent-edge nuisance compensation",
    "aligned": "Camera alignment only",
    "aligned_global": "Camera alignment plus global exposure compensation",
    "aligned_global_jitter": (
        "Alignment, global exposure compensation, and persistent-edge jitter suppression"
    ),
    "full": "Complete production nuisance-defence pipeline including local lighting compensation",
}


def profile_names() -> tuple[str, ...]:
    """Return profiles in the required cumulative-ablation order."""

    return tuple(ABLATION_PROFILES)


def build_vision_config(
    profile: str,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete detector configuration for one ablation profile.

    Operational settings override the lower-level monitor defaults, then the
    selected profile changes only the nuisance-defence switches.  Explicit
    experiment overrides are applied last and should be archived with the run.
    """

    try:
        profile_values = ABLATION_PROFILES[profile]
    except KeyError as exc:
        choices = ", ".join(profile_names())
        raise ValueError(f"unknown ablation profile {profile!r}; choose: {choices}") from exc

    config = dict(VisionMonitor.DEFAULTS)
    config.update(DEFAULT_SETTINGS)
    config.update(profile_values)
    if overrides:
        config.update(dict(overrides))
    return config
