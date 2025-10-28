import copy
import datetime
import hashlib
import json
import random
import re
import socket
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# -------------------------
# public float range helper
# -------------------------
def frange(start: float, stop: float, step: float) -> List[float]:
    """
    Floating-range generator that is robust to floating point error and supports negative steps.
    Raises ValueError on step == 0.
    """
    if step == 0:
        raise ValueError("step must be non-zero")
    out: List[float] = []
    eps = 1e-12
    x = float(start)
    increasing = step > 0
    # Use a safe loop condition depending on sign of step
    if increasing:
        while x <= stop + eps:
            out.append(round(x, 12))
            x += step
    else:
        while x >= stop - eps:
            out.append(round(x, 12))
            x += step
    return out


# -------------------------
# internal helpers
# -------------------------
def json_dumps(obj: Any, indent: int = 4, sort_keys: bool = True) -> str:
    """
    Robust JSON dump that handles numpy types, pandas objects, Path, datetime, sets, etc.
    Falls back to `str()` for unknown objects.
    """

    def _default(o: Any):
        # numpy types
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
        # pandas types
        if isinstance(o, (pd.Timestamp, datetime.datetime, datetime.date)):
            return o.isoformat()
        if isinstance(o, (pd.Series, pd.Index)):
            return o.tolist()
        if isinstance(o, pd.DataFrame):
            return o.to_dict(orient="list")
        # pathlib
        if isinstance(o, Path):
            return str(o)
        # common collections
        if isinstance(o, set):
            return list(o)
        if isinstance(o, bytes):
            return o.decode(errors="ignore")
        # fallback
        try:
            return str(o)
        except Exception:
            return repr(o)

    return json.dumps(
        obj, default=_default, sort_keys=sort_keys, indent=indent, ensure_ascii=False
    )


