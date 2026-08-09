import json

import pytest

from hathor.interfaces.cli.main import main


def test_cli_writes_identical_output_for_same_seed(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        code = main(
            [
                "generate",
                "--seed",
                "42",
                "--dry-run",
                "--stages",
                "structure,harmony",
                "--out",
                str(out),
            ]
        )
        assert code == 0
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    ja.pop("job"), jb.pop("job")
    assert ja == jb


def test_cli_prints_when_no_out(capsys):
    assert main(["generate", "--seed", "1", "--dry-run"]) == 0
    assert "harmony" in capsys.readouterr().out


def test_cli_requires_dry_run():
    assert main(["generate", "--seed", "1"]) == 2


def test_cli_rejects_unknown_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", "mixing"])


def test_cli_rejects_empty_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", " , "])
