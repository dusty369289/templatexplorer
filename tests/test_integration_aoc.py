"""Golden integration test: build the AoC 2022-style scaffold end-to-end."""

from pathlib import Path

from templatexplorer import build, expand, parse_temx

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "aoc.temx"


def test_aoc_example_builds_expected_tree(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template, overrides={"year": "2022"})
    build(plan, tmp_path)

    root = tmp_path / "aoc-2022"
    assert root.is_dir()

    day_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    assert len(day_dirs) == 25
    # Lexicographic sort puts "Day 1" before "Day 10" — verify both ends exist.
    assert (root / "Day 1").is_dir()
    assert (root / "Day 25").is_dir()
    # No zero-padding: "Day 01" must NOT exist.
    assert not (root / "Day 01").exists()

    for n in range(1, 26):
        day = root / f"Day {n}"
        assert (day / "input.txt").read_text() == ""
        assert (day / "input_test.txt").read_text() == ""
        main = (day / "main.py").read_text()
        # Each main.py references its own day folder in the path strings.
        assert f'load_input("Day {n}/input_test.txt")' in main
        assert f'load_input("Day {n}/input.txt")' in main
        # Functions present.
        assert "def load_input" in main
        assert "def part1" in main
        assert "def part2" in main


def test_aoc_cli_override_year(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template, overrides={"year": "2030"})
    build(plan, tmp_path)
    assert (tmp_path / "aoc-2030").is_dir()
    assert (tmp_path / "aoc-2030" / "Day 1" / "main.py").is_file()


def test_aoc_dry_run_does_not_write(tmp_path):
    template = parse_temx(EXAMPLE)
    plan = expand(template)
    written = build(plan, tmp_path, dry_run=True)
    assert not any(tmp_path.iterdir())
    # 1 outer dir ("aoc-{year}") + 25 day dirs + 25 * 3 files = 1 + 25 + 75 = 101
    assert len(written) == 101


def test_aoc_single_day_via_override(tmp_path):
    # --var day=7 collapses the 1..25 loop to just day 7.
    template = parse_temx(EXAMPLE)
    plan = expand(template, overrides={"year": "2022", "day": "7"})
    build(plan, tmp_path)
    root = tmp_path / "aoc-2022"
    day_dirs = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert day_dirs == ["Day 7"]
    assert 'load_input("Day 7/input.txt")' in (root / "Day 7" / "main.py").read_text()
