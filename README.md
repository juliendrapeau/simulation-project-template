# simulation-project-template

A template for reproducible parameter-sweep simulation projects in Python.
Combines [uv](https://docs.astral.sh/uv/) for package management,
[Snakemake](https://snakemake.readthedocs.io/) for workflow orchestration,
[Docker](https://www.docker.com/) + [Apptainer](https://apptainer.org/) for
portable execution, and `hpc/lifecycle.py` for one-command SLURM cluster runs.

> [!WARNING]
> **HPC users — be a responsible cluster citizen.**
> Submitting large parameter sweeps without testing first can flood the scheduler with hundreds or thousands of jobs, waste allocation hours on misconfigured runs, and get your account flagged or suspended by the cluster administrators.
> Before submitting at scale, always:
>
> 1. Validate locally with a small config or `snakemake --dryrun`.
> 2. Submit a single test job (`--test` flag) and confirm it completes correctly.
> 3. Check current queue pressure with `python hpc/lifecycle.py status <cluster>` before submitting.
> 4. Prefer the `profile` mode so Snakemake caps concurrency via `slurm_profile.yaml` rather than flooding the queue all at once.

## Layout

```
simulation-project-template/
├── src/                        # installable Python package
├── tests/                      # pytest suite
├── workflow/                   # Snakemake pipeline
│   ├── Snakefile
│   ├── rules/                  # *.smk rule definitions
│   ├── scripts/                # per-rule Python jobs
│   └── tools/                  # shared helpers (sweeper, job metadata)
├── sweeps/                     # parameter-grid scripts + generated CSVs
├── configs/                    # static per-run JSON configs (optional)
├── data/                       # generated outputs  (gitignored)
├── results/                    # aggregated results (gitignored)
├── containers/                 # Apptainer SIF images (gitignored)
├── hpc/                        # cluster lifecycle manager
├── docs/                       # guides and extension templates
├── notebooks/                  # exploratory notebooks
├── figures/                    # publication figures
├── scratch/                    # temporary scratch files (gitignored)
├── Dockerfile
└── workflow.yaml               # active stage, steps, CSV path, num_instances
```

## Installation

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone <your-repo>
cd <your-repo>
uv sync --dev
```

### Optional tools

| Tool | Purpose |
|---|---|
| [Docker](https://docs.docker.com/engine/install/) | Build portable container images |
| [Apptainer](https://apptainer.org/docs/admin/main/installation.html) | Run containers on HPC |

## Quickstart

```bash
uv sync --dev                            # install package + dev dependencies
python sweeps/simulation/e0/sweep.py    # materialise the parameter-grid CSV
uv run snakemake --cores 4
```

That runs the full `simulate → aggregate` pipeline across every parameter
combination × `num_instances` replications, producing `results/simulation/e0/results.csv`.

### Running inside a container

Build the Apptainer image, then enable it in `workflow.yaml`:

```bash
uv run hpc/containers/build_sif.py --platforms linux/amd64
```

```yaml
# workflow.yaml
container: containers/simulation-project-template-0.1.0.sif
```

```bash
uv run python -m snakemake --snakefile workflow/Snakefile --cores 4 --use-singularity
```

### Running on a SLURM cluster

```bash
# 1. Copy config templates and fill in your cluster details.
cp hpc/config_example.yaml  hpc/config.yaml
cp hpc/submit_example.yaml  hpc/submit.yaml

# 2. Build the SIF image and upload the project.
uv run hpc/containers/build_sif.py
python hpc/lifecycle.py upload mycluster myproject/workflow

# 3. One-time venv bootstrap on the cluster.
python hpc/lifecycle.py setup mycluster myproject/workflow

# 4. Submit and monitor.
python hpc/lifecycle.py submit mycluster myproject/workflow
python hpc/lifecycle.py status mycluster
python hpc/lifecycle.py check  mycluster myproject/workflow

# 5. Pull results back.
python hpc/lifecycle.py download mycluster myproject/workflow --paths results
```

See [`docs/hpc-workflow.md`](docs/hpc-workflow.md) for the full HPC guide.

## CLI

The package exposes a `spt` command:

```bash
spt generate 100 -o numbers.json --seed 42   # generate random numbers
spt mean numbers.json                         # compute mean
```

## Tests

```bash
uv run python -m pytest tests/
```

## Adapting this template

1. **Rename the package.** Change `simulation-project-template` / `simulation_project_template` everywhere (pyproject.toml, src/, Dockerfile, workflow/tools/job_utils.py).
2. **Replace the simulation logic.** Rewrite `src/simulation_project_template/` with your model; update `workflow/scripts/simulate.py` to call it.
3. **Define your parameter grid.** Edit `sweeps/simulation/e0/sweep.py`; add new experiments by copying to `sweeps/simulation/e1/sweep.py`, etc.
4. **Add steps or stages.** Follow the templates in [`docs/templates/`](docs/templates/).

## Documentation

| Guide | Contents |
|---|---|
| [`docs/snakemake-workflow.md`](docs/snakemake-workflow.md) | Pipeline layout, stages, steps, parameter grid, launching |
| [`docs/hpc-workflow.md`](docs/hpc-workflow.md) | Cluster upload, setup, submit, download |
| [`docs/cli-workflow.md`](docs/cli-workflow.md) | CLI usage and extension |
| [`docs/templates/`](docs/templates/) | Skeletons for new stages and steps |
