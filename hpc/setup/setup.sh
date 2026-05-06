#!/bin/bash
set -euo pipefail

# One-time cluster environment setup.
# Run from the project root after the first upload:
#   python hpc/lifecycle.py upload <cluster> <remote_folder>
#   python hpc/lifecycle.py setup  <cluster> <remote_folder>

ENV="venv"

# Compute Canada (Digital Research Alliance) modules — adjust for your cluster.
module load StdEnv/2023
module load python/3.13
module load scipy-stack/2026a

echo "[INFO] Creating virtual environment in $ENV/"
python -m venv "$ENV"
source "$ENV/bin/activate"

pip install --upgrade pip

# Install pinned Snakemake + executor plugin from the lockfile.
# The project package itself runs inside the Apptainer container and does not
# need to be installed here.
pip install -r hpc/setup/requirements.txt

deactivate
