"""Golden integration test: build the Everybody Codes year scaffold end-to-end."""

from pathlib import Path

from templatexplorer import build, expand, parse_temx

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "everybodycodes.temx"


def test_everybodycodes_builds_year_scaffold(tmp_path):
    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2024"})
    build(plan, tmp_path)

    root = tmp_path / "everybodycodes2024"
    assert root.is_dir()

    # Year-root tooling.
    for name in ("ec.py", "runner.py", "new_quest.py", ".gitignore", "README.md"):
        assert (root / name).is_file(), f"missing {name}"

    # The year variable lands in the README title and the dir name.
    assert "Everybody Codes 2024" in (root / "README.md").read_text()

    # Seed quest with a per-part input layout (real + sample for parts 1-3).
    quest = root / "Quest 01"
    assert (quest / "solution.py").is_file()
    for part in (1, 2, 3):
        assert (quest / f"p{part}.txt").read_text() == ""
        assert (quest / f"p{part}_sample.txt").read_text() == ""

    # The generator carries the same solution skeleton it stamps into new quests.
    gen = (root / "new_quest.py").read_text()
    assert "def next_number" in gen
    assert "@quest.solver(1)" in gen


def test_everybodycodes_ships_vscode_tasks(tmp_path):
    import json

    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2024"})
    build(plan, tmp_path)

    tasks_file = tmp_path / "everybodycodes2024" / ".vscode" / "tasks.json"
    assert tasks_file.is_file()
    tasks = json.loads(tasks_file.read_text())  # also asserts the JSON survived escaping

    by_label = {t["label"]: t for t in tasks["tasks"]}
    samples = by_label["Run all samples (current file)"]
    real = by_label["Run all real (current file)"]
    # Each acts on the open file; samples passes -s, real does not. ${file}
    # must have round-tripped through the {{}} escape, not been interpolated.
    assert samples["args"] == ["${file}", "-s"]
    assert real["args"] == ["${file}"]
    # Tasks must follow VS Code's selected interpreter (the venv), not PATH python.
    assert samples["command"] == "${command:python.interpreterPath}"
    assert real["command"] == "${command:python.interpreterPath}"
    # Must be shell, not process: a process task resolves the absolute
    # interpreter path relative to the cwd and mangles it on Windows.
    assert samples["type"] == "shell"
    assert real["type"] == "shell"


def test_everybodycodes_braces_round_trip(tmp_path):
    # The Python files are full of literal braces (f-strings, `{}` literals).
    # Confirm templatexplorer rendered them verbatim, not as interpolations.
    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2024"})
    build(plan, tmp_path)
    ec = (tmp_path / "everybodycodes2024" / "ec.py").read_text()
    assert "self.solvers: dict[int, Solver] = {}" in ec
    assert 'f"p{part}{' in ec  # f-string with a literal brace survived


def test_everybodycodes_generated_code_compiles(tmp_path):
    import py_compile

    plan = expand(parse_temx(EXAMPLE), overrides={"year": "2024"})
    build(plan, tmp_path)
    root = tmp_path / "everybodycodes2024"
    for rel in ("ec.py", "runner.py", "new_quest.py", "Quest 01/solution.py"):
        py_compile.compile(str(root / rel), doraise=True)
