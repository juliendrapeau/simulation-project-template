# Versioning

This template uses [semantic versioning](https://semver.org) (`MAJOR.MINOR.PATCH`).
Every simulation must run against a tagged commit so results are reproducible
and traceable.

## Version policy

| Component | Meaning | Target branch | Example |
|-----------|---------|---------------|---------|
| **MAJOR** | Canonical research state merged into `main` | `main` | `0.1.0 → 1.0.0` |
| **MINOR** | New development milestone merged into `dev` | `dev` | `0.1.0 → 0.2.0` |
| **PATCH** | Small correction or hotfix | `main` or `dev` | `0.1.0 → 0.1.1` |

Every PR merge must result in a tag. That tag becomes the authoritative
reference used by simulations, SIF naming, `git checkout`, and
`metadata.json`.

**GitHub Releases are only created for major releases** (tags matching
`vX.0.0`). Minor and patch tags are still pushed for reproducibility but do
not trigger the release CI. This keeps the Releases page clean and meaningful
while still giving you a precise version reference on every merge.

## Workflow

Version bumps happen **inside the PR** — not after merge. CI handles tagging
automatically on merge.

### In the PR

1. Bump the version in `pyproject.toml`:

   ```bash
   uv version 0.X.0   # sets project.version and regenerates uv.lock
   ```

2. Commit both:

   ```bash
   git add pyproject.toml uv.lock && git commit -m "chore: bump version to 0.X.0"
   ```

3. Open/push the PR as normal.

CI (`version_check.yml`) will verify that:

- the version changed relative to the base branch, and
- the tag `v{version}` does not already exist on the remote.

### On merge

CI (`auto_tag.yml`) reads the version from `pyproject.toml` on the merge
commit and creates + pushes the tag automatically. No manual tagging needed.

For major releases (`vX.0.0` merged into `main`), the tag also triggers
`build_dist.yml`, which:

1. Verifies the tag matches `pyproject.toml`.
2. Builds sdist + wheel via `python -m build`.
3. Validates the artifacts with `twine check`.
4. Creates a GitHub Release with auto-generated notes and the dist files attached.

## Tying simulations to a version

Every simulation should run inside an Apptainer SIF built from the same tagged
commit. Build the SIF **after the tag is created** — never from an untagged or
dirty tree, because the Dockerfile copies `src/` from the working tree and any
uncommitted changes would be silently baked in under the wrong version name.

`build_sif.py` enforces this: it checks `git status --porcelain` and
refuses to build if there are any uncommitted changes in the tree.

```bash
# After CI has pushed the tag (wait for auto_tag.yml to complete)

# 1. Pull the tag locally
git fetch --tags

# 2. Build the SIF from the clean tagged tree
uv run hpc/containers/build_sif.py --platforms linux/amd64
# → containers/simulation-project-template-0.2.0.sif

# 3. Upload
python hpc/lifecycle.py upload <host> <remote_path>
```

Set `container` in `workflow.yaml` to lock the pipeline to that image:

```yaml
# workflow.yaml
container: containers/simulation-project-template-0.2.0.sif
```

Snakemake passes this to `--use-singularity`, so every job runs inside the
fixed image regardless of the host environment. The container path is recorded
in the `workflow.yaml` that gets uploaded to the cluster by `lifecycle.py`, and
it also ends up in `metadata.json` for every aggregate run — providing a full
chain of traceability from result files back to the exact codebase version.

### Keeping vs. rebuilding SIF files

You don't need to keep old SIF files around. Python dependencies are fully
pinned in `uv.lock`, so rebuilding from a tagged commit always produces the
same application layer. The OS layer may differ slightly (e.g. a security
patch in the base image), but that has no effect on simulation results.

### Reproducing an old simulation

```bash
# Check out the exact version
git checkout v0.1.0

# Or install that version from PyPI / GitHub Releases
uv add 'simulation-project-template==0.1.0'
```

If the original SIF is still available, use it directly in `workflow.yaml` so
the job environment is byte-for-byte identical to the original run.
