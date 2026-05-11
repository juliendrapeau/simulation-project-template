"""Shared utilities for Snakemake job scripts (importable as ``tools.job_utils``)."""

import datetime
import hashlib
import os
import platform
import resource
import socket
import subprocess
import sys
from importlib import metadata as _pkg_meta


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _pkg_version(name: str) -> str:
    try:
        return _pkg_meta.version(name)
    except Exception:
        return "unknown"


def _peak_rss_mb() -> float:
    """Peak resident-set size in MB. Linux reports KB, macOS reports bytes."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def _slurm_int(key: str) -> int | None:
    val = os.environ.get(key)
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None


def _sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# Packages to include in run-level metadata. Customize for your project.
_TRACKED_PACKAGES = ["simulation-project-template"]


def capture_job_metadata() -> dict:
    """Per-job metadata that varies per (path, instance). Flows into results.json."""
    return {
        "host": socket.gethostname(),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "peak_rss_mb": round(_peak_rss_mb(), 2),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION"),
        "slurm_cpus_per_task": _slurm_int("SLURM_CPUS_PER_TASK"),
        "slurm_mem_per_cpu_mb": _slurm_int("SLURM_MEM_PER_CPU"),
        "slurm_nodelist": (
            os.environ.get("SLURM_JOB_NODELIST") or os.environ.get("SLURM_NODELIST")
        ),
        "slurm_timelimit": os.environ.get("SLURM_TIMELIMIT"),
        "slurm_array_task_id": _slurm_int("SLURM_ARRAY_TASK_ID"),
    }


def capture_run_metadata() -> dict:
    """Run-level metadata expected constant across a Snakemake invocation."""
    container_path = (
        os.environ.get("APPTAINER_CONTAINER")
        or os.environ.get("SINGULARITY_CONTAINER")
        or ""
    )
    return {
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "container_image": os.path.basename(container_path) or None,
        "container_image_digest": _sha256_file(container_path),
        "versions": {pkg: _pkg_version(pkg) for pkg in _TRACKED_PACKAGES},
    }


def derive_seed(path: str, instance: str) -> int:
    """Deterministic 32-bit seed from ``(path, instance)`` via SHA-256."""
    key = f"{path}::{instance}"
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big")