# -------------------------
# Config: single configuration
# -------------------------
class Config:
    """Single configuration with params (nested dict) and metadata."""

    def __init__(
        self,
        params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ):
        self.params: Dict[str, Any] = copy.deepcopy(params or {})
        # Avoid mutable default arg bug
        self.metadata: Dict[str, Any] = self.default_metadata(seed=seed)
        if metadata:
            self.add_metadata(**metadata)

    def __repr__(self) -> str:
        return f"Config(hash={self.hashed(8)}, params_keys={list(self.params.keys())})"

    # ----- flatten / nest helpers for serialization -----
    @staticmethod
    def _flatten(
        d: Mapping[str, Any], parent: str = "", sep: str = "."
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in d.items():
            nk = f"{parent}{sep}{k}" if parent else k
            if isinstance(v, Mapping):
                out.update(Config._flatten(v, nk, sep=sep))
            else:
                out[nk] = v
        return out

    @staticmethod
    def _nest(flat: Mapping[str, Any], sep: str = ".") -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for dk, v in flat.items():
            parts = dk.split(sep)
            cur = out
            for p in parts[:-1]:
                if p not in cur or not isinstance(cur[p], dict):
                    cur[p] = {}
                cur = cur[p]
            cur[parts[-1]] = v
        return out

    # ----- public apis -----
    def to_flat_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        flat = Config._flatten(self.params)
        if include_metadata:
            flat.update({f"meta.{k}": v for k, v in self.metadata.items()})
        return flat

    def to_json(self, indent: int = 2, include_metadata: bool = False) -> str:
        obj: Dict[str, Any] = copy.deepcopy(self.params)
        if include_metadata:
            obj["metadata"] = self.metadata
        return json_dumps(obj, indent=indent)

    def hashed(self, length: int = 16, include_metadata: bool = False) -> str:
        flat = self.to_flat_dict(include_metadata=include_metadata)
        h = hashlib.sha256(json_dumps(flat, sort_keys=True).encode("utf-8")).hexdigest()
        return h[:length]

    def slugify(
        self,
        structure: Optional[Iterable[Any]] = None,
        key_map: Optional[Dict[str, str]] = None,
        pretty: bool = True,
    ) -> Path:
        """
        Create a filesystem-safe path based on parameter keys.
        `structure` may be a list of keys (or iterables of keys to be joined).
        Missing keys are skipped with a warning (no exception).
        """
        key_map = key_map or {}

        def _s(x: Any) -> str:
            if isinstance(x, float):
                s = format(x, ".12g")  # compact representation
                return s.replace(".", "p")
            if isinstance(x, (int, np.integer)):
                return str(int(x))
            return re.sub(r"[^A-Za-z0-9_\-\.]", "_", str(x))

        flat = self.to_flat_dict()
        parts: List[str] = []

        if structure is None:
            keys = sorted(flat.keys())
        else:
            keys = list(structure)

        for key in keys:
            if isinstance(key, (list, tuple)):
                comp: List[str] = []
                for k in key:
                    if k not in flat:
                        # skip missing keys
                        continue
                    mapped = key_map.get(k, (k.split(".")[-1] if pretty else k))
                    comp.append(f"{mapped}{_s(flat[k])}")
                if comp:
                    parts.append("-".join(comp))
            else:
                if key not in flat:
                    continue
                k = key_map.get(key, (key.split(".")[-1] if pretty else key))
                parts.append(f"{k}{_s(flat[key])}")

        if not parts:
            parts = ["empty"]

        # Limit each path part length to something reasonable to avoid OS issues
        safe_parts = [p[:200] for p in parts]
        return Path(*safe_parts)

    def add_params(self, **kwargs: Any) -> None:
        self.params.update(kwargs)

    def add_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    @staticmethod
    def default_metadata(seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Return sensible metadata. Does NOT alter the global RNG.
        If you want to set the global RNG, call random.seed(...) and np.random.seed(...) yourself.
        """
        # Generate a deterministic seed if not provided
        if seed is None:
            seed = random.SystemRandom().randint(0, 2**32 - 1)
        # Try to get git commit; don't raise on failure
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
            "seed": int(seed),
            "tags": [],
        }

    def to_metadata(self, indent: int = 2) -> str:
        obj: Dict[str, Any] = {"metadata": self.metadata}
        return json_dumps(obj, indent=indent)

    def merge(self, other: "Config") -> "Config":
        """
        Deep-merge `other` into this config (other wins on conflicts).
        Returns a new Config instance.
        """

        def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
            r = copy.deepcopy(a)
            for k, v in b.items():
                if k in r and isinstance(r[k], dict) and isinstance(v, dict):
                    r[k] = _deep_merge(r[k], v)
                else:
                    r[k] = copy.deepcopy(v)
            return r

        merged_params = _deep_merge(self.params, other.params)
        merged_meta = {**self.metadata, **other.metadata}
        return Config(params=merged_params, metadata=merged_meta)


# -------------------------
# ConfigSet: collection + expansion
# -------------------------
class ConfigSet:
    """Collection of Config objects and methods to create/manipulate them."""

    def __init__(self, configs: Optional[List[Config]] = None):
        self.configs: List[Config] = copy.deepcopy(configs or [])

    def __len__(self) -> int:
        return len(self.configs)

    def __iter__(self):
        return iter(self.configs)

    def append(self, cfg: Config) -> None:
        self.configs.append(cfg)

    def to_dataframe(self, include_metadata: bool = False) -> pd.DataFrame:
        rows = [c.to_flat_dict(include_metadata=include_metadata) for c in self.configs]
        return pd.DataFrame(rows)

    def to_csv(
        self, path: Union[str, Path] = "summary.csv", include_metadata: bool = False
    ) -> str:
        df = self.to_dataframe(include_metadata=include_metadata)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False, encoding="utf-8")
        return str(p.resolve())

    def slugify_all(
        self,
        experiment_name: Union[str, Path],
        root: Union[str, Path] = "configs",
        slugify_structure: Optional[List[Any]] = None,
        slugify_keymap: Optional[Dict[str, str]] = None,
    ) -> None:
        root_p = Path(root)
        root_p.mkdir(parents=True, exist_ok=True)

        for i, cfg in enumerate(self.configs):
            hash_value = cfg.hashed()

            if slugify_structure == []:
                slug = hash_value
            else:
                slug = cfg.slugify(structure=slugify_structure, key_map=slugify_keymap)

            config_p = root_p / slug / "config.csv"

            cfg.add_params(
                instance_name=f"{experiment_name}/{slug}",
                config_path=config_p,
                hash_value=hash_value,
            )
            self.configs[i] = cfg

    @classmethod
    def expand_from_grid(
        cls,
        param_grid: Dict[str, Any],
        constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ConfigSet":
        """
        Expand a nested param_grid into all combos. Values in the grid may be:
          - a list/tuple/range (treated as multiple options)
          - a callable(params) -> single value or iterable (callable receives the current base params)
          - a single value (treated as singleton)
        Nested dicts are interpreted as nested parameter structures.
        """

        configs: List[Config] = []

        def expand_value(value: Any, params: Dict[str, Any]) -> Iterable[Any]:
            if callable(value):
                result = value(params)
                if isinstance(result, (list, tuple, range)):
                    return list(result)
                return [result]
            if isinstance(value, (list, tuple, range, np.ndarray, pd.Index)):
                return list(value)
            return [value]

        def expand_dict(grid: Dict[str, Any], base_params: Dict[str, Any]):
            if not grid:
                yield base_params
                return
            # Process first item; preserve insertion order (py3.7+)
            (key, value), *rest_items = list(grid.items())
            rest = dict(rest_items)
            if isinstance(value, dict):
                # Recurse into nested dict structure: treat nested dict as nested group to be filled
                for nested in expand_dict(value, {}):
                    new_params = copy.deepcopy(base_params)
                    new_params[key] = nested
                    if rest:
                        yield from expand_dict(rest, new_params)
                    else:
                        yield new_params
            else:
                for expanded_val in expand_value(value, base_params):
                    new_params = copy.deepcopy(base_params)
                    new_params[key] = expanded_val
                    if rest:
                        yield from expand_dict(rest, new_params)
                    else:
                        yield new_params

        for param_set in expand_dict(param_grid, {}):
            if constraint is None or constraint(param_set):
                cfg = Config(params=param_set, metadata=metadata)
                configs.append(cfg)

        return cls(configs)

    @classmethod
    def generate_and_save(
        cls,
        param_grid: Dict[str, Any],
        experiment_name: str,
        slugify_structure: Optional[List[Any]] = None,
        slugify_keymap: Optional[Dict[str, str]] = None,
        root: str = "configs",
        seed: Optional[int] = None,
        tags: Optional[List[str]] = None,
        constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Tuple["ConfigSet", str]:
        exp = Path(root) / f"{experiment_name}"

        exp.mkdir(parents=True, exist_ok=True)
        meta = {"tags": tags or []}
        cfgset = cls.expand_from_grid(param_grid, constraint=constraint, metadata=meta)
        cfgset.slugify_all(
            root=exp,
            experiment_name=experiment_name,
            slugify_structure=slugify_structure,
            slugify_keymap=slugify_keymap,
        )
        csv_path = exp / "config.csv"
        cfgset.to_csv(path=str(csv_path), include_metadata=False)
        return cfgset, str(csv_path.resolve())

    @classmethod
    def import_from_dir(cls, dir_path: Union[str, Path]) -> "ConfigSet":
        """
        Recursively scan a directory for `config.json` files, read them, and create a ConfigSet.
        """
        dir_path = Path(dir_path)
        configs: List[Config] = []

        for cfg_file in dir_path.rglob("*.json"):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    params = json.load(f)

                cfg = Config(params=params)
                configs.append(cfg)
            except Exception as e:
                print(f"Failed to read {cfg_file}: {e}")

        return cls(configs)
