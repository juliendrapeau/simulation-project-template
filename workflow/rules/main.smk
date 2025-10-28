rule generate_numbers:
    input:
        config = f"{config["config_csv"]}",
    output:
        number_set = "data/{instance_name}/number_set.json"
    benchmark:
        "data/{instance_name}/benchmark_number_set.txt"
    threads:
        1
    # Resources are only taken in account on SLURM
    resources:
        runtime = 1,
        mem_gb = 2
    script:
        "../scripts/main_generate_numbers.py"

rule compute_mean:
    input:
        config = f"{config["config_csv"]}",
        number_set = "data/{instance_name}/number_set.json"
    output:
        mean = "data/{instance_name}/results.json"
    benchmark:
        "data/{instance_name}/benchmark_results.txt"
    script:
        "../scripts/main_compute_mean.py"
