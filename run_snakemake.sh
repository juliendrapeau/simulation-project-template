#!/bin/bash
#SBATCH --account=def-ko1
#SBATCH --partition=c-iq,c-aphex
#SBATCH --time=24:00:00
#SBATCH --job-name=snakemake
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=1G
#SBATCH --output=slurm-snakemake.out
#SBATCH --error=slurm-snakemake.err

# Load modules
module load StdEnv/2023 apptainer/1.3 python/3.13

# Install snakemake
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install snakemake snakemake-executor-plugin-slurm

snakemake --profile workflow/profiles/slurm/

echo 'My job is finished !'
