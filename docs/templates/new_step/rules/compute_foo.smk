# Rename to compute_<name>.smk and replace "foo" throughout.
# Available from the Snakefile: ACTIVE_STAGE, EXP, params_by_path, instances, config.

rule compute_foo:
    input:
        results = f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/results.json",
    output:
        f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/foo.json"
    log:
        f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/foo.log"
    benchmark:
        f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/benchmark_foo.txt"
    params:
        my_param = config.get("my_param", 42),
    threads: 1
    resources:
        mem_mb = 2000
    script:
        "../scripts/compute_foo.py"
