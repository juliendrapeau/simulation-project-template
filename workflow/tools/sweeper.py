"""Configuration generation utilities for reproducible parameter-sweep experiments.

This module provides two classes:

- :class:`Config` — a single experiment configuration: a nested parameter dict
  plus reproducibility metadata (timestamp, git commit, seed, host).
- :class:`ConfigSet` — a collection of :class:`Config` objects with helpers to
  expand a parameter grid (or a list of grids), assign filesystem paths,
  persist to JSON, and emit a summary CSV for downstream tools (e.g. Snakemake).

Typical workflow
----------------
1. Define one ``param_grid`` dict **or** a list of them.
2. Call :meth:`ConfigSet.generate_and_save` once (outside Snakemake) to write
   all ``config.json`` / ``metadata.json`` files and a ``summary.csv``.
3. Point ``workflow.yaml`` at the CSV; Snakemake reads the ``short_path`` column
   to fan out jobs.

Example::

    from workflow.tools.config_generator import ConfigSet

    param_grid = {
        "count": [50, 100, 200],
        "low": 0.0,
        "high": 1.0,
    }

    cfgset, csv_path = ConfigSet.generate_and_save(
        param_grid,
        name="simulation",
        experiment_name="e0",
        slugify_structure=["count"],
        slugify_keymap={"count": "n"},
    )
"""

from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import random
import re
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def frange(start: float, stop: float, step: float) -> List[float]:
    """Return a list of evenly spaced floats from ``start`` to ``stop`` (inclusive).

    Unlike ``range``, this works with floating-point step sizes.  Values are
    rounded to 12 decimal places to avoid floating-point drift.

    Examples
    --------
    >>> frange(0.0, 0.1, 0.05)
    [0.0, 0.05, 0.1]
    """
    vals: List[float] = []
    x = float(start)
    while x <= stop + 1e-12:
        vals.append(round(x, 12))
        x += step
    return vals


