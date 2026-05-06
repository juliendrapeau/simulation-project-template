# Snakemake Pipeline

Snakemake workflow that sweeps over parameter grids, runs simulations in
parallel, and aggregates results into a flat CSV.

## Layout

```
workflow/
├── Snakefile                  # top-level entrypoint (run from project root)
├── rules/                     # *.smk rule definitions
│   ├── simulate.smk
│   └── aggregate.smk
├── scripts/                   # per-rule Python jobs
│   ├── simulate.py
│   └── aggregate.py
└── tools/                     # shared helpers
    ├── sweeper.py             # Config / ConfigSet — parameter-grid generation
    └── job_utils.py           # seed derivation, job/run metadata capture
```

## Stages and steps

A **stage** is a named simulation family (e.g. `simulation`, `monte_carlo`) with
its own parameter grid, sweep CSV, and `data/` output namespace.
A **step** is one computation phase within a stage.

The two built-in steps:

| Step | Rule | Output |
|---|---|---|
| `simulate` | `simulate` | `results.json` per `(path, instance)` |
| `aggregate` | `aggregate` | `results.csv` per stage |

Active stage and steps are selected in `workflow.yaml`:

```yaml
active:
  stage: simulation
  steps: [simulate, aggregate]
```

Valid step combinations (later steps depend on earlier ones):

- `[simulate]`
- `[simulate, aggregate]`

## Parameter grid

Each stage has a sweep script under `sweeps/<stage>/<exp>/sweep.py` that
defines a `param_grid` dict and calls `ConfigSet.generate_and_save` to
materialise a `summary.csv`. Nested dicts flatten to dot-separated CSV columns.

Supported value types in `param_grid`:

| Value | Behaviour |
|---|---|
| scalar | broadcast to every combination |
| `list` / `range` | Cartesian product axis |
| `lambda p: scalar` | derived lazily from already-resolved params |
| nested `dict` | keys appear as `parent.child` columns |

Generate or regenerate the CSV after any edit:

```bash
python sweeps/simulation/e0/sweep.py
```

The Snakefile expands targets over every `short_path` row × `{1..num_instances}`.

## Instances and deterministic seeds

Each parameter point (one row in `summary.csv`) is run `num_instances` times.
The `{instance}` wildcard is `1`, `2`, … `num_instances`. Every job derives its
RNG seed deterministically from `(path, instance)` via SHA-256:

- Same job → same result.
- Different instances of the same point → different random draws.
- `--rerun-incomplete` reproduces failed instances exactly.

The seed is stored in `results.json` and carried into `results.csv`.

## Launching

```bash
# Dry-run: show what would execute.
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4 -n

# Real run, 4 local workers.
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4

# Force-rerun everything (e.g. after changing a script).
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4 --forceall

# Rerun only incomplete / failed jobs.
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4 --rerun-incomplete
```

### Running jobs inside a container

Set `container` in `workflow.yaml` to a local Apptainer image (`.sif`) and
launch with `--use-singularity`:

```yaml
# workflow.yaml
container: containers/simulation-project-template-0.1.0.sif
```

```bash
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4 --use-singularity
```

The host environment provides `snakemake`; each job runs inside the container
via the workflow's global `container:` directive.

### Running on a cluster

See [`docs/hpc-workflow.md`](hpc-workflow.md) for the full cluster guide.
One-liner for reference:

```bash
uv run python -m snakemake --snakefile workflow/Snakefile \
  --executor slurm --jobs 500 \
  --default-resources slurm_account=<acct> slurm_partition=<part> \
  --use-singularity
```

Or use the lifecycle manager:

```bash
python hpc/lifecycle.py submit mycluster myproject/workflow
```

## Outputs

```
data/<stage>/<exp>/<short_path>/<instance>/
  ├── results.json      # params + seed + simulation output
  ├── numbers.json      # intermediate data written by simulate.py
  ├── simulate.log      # per-job stdout/stderr
  └── benchmark.txt     # Snakemake per-rule timing

results/<stage>/<exp>/
  └── results.csv       # flat per-run rows: params + seed + simulation output
```

## Snakefile internals

What happens at parse time (before any job runs):

1. `configfile` loaded → `ACTIVE_STAGE`, `ACTIVE_STEPS`, `EXP`, `CSV`.
2. `summary.csv` read into `_df` — **must exist** or Snakemake aborts immediately.
3. `params_by_path` dict built from CSV rows, keyed by `short_path`.
4. `instances = [1..num_instances]`.
5. `include:` rule files — `EXP`, `_df`, `params_by_path`, `instances`, `config`
   are module-level globals available in every `.smk` file. Do not shadow them.
6. `rule all` targets computed by `_all_targets()` from `ACTIVE_STEPS`.

## Adding a new experiment

Same stage, different parameter ranges — copy the sweep script:

```bash
cp sweeps/simulation/e0/sweep.py sweeps/simulation/e1/sweep.py
# edit e1/sweep.py: change experiment_name="e1", adjust param_grid
python sweeps/simulation/e1/sweep.py
```

Then point `workflow.yaml` at it:

```yaml
stages:
  simulation:
    exp: e1
    csv: sweeps/simulation/e1/summary.csv
```

Old `e0` outputs in `data/` and `results/` are untouched.

## Adding a new step

A per-`(path, instance)` computation that consumes data produced by earlier
steps. `docs/templates/new_step/` ships the skeleton. Steps:

1. Implement the computation logic in `src/<package>/` and test it.
2. Copy `docs/templates/new_step/rules/compute_foo.smk` →
   `workflow/rules/compute_foo.smk`; wire inputs/outputs to match your step.
3. Copy `docs/templates/new_step/scripts/compute_foo.py` →
   `workflow/scripts/compute_foo.py`; call your library function.
4. Apply `Snakefile.additions.py` and `workflow.yaml.additions` (one `include:`,
   one `_all_targets()` branch, one entry in `active.steps`).

## Adding a new stage

An independent simulation family with its own CSV and `data/` tree.
`docs/templates/new_stage/` ships a ready-made skeleton: sweep script, rule,
script, and the two `*.additions` files.

1. Copy `docs/templates/new_stage/` → `workflow/rules/simulate_bar.smk`,
   `workflow/scripts/simulate_bar.py`, `sweeps/bar/e0/sweep.py`.
2. Edit `param_grid` and replace `bar` with your stage name throughout.
3. Run the sweep script, then register the stage in `workflow.yaml`.
4. Apply `Snakefile.additions.py` (one `include:`, one stage branch in
   `_all_targets()`).
