#!/usr/bin/env python3
"""Create the paper's Tables 5-8 from the trial sheet and run logs.

    python scripts/experiments/make_paper_tables.py --trials trials.csv \
        --db lost_items.db --health health.csv --resources resources.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.trial_report import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
