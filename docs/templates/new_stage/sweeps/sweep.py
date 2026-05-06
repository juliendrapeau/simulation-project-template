"""Generate sweep configuration for bar/e0.

Rename "bar" to your stage name throughout, adjust param_grid, then run from
the project root:
  python sweeps/bar/e0/sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from workflow.tools.sweeper import ConfigSet

param_grid = {
    "my_param": [1, 2, 4],
    "fixed_param": 0.5,
}

cfgset, csv_path = ConfigSet.generate_and_save(
    param_grid,
    name="bar",
    experiment_name="e0",
    slugify_structure=["my_param"],
    slugify_keymap={"my_param": "p"},
    root="sweeps",
)
print(f"Generated {len(cfgset)} configs → {csv_path}")
