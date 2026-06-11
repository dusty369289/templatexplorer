"""Smoke test: every example .temx parses, expands, and builds cleanly.

This catches accidental breakage of the example library when the format or
implementation evolves.
"""

from pathlib import Path

import pytest

from templatexplorer import build, expand, parse_temx

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("*.temx"))


def test_examples_directory_is_populated():
    """If someone deletes all examples by accident, fail loudly."""
    assert len(EXAMPLES) >= 6, f"expected at least 6 examples, found {len(EXAMPLES)}"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_parses_and_expands(path):
    template = parse_temx(path)
    plan = expand(template)
    assert plan, f"{path.name} produced an empty plan"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_builds_into_clean_tmpdir(tmp_path, path):
    template = parse_temx(path)
    plan = expand(template)
    written = build(plan, tmp_path)
    assert written, f"{path.name}: no files written"
    # Every promised path actually exists on disk.
    for p in written:
        assert p.exists(), f"{path.name}: planned path {p} not present after build"


def test_aoc_scaffold_produces_25_day_folders(tmp_path):
    # Light golden check on the AoC example — confirms one of the loop-heavy
    # cases still produces the expected layout shape.
    path = EXAMPLES_DIR / "aoc-scaffold.temx"
    plan = expand(parse_temx(path), overrides={"year": "2022"})
    build(plan, tmp_path)
    day_dirs = sorted(p.name for p in (tmp_path / "aoc-2022").iterdir() if p.is_dir())
    assert len(day_dirs) == 25
    assert "Day 1" in day_dirs and "Day 25" in day_dirs


def test_multi_env_config_produces_full_matrix(tmp_path):
    # 3 envs × 3 regions = 9 leaf configs.
    path = EXAMPLES_DIR / "multi-env-config.temx"
    plan = expand(parse_temx(path))
    build(plan, tmp_path)
    leaves = list((tmp_path / "deploy").rglob("config.yaml"))
    assert len(leaves) == 9


def test_weekly_journal_produces_52_weeks(tmp_path):
    path = EXAMPLES_DIR / "weekly-journal.temx"
    plan = expand(parse_temx(path), overrides={"year": "2026"})
    build(plan, tmp_path)
    weeks = sorted((tmp_path / "journal-2026").glob("week-*.md"))
    assert len(weeks) == 52
    assert weeks[0].name == "week-01.md"
    assert weeks[-1].name == "week-52.md"


def test_python_package_renames_consistently(tmp_path):
    path = EXAMPLES_DIR / "python-package.temx"
    plan = expand(parse_temx(path), overrides={"pkg": "widget"})
    build(plan, tmp_path)
    assert (tmp_path / "widget" / "src" / "widget" / "__init__.py").is_file()
    assert (tmp_path / "widget" / "tests" / "test_core.py").is_file()
    # Package name appears in pyproject and test imports.
    assert 'name = "widget"' in (tmp_path / "widget" / "pyproject.toml").read_text()
    assert "from widget.core" in (tmp_path / "widget" / "tests" / "test_core.py").read_text()
