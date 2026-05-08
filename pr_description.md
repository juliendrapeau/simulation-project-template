# CI & tooling improvements (backport from sgcode/dev PRs #37 and #38)

## Summary

- **Bump action versions** — `setup-python@v5 → @v6`, `setup-uv@v7 → @v8.1.0` in `tests.yml`
- **Replace mypy with ty** — faster type checker; update pre-commit hook, CI step, and dev dependencies; fix type-ignore comments in workflow scripts and annotate `lifecycle.py` set to avoid `LiteralString` widening
- **Add `auto_tag` and `version_check` CI workflows** — version bump now happens inside the PR; CI tags automatically on merge, no more manual `git tag && git push`
- **Full-tree SIF cleanliness check** — `build_sif.py` now checks the entire working tree (not just `src/`) before building, preventing uncommitted config or lock changes from being baked into the image
- **Update versioning guide** — rewrite `docs/versioning.md` to document the new CI-driven tagging workflow

## Test plan

- [ ] `uv run ty check src/ tests/ workflow/ hpc/` passes locally
- [ ] `pre-commit run --all-files` passes
- [ ] `tests.yml` CI passes on the PR
- [ ] `version_check.yml` triggers on this PR (pyproject.toml changed) and passes
- [ ] After merge, `auto_tag.yml` creates tag `v0.2.0` automatically
