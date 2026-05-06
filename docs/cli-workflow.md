# CLI Workflow

The package exposes the `spt` command, defined in
`src/simulation_project_template/cli.py` and registered in `pyproject.toml`:

```toml
[project.scripts]
spt = "simulation_project_template.cli:main"
```

## Built-in commands

```bash
# Generate N random numbers in [low, high) and save to JSON.
spt generate <count> [-o OUTPUT] [--low 0.0] [--high 1.0] [--seed SEED]

# Compute the mean of a previously generated file.
spt mean <input.json>
```

### Examples

```bash
spt generate 1000 -o data/sample.json --seed 42
spt mean data/sample.json
```

## Adding a new command

Commands are plain functions registered on an `argparse` subparser.
No global registry or plugin system is needed — add a function, wire it up,
and it appears in `spt --help`.

```python
# src/simulation_project_template/cli.py

def _cmd_mycommand(args: argparse.Namespace) -> int:
    # implement your command here
    print(args.value)
    return 0


# Inside main(), after the other sub.add_parser(...) blocks:
cmd = sub.add_parser("mycommand", help="Short description.")
cmd.add_argument("value", help="Some input.")
cmd.set_defaults(func=_cmd_mycommand)
```

The command is then available as:

```bash
spt mycommand <value>
```

## Snakemake scripts vs. the CLI

Snakemake scripts in `workflow/scripts/` import directly from the package
(`from simulation_project_template import ...`) — they do not go through the
CLI. The CLI is intended for local interactive use and quick sanity checks, not
for pipeline execution.
