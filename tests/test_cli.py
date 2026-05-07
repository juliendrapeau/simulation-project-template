import json
import sys
from argparse import Namespace
from unittest.mock import patch

import pytest

from simulation_project_template.cli import _cmd_generate, _cmd_mean, main


def test_cmd_generate(tmp_path):
    out = str(tmp_path / "out.json")
    args = Namespace(count=5, output=out, low=0.0, high=1.0, seed=42)
    assert _cmd_generate(args) == 0
    with open(out) as f:
        data = json.load(f)
    assert len(data["number_set"]) == 5


def test_cmd_mean_valid(tmp_path):
    p = tmp_path / "nums.json"
    p.write_text(json.dumps({"number_set": [1.0, 2.0, 3.0]}))
    args = Namespace(input=str(p))
    assert _cmd_mean(args) == 0


def test_cmd_mean_bare_list(tmp_path):
    p = tmp_path / "bare.json"
    p.write_text(json.dumps([4.0, 5.0]))
    args = Namespace(input=str(p))
    assert _cmd_mean(args) == 0


def test_cmd_mean_invalid(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"number_set": "not-a-list"}))
    args = Namespace(input=str(p))
    assert _cmd_mean(args) == 1


def test_main_generate(tmp_path):
    out = str(tmp_path / "nums.json")
    with patch.object(sys, "argv", ["spt", "generate", "10", "-o", out, "--seed", "7"]):
        assert main() == 0


def test_main_mean(tmp_path):
    p = tmp_path / "nums.json"
    p.write_text(json.dumps({"number_set": [1.0, 2.0]}))
    with patch.object(sys, "argv", ["spt", "mean", str(p)]):
        assert main() == 0


def test_main_no_command():
    with patch.object(sys, "argv", ["spt"]):
        with pytest.raises(SystemExit):
            main()
