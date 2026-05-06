"""Command-line interface for simulation-project-template."""

from __future__ import annotations

import argparse
import json
import sys

from .utils import compute_mean, generate_random_numbers


def _cmd_generate(args: argparse.Namespace) -> int:
    path = generate_random_numbers(
        args.count,
        args.output,
        low=args.low,
        high=args.high,
        seed=args.seed,
    )
    print(f"Generated {args.count} numbers → {path}")
    return 0


def _cmd_mean(args: argparse.Namespace) -> int:
    with open(args.input) as f:
        data = json.load(f)
    numbers = data.get("number_set", data)
    if not isinstance(numbers, list):
        print("Error: expected a list under 'number_set' key.", file=sys.stderr)
        return 1
    print(compute_mean(numbers))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="simulation-project-template CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  spt generate 100 -o numbers.json --seed 42\n"
            "  spt mean numbers.json\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate random numbers and save to JSON.")
    gen.add_argument("count", type=int, help="Number of random values to generate.")
    gen.add_argument("-o", "--output", default=None, help="Output JSON file path.")
    gen.add_argument(
        "--low", type=float, default=0.0, help="Lower bound (default: 0.0)."
    )
    gen.add_argument(
        "--high", type=float, default=1.0, help="Upper bound (default: 1.0)."
    )
    gen.add_argument("--seed", type=int, default=None, help="Random seed.")
    gen.set_defaults(func=_cmd_generate)

    mean = sub.add_parser("mean", help="Compute mean from a JSON file.")
    mean.add_argument("input", help="Path to a JSON file with 'number_set' key.")
    mean.set_defaults(func=_cmd_mean)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
