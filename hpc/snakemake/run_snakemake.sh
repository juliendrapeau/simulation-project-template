#!/bin/bash
set -euo pipefail

# Submitted via: python hpc/lifecycle.py submit <cluster> <remote_folder> [--mode profile|local]
# Resources (time, cpus, mem, account, ...) are passed by lifecycle.py from hpc/submit.yaml.

MODE="${1:-profile}"
shift 1 || true
EXTRA_FROM_SUBMIT="${*:-}"

ENV="venv"

# Compute Canada (Digital Research Alliance) modules — adjust for your cluster.
module load StdEnv/2023
module load apptainer/1.4.5
module load python/3.13
module load scipy-stack/2026a

source "$ENV"/bin/activate

# Bind the project root into every Apptainer container so that relative
# output paths (data/, results/) resolve to the writable host filesystem
# instead of the container's read-only image layer.
export APPTAINER_BIND="${PWD}:${PWD}"
export SINGULARITY_BIND="${PWD}:${PWD}" # compatibility alias for older installations

case "$MODE" in
profile)
  # Distribute jobs across the cluster via the SLURM profile.
  # shellcheck disable=SC2086
  snakemake --snakefile workflow/Snakefile --profile hpc $EXTRA_FROM_SUBMIT
  ;;
local)
  # Run all rules in this single job using all allocated CPUs.
  # shellcheck disable=SC2086
  snakemake --snakefile workflow/Snakefile -c "$SLURM_CPUS_PER_TASK" --software-deployment-method apptainer $EXTRA_FROM_SUBMIT
  ;;
*)
  echo "Unknown mode: $MODE  (expected: profile | local)" >&2
  exit 1
  ;;
esac

deactivate
echo "Job finished!"
