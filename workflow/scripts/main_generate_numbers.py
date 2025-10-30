"""Generate random numbers and save them to a file using the package helper.

Usage:
  - No args: generate 10 numbers to ./generated_numbers.txt
  - Provide count and optional output path: python3 main_generate_numbers.py 100 out.txt

This script inserts the repo `src/` on sys.path so it can import the
local package without requiring installation.
"""

import pandas as pd
from snakemake.script import snakemake

from snakemake_template.utils import generate_random_numbers


def main(config_path, instance_name, output_path) -> int:
    df = pd.read_csv(config_path)
    df_tp = df[df["instance_name"] == instance_name]

    generate_random_numbers(
        int(df_tp["sample_size"].iloc[0]),
        output_path,
        low=0.0,
        high=int(df_tp["range_size"].iloc[0]),
    )

    return 0


if __name__ == "__main__":
    config_path = snakemake.input[0]
    output_path = snakemake.output[0]
    instance_name = snakemake.wildcards["instance_name"]

    raise SystemExit(main(config_path, instance_name, output_path))
