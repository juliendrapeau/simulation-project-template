# snakemake-template

This repository is an example of a reproducible simulation workflow using [Snakemake](https://snakemake.readthedocs.io/en/stable/). For an even more reproducible pipeline, it is recommended to use [Docker](https://www.docker.com/) and [Apptainer](https://apptainer.org/).

## Installation

To use this template, the package manager `uv` is strongly recommended. Installation can be done following [uv's documentation](https://docs.astral.sh/uv/getting-started/installation/). It is also recommended to use `docker`, which can be installed following [docker's documentation](https://docs.docker.com/engine/install/). Unfortunately, `snakemake` doesn't directly support `docker`, so it is recommended to also install `apptainer` (mostly for testing purposes) following [apptainer's documentation](https://apptainer.org/docs/admin/main/installation.html).

## Getting started

### Local

First, install the dependencies of the project listed in `pyproject.toml`. It is recommended to use `uv`. The dependencies can then be installed simply by running

```bash
uv sync
```

Then, generate the simulation configurations by choosing the appropriate parameters in `configs/experiment-1/config.py` and running

```bash
python configs/experiment-1/config.py
```

Finally, run the simulation using the following command

```bash
snakemake -c num_cores
```
where `num_cores` is the number of cores needed.

### Local + Docker/Apptainer

First, install `snakemake` into a local virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install snakemake
```

Then, build the docker image of the project with

```bash
chmod u+x run_docker.sh
./run_docker.sh
```

The docker image must be converted to an apptainer image with

```bash
docker save -o docker_image.tar $(cat .docker_image_id)
apptainer build apptainer_image.sif docker-archive://docker_image.tar
```

Then, generate the simulation configurations by choosing the appropriate parameters in `configs/experiment-1/config.py` and running

```bash
python configs/experiment-1/config.py
```

Finally, run the simulation using the following command

```bash
snakemake -sdm apptainer -c num_cores
```
where `num_cores` is the number of cores needed

### SLURM + Docker/Apptainer

TBA.



