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

> [!NOTE]
> This template may lag behind my latest developments and is not guaranteed to work perfectly. Feel free to open an issue or discussion if you run into problems.

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
git clone git@github.com:juliendrapeau/snakemake-template.git
cd snakemake-template
uv sync --dev
```

### Optional tools

| Tool | Purpose |
|---|---|
| [Docker](https://docs.docker.com/engine/install/) | Build portable container images |
| [Apptainer](https://apptainer.org/docs/admin/main/installation.html) | Run containers on HPC |

## Quickstart

The typical workflow goes: run locally → containerize → submit to HPC.

### 1. Local run

First, validate the pipeline locally. Generate the parameter grid from your sweep script, then let Snakemake fan out the jobs:

```bash
python sweeps/simulation/e0/sweep.py   # generate the parameter-grid CSV
uv run python -m snakemake --cores 4   # run simulate → aggregate
```

Results land in `results/simulation/e0/results.csv`.
See [`docs/snakemake-workflow.md`](docs/snakemake-workflow.md) for a full guide on stages, steps, and parameter grids.

### 2. Build the container

Package the environment into an [Apptainer](https://apptainer.org/) SIF image to pin dependencies and make runs portable. This step is required before submitting to HPC, and is good practice for local reproducibility too:

```bash
uv run hpc/containers/build_sif.py --platforms linux/amd64
```

Point `workflow.yaml` at the generated image and re-run with `--use-singularity` to confirm everything works inside the container:

```yaml
# workflow.yaml
container: containers/simulation-project-template-0.1.0.sif
```

```bash
uv run python -m snakemake --cores 4 --use-singularity
```

### 3. Run on a SLURM cluster

`hpc/lifecycle.py` manages the full HPC lifecycle from your local machine — it uploads the project, bootstraps a venv on the cluster, submits the Snakemake job via SLURM, and pulls results back.
See [`docs/hpc-workflow.md`](docs/hpc-workflow.md) for the full guide.

```bash
# 1. Configure your cluster and submission settings.
cp hpc/config_example.yaml hpc/config.yaml
cp hpc/submit_example.yaml hpc/submit.yaml

# 2. Build the SIF image (if not done already) and upload the project.
uv run hpc/containers/build_sif.py
python hpc/lifecycle.py upload mycluster myproject

# 3. One-time venv bootstrap on the cluster.
python hpc/lifecycle.py setup mycluster myproject

# 4. Submit, then monitor progress.
python hpc/lifecycle.py submit mycluster myproject
python hpc/lifecycle.py status mycluster
python hpc/lifecycle.py check  mycluster myproject

# 5. Pull results back when done.
python hpc/lifecycle.py download mycluster myproject --paths results
```

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

## Releases

The package uses semantic versioning — major for PRs into `main`, minor for PRs into
`dev`, patch for hotfixes. To cut a release, bump `pyproject.toml`, commit,
and push a `vX.Y.Z` tag. CI builds the sdist + wheel and creates a GitHub
Release automatically.

Every simulation should run inside a SIF built from the tagged commit so
results stay traceable:

```bash
uv run hpc/containers/build_sif.py          # → containers/sgcode-X.Y.Z.sif
# set container: containers/sgcode-X.Y.Z.sif in workflow.yml
```

See [`docs/versioning.md`](docs/versioning.md) for the full procedure.

## Adapting this template

1. **Rename the package.** Change `simulation-project-template` / `simulation_project_template` everywhere (pyproject.toml, license, src/, Dockerfile, workflow/tools/job_utils.py, etc.).
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
