"""Snakemake script: aggregate per-run results.json files into results.csv."""

# ruff: noqa: F821

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    snakemake: Any

import json
from pathlib import Path

import pandas as pd

result_files: list[str] = list(snakemake.input.results)  # type: ignore
output_csv: str = snakemake.output.results  # type: ignore

rows = []
for path in result_files:
    with open(path) as f:
        data = json.load(f)
    row: dict = {}
    row.update({k: v for k, v in data.get("params", {}).items() if k != "short_path"})
    row["path"] = data.get("path")
    row["instance"] = data.get("instance")
    row["seed"] = data.get("seed")
    row["count"] = data.get("count")
    row["mean"] = data.get("mean")
    rows.append(row)

df = pd.DataFrame(rows)
Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_csv, index=False)
