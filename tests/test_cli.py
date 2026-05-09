import json

from click.testing import CliRunner

from simulation_project_template.cli import generate, main, mean


def test_generate_creates_file(tmp_path):
    out = str(tmp_path / "out.json")
    result = CliRunner().invoke(generate, ["5", "-o", out, "--seed", "42"])
    assert result.exit_code == 0
    with open(out) as f:
        data = json.load(f)
    assert len(data["number_set"]) == 5


def test_mean_valid(tmp_path):
    p = tmp_path / "nums.json"
    p.write_text(json.dumps({"number_set": [1.0, 2.0, 3.0]}))
    result = CliRunner().invoke(mean, [str(p)])
    assert result.exit_code == 0


def test_mean_bare_list(tmp_path):
    p = tmp_path / "bare.json"
    p.write_text(json.dumps([4.0, 5.0]))
    result = CliRunner().invoke(mean, [str(p)])
    assert result.exit_code == 0


def test_mean_invalid_type(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"number_set": "not-a-list"}))
    result = CliRunner().invoke(mean, [str(p)])
    assert result.exit_code != 0


def test_main_generate(tmp_path):
    out = str(tmp_path / "nums.json")
    result = CliRunner().invoke(main, ["generate", "10", "-o", out, "--seed", "7"])
    assert result.exit_code == 0


def test_main_mean(tmp_path):
    p = tmp_path / "nums.json"
    p.write_text(json.dumps({"number_set": [1.0, 2.0]}))
    result = CliRunner().invoke(main, ["mean", str(p)])
    assert result.exit_code == 0


def test_main_no_command():
    result = CliRunner().invoke(main, [])
    assert result.exit_code != 0
