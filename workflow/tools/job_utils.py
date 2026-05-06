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


# Packages to include in run-level metadata. Customize for your project.
_TRACKED_PACKAGES = ["simulation-project-template"]


def capture_job_metadata() -> dict:
    """Per-job metadata that varies per (path, instance). Flows into results.json."""
    return {
        "host": socket.gethostname(),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "peak_rss_mb": round(_peak_rss_mb(), 2),
    }


def capture_run_metadata() -> dict:
    """Run-level metadata expected constant across a Snakemake invocation."""
    return {
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "container_image_digest": os.environ.get("CONTAINER_DIGEST"),
        "versions": {pkg: _pkg_version(pkg) for pkg in _TRACKED_PACKAGES},
    }


def derive_seed(path: str, instance: str) -> int:
    """Deterministic 32-bit seed from ``(path, instance)`` via SHA-256."""
    key = f"{path}::{instance}"
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big")
