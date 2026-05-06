# Edits to apply in workflow/Snakefile when adding a step called "foo".

# 1. include: the rule file (alongside existing includes).
# include: "rules/compute_foo.smk"

# 2. Add a branch in _all_targets().
# if "foo" in ACTIVE_STEPS:
#     targets += expand(
#         f"data/{ACTIVE_STAGE}/{EXP}/{{path}}/{{instance}}/foo.json",
#         path=_df["short_path"], instance=instances,
#     )

# 3. (Optional) to roll foo.json fields into aggregate:
#    - add a "foo" input list in rules/aggregate.smk
#    - read and flatten foo fields in scripts/aggregate.py
