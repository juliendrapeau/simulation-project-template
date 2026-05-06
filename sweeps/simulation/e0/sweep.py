"""Generate sweep configuration for simulation/e0.

Run from the project root:
  python sweeps/simulation/e0/sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from workflow.tools.sweeper import ConfigSet  # noqa

param_grid = {
    "count": [50, 100, 200],
    "low": 0.0,
    "high": 1.0,
}

cfgset, csv_path = ConfigSet.generate_and_save(
    param_grid,
    name="simulation",
    experiment_name="experiment-1",
    slugify_structure=["count"],
    slugify_keymap={"count": "n"},
    root="sweeps",
)
print(f"Generated {len(cfgset)} configs → {csv_path}")
