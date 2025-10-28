# snakemake-template

## Getting started

First, install the dependencies of the project by running

```
uv sync
```

Then, generate the simulation configurations by running `configs/experiment-1/config.csv` with the appropriate parameters.

Finally, run the simulation using the following command

```
snakemake -c num_cores
```
where `num_cores` is the number of cores needed.