import pytest

from templatexplorer import TemxError, expand, parse_temx


def _expand(src: str, overrides=None):
    return expand(parse_temx(src), overrides=overrides or {})


def test_single_file_no_vars():
    items = _expand("root:\n  - file: hello.txt\n    content: hi\n")
    assert len(items) == 1
    assert items[0].kind == "file"
    assert str(items[0].path) == "hello.txt"
    assert items[0].content == "hi"


def test_empty_dir():
    items = _expand("root:\n  - dir: empty\n")
    assert len(items) == 1
    assert items[0].kind == "dir"
    assert str(items[0].path) == "empty"


def test_static_variable_substituted_in_name_and_content():
    items = _expand(
        "variables:\n  name: world\n"
        "root:\n  - file: 'greet_{name}.txt'\n    content: 'hello, {name}!'\n"
    )
    assert str(items[0].path) == "greet_world.txt"
    assert items[0].content == "hello, world!"


def test_range_loop_on_file():
    items = _expand(
        "variables:\n  i:\n    range: [1, 3]\n"
        "root:\n  - file: 'f{i}.txt'\n    repeat: i\n"
    )
    paths = [str(it.path) for it in items]
    assert paths == ["f1.txt", "f2.txt", "f3.txt"]


def test_range_loop_with_format_spec():
    items = _expand(
        "variables:\n  day:\n    range: [1, 3]\n"
        "root:\n  - file: 'day{day:02d}.txt'\n    repeat: day\n"
    )
    assert [str(it.path) for it in items] == ["day01.txt", "day02.txt", "day03.txt"]


def test_list_loop():
    items = _expand(
        "variables:\n  env:\n    list: [dev, staging, prod]\n"
        "root:\n  - dir: '{env}'\n    repeat: env\n"
    )
    assert [str(it.path) for it in items] == ["dev", "staging", "prod"]


def test_nested_loops_outer_visible_inside():
    items = _expand(
        """
variables:
  week:
    range: [1, 2]
  day:
    range: [1, 3]
root:
  - dir: 'week{week}'
    repeat: week
    children:
      - file: 'day{day}_in_week{week}.txt'
        repeat: day
""".strip()
    )
    files = [str(it.path) for it in items if it.kind == "file"]
    assert files == [
        "week1/day1_in_week1.txt",
        "week1/day2_in_week1.txt",
        "week1/day3_in_week1.txt",
        "week2/day1_in_week2.txt",
        "week2/day2_in_week2.txt",
        "week2/day3_in_week2.txt",
    ]


def test_undefined_variable_in_template_errors():
    with pytest.raises(TemxError, match="undefined variable 'who'"):
        _expand("root:\n  - file: '{who}.txt'\n")


def test_cli_override_of_declared_value():
    items = _expand(
        "variables:\n  name: alice\nroot:\n  - file: '{name}.txt'\n",
        overrides={"name": "bob"},
    )
    assert str(items[0].path) == "bob.txt"


def test_cli_override_of_undeclared_var():
    items = _expand(
        "root:\n  - file: '{project}.txt'\n",
        overrides={"project": "myapp"},
    )
    assert str(items[0].path) == "myapp.txt"


def test_cli_override_collapses_loop_to_single_value():
    items = _expand(
        "variables:\n  day:\n    range: [1, 25]\n"
        "root:\n  - file: 'day{day:02d}.txt'\n    repeat: day\n",
        overrides={"day": "7"},
    )
    assert len(items) == 1
    assert str(items[0].path) == "day07.txt"


def test_cli_override_of_int_range_coerces_to_int():
    items = _expand(
        "variables:\n  day:\n    range: [1, 25]\n"
        "root:\n  - file: 'day{day:02d}.txt'\n    repeat: day\n",
        overrides={"day": "12"},
    )
    assert str(items[0].path) == "day12.txt"


def test_path_traversal_in_rendered_name_rejected():
    with pytest.raises(TemxError, match="path separator"):
        _expand(
            "variables:\n  name:\n    value: 'a/b'\nroot:\n  - file: '{name}.txt'\n"
        )


def test_double_dot_in_rendered_name_rejected():
    with pytest.raises(TemxError, match="escape"):
        _expand("variables:\n  name: '..'\nroot:\n  - dir: '{name}'\n")


def test_empty_rendered_name_rejected():
    with pytest.raises(TemxError, match="empty"):
        _expand("variables:\n  name: ''\nroot:\n  - file: '{name}'\n")


def test_static_variable_does_not_need_repeat():
    items = _expand(
        "variables:\n  year: 2026\nroot:\n  - dir: 'proj-{year}'\n"
    )
    assert str(items[0].path) == "proj-2026"


def test_dir_with_children_gets_dir_then_children():
    items = _expand(
        """
root:
  - dir: outer
    children:
      - file: a.txt
      - dir: inner
        children:
          - file: b.txt
""".strip()
    )
    paths = [(it.kind, str(it.path)) for it in items]
    assert paths == [
        ("dir", "outer"),
        ("file", "outer/a.txt"),
        ("dir", "outer/inner"),
        ("file", "outer/inner/b.txt"),
    ]


def test_loop_variable_does_not_leak_outside_scope():
    # After a `repeat: i` finishes, sibling nodes must not see `i`.
    with pytest.raises(TemxError, match="undefined variable 'i'"):
        _expand(
            """
variables:
  i:
    range: [1, 2]
root:
  - dir: 'd{i}'
    repeat: i
  - file: 'after-{i}.txt'
""".strip()
        )