def _json_dumps(obj: Any, indent: int = 4) -> str:
    try:
        return json.dumps(obj, sort_keys=True, indent=indent)
    except TypeError:

        def _convert(o: Any) -> Any:
            if isinstance(o, dict):
                return {k: _convert(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [_convert(x) for x in o]
            try:
                json.dumps(o)
                return o
            except Exception:
                return str(o)

        return json.dumps(_convert(obj), sort_keys=True, indent=indent)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class Config:
    """A single experiment configuration.

    Parameters
    ----------
    params : dict, optional
        Experiment parameters.  May be arbitrarily nested.
    metadata : dict, optional
        Extra key-value pairs merged into the auto-generated metadata.
    seed : int, optional
        RNG seed.  If ``None``, a random 32-bit integer is chosen.
    """

    def __init__(
        self,
        params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.params: Dict[str, Any] = params or {}
        self.metadata: Dict[str, Any] = self.default_metadata(seed=seed)
        self.short_path: Optional[str] = None
        if metadata:
            self.add_metadata(**metadata)

    @staticmethod
    def _flatten(d: Dict[str, Any], parent: str = "", sep: str = ".") -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in d.items():
            nk = f"{parent}{sep}{k}" if parent else k
            if isinstance(v, dict):
                out.update(Config._flatten(v, nk, sep=sep))
            else:
                out[nk] = v
        return out

    @staticmethod
    def _nest(flat: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for dk, v in flat.items():
            parts = dk.split(sep)
            cur = out
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = v
        return out

    def to_flat_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        flat = Config._flatten(self.params)
        if self.short_path is not None:
            flat["short_path"] = self.short_path
        if include_metadata:
            flat.update({f"meta.{k}": v for k, v in self.metadata.items()})
        return flat

    def to_json(self, indent: int = 2, include_metadata: bool = False) -> str:
        obj: Dict[str, Any] = dict(self.params)
        if include_metadata:
            obj["metadata"] = self.metadata
        return _json_dumps(obj, indent=indent)

    def to_metadata(self, indent: int = 2) -> str:
        return _json_dumps({"metadata": self.metadata}, indent=indent)

    def hash(self, length: int = 16, include_metadata: bool = False) -> str:
        flat = self.to_flat_dict(include_metadata=include_metadata)
        digest = hashlib.sha256(_json_dumps(flat).encode()).hexdigest()
        return digest[:length]

    def slugify(
        self,
        structure: Optional[List[Any]] = None,
        key_map: Optional[Dict[str, str]] = None,
        pretty: bool = True,
    ) -> Path:
        """Build a hierarchical filesystem path from the parameter values.

        Each element of *structure* becomes one path component:

        - A plain string key → a single ``label+value`` segment.
        - A list/tuple of keys → all pairs joined with ``"-"`` in one segment.

        Examples
        --------
        >>> cfg = Config({"count": 100, "high": 1.0})
        >>> str(cfg.slugify(structure=["count"], key_map={"count": "n"}))
        'n100'
        """
        key_map = key_map or {}

        def _sanitize(x: Any) -> str:
            if isinstance(x, float):
                return str(x).replace(".", "p")
            return re.sub(r"[^a-zA-Z0-9_-]", "_", str(x))

        flat = self.to_flat_dict()
        keys: List[Any] = sorted(flat.keys()) if structure is None else structure
        parts: List[str] = []

        for key in keys:
            if isinstance(key, (list, tuple)):
                segment = "-".join(
                    f"{key_map.get(k, k.split('.')[-1] if pretty else k)}{_sanitize(flat[k])}"
                    for k in key
                )
                parts.append(segment)
            else:
                label = key_map.get(key, key.split(".")[-1] if pretty else key)
                parts.append(f"{label}{_sanitize(flat[key])}")

        return Path(*parts)

    def add_params(self, **kwargs: Any) -> None:
        self.params.update(kwargs)

    def add_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    @staticmethod
    def default_metadata(seed: Optional[int] = None) -> Dict[str, Any]:
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        random.seed(seed)
        np.random.seed(seed)
        try:
            commit = (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except Exception:
            commit = "unknown"
        return {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "git_commit": commit,
            "seed": seed,
            "tags": [],
        }

    def merge(self, other: Config) -> Config:
        """Return a new :class:`Config` with parameters deep-merged from *other*."""

        def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
            result = a.copy()
            for k, v in b.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _deep_merge(result[k], v)
                else:
                    result[k] = v
            return result

        merged = Config(
            params=_deep_merge(self.params, other.params),
            metadata={**self.metadata, **other.metadata},
        )
        merged.short_path = other.short_path if other.short_path is not None else self.short_path
        return merged


# ---------------------------------------------------------------------------
# ConfigSet
# ---------------------------------------------------------------------------


class ConfigSet:
    """An ordered collection of :class:`Config` objects.

    Provides methods for expanding parameter grids, assigning filesystem paths,
    persisting to JSON, and emitting a summary CSV for Snakemake.
    """

    def __init__(self, configs: Optional[List[Config]] = None) -> None:
        self.configs: List[Config] = configs or []

    def __len__(self) -> int:
        return len(self.configs)

    def __iter__(self):
        return iter(self.configs)

    def append(self, cfg: Config) -> None:
        self.configs.append(cfg)

    def to_csv(self, path: str = "summary.csv", include_metadata: bool = False) -> str:
        rows = [c.to_flat_dict(include_metadata=include_metadata) for c in self.configs]
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
        return str(Path(path).resolve())

    def slugify_all(
        self,
        root: str = "sweeps",
        slugify_structure: Optional[List[Any]] = None,
        slugify_keymap: Optional[Dict[str, str]] = None,
    ) -> None:
        root_p = Path(root)
        root_p.mkdir(parents=True, exist_ok=True)

        for cfg in self.configs:
            slug = cfg.slugify(structure=slugify_structure, key_map=slugify_keymap)
            cfg.short_path = str(slug)
            cfg.add_metadata(short_path=str(slug))

    def save_all(self, root: str = "sweeps", overwrite: bool = True) -> None:
        root_p = Path(root)
        root_p.mkdir(parents=True, exist_ok=True)

        for cfg in self.configs:
            if cfg.short_path is None:
                raise RuntimeError(
                    "cfg.short_path is None — call slugify_all() before save_all()."
                )
            h = cfg.hash()
            config_path = root_p / cfg.short_path / "config.json"
            metadata_path = root_p / cfg.short_path / f"metadata-{h}.json"

            if not overwrite and config_path.exists():
                continue

            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w") as f:
                f.write(cfg.to_json())
            with open(metadata_path, "w") as f:
                f.write(cfg.to_metadata())

    @classmethod
    def expand_from_grid(
        cls,
        param_grid: Dict[str, Any],
        constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfigSet:
        """Generate all parameter combinations from a (possibly nested) grid.

        Each key maps to a scalar, a list/tuple/range (iterated in Cartesian
        product), a callable ``f(flat_params) → scalar`` (resolved lazily), or
        a nested dict (recursively expanded).
        """

        def _flatten_grid(grid: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, v in grid.items():
                dotted = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    out.update(_flatten_grid(v, dotted))
                else:
                    out[dotted] = v
            return out

        def _nest(flat: Dict[str, Any]) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for dk, v in flat.items():
                parts = dk.split(".")
                cur = out
                for p in parts[:-1]:
                    cur = cur.setdefault(p, {})
                cur[parts[-1]] = v
            return out

        def _as_list(value: Any) -> List[Any]:
            if isinstance(value, (list, tuple, range)):
                return list(value)
            return [value]

        flat_grid = _flatten_grid(param_grid)

        static_keys: List[str] = []
        static_values: List[List[Any]] = []
        callable_keys: List[str] = []
        callable_fns: List[Callable] = []

        for key, value in flat_grid.items():
            if callable(value):
                callable_keys.append(key)
                callable_fns.append(value)
            else:
                static_keys.append(key)
                static_values.append(_as_list(value))

        configs: List[Config] = []

        for combo in itertools.product(*static_values):
            flat: Dict[str, Any] = dict(zip(static_keys, combo))

            for key, fn in zip(callable_keys, callable_fns):
                result = fn(flat)
                if isinstance(result, (list, tuple, range)):
                    result = list(result)
                    if len(result) == 1:
                        result = result[0]
                    else:
                        raise ValueError(
                            f"Callable for key '{key}' returned {len(result)} values. "
                            "Callables must return a single value."
                        )
                flat[key] = result

            nested = _nest(flat)
            if constraint is None or constraint(nested):
                configs.append(Config(nested, metadata=metadata))

        return cls(configs)

    @classmethod
    def expand_from_grids(
        cls,
        param_grids: List[Dict[str, Any]],
        constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfigSet:
        """Expand a list of parameter grids and combine the results."""
        combined: List[Config] = []
        for grid in param_grids:
            partial = cls.expand_from_grid(grid, constraint=constraint, metadata=metadata)
            combined.extend(partial.configs)
        return cls(combined)

    @classmethod
    def generate_and_save(
        cls,
        param_grid: "Dict[str, Any] | List[Dict[str, Any]]",
        name: str,
        experiment_name: str,
        slugify_structure: Optional[List[Any]] = None,
        slugify_keymap: Optional[Dict[str, str]] = None,
        root: str = "sweeps",
        tags: Optional[List[str]] = None,
        constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Tuple[ConfigSet, str]:
        """Expand a parameter grid, assign paths, and persist to disk.

        This is the primary entry point for experiment setup.

        Parameters
        ----------
        param_grid : dict or list of dict
            A single parameter grid, or a list of grids (each expanded
            independently, then concatenated).
        name : str
            Experiment name (e.g. ``"simulation"``).
        experiment_name : str
            Experiment identifier (e.g. ``"e0"``).
        slugify_structure : list, optional
            Ordered list of parameter keys used to build the slug path.
        slugify_keymap : dict, optional
            Short labels for parameter keys used in the slug (e.g. ``{"count": "n"}``).
        root : str, optional
            Root directory for sweep files.  Default is ``"sweeps"``.
        tags : list of str, optional
            Labels attached to every config's metadata under ``"tags"``.
        constraint : callable, optional
            ``f(nested_params) → bool`` — discard combinations returning ``False``.

        Returns
        -------
        cfgset : ConfigSet
        csv_path : str
            Absolute path of the written ``summary.csv``.

        Examples
        --------
        ::

            cfgset, csv = ConfigSet.generate_and_save(
                param_grid={"count": [50, 100, 200], "high": 1.0},
                name="simulation",
                experiment_name="e0",
                slugify_structure=["count"],
                slugify_keymap={"count": "n"},
            )
        """
        exp_dir = Path(root) / name / experiment_name
        exp_dir.mkdir(parents=True, exist_ok=True)

        expand_meta = {"tags": tags or []}
        if isinstance(param_grid, list):
            cfgset = cls.expand_from_grids(param_grid, constraint=constraint, metadata=expand_meta)
        else:
            cfgset = cls.expand_from_grid(param_grid, constraint=constraint, metadata=expand_meta)

        cfgset.slugify_all(
            root=str(exp_dir),
            slugify_structure=slugify_structure,
            slugify_keymap=slugify_keymap,
        )

        csv_path = exp_dir / "summary.csv"
        cfgset.to_csv(path=str(csv_path), include_metadata=False)

        return cfgset, str(csv_path)
