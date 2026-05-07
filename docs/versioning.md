# Versioning

This template uses [semantic versioning](https://semver.org) (`MAJOR.MINOR.PATCH`).
Every simulation must run against a tagged commit so results are reproducible
and traceable.

## Version policy

| Component | When to bump | Example |
|-----------|-------------|---------|
| **MAJOR** | PR merged into `main` | `0.1.0 → 1.0.0` |
| **MINOR** | PR merged into `dev` | `0.1.0 → 0.2.0` |
| **PATCH** | Hotfix or small correction | `0.1.0 → 0.1.1` |

**Tag every PR merge** — that tag is the anchor for simulations (SIF name,
`git checkout`, `metadata.json`). Whether or not a GitHub Release is published
is a separate question.

**GitHub Releases are only created for major releases** (tags matching
`vX.0.0`). Minor and patch tags are pushed but do not trigger the release CI.
This keeps the Releases page clean and meaningful while still giving you a
precise version reference on every merge.

## Tagging a PR merge

All changes to `pyproject.toml` and the lockfile must be committed **before**
pushing the tag. CI verifies that the tag name matches `pyproject.toml`
`project.version` and fails fast if they disagree.

```bash
# 1. Bump the version in pyproject.toml
$EDITOR pyproject.toml

# 2. Regenerate the lockfile
uv lock

# 3. Commit and tag
git add pyproject.toml uv.lock
git commit -m "chore: bump version to 0.2.0"
git tag v0.2.0
git push origin HEAD v0.2.0
```

For major releases (`vX.0.0` only), pushing the tag also triggers
`.github/workflows/build_dist.yml`, which:

1. Verifies the tag matches `pyproject.toml`.
2. Builds sdist + wheel via `python -m build`.
3. Validates the artifacts with `twine check`.
4. Creates a GitHub Release with auto-generated notes and the dist files attached.

## Tying simulations to a version

Every simulation should run inside an Apptainer SIF built from the same tagged
commit. Build the SIF **after tagging, before uploading** — never during upload,
because the Dockerfile copies `src/` from the working tree and any uncommitted
changes would be silently baked in under the wrong version name.

`build_sif.py` enforces this: it checks `git status --porcelain src/` and
refuses to build if there are uncommitted changes.

```bash
# 1. Tag the commit (see above)
git tag v0.2.0 && git push origin HEAD v0.2.0

# 2. Build the SIF from the clean tree
uv run hpc/containers/build_sif.py --platforms linux/amd64
# → containers/spt-0.2.0.sif

# 3. Upload
python hpc/lifecycle.py upload <host> <remote_path>
```

Set `container` in `workflow.yml` to lock the pipeline to that image:

```yaml
# workflow.yml
container: containers/spt-0.2.0.sif
```

Snakemake passes this to `--use-singularity`, so every job runs inside the
fixed image regardless of the host environment. The container path is recorded
in the `workflow.yml` that gets uploaded to the cluster by `lifecycle.py`, and
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
uv add 'spt==0.1.0'
```

If the original SIF is still available, use it directly in `workflow.yml` so
the job environment is byte-for-byte identical to the original run.
