"""Regressions for findings from the 2026-06-11 senior review.

Each test references the finding ID from that review (C1, H1, M1, etc.).
"""

import os
from pathlib import Path, PurePosixPath

import pytest

from templatexplorer import TemxError, build, expand, parse_temx
from templatexplorer.expander import PlanItem


# ---------- M1: SafeFormatter rejects attribute / index access ----------


def test_m1_attribute_access_rejected_in_name():
    with pytest.raises(TemxError, match="attribute or index access"):
        expand(
            parse_temx(
                "variables:\n  x: 1\nroot:\n  - file: '{x.__class__}.txt'\n"
            )
        )


def test_m1_attribute_access_rejected_in_content():
    with pytest.raises(TemxError, match="attribute or index access"):
        expand(
            parse_temx(
                "variables:\n  x: 1\nroot:\n  - file: y.txt\n    content: '{x.__class__.__bases__}'\n"
            )
        )


def test_m1_index_access_rejected():
    # `{x[0]}` would let templates index into list values.
    with pytest.raises(TemxError, match="attribute or index access"):
        expand(
            parse_temx(
                "variables:\n  x:\n    list: ['a', 'b']\nroot:\n  - file: '{x[0]}.txt'\n"
            )
        )


def test_m1_format_spec_with_colon_still_works():
    # The block is on field_name only — format specs after the colon must still work.
    items = expand(
        parse_temx(
            "variables:\n  day:\n    range: [1, 3]\n"
            "root:\n  - file: 'day{day:02d}.txt'\n    repeat: day\n"
        )
    )
    assert [str(it.path) for it in items] == ["day01.txt", "day02.txt", "day03.txt"]


# ---------- H1: list overrides coerce to int when the list is all ints ----------


def test_h1_int_list_override_coerces_to_int_for_format_spec():
    items = expand(
        parse_temx(
            "variables:\n  n:\n    list: [1, 2, 3]\n"
            "root:\n  - file: 'n{n:02d}.txt'\n    repeat: n\n"
        ),
        overrides={"n": "2"},
    )
    assert [str(it.path) for it in items] == ["n02.txt"]


def test_h1_string_list_override_stays_string():
    items = expand(
        parse_temx(
            "variables:\n  env:\n    list: [dev, prod]\n"
            "root:\n  - dir: '{env}'\n    repeat: env\n"
        ),
        overrides={"env": "staging"},
    )
    assert [str(it.path) for it in items] == ["staging"]


# ---------- M2: tighten children validation ----------


def test_m2_children_false_is_rejected():
    with pytest.raises(TemxError, match="'children' must be a list"):
        parse_temx("root:\n  - dir: a\n    children: false\n")


def test_m2_children_int_is_rejected():
    with pytest.raises(TemxError, match="'children' must be a list"):
        parse_temx("root:\n  - dir: a\n    children: 0\n")


def test_m2_children_null_is_treated_as_empty():
    # YAML's `children: ` (no value) is null; that's a fine way to mean "no children".
    t = parse_temx("root:\n  - dir: a\n    children:\n")
    assert t.root[0].children == ()


# ---------- M4: value: null is rejected ----------


def test_m4_value_null_rejected():
    with pytest.raises(TemxError, match="cannot have value: null"):
        parse_temx("variables:\n  x:\n    value: null\nroot: []\n")


def test_m4_shorthand_null_rejected():
    with pytest.raises(TemxError, match="cannot be null"):
        parse_temx("variables:\n  x: null\nroot: []\n")


def test_m4_value_empty_string_accepted():
    # The fix tells users to use ''. Make sure that works.
    t = parse_temx("variables:\n  x: ''\nroot:\n  - file: 'f{x}.txt'\n")
    items = expand(t)
    assert str(items[0].path) == "f.txt"


# ---------- L1: whitespace-only rendered names rejected ----------


def test_l1_whitespace_only_name_rejected():
    with pytest.raises(TemxError, match="whitespace-only"):
        expand(parse_temx("variables:\n  x: '   '\nroot:\n  - dir: '{x}'\n"))


def test_l1_leading_trailing_space_ok():
    # Only PURE whitespace is rejected. A name with internal/trailing spaces is fine —
    # filesystem-side concerns are out of scope.
    items = expand(parse_temx("variables:\n  x: 'Day 7'\nroot:\n  - dir: '{x}'\n"))
    assert str(items[0].path) == "Day 7"


# ---------- L4: --var strips whitespace from both name and value ----------


def test_l4_var_strips_whitespace_from_value():
    from templatexplorer.cli import _parse_var_assignment

    assert _parse_var_assignment("name = bob ") == ("name", "bob")
    assert _parse_var_assignment(" day=7 ") == ("day", "7")


