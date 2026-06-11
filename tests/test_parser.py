import pytest

from templatexplorer import TemxError, parse_temx


def test_minimal_template():
    t = parse_temx("root:\n  - file: hello.txt\n")
    assert t.variables == {}
    assert len(t.root) == 1
    assert t.root[0].kind == "file"
    assert t.root[0].name == "hello.txt"
    assert t.root[0].content == ""


def test_empty_file_errors():
    with pytest.raises(TemxError, match="empty"):
        parse_temx("")


def test_top_level_must_be_mapping():
    with pytest.raises(TemxError, match="top level"):
        parse_temx("- a\n- b\n")


def test_unknown_top_level_key():
    with pytest.raises(TemxError, match="unknown top-level keys"):
        parse_temx("root: []\nbogus: 1\n")


def test_missing_root():
    with pytest.raises(TemxError, match="missing required key 'root'"):
        parse_temx("variables: {}\n")


def test_root_must_be_list():
    with pytest.raises(TemxError, match="must be a list"):
        parse_temx("root: not-a-list\n")


def test_variable_shorthand_value():
    t = parse_temx("variables:\n  year: 2019\nroot: []\n")
    assert t.variables["year"].value == 2019


def test_variable_explicit_value():
    t = parse_temx("variables:\n  year:\n    value: 2019\nroot: []\n")
    assert t.variables["year"].value == 2019


def test_variable_range():
    t = parse_temx("variables:\n  day:\n    range: [1, 25]\nroot: []\n")
    assert t.variables["day"].range == (1, 25)
    assert t.variables["day"].values() == list(range(1, 26))


def test_variable_list():
    t = parse_temx("variables:\n  env:\n    list: [dev, prod]\nroot: []\n")
    assert t.variables["env"].list == ("dev", "prod")
    assert t.variables["env"].values() == ["dev", "prod"]


def test_variable_multiple_forms_rejected():
    with pytest.raises(TemxError, match="exactly one of"):
        parse_temx("variables:\n  x:\n    value: 1\n    range: [1, 2]\nroot: []\n")


def test_variable_unknown_key():
    with pytest.raises(TemxError, match="unknown keys"):
        parse_temx("variables:\n  x:\n    bogus: 1\nroot: []\n")


def test_variable_range_must_be_int_pair():
    with pytest.raises(TemxError, match="range must be"):
        parse_temx("variables:\n  x:\n    range: [1.0, 2.0]\nroot: []\n")


def test_variable_range_start_gt_end():
    with pytest.raises(TemxError, match="greater than"):
        parse_temx("variables:\n  x:\n    range: [5, 3]\nroot: []\n")


def test_variable_empty_list_rejected():
    with pytest.raises(TemxError, match="must not be empty"):
        parse_temx("variables:\n  x:\n    list: []\nroot: []\n")


def test_variable_invalid_identifier():
    with pytest.raises(TemxError, match="not a valid identifier"):
        parse_temx("variables:\n  '1bad': 1\nroot: []\n")


def test_node_requires_dir_or_file():
    with pytest.raises(TemxError, match="exactly one of 'dir' or 'file'"):
        parse_temx("root:\n  - name: x\n")


def test_node_cannot_have_both_dir_and_file():
    with pytest.raises(TemxError, match="exactly one of 'dir' or 'file'"):
        parse_temx("root:\n  - dir: a\n    file: b\n")


def test_dir_node_unknown_key_rejected():
    with pytest.raises(TemxError, match="unknown keys"):
        parse_temx("root:\n  - dir: a\n    content: nope\n")


def test_file_node_unknown_key_rejected():
    with pytest.raises(TemxError, match="unknown keys"):
        parse_temx("root:\n  - file: a\n    children: []\n")


def test_repeat_must_reference_declared_var():
    with pytest.raises(TemxError, match="undefined variable"):
        parse_temx("root:\n  - dir: d\n    repeat: missing\n")


def test_repeat_known_var_ok():
    t = parse_temx(
        "variables:\n  i:\n    range: [1, 3]\nroot:\n  - dir: 'd{i}'\n    repeat: i\n"
    )
    assert t.root[0].repeat == "i"


def test_file_content_must_be_string():
    with pytest.raises(TemxError, match="must be a string"):
        parse_temx("root:\n  - file: a\n    content: 123\n")


def test_repeat_must_be_string():
    with pytest.raises(TemxError, match="must be a string variable name"):
        parse_temx("variables:\n  i: 1\nroot:\n  - dir: d\n    repeat: 1\n")


def test_dir_name_must_be_non_empty():
    with pytest.raises(TemxError, match="non-empty string"):
        parse_temx("root:\n  - dir: ''\n")


def test_yaml_syntax_error_surfaced():
    with pytest.raises(TemxError, match="YAML syntax error"):
        parse_temx("root:\n  - dir: [unterminated\n")
