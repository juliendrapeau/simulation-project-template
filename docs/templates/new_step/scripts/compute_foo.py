"""Snakemake script template for a new per-(path, instance) step. Rename foo → your step."""

# ruff: noqa: F821

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    snakemake: Any

import json
import logging
import time

from tools.job_utils import capture_job_metadata, capture_run_metadata

logging.basicConfig(
    filename=snakemake.log[0],  # type: ignore[attr-defined]
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

results_path    = snakemake.input.results         # type: ignore[attr-defined]
output_path     = snakemake.output[0]             # type: ignore[attr-defined]
wildcard_path   = snakemake.wildcards.path        # type: ignore[attr-defined]
wildcard_instance = snakemake.wildcards.instance  # type: ignore[attr-defined]
my_param: int   = snakemake.params.my_param       # type: ignore[attr-defined]


def compute_foo() -> None:
    with open(results_path) as f:
        prev = json.load(f)

    t0 = time.time()
    result = None  # TODO: replace with your computation using prev data
    elapsed = time.time() - t0

    job_meta = capture_job_metadata()
    job_meta["time_s"] = elapsed

    output_data = {
        "metadata": job_meta,
        "run_metadata": capture_run_metadata(),
        "params": prev.get("params", {}),
        "path": wildcard_path,
        "instance": int(wildcard_instance),
        "seed": prev.get("seed"),
        "foo": {"result": result, "time": elapsed},
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=4)

    log.info("Done: time=%.4fs", elapsed)


compute_foo()
