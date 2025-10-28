"""
Top-level package for snakemake_template.
"""

from importlib import metadata as _metadata
from typing import Any

try:
    __version__ = _metadata.version("snakemake-template")
except Exception:
    # Package may not be installed; provide a sensible default.
    __version__ = "0.0.1"

from .utils import compute_mean, generate_random_numbers

__all__ = ["compute_mean", "generate_random_numbers", "__version__"]


def info() -> dict[str, Any]:
    """Return small package info useful for debugging.

    Example:
            >>> info()["version"]
            '0.0.0'
    """
    return {"version": __version__}
