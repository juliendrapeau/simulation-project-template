# snakemake-template

## Getting started

First, install the dependencies of the project by running

```
uv sync
```

Then, generate the simulation configurations by choosing the appropriate parameters in `configs/experiment-1/config.py` and running

```
python configs/experiment-1/config.py
```

Finally, run the simulation using the following command

```
snakemake -c num_cores
```
where `num_cores` is the number of cores needed.