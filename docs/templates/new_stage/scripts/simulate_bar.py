"""Snakemake script template for the main rule of a new stage. Rename bar → your stage."""

# ruff: noqa: F821

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    snakemake: Any

import json
import logging
import os
import time

from tools.job_utils import capture_job_metadata, capture_run_metadata, derive_seed

logging.basicConfig(
    filename=snakemake.log[0],  # type: ignore[attr-defined]
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

cfg             = snakemake.params.cfg            # type: ignore[attr-defined]
output_result   = snakemake.output.result         # type: ignore[attr-defined]
wildcard_path   = snakemake.wildcards.path        # type: ignore[attr-defined]
wildcard_instance = snakemake.wildcards.instance  # type: ignore[attr-defined]
my_stage_param  = snakemake.params.my_stage_param # type: ignore[attr-defined]

seed = derive_seed(wildcard_path, wildcard_instance)
log.info("Starting bar path=%s instance=%s seed=%d", wildcard_path, wildcard_instance, seed)


def simulate_bar() -> None:
    my_param = int(cfg.get("my_param", 1))

    t0 = time.time()
    result_value = None  # TODO: replace with your computation
    elapsed = time.time() - t0

    job_meta = capture_job_metadata()
    job_meta["time_s"] = elapsed

    output_data = {
        "metadata": job_meta,
        "run_metadata": capture_run_metadata(),
        "params": {k: v for k, v in cfg.items() if k != "short_path"},
        "path": wildcard_path,
        "instance": int(wildcard_instance),
        "seed": seed,
        "bar": {"result": result_value, "time": elapsed},
    }

    os.makedirs(os.path.dirname(output_result), exist_ok=True)
    with open(output_result, "w") as f:
        json.dump(output_data, f, indent=4)

    log.info("Done: time=%.4fs", elapsed)


simulate_bar()
