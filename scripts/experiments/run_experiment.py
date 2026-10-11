#!/usr/bin/env python3
"""Guided paper experiment: perform each action, press Enter, nothing else.

    python scripts/experiments/run_experiment.py

See docs/paper/EXPERIMENT_GUIDE.md.  Only the Python standard library is
needed, so it runs on the Windows laptop while the usual SSH tunnel is open.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.live_session import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
