"""simulation-project-template: a template for reproducible simulation projects."""

from importlib import metadata as _metadata

try:
    __version__ = _metadata.version("simulation-project-template")
except Exception:
    __version__ = "0.0.0"

from .utils import compute_mean, generate_random_numbers

__all__ = ["compute_mean", "generate_random_numbers", "__version__"]
