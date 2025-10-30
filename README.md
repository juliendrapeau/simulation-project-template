# snakemake-template

This repository is an example of a reproducible simulation workflow using [Snakemake](https://snakemake.readthedocs.io/en/stable/). For maximum reproducibility, it is recommended to use [Docker](https://www.docker.com/) and [Apptainer](https://apptainer.org/).

## Installation

To use this template, the package manager `uv` is strongly recommended. Installation can be done following [uv's documentation](https://docs.astral.sh/uv/getting-started/installation/). It is also recommended to use `docker`, which can be installed following [Docker's documentation](https://docs.docker.com/engine/install/). `snakemake` cannot directly run Docker images, so installing `apptainer` (primarily for testing and cluster use) is recommended. Follow [Apptainer's installation guide](https://apptainer.org/docs/admin/main/installation.html).

## Getting started

The recommended workflow for a simple yet fully reproducible pipeline is as follows. First, build your package and test your simulations locally. To do so, use the package manager `uv` to manage dependencies. When ready, use `snakemake` to manage simulations. For more information, see [Local](#local). Once everything works as expected, build your package as a container using `docker` and `apptainer` to ensure it can run anywhere. See [Local + Docker/Apptainer](#local--dockerapptainer) for details. Finally, run everything on the cluster — a straightforward process once containers are ready. See [SLURM + Docker/Apptainer](#slurm--dockerapptainer) for guidance.

---

### Local

First, install the project dependencies listed in `pyproject.toml`. It is recommended to use `uv`. Install dependencies with:

```bash
uv sync
````

Next, generate the simulation configurations by editing the appropriate parameters in `configs/experiment-1/config.py` and running:

```bash
python configs/experiment-1/config.py
```

Finally, run the simulation using:

```bash
snakemake -c num_cores
```

where `num_cores` is the number of CPU cores to use.

---

### Local + Docker/Apptainer

First, install `snakemake` in a local virtual environment (skip this step if you already installed `snakemake` with `uv` before):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install snakemake
```

Then, build the Docker image of the project:

```bash
chmod u+x run_docker.sh
./run_docker.sh
```

Convert the Docker image to an Apptainer image:

```bash
docker save -o docker_image.tar $(cat .docker_image_id)
apptainer build apptainer_image.sif docker-archive://docker_image.tar
```

Generate simulation configurations by editing `configs/experiment-1/config.py` and running:

```bash
python configs/experiment-1/config.py
```

Finally, run the simulation using:

```bash
snakemake --sdm apptainer -c num_cores
```

where `num_cores` is the number of CPU cores to use.

---

### SLURM + Docker/Apptainer

First, install `snakemake` in a local virtual environment on the SLURM cluster:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install snakemake snakemake-executor-plugin-slurm
```

Use the Apptainer image of your project. There are two approaches:

1. Locally build the Docker image, convert it to Apptainer, and upload it to the cluster (recommended).
2. Build and upload the Docker image to Docker Hub, download it on the cluster, and convert it to Apptainer.

Generate simulation configurations by editing `configs/experiment-1/config.py` and running:

```bash
python configs/experiment-1/config.py
```

Adjust SLURM parameters in `workflow/profiles/slurm`. Run the simulation with:

```bash
snakemake --profile workflow/profiles/slurm/
```

Logs can be found in `.snakemake/slurm_logs`.
