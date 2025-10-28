"""Example script that uses `compute_mean` from the local package.

Run with numbers as arguments, or no arguments to use a default list.
"""

import json

from snakemake.script import snakemake

from snakemake_template.utils import compute_mean


def main(config_path, input_path, instance_name, output_path) -> int:
    with open(input_path, "r") as f:
        data = json.load(f)

    mean = compute_mean(data["number_set"])

    with open(output_path, "w") as f:
        json.dump({"mean": mean}, f)

    return 0


if __name__ == "__main__":
    config_path = snakemake.input[0]
    input_path = snakemake.input[1]
    output_path = snakemake.output[0]
    instance_name = snakemake.wildcards["instance_name"]

    raise SystemExit(main(config_path, input_path, instance_name, output_path))
