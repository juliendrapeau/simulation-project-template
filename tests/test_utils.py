import json

import pytest

from simulation_project_template.utils import compute_mean, generate_random_numbers


def test_compute_mean_basic():
    assert compute_mean([1.0, 2.0, 3.0]) == 2.0


def test_compute_mean_single():
    assert compute_mean([5.0]) == 5.0


def test_compute_mean_empty():
    with pytest.raises(ValueError):
        compute_mean([])


def test_generate_random_numbers(tmp_path):
    path = str(tmp_path / "out.json")
    result = generate_random_numbers(10, path, seed=42)
    assert result == path
    with open(path) as f:
        data = json.load(f)
    assert len(data["number_set"]) == 10
    assert all(0.0 <= x <= 1.0 for x in data["number_set"])


def test_generate_random_numbers_reproducible(tmp_path):
    p1 = generate_random_numbers(5, str(tmp_path / "a.json"), seed=0)
    p2 = generate_random_numbers(5, str(tmp_path / "b.json"), seed=0)
    with open(p1) as f:
        d1 = json.load(f)
    with open(p2) as f:
        d2 = json.load(f)
    assert d1["number_set"] == d2["number_set"]


def test_generate_random_numbers_invalid_count(tmp_path):
    with pytest.raises(ValueError, match="positive integer"):
        generate_random_numbers(0, str(tmp_path / "out.json"))


def test_generate_random_numbers_invalid_bounds(tmp_path):
    with pytest.raises(ValueError, match="low must be less than high"):
        generate_random_numbers(5, str(tmp_path / "out.json"), low=1.0, high=0.0)
