# Rename to simulate_<bar>.smk and replace "bar" throughout.
# Available from the Snakefile: ACTIVE_STAGE, EXP, params_by_path, instances, config.

rule simulate_bar:
    output:
        result = f"data/bar/{EXP}/{{path}}/{{instance}}/bar.json",
    log:
        f"data/bar/{EXP}/{{path}}/{{instance}}/bar.log"
    benchmark:
        f"data/bar/{EXP}/{{path}}/{{instance}}/benchmark_bar.txt"
    params:
        cfg           = lambda wc: params_by_path[wc.path],
        my_stage_param = config.get("my_stage_param", 1),
    threads: 1
    resources:
        mem_mb = 2000
    script:
        "../scripts/simulate_bar.py"
