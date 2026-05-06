"""HPC lifecycle manager for cluster upload/setup/submit/check/download/status.

Usage:
  python hpc/lifecycle.py upload   <cluster> <remote_folder> [--dry-run] [--no-build-sif]
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

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Map SSH host aliases to their scratch/project root paths.
# Customize for your cluster(s).
CLUSTER_ROOTS: dict[str, Path] = {
    # "mycluster": Path("/scratch/myuser"),
}
DEFAULT_CLUSTER_ROOT = Path("~/projects/def-supervisor").expanduser() / Path.home().name

# Paths uploaded to the cluster. workflow.yaml extra references (csv, container)
# are appended automatically if they exist locally.
CORE_UPLOAD_PATHS = (
    "README.md",
    "pyproject.toml",
    "hpc/",
    "workflow/",
    "workflow.yaml",
)


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
            capture_output=True, text=True, check=True, cwd=project_root,
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
    required = {p.rstrip("/") for p in CORE_UPLOAD_PATHS}
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
# upload
# ---------------------------------------------------------------------------


def _add_upload_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("upload", help="Upload required workflow files to the cluster.")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("remote_folder", help="Destination folder under the cluster root.")
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent))
    p.add_argument("--remote-root", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-build-sif", action="store_true", help="Skip SIF image build.")
    p.add_argument("--sif-platform", default="linux/amd64")
    p.add_argument("--sif-suffix", default="")
    p.set_defaults(func=cmd_upload)


def cmd_upload(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Project root not found: {project_root}")

    if not args.no_build_sif:
        sif_cmd = ["uv", "run", "hpc/containers/build_sif.py", "--platforms", args.sif_platform]
        if args.sif_suffix:
            sif_cmd.extend(["--suffix", args.sif_suffix])
        print(f"[INFO] Building SIF: {' '.join(sif_cmd)}")
        run_cmd(sif_cmd, cwd=project_root)

    root = get_cluster_root(args.cluster, args.remote_root)
    remote_target = root / args.remote_folder

    if not _confirm_existing_upload_target(args.cluster, remote_target):
        print(f"[INFO] Upload cancelled.")
        return 0

    paths = collect_upload_paths(project_root)
    if not paths:
        raise RuntimeError("No files found to upload.")

    rsync_cmd = ["rsync", "-az", "--progress", "--relative", "--exclude=__pycache__"]
    if args.dry_run:
        rsync_cmd.append("--dry-run")
    rsync_cmd.extend([f"./{p}" for p in paths])
    rsync_cmd.append(f"{args.cluster}:{remote_target}/")

    print("[INFO] Uploading:")
    for p in paths:
        print(f"  - {p}")
    run_cmd(rsync_cmd, cwd=project_root)
    print(
        "[DONE] Upload complete.\n"
        f"  Next: python hpc/lifecycle.py submit {args.cluster} {args.remote_folder}"
    )
    return 0


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------


def _add_submit_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("submit", help="SSH to the cluster and submit a Snakemake SLURM job.")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("remote_folder", help="Remote project folder under the cluster root.")
    p.add_argument(
        "--mode", choices=["profile", "local"], default="profile",
        help="'profile' dispatches jobs via hpc/config.yaml; 'local' runs with -c $SLURM_CPUS_PER_TASK.",
    )
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent))
    p.add_argument("--remote-root", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--snakemake-dry-run", action="store_true",
                   help="Pass --dryrun to Snakemake: plan only, no jobs executed.")
    p.set_defaults(func=cmd_submit)


def cmd_submit(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    submit_cfg = project_root / "hpc" / "submit.yaml"
    if not submit_cfg.exists():
        raise FileNotFoundError(
            f"Submit config not found: {submit_cfg}\n"
            "  Create it from the template: cp hpc/submit_example.yaml hpc/submit.yaml"
        )

    data = load_yaml(submit_cfg)
    resources: dict[str, Any] = data.get("resources", {})
    extra: list[str] = data.get("extra_sbatch_args", [])

    sbatch_flags = [
        f"--{k.replace('_', '-')}={v}" for k, v in resources.items() if v is not None
    ] + extra

    root = get_cluster_root(args.cluster, args.remote_root)
    remote_target = root / args.remote_folder

    extra_smk: list[str] = []
    if args.snakemake_dry_run:
        extra_smk.append("--dryrun")

    script_cmd = "hpc/snakemake/run_snakemake.sh " + args.mode
    if extra_smk:
        script_cmd += " " + " ".join(extra_smk)
    sbatch_line = "sbatch " + " ".join(sbatch_flags) + " " + script_cmd
    remote_cmd = f"cd {shlex.quote(str(remote_target))} && {sbatch_line}"

    print(f"[INFO] Submitting [{args.mode}] to {args.cluster}:{remote_target}")
    print(f"       {sbatch_line}")

    if args.dry_run:
        return 0

    run_cmd(["ssh", args.cluster, remote_cmd])
    print("[DONE] Job submitted.")
    return 0


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


def _add_download_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("download", help="Download workflow outputs from the cluster.")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("remote_folder", help="Remote project folder under the cluster root.")
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent))
    p.add_argument("--remote-root", default=None)
    p.add_argument("--paths", nargs="+", default=["results"],
                   help="Relative paths to download (default: results).")
    p.add_argument("--include-data", action="store_true",
                   help="Also download data/ in addition to --paths.")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_download)


def cmd_download(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Project root not found: {project_root}")

    root = get_cluster_root(args.cluster, args.remote_root)
    remote_target = root / args.remote_folder

    selected = {p.strip().strip("/") for p in args.paths if p.strip()}
    if args.include_data:
        selected.add("data")
    if not selected:
        raise RuntimeError("No remote paths selected.")

    print("[INFO] Downloading:")
    for rel in sorted(selected):
        local_target = project_root / rel
        if not _confirm_existing_download_target(local_target):
            print(f"[INFO] Skipping existing local path: {local_target}")
            continue
        rsync_cmd = ["rsync", "-az", "--progress", "--exclude=__pycache__"]
        if args.dry_run:
            rsync_cmd.append("--dry-run")
        local_target.mkdir(parents=True, exist_ok=True)
        rsync_cmd.extend([f"{args.cluster}:{remote_target}/{rel}/", f"{local_target}/"])
        run_cmd(rsync_cmd, cwd=project_root)

    print(f"[DONE] Downloaded into: {project_root}")

    if not args.dry_run:
        _write_manifest(project_root, args, root, sorted(selected))

    return 0


def _write_manifest(project_root: Path, args: argparse.Namespace, root: Path, paths: list[str]) -> None:
    manifest = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "cluster": args.cluster,
        "remote_folder": args.remote_folder,
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


def _add_setup_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("setup", help="Run the cluster setup script (creates venv + installs deps).")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("remote_folder", help="Remote project folder under the cluster root.")
    p.add_argument("--remote-root", default=None)
    p.add_argument("--script", default="hpc/setup/setup.sh")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--salloc", action="store_true",
                   help="Run setup inside an interactive SLURM allocation.")
    p.add_argument("--salloc-args", default="")
    p.set_defaults(func=cmd_setup)


def cmd_setup(args: argparse.Namespace) -> int:
    root = get_cluster_root(args.cluster, args.remote_root)
    remote_target = root / args.remote_folder
    quoted_script = shlex.quote(args.script)

    setup_cmd = (
        f"cd {shlex.quote(str(remote_target))} && chmod +x {quoted_script} && "
        f"bash {quoted_script}"
    )
    remote_cmd = setup_cmd
    if args.salloc:
        salloc_args = args.salloc_args.strip()
        remote_cmd = "salloc"
        if salloc_args:
            remote_cmd += f" {salloc_args}"
        remote_cmd += f" bash -lc {shlex.quote(setup_cmd)}"

    print(f"[INFO] Running cluster setup on {args.cluster}:{remote_target}")
    print(f"       {remote_cmd}")

    if args.dry_run:
        return 0

    run_cmd(["ssh", args.cluster, remote_cmd])
    print("[DONE] Environment ready.")
    print("       Submit jobs with: python hpc/lifecycle.py submit <cluster> <remote_folder>")
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def _add_check_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("check", help="SSH to the cluster and run snakemake --summary.")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("remote_folder", help="Remote project folder under the cluster root.")
    p.add_argument("--remote-root", default=None)
    p.set_defaults(func=cmd_check)


def cmd_check(args: argparse.Namespace) -> int:
    root = get_cluster_root(args.cluster, args.remote_root)
    remote_target = root / args.remote_folder

    remote_cmd = (
        f"cd {shlex.quote(str(remote_target))} && "
        "module load StdEnv/2023 python/3.13 scipy-stack/2026a 2>/dev/null && "
        "source venv/bin/activate && "
        "snakemake --snakefile workflow/Snakefile --summary"
    )

    print(f"[INFO] Checking {args.cluster}:{remote_target} ...")

    try:
        output = capture_cmd(["ssh", args.cluster, remote_cmd])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] SSH/Snakemake failed (exit {exc.returncode}).")
        return exc.returncode

    lines = output.splitlines()
    if len(lines) < 2:
        print("[WARN] No summary output returned.")
        return 0

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
            status = update_state
        else:
            status = exec_state
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    print(f"\nSummary for {args.cluster}:{remote_target}")
    print(f"  Total   : {total}")
    print(f"  Done    : {counts.get('up to date', 0)}")
    print(f"  Missing : {counts.get('missing', 0)}")
    print(f"  Pending : {counts.get('pending', 0)}")
    print("\n  Breakdown:")
    for status, count in sorted(counts.items()):
        print(f"    {status}: {count}")
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def _add_status_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("status", help="Show running SLURM jobs on the cluster.")
    p.add_argument("cluster", help="SSH host alias.")
    p.add_argument("--user", default=None)
    p.add_argument("--full", action="store_true",
                   help="Show completed job history via sacct instead of squeue.")
    p.set_defaults(func=cmd_status)


def cmd_status(args: argparse.Namespace) -> int:
    user = args.user or "${USER:-$(whoami)}"
    if args.full:
        remote_cmd = f"sacct -u {user} --format=JobID,JobName,State,Elapsed,NodeList,ExitCode -X"
    else:
        remote_cmd = f"squeue -u {user}"
    run_cmd(["ssh", args.cluster, remote_cmd])
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HPC lifecycle manager: upload, setup, submit, download.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python hpc/lifecycle.py upload   mycluster myproject/workflow\n"
            "  python hpc/lifecycle.py setup    mycluster myproject/workflow\n"
            "  python hpc/lifecycle.py setup    mycluster myproject/workflow --salloc\n"
            "  python hpc/lifecycle.py submit   mycluster myproject/workflow --mode profile\n"
            "  python hpc/lifecycle.py submit   mycluster myproject/workflow --snakemake-dry-run\n"
            "  python hpc/lifecycle.py check    mycluster myproject/workflow\n"
            "  python hpc/lifecycle.py status   mycluster\n"
            "  python hpc/lifecycle.py download mycluster myproject/workflow --paths results\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_upload_parser(sub)
    _add_setup_parser(sub)
    _add_submit_parser(sub)
    _add_check_parser(sub)
    _add_download_parser(sub)
    _add_status_parser(sub)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
