from pathlib import Path

from templatexplorer.cli import main


def _write_template(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "t.temx"
    p.write_text(body)
    return p


def test_cli_builds(tmp_path, capsys):
    t = _write_template(tmp_path, "root:\n  - file: x.txt\n    content: hi\n")
    out = tmp_path / "out"
    rc = main([str(t), "--out", str(out)])
    assert rc == 0
    assert (out / "x.txt").read_text() == "hi"
    assert "Wrote" in capsys.readouterr().out


def test_cli_dry_run(tmp_path, capsys):
    t = _write_template(tmp_path, "root:\n  - file: x.txt\n")
    out = tmp_path / "out"
    rc = main([str(t), "--out", str(out), "--dry-run"])
    assert rc == 0
    assert not (out / "x.txt").exists()
    assert "dry run" in capsys.readouterr().out


def test_cli_var_override(tmp_path):
    t = _write_template(
        tmp_path,
        "variables:\n  name: alice\nroot:\n  - file: '{name}.txt'\n    content: hi\n",
    )
    out = tmp_path / "out"
    rc = main([str(t), "--out", str(out), "--var", "name=bob"])
    assert rc == 0
    assert (out / "bob.txt").is_file()


def test_cli_error_on_collision(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.txt").write_text("old")
    t = _write_template(tmp_path, "root:\n  - file: x.txt\n    content: new\n")
    rc = main([str(t), "--out", str(out)])
    assert rc == 1
    assert (out / "x.txt").read_text() == "old"
    assert "error:" in capsys.readouterr().err


def test_cli_force_overwrites(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.txt").write_text("old")
    t = _write_template(tmp_path, "root:\n  - file: x.txt\n    content: new\n")
    rc = main([str(t), "--out", str(out), "--force"])
    assert rc == 0
    assert (out / "x.txt").read_text() == "new"


def test_cli_var_missing_equals(tmp_path, capsys):
    t = _write_template(tmp_path, "root:\n  - file: x.txt\n")
    out = tmp_path / "out"
    # argparse uses SystemExit for type errors.
    try:
        main([str(t), "--out", str(out), "--var", "noequals"])
    except SystemExit as exc:
        assert exc.code == 2
    err = capsys.readouterr().err
    assert "name=value" in err


def test_cli_parse_error_exits_nonzero(tmp_path, capsys):
    t = _write_template(tmp_path, "this: is: not: valid yaml :\n")
    out = tmp_path / "out"
    rc = main([str(t), "--out", str(out)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