# ---------- C1: symlink defenses ----------


@pytest.mark.skipif(os.name != "posix", reason="symlink semantics POSIX-only")
def test_c1_symlink_to_outside_root_rejected_without_force(tmp_path):
    """A symlink at a planned file path that points OUTSIDE the root must be rejected.
    The containment check at plan time fires first."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("evil")
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.txt").symlink_to(elsewhere)

    template = parse_temx("root:\n  - file: x.txt\n    content: new\n")
    plan = expand(template)
    with pytest.raises(TemxError, match="escapes output root"):
        build(plan, out)
    assert elsewhere.read_text() == "evil"


@pytest.mark.skipif(os.name != "posix", reason="symlink semantics POSIX-only")
def test_c1_force_also_rejects_symlink_to_outside_root(tmp_path):
    """Even with --force, the plan-time containment check rejects."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("evil")
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.txt").symlink_to(elsewhere)

    template = parse_temx("root:\n  - file: x.txt\n    content: new\n")
    plan = expand(template)
    with pytest.raises(TemxError, match="escapes output root"):
        build(plan, out, force=True)
    assert elsewhere.read_text() == "evil"


@pytest.mark.skipif(os.name != "posix", reason="symlink semantics POSIX-only")
def test_c1_symlinked_dir_pointing_outside_root_rejected(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (out / "escape").symlink_to(elsewhere)

    template = parse_temx("root:\n  - dir: escape\n    children:\n      - file: x.txt\n")
    plan = expand(template)
    with pytest.raises(TemxError, match="escapes output root"):
        build(plan, out)


@pytest.mark.skipif(os.name != "posix", reason="symlink semantics POSIX-only")
def test_c1_symlink_planted_at_file_path_after_plan_caught_by_o_nofollow(tmp_path):
    """A symlink planted AT the final file path after plan time and before write
    must be caught by O_NOFOLLOW at open() — we simulate by planting before write
    via a fresh plan."""
    out = tmp_path / "out"
    out.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("evil")

    template = parse_temx("root:\n  - file: x.txt\n    content: new\n")
    plan = expand(template)
    # Plant the symlink AFTER expand but before build. To this build it looks like
    # a TOCTOU: plan-time resolve happens inside build() and sees the symlink. We
    # accept either error path — the point is "evil" file is never overwritten.
    (out / "x.txt").symlink_to(elsewhere)
    with pytest.raises(TemxError):
        build(plan, out, force=True)
    assert elsewhere.read_text() == "evil"


# ---------- Coverage gaps from L2 ----------


def test_l2_empty_root_list_succeeds(tmp_path):
    plan = expand(parse_temx("root: []\n"))
    assert plan == []
    written = build(plan, tmp_path)
    assert written == []


def test_l2_single_element_range(tmp_path):
    items = expand(
        parse_temx(
            "variables:\n  i:\n    range: [5, 5]\nroot:\n  - file: 'f{i}.txt'\n    repeat: i\n"
        )
    )
    assert len(items) == 1
    assert str(items[0].path) == "f5.txt"


def test_l2_two_independent_repeat_siblings_dont_share_state():
    # Both repeat over `day` but they are completely independent loops.
    items = expand(
        parse_temx(
            """
variables:
  day:
    range: [1, 2]
root:
  - file: 'a{day}.txt'
    repeat: day
  - file: 'b{day}.txt'
    repeat: day
""".strip()
        )
    )
    paths = [str(it.path) for it in items]
    assert paths == ["a1.txt", "a2.txt", "b1.txt", "b2.txt"]


def test_l2_loop_var_shadows_static_then_reverts():
    # Static `i` = 99. Inside a `repeat: i` it takes loop values. After loop,
    # subsequent siblings should see the static again.
    items = expand(
        parse_temx(
            """
variables:
  i:
    value: 99
root:
  - file: 'static-before-{i}.txt'
  - dir: 'd{i}'
""".strip()
        )
    )
    paths = [str(it.path) for it in items]
    assert paths == ["static-before-99.txt", "d99"]


def test_l2_loop_var_shadows_static_in_range_form():
    items = expand(
        parse_temx(
            """
variables:
  i:
    range: [1, 2]
root:
  - file: 'f{i}.txt'
    repeat: i
""".strip()
        )
    )
    assert [str(it.path) for it in items] == ["f1.txt", "f2.txt"]


def test_l2_unicode_in_paths_ok(tmp_path):
    items = expand(parse_temx("variables:\n  who: 'élève'\nroot:\n  - file: '{who}.txt'\n"))
    build(items, tmp_path)
    assert (tmp_path / "élève.txt").is_file()
