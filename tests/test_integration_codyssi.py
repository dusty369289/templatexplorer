"""Golden integration test: build the Codyssi year scaffold end-to-end."""

from pathlib import Path

from templatexplorer import build, expand, parse_temx

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "codyssi.temx"


def test_codyssi_builds_year_scaffold(tmp_path):
    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2025"})
    build(plan, tmp_path)

    root = tmp_path / "codyssi2025"
    assert root.is_dir()

    for name in ("codyssi.py", "runner.py", "new_day.py", ".gitignore", "README.md"):
        assert (root / name).is_file(), f"missing {name}"
    assert "Codyssi 2025" in (root / "README.md").read_text()

    # Codyssi shares ONE input across all three parts (AoC model), so a day has
    # input.txt + sample.txt — NOT a per-part pN.txt layout.
    day = root / "Day 01"
    assert (day / "solution.py").is_file()
    assert (day / "input.txt").read_text() == ""
    assert (day / "sample.txt").read_text() == ""
    assert not (day / "p1.txt").exists()

    gen = (root / "new_day.py").read_text()
    assert "def next_number" in gen
    assert "@problem.solver(1)" in gen


def test_codyssi_ships_vscode_tasks(tmp_path):
    import json

    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2025"})
    build(plan, tmp_path)

    tasks = json.loads((tmp_path / "codyssi2025" / ".vscode" / "tasks.json").read_text())
    by_label = {t["label"]: t for t in tasks["tasks"]}
    samples = by_label["Run all samples (current file)"]
    real = by_label["Run all real (current file)"]
    assert samples["args"] == ["${file}", "-s"]
    assert real["args"] == ["${file}"]
    # Shell type + selected interpreter (the venv), not PATH python.
    for task in (samples, real):
        assert task["type"] == "shell"
        assert task["command"] == "${command:python.interpreterPath}"


def test_codyssi_braces_round_trip(tmp_path):
    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2025"})
    build(plan, tmp_path)
    codyssi = (tmp_path / "codyssi2025" / "codyssi.py").read_text()
    assert "self.solvers: dict[int, Solver] = {}" in codyssi


def test_codyssi_generated_code_compiles(tmp_path):
    import py_compile

    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2025"})
    build(plan, tmp_path)
    root = tmp_path / "codyssi2025"
    for rel in ("codyssi.py", "runner.py", "new_day.py", "Day 01/solution.py"):
        py_compile.compile(str(root / rel), doraise=True)
