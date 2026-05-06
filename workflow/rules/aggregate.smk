rule aggregate:
    input:
        results = expand(
            f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/results.json",
            path=_df["short_path"],
            instance=instances,
        )
    output:
        results = f"results/{ACTIVE_STAGE}/{EXP}/results.csv",
    log:
        f"results/{ACTIVE_STAGE}/{EXP}/aggregate.log"
    script:
        "../scripts/aggregate.py"
