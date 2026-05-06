# Edits to apply in workflow/Snakefile when adding a stage called "bar".

# 1. include: the rule file (alongside the existing includes).
# include: "rules/simulate_bar.smk"
# include: "rules/aggregate_bar.smk"  # if bar has its own aggregate rule

# 2. Add a branch in _all_targets() (step name must match active.steps in workflow.yaml).
# if ACTIVE_STAGE == "bar" and "bar" in ACTIVE_STEPS:
#     targets += expand(
#         f"data/bar/{EXP}/{{path}}/{{instance}}/bar.json",
#         path=_df["short_path"], instance=instances,
#     )
# if ACTIVE_STAGE == "bar" and "aggregate" in ACTIVE_STEPS:
#     targets += [f"results/bar/{EXP}/results.csv"]
