"""Golden integration test: build the AoC scaffold end-to-end."""

from pathlib import Path

from templatexplorer import build, expand, parse_temx

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "aoc.temx"


def test_aoc_example_builds_expected_tree(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template, overrides={"year": "2019"})
    build(plan, tmp_path)

    root = tmp_path / "advent-of-code-2019"
    assert root.is_dir()
    assert (root / "README.md").read_text().splitlines()[0] == "# Advent of Code 2019"
    assert (root / "solve.py").is_file()
    assert (root / "days" / "__init__.py").is_file()
    assert (root / "inputs" / ".gitkeep").is_file()

    # 25 day source files
    sources = sorted((root / "days").glob("day*.py"))
    assert len(sources) == 25
    assert sources[0].name == "day01.py"
    assert sources[-1].name == "day25.py"
    assert "DAY = 1" in sources[0].read_text()
    assert "DAY = 25" in sources[-1].read_text()

    # 25 inputs + 25 test inputs
    inputs = sorted((root / "inputs").glob("day??.txt"))
    test_inputs = sorted((root / "inputs").glob("day??_test.txt"))
    assert len(inputs) == 25
    assert len(test_inputs) == 25
    assert all(p.read_text() == "" for p in inputs + test_inputs)


def test_aoc_cli_override_year(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template, overrides={"year": "2030"})
    build(plan, tmp_path)
    assert (tmp_path / "advent-of-code-2030" / "README.md").is_file()


def test_aoc_dry_run_does_not_write(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template)
    written = build(plan, tmp_path, dry_run=True)
    assert not any(tmp_path.iterdir())
    # 1 outer dir + README + solve.py + days dir + __init__.py + 25 day*.py + inputs dir + .gitkeep + 25 + 25
    # = 1 + 1 + 1 + 1 + 1 + 25 + 1 + 1 + 25 + 25 = 82
    assert len(written) == 82
