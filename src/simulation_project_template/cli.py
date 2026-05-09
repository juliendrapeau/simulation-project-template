"""Command-line interface for simulation-project-template."""

from __future__ import annotations

import json

import click

from .utils import compute_mean, generate_random_numbers


@click.group()
def main() -> None:
    """simulation-project-template CLI."""


@main.command()
@click.argument("count", type=int)
@click.option("-o", "--output", default=None, help="Output JSON file path.")
@click.option("--low", type=float, default=0.0, help="Lower bound (default: 0.0).")
@click.option("--high", type=float, default=1.0, help="Upper bound (default: 1.0).")
@click.option("--seed", type=int, default=None, help="Random seed.")
def generate(
    count: int,
    output: str | None,
    low: float,
    high: float,
    seed: int | None,
) -> None:
    """Generate random numbers and save to JSON."""
    path = generate_random_numbers(count, output, low=low, high=high, seed=seed)
    print(f"Generated {count} numbers → {path}")


@main.command()
@click.argument("input", type=click.Path(exists=True))
def mean(input: str) -> None:
    """Compute mean from a JSON file."""
    with open(input) as f:
        data = json.load(f)
    numbers = data if isinstance(data, list) else data.get("number_set", data)
    if not isinstance(numbers, list):
        raise click.ClickException("Expected a list under 'number_set' key.")
    click.echo(compute_mean(numbers))


if __name__ == "__main__":
    main()
