import sys
from pathlib import Path

# Make repository root importable so `workflow` can be imported from configs
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from workflow.tools.config_generator import ConfigSet

# Turn on for hashed-based structure instead of name-based structure
hash_based = False

param_grid = {
    "name": "experiment-1",
    "sample_size": 100,
    "instance": range(1, 11),
    "range_size": lambda params: [10 * params["instance"]],
}

key_map = {
    "name": "",
    "sample_size": "s",
    "instance": "i",
    "range_size": "r",
}

if hash_based:
    slugify = []
else:
    slugify = [("sample_size", "range_size"), "instance"]


cfgset = ConfigSet.generate_and_save(
    param_grid,
    param_grid["name"],
    slugify_structure=slugify,
    slugify_keymap=key_map,
)
