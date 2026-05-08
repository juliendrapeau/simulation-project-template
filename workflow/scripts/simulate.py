"""Snakemake script: run simulation for one parameter set and write results.json."""

# ruff: noqa: F821

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    snakemake: Any

import json
import logging
import os

from tools.job_utils import capture_job_metadata, capture_run_metadata, derive_seed  # type: ignore

from simulation_project_template import compute_mean, generate_random_numbers

_log_path = snakemake.log[0]  # type: ignore
logging.basicConfig(
    filename=_log_path,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

cfg = snakemake.params.cfg  # type: ignore
output_path = snakemake.output.results  # type: ignore
wildcard_path = snakemake.wildcards.path  # type: ignore
wildcard_instance = snakemake.wildcards.instance  # type: ignore

seed = derive_seed(wildcard_path, wildcard_instance)
count = int(cfg.get("count", 100))
low = float(cfg.get("low", 0.0))
high = float(cfg.get("high", 1.0))

log.info(
    "Starting simulation path=%s instance=%s count=%d seed=%d",
    wildcard_path,
    wildcard_instance,
    count,
    seed,
)

numbers_path = os.path.join(os.path.dirname(output_path), "numbers.json")
generate_random_numbers(count, numbers_path, low=low, high=high, seed=seed)

with open(numbers_path) as f:
    data = json.load(f)

mean = compute_mean(data["number_set"])

result = {
    "metadata": capture_job_metadata(),
    "run_metadata": capture_run_metadata(),
    "params": {k: v for k, v in cfg.items() if k != "short_path"},
    "path": wildcard_path,
    "instance": int(wildcard_instance),
    "seed": seed,
    "mean": mean,
    "count": count,
}

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w") as f:
    json.dump(result, f, indent=4)

log.info("Done: mean=%.6f count=%d seed=%d", mean, count, seed)
