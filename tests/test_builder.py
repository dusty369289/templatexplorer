from pathlib import PurePosixPath

import pytest

from templatexplorer import TemxError, build, expand, parse_temx
from templatexplorer.expander import PlanItem


def _build(src, tmp_path, **kwargs):
    template = parse_temx(src)
    plan = expand(template)
    return build(plan, tmp_path, **kwargs)


def test_build_creates_files_and_dirs(tmp_path):
    _build(
        """
root:
  - dir: a
    children:
      - file: hello.txt
        content: hi
""".strip(),
        tmp_path,
    )
    assert (tmp_path / "a").is_dir()
    assert (tmp_path / "a" / "hello.txt").read_text() == "hi"


def test_build_creates_out_root_if_missing(tmp_path):
    target = tmp_path / "doesnotexistyet"
    _build("root:\n  - file: x.txt\n", target)
    assert target.is_dir()
    assert (target / "x.txt").exists()


def test_collision_without_force_errors(tmp_path):
    (tmp_path / "x.txt").write_text("preexisting")
    with pytest.raises(TemxError, match="already exist"):
        _build("root:\n  - file: x.txt\n    content: new\n", tmp_path)
    # Existing file untouched.
    assert (tmp_path / "x.txt").read_text() == "preexisting"


def test_collision_with_force_overwrites(tmp_path):
    (tmp_path / "x.txt").write_text("preexisting")
    _build("root:\n  - file: x.txt\n    content: new\n", tmp_path, force=True)
    assert (tmp_path / "x.txt").read_text() == "new"


def test_existing_dir_is_reused_without_force(tmp_path):
    # An existing directory at a planned dir path is NOT a collision —
    # we just write into it. (Only existing FILES at planned paths block.)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "untouched.txt").write_text("keep me")
    _build(
        "root:\n  - dir: a\n    children:\n      - file: new.txt\n        content: hi\n",
        tmp_path,
    )
    assert (tmp_path / "a" / "untouched.txt").read_text() == "keep me"
    assert (tmp_path / "a" / "new.txt").read_text() == "hi"


def test_existing_file_where_dir_planned_is_collision(tmp_path):
    (tmp_path / "a").write_text("I'm a file")
    with pytest.raises(TemxError, match="already exist"):
        _build("root:\n  - dir: a\n", tmp_path)


def test_dry_run_writes_nothing(tmp_path):
    written = _build(
        "root:\n  - file: x.txt\n    content: hi\n",
        tmp_path,
        dry_run=True,
    )
    assert not (tmp_path / "x.txt").exists()
    assert len(written) == 1


def test_out_root_is_a_file_errors(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")
    with pytest.raises(TemxError, match="not a directory"):
        _build("root:\n  - file: x.txt\n", target)


def test_two_files_same_path_rejected(tmp_path):
    plan = [
        PlanItem(kind="file", path=PurePosixPath("dup.txt"), content="a"),
        PlanItem(kind="file", path=PurePosixPath("dup.txt"), content="b"),
    ]
    with pytest.raises(TemxError, match="two files at the same path"):
        build(plan, tmp_path)


def test_conflicting_kinds_at_same_path_rejected(tmp_path):
    plan = [
        PlanItem(kind="file", path=PurePosixPath("x"), content=""),
        PlanItem(kind="dir", path=PurePosixPath("x")),
    ]
    with pytest.raises(TemxError, match="conflicting kinds"):
        build(plan, tmp_path)


def test_absolute_plan_path_rejected(tmp_path):
    plan = [PlanItem(kind="file", path=PurePosixPath("/etc/passwd"), content="")]
    with pytest.raises(TemxError, match="absolute"):
        build(plan, tmp_path)


def test_force_overwrite_does_not_blow_away_sibling_files(tmp_path):
    (tmp_path / "keep.txt").write_text("untouched")
    (tmp_path / "x.txt").write_text("old")
    _build("root:\n  - file: x.txt\n    content: new\n", tmp_path, force=True)
    assert (tmp_path / "keep.txt").read_text() == "untouched"
    assert (tmp_path / "x.txt").read_text() == "new"
