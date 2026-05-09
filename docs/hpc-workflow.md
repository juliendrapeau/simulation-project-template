# HPC Workflow

Running the Snakemake pipeline on a SLURM cluster via Apptainer/Singularity.
Per-simulation knobs live in gitignored files (`hpc/config.yaml`,
`hpc/submit.yaml`), so the tracked code stays stable across experiments.

## Layout

```
hpc/                              ← tracked
├── lifecycle.py                  # CLI: upload / setup / submit / check / download / status
├── config_example.yaml           # Snakemake SLURM profile template
├── submit_example.yaml           # sbatch launcher-job resources template
├── setup/
│   ├── setup.sh                  # one-time cluster venv bootstrap
│   └── requirements.txt          # pinned Snakemake + executor-plugin deps
├── snakemake/
│   └── run_snakemake.sh          # cluster job entrypoint (called by sbatch)
└── containers/
    ├── build_sif.py              # Docker → OCI archive → Apptainer SIF
    └── build_docker.sh           # local Docker build + run (dev / testing)

hpc/config.yaml                   ← gitignored, copy from config_example.yaml
hpc/submit.yaml                   ← gitignored, copy from submit_example.yaml
```

## Tracked vs. per-simulation — what goes where

| Concern | File | Tracked? |
|---|---|---|
| HPC orchestration code | `hpc/*.py`, `hpc/**/*.sh` | yes |
| Per-rule SLURM defaults (memory, cpus, runtime) | `hpc/config_example.yaml` | yes (example) |
| Active Snakemake cluster profile | `hpc/config.yaml` | **no** |
| Launcher job resources (wall time, mail) | `hpc/submit_example.yaml` | yes (example) |
| Launcher job resources (your values) | `hpc/submit.yaml` | **no** |
| Experiment parameters (stage, CSV, instances) | `workflow.yaml` | yes |
| SIF / OCI image artifacts | `containers/*.sif`, `*.tar.gz` | **no** |

To change resources or which experiment runs, only touch the gitignored files —
the workflow code itself never needs editing per simulation.

## First-time setup

From the project root:

```bash
# 1. Create config files from the example templates.
cp hpc/config_example.yaml  hpc/config.yaml    # adjust account, partition, resources
cp hpc/submit_example.yaml  hpc/submit.yaml    # adjust wall time, mail, account

# 2. (Optional) Build the Apptainer SIF image locally.
uv run hpc/containers/build_sif.py --platforms linux/amd64

# 3. Generate the parameter-grid CSV.
python sweeps/simulation/e0/sweep.py

# 4. Upload workflow files (and the SIF if built) to the cluster.
python hpc/lifecycle.py upload mycluster myproject/workflow

# 5. One-time on the cluster: create the venv with Snakemake.
python hpc/lifecycle.py setup mycluster myproject/workflow

# If your site requires a compute allocation for pip installs:
python hpc/lifecycle.py setup mycluster myproject/workflow --salloc
```

`mycluster` is an SSH host alias (defined in `~/.ssh/config`).
`myproject/workflow` is the path under the cluster root where the project lands.

### Cluster roots

`hpc/lifecycle.py` has a `CLUSTER_ROOTS` dict you can pre-populate with your
cluster's scratch or project path:

```python
# hpc/lifecycle.py
CLUSTER_ROOTS: dict[str, Path] = {
    "mycluster": Path("/scratch/myuser"),
}
```

Or pass `--remote-root /path/to/root` on every command.

## Running an experiment

```bash
# Submit (profile mode: one SLURM job per rule instance -> good for long jobs).
python hpc/lifecycle.py submit mycluster myproject/workflow

# Submit (local mode: single job using all allocated CPUs -> good for quick jobs)
python hpc/lifecycle.py submit mycluster myproject/workflow --mode local

# Plan only — show what Snakemake would run without submitting.
python hpc/lifecycle.py submit mycluster myproject/workflow --snakemake-dry-run

# Monitor.
python hpc/lifecycle.py status mycluster            # squeue
python hpc/lifecycle.py status mycluster --full     # sacct history
python hpc/lifecycle.py check  mycluster myproject/workflow  # snakemake --summary

# Pull results back.
python hpc/lifecycle.py download mycluster myproject/workflow --paths results
python hpc/lifecycle.py download mycluster myproject/workflow --include-data   # + data/
```

## How the configs flow

```
local: hpc/submit.yaml       ──┐
                               │  rsync via lifecycle.py upload
local: workflow.yaml           ┤
local: sweeps/*/e*/summary.csv ┘
                               ▼
cluster: <remote_folder>/      (same paths, read by lifecycle.py submit + run_snakemake.sh)
                               │
                               ▼
   sbatch <submit.yaml flags> hpc/snakemake/run_snakemake.sh <mode>
                               │
                               ▼
   snakemake --snakefile workflow/Snakefile --profile hpc ...
```

`hpc/submit.yaml` controls the **launcher** job that owns the Snakemake process.
`hpc/config.yaml` controls each **per-rule** job dispatched by Snakemake.

## Building containers

### Docker (local testing)

```bash
# Build + run with auto-mounted ./configs and ./results.
./hpc/containers/build_docker.sh

# Pass CLI args directly.
./hpc/containers/build_docker.sh generate 100 -o /results/out.json
```

### Apptainer SIF (cluster)

```bash
# linux/amd64 SIF (default).
uv run hpc/containers/build_sif.py

# Multi-platform.
uv run hpc/containers/build_sif.py --platforms linux/amd64 linux/arm64
```

The SIF lands in `containers/`. Point `workflow.yaml` at it before uploading:

```yaml
container: containers/simulation-project-template-0.1.0.sif
```

## Updating pinned Snakemake deps

`hpc/setup/requirements.txt` lists the Snakemake packages installed on the
cluster venv. Update it when bumping Snakemake:

```bash
# Pin only the packages needed on the cluster (no project package itself).
uv export --no-hashes --no-emit-project \
  --only-package snakemake \
  --only-package snakemake-executor-plugin-slurm \
  --only-package importlib-metadata \
  > hpc/setup/requirements.txt
```
