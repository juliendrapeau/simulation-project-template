"""Small utilities: a numeric helper and a prime check helper.

This module contains two unrelated, minimal functions intended as
examples for a simple function package:

- `compute_mean(values)` — numeric helper that returns the mean.
- `is_prime(n)` — integer helper that returns True when n is prime.
"""

import json
from collections.abc import Iterable

import numpy as np

__all__ = ["compute_mean", "generate_random_numbers"]


def compute_mean(values: Iterable[float]) -> float:
    """Return the arithmetic mean of ``values``.

    Raises ValueError when ``values`` is empty.
    """
    vals = [float(x) for x in values]
    if not vals:
        raise ValueError("compute_mean() requires at least one numeric value")
    return sum(vals) / len(vals)


def generate_random_numbers(
    count: int,
    filepath: str | None = None,
    *,
    low: float = 0.0,
    high: float = 1.0,
    seed: int | None = None,
) -> str:
    """Generate `count` random floats in [low, high) and save to `filepath`.

    Parameters
    - count: number of random values to generate (int > 0).
    - filepath: path to write the values. If None, defaults to
      "generated_numbers.txt" in the current working directory.
    - low, high: float bounds for random values (low < high).
    - seed: optional int seed for reproducible output.

    Returns
    - The file path written (as string).

    The file is written as newline-separated floats in text format.
    """
    from pathlib import Path

    if count <= 0:
        raise ValueError("count must be a positive integer")
    if low >= high:
        raise ValueError("low must be less than high")

    out_path = Path(filepath) if filepath else Path.cwd() / "generated_numbers.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Use numpy's Generator for reproducibility when seed is provided
    rng = np.random.default_rng(seed)
    numbers = list(rng.uniform(low, high, size=count))

    with open(out_path, "w") as f:
        json.dump({"number_set": numbers}, f)

    return str(out_path)


if __name__ == "__main__":
    # tiny demo
    nums = [1.0, 2.0, 3.0]
    print("nums:", nums)
    print("mean:", compute_mean(nums))
