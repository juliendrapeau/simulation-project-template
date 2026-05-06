rule simulate:
    output:
        results = f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/results.json",
    log:
        f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/simulate.log"
    benchmark:
        f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/benchmark.txt"
    params:
        cfg = lambda wc: params_by_path[wc.path]
    script:
        "../scripts/simulate.py"
