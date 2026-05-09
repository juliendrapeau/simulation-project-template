"""HPC lifecycle manager for cluster upload/setup/submit/check/download/status.

Usage:
  python hpc/lifecycle.py upload   <cluster> <remote_folder> [--dry-run] [--build-sif]
  python hpc/lifecycle.py setup    <cluster> <remote_folder> [--salloc] [--dry-run]
  python hpc/lifecycle.py submit   <cluster> <remote_folder> [--mode profile|local] [--dry-run]
  python hpc/lifecycle.py download <cluster> <remote_folder> [--paths results] [--dry-run]
  python hpc/lifecycle.py check    <cluster> <remote_folder>
  python hpc/lifecycle.py status   <cluster>

Config files (gitignored — copy from *.example templates):
  hpc/submit.yaml           SLURM resources for the launcher job
  hpc/config.yaml           Snakemake cluster profile (--profile hpc)
  workflow.yaml             experiment parameters
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import yaml

# Map SSH host aliases to their scratch/project root paths.
# Customize for your cluster(s).
CLUSTER_ROOTS: dict[str, Path] = {
    # "mycluster": Path("/scratch/myuser"),
}
DEFAULT_CLUSTER_ROOT = Path("~/projects/def-ko1").expanduser() / Path.home().name

# Paths uploaded to the cluster. workflow.yaml extra references (csv, container)
# are appended automatically if they exist locally.
CORE_UPLOAD_PATHS = (
    "README.md",
    "pyproject.toml",
    "hpc/",
    "workflow/",
    "workflow.yaml",
)

_PROJECT_ROOT_DEFAULT = str(Path(__file__).resolve().parent.parent)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def get_cluster_root(cluster: str, override: str | None = None) -> Path:
    if override:
        return Path(override)
    return CLUSTER_ROOTS.get(cluster, DEFAULT_CLUSTER_ROOT)


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=cwd)


def capture_cmd(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def _confirm_existing_download_target(local_target: Path) -> bool:
    if not local_target.exists():
        return True
    if local_target.is_dir() and not any(local_target.iterdir()):
        return True
    while True:
        answer = input(
            f"[WARN] Local path already contains files: {local_target}\n"
            "       Continue download and overwrite matching files? [y/N]: "
        ).strip()
        if not answer:
            return False
        normalized = answer.lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"n", "no"}:
            return False
        print("[WARN] Please answer 'y' or 'n'.")


def _confirm_existing_upload_target(cluster: str, remote_target: Path) -> bool:
    remote_q = shlex.quote(str(remote_target))
    remote_cmd = (
        f"if [ ! -e {remote_q} ]; then echo missing; "
        f'elif [ -d {remote_q} ] && [ -z "$(ls -A {remote_q})" ]; then echo empty_dir; '
        "else echo populated; fi"
    )
    state = capture_cmd(["ssh", cluster, remote_cmd]).strip()
    if state in {"missing", "empty_dir"}:
        return True
    while True:
        answer = input(
            f"[WARN] Remote path already contains files: {cluster}:{remote_target}\n"
            "       Continue upload and overwrite matching files? [y/N]: "
        ).strip()
        if not answer:
            return False
        normalized = answer.lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"n", "no"}:
            return False
        print("[WARN] Please answer 'y' or 'n'.")


def _git_commit(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}.")
    return data


def _parse_workflow_refs(config_path: Path) -> set[str]:
    """Extract csv: and container: values referenced in workflow.yaml."""
    refs: set[str] = set()
    for raw in config_path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("csv:") or line.startswith("container:"):
            value = line.split(":", 1)[1].strip().strip("'\"")
            if value and value.lower() != "null":
                refs.add(value.rstrip("/"))
    return refs


def collect_upload_paths(project_root: Path) -> list[str]:
    required: set[str] = {p.rstrip("/") for p in CORE_UPLOAD_PATHS}
    cfg = project_root / "workflow.yaml"
    if cfg.exists():
        required.update(_parse_workflow_refs(cfg))
    existing = []
    for rel in sorted(required):
        if (project_root / rel).exists():
            existing.append(rel)
        else:
            print(f"[WARN] Skipping missing path: {rel}")
    return existing


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """HPC lifecycle manager: upload, setup, submit, download."""


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.argument("remote_folder")
@click.option(
    "--project-root",
    default=_PROJECT_ROOT_DEFAULT,
    help="Local project root (default: repository root).",
)
@click.option("--remote-root", default=None, help="Override the cluster root path.")
@click.option("--dry-run", is_flag=True)
@click.option("--build-sif", is_flag=True, help="Build SIF image before uploading.")
@click.option("--sif-platform", default="linux/amd64")
@click.option("--sif-suffix", default="")
def upload(
    cluster: str,
    remote_folder: str,
    project_root: str,
    remote_root: str | None,
    dry_run: bool,
    build_sif: bool,
    sif_platform: str,
    sif_suffix: str,
) -> None:
    """Upload required workflow files to the cluster."""
    root_path = Path(project_root).resolve()
    if not root_path.exists():
        raise click.ClickException(f"Project root not found: {root_path}")

    if build_sif:
        sif_cmd = [
            "uv",
            "run",
            "hpc/containers/build_sif.py",
            "--platforms",
            sif_platform,
        ]
        if sif_suffix:
            sif_cmd.extend(["--suffix", sif_suffix])
        print(f"[INFO] Building SIF: {' '.join(sif_cmd)}")
        run_cmd(sif_cmd, cwd=root_path)

    remote_target = get_cluster_root(cluster, remote_root) / remote_folder

    if not _confirm_existing_upload_target(cluster, remote_target):
        print("[INFO] Upload cancelled.")
        return

    paths = collect_upload_paths(root_path)
    if not paths:
        raise click.ClickException("No files found to upload.")

    rsync_cmd = ["rsync", "-az", "--progress", "--relative", "--exclude=__pycache__"]
    if dry_run:
        rsync_cmd.append("--dry-run")
    rsync_cmd.extend([f"./{p}" for p in paths])
    rsync_cmd.append(f"{cluster}:{remote_target}/")

    print("[INFO] Uploading:")
    for p in paths:
        print(f"  - {p}")
    run_cmd(rsync_cmd, cwd=root_path)
    print(
        "[DONE] Upload complete.\n"
        f"  Next: python hpc/lifecycle.py submit {cluster} {remote_folder}"
    )


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.argument("remote_folder")
@click.option(
    "--mode",
    type=click.Choice(["profile", "local"]),
    default="profile",
    help="'profile' dispatches jobs via hpc/config.yaml; 'local' runs with -c $SLURM_CPUS_PER_TASK.",
)
@click.option("--project-root", default=_PROJECT_ROOT_DEFAULT)
@click.option("--remote-root", default=None)
@click.option(
    "--dry-run", is_flag=True, help="Print the sbatch command without submitting."
)
@click.option(
    "--snakemake-dry-run",
    is_flag=True,
    help="Pass --dryrun to Snakemake: plan only, no jobs executed.",
)
@click.option(
    "--test",
    is_flag=True,
    help="Run with test_mode=true and num_instances=1 to validate the pipeline.",
)
def submit(
    cluster: str,
    remote_folder: str,
    mode: str,
    project_root: str,
    remote_root: str | None,
    dry_run: bool,
    snakemake_dry_run: bool,
    test: bool,
) -> None:
    """SSH to the cluster and submit a Snakemake SLURM job."""
    root_path = Path(project_root).resolve()
    submit_cfg = root_path / "hpc" / "submit.yaml"
    if not submit_cfg.exists():
        raise click.ClickException(
            f"Submit config not found: {submit_cfg}\n"
            "  Create it from the template: cp hpc/submit_example.yaml hpc/submit.yaml"
        )

    data = load_yaml(submit_cfg)
    resources: dict[str, Any] = data.get("resources", {})
    extra: list[str] = data.get("extra_sbatch_args", [])

    sbatch_flags = [
        f"--{k.replace('_', '-')}={v}" for k, v in resources.items() if v is not None
    ] + extra

    remote_target = get_cluster_root(cluster, remote_root) / remote_folder

    extra_smk: list[str] = []
    if snakemake_dry_run:
        extra_smk.append("--dryrun")
    if test:
        extra_smk.append("--config test_mode=true num_instances=1")

    script_cmd = "hpc/snakemake/run_snakemake.sh " + mode
    if extra_smk:
        script_cmd += " " + " ".join(extra_smk)
    sbatch_line = "sbatch " + " ".join(sbatch_flags) + " " + script_cmd
    remote_cmd = f"cd {shlex.quote(str(remote_target))} && {sbatch_line}"

    print(f"[INFO] Submitting [{mode}] to {cluster}:{remote_target}")
    print(f"       {sbatch_line}")

    if dry_run:
        return

    run_cmd(["ssh", cluster, remote_cmd])
    print("[DONE] Job submitted.")


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.argument("remote_folder")
@click.option("--project-root", default=_PROJECT_ROOT_DEFAULT)
@click.option("--remote-root", default=None)
@click.option(
    "--paths",
    multiple=True,
    default=["results"],
    help="Relative paths to download (default: results).",
)
@click.option(
    "--include-data", is_flag=True, help="Also download data/ in addition to --paths."
)
@click.option("--dry-run", is_flag=True)
def download(
    cluster: str,
    remote_folder: str,
    project_root: str,
    remote_root: str | None,
    paths: tuple[str, ...],
    include_data: bool,
    dry_run: bool,
) -> None:
    """Download workflow outputs from the cluster."""
    root_path = Path(project_root).resolve()
    if not root_path.exists():
        raise click.ClickException(f"Project root not found: {root_path}")

    remote_target = get_cluster_root(cluster, remote_root) / remote_folder

    selected = {p.strip().strip("/") for p in paths if p.strip()}
    if include_data:
        selected.add("data")
    if not selected:
        raise click.ClickException("No remote paths selected.")

    print("[INFO] Downloading:")
    for rel in sorted(selected):
        local_target = root_path / rel
        if not _confirm_existing_download_target(local_target):
            print(f"[INFO] Skipping existing local path: {local_target}")
            continue
        rsync_cmd = ["rsync", "-az", "--progress", "--exclude=__pycache__"]
        if dry_run:
            rsync_cmd.append("--dry-run")
        local_target.mkdir(parents=True, exist_ok=True)
        rsync_cmd.extend([f"{cluster}:{remote_target}/{rel}/", f"{local_target}/"])
        run_cmd(rsync_cmd, cwd=root_path)

    print(f"[DONE] Downloaded into: {root_path}")

    if not dry_run:
        _write_manifest(
            root_path,
            cluster,
            remote_folder,
            get_cluster_root(cluster, remote_root),
            sorted(selected),
        )


def _write_manifest(
    project_root: Path,
    cluster: str,
    remote_folder: str,
    root: Path,
    paths: list[str],
) -> None:
    manifest = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "cluster": cluster,
        "remote_folder": remote_folder,
        "remote_root": str(root),
        "paths": paths,
        "git_commit": _git_commit(project_root),
    }
    manifest_path = project_root / "results" / ".manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[INFO] Manifest written to {manifest_path}")


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.argument("remote_folder")
@click.option("--remote-root", default=None)
@click.option("--script", default="hpc/setup/setup.sh")
@click.option("--dry-run", is_flag=True)
@click.option(
    "--salloc",
    is_flag=True,
    help="Run setup inside an interactive SLURM allocation.",
)
@click.option("--salloc-args", default="")
def setup(
    cluster: str,
    remote_folder: str,
    remote_root: str | None,
    script: str,
    dry_run: bool,
    salloc: bool,
    salloc_args: str,
) -> None:
    """Run the cluster setup script (creates venv + installs deps)."""
    remote_target = get_cluster_root(cluster, remote_root) / remote_folder
    quoted_script = shlex.quote(script)

    setup_cmd = (
        f"cd {shlex.quote(str(remote_target))} && chmod +x {quoted_script} && "
        f"bash {quoted_script}"
    )
    remote_cmd = setup_cmd
    if salloc:
        args_str = salloc_args.strip()
        remote_cmd = "salloc"
        if args_str:
            remote_cmd += f" {args_str}"
        remote_cmd += f" bash -lc {shlex.quote(setup_cmd)}"

    print(f"[INFO] Running cluster setup on {cluster}:{remote_target}")
    print(f"       {remote_cmd}")

    if dry_run:
        return

    run_cmd(["ssh", cluster, remote_cmd])
    print("[DONE] Environment ready.")
    print(
        "       Submit jobs with: python hpc/lifecycle.py submit <cluster> <remote_folder>"
    )


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.argument("remote_folder")
@click.option("--remote-root", default=None)
def check(cluster: str, remote_folder: str, remote_root: str | None) -> None:
    """SSH to the cluster and run snakemake --summary."""
    remote_target = get_cluster_root(cluster, remote_root) / remote_folder

    remote_cmd = (
        f"cd {shlex.quote(str(remote_target))} && "
        "module load StdEnv/2023 python/3.13 scipy-stack/2026a 2>/dev/null && "
        "source venv/bin/activate && "
        "snakemake --snakefile workflow/Snakefile --summary"
    )

    print(f"[INFO] Checking {cluster}:{remote_target} ...")

    try:
        output = capture_cmd(["ssh", cluster, remote_cmd])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] SSH/Snakemake failed (exit {exc.returncode}).")
        sys.exit(exc.returncode)

    lines = output.splitlines()
    if len(lines) < 2:
        print("[WARN] No summary output returned.")
        return

    counts: dict[str, int] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.rsplit("\t") if "\t" in line else line.split()
        if len(parts) < 2:
            continue
        update_state = parts[-1].strip().lower()
        exec_state = parts[-2].strip().lower() if len(parts) >= 2 else "unknown"
        if exec_state == "missing":
            status = "missing"
        elif exec_state == "ok":
            status = "up to date" if "no update" in update_state else "pending"
        else:
            status = exec_state
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    print(f"\nSummary for {cluster}:{remote_target}")
    print(f"  Total   : {total}")
    print(f"  Done    : {counts.get('up to date', 0)}")
    print(f"  Missing : {counts.get('missing', 0)}")
    print(f"  Pending : {counts.get('pending', 0)}")
    print("\n  Breakdown:")
    for status, count in sorted(counts.items()):
        print(f"    {status}: {count}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@main.command()
@click.argument("cluster")
@click.option(
    "--user", default=None, help="SLURM username (default: $USER on the cluster)."
)
@click.option(
    "--full",
    is_flag=True,
    help="Show completed job history via sacct instead of squeue.",
)
def status(cluster: str, user: str | None, full: bool) -> None:
    """Show running SLURM jobs on the cluster."""
    user_str = user or "${USER:-$(whoami)}"
    if full:
        remote_cmd = f"sacct -u {user_str} --format=JobID,JobName,State,Elapsed,NodeList,ExitCode -X"
    else:
        remote_cmd = f"squeue -u {user_str}"
    run_cmd(["ssh", cluster, remote_cmd])


if __name__ == "__main__":
    main()
