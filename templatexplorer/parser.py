"""Parse a .temx YAML file into a validated AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import TemxError


@dataclass(frozen=True)
class Variable:
    name: str
    # Exactly one of these is set.
    value: Any = None
    range: tuple[int, int] | None = None
    list: tuple[Any, ...] | None = None

    def values(self) -> list[Any]:
        if self.range is not None:
            lo, hi = self.range
            return list(range(lo, hi + 1))
        if self.list is not None:
            return list(self.list)
        return [self.value]


@dataclass(frozen=True)
class Node:
    kind: str  # 'dir' or 'file'
    name: str
    repeat: str | None = None
    children: tuple["Node", ...] = ()
    content: str | None = None  # only meaningful for files


@dataclass(frozen=True)
class Template:
    variables: dict[str, Variable]
    root: tuple[Node, ...]


_RESERVED_VAR_NAMES = {"true", "false", "null", "yes", "no"}


def parse_temx(source: str | Path) -> Template:
    """Parse a .temx YAML document (string or path) into a Template."""
    if isinstance(source, Path):
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise TemxError(f"Could not read template file {source}: {exc}") from exc
        where = str(source)
    else:
        text = source
        where = "<string>"

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TemxError(f"YAML syntax error in {where}: {exc}") from exc

    if data is None:
        raise TemxError(f"{where} is empty")
    if not isinstance(data, dict):
        raise TemxError(f"{where}: top level must be a mapping, got {type(data).__name__}")

    allowed_top = {"variables", "root"}
    extra = set(data) - allowed_top
    if extra:
        raise TemxError(f"{where}: unknown top-level keys: {sorted(extra)}")

    variables = _parse_variables(data.get("variables") or {}, where)

    root_raw = data.get("root")
    if root_raw is None:
        raise TemxError(f"{where}: missing required key 'root'")
    if not isinstance(root_raw, list):
        raise TemxError(f"{where}: 'root' must be a list of nodes")

    root_nodes = tuple(_parse_node(item, where, path="root", defined_vars=set(variables)) for item in root_raw)
    return Template(variables=variables, root=root_nodes)


def _parse_variables(raw: Any, where: str) -> dict[str, Variable]:
    if not isinstance(raw, dict):
        raise TemxError(f"{where}: 'variables' must be a mapping")
    out: dict[str, Variable] = {}
    for name, spec in raw.items():
        if not isinstance(name, str) or not name:
            raise TemxError(f"{where}: variable name must be a non-empty string, got {name!r}")
        if not name.isidentifier():
            raise TemxError(
                f"{where}: variable name {name!r} is not a valid identifier (letters, digits, underscore; not starting with digit)"
            )
        if name in _RESERVED_VAR_NAMES:
            raise TemxError(f"{where}: variable name {name!r} is reserved")
        out[name] = _parse_variable_spec(name, spec, where)
    return out


def _parse_variable_spec(name: str, spec: Any, where: str) -> Variable:
    # Shorthand: plain scalar means a static value.
    if not isinstance(spec, dict):
        return Variable(name=name, value=spec)

    keys = set(spec)
    allowed = {"value", "range", "list"}
    extra = keys - allowed
    if extra:
        raise TemxError(f"{where}: variable {name!r} has unknown keys: {sorted(extra)}")
    forms = keys & allowed
    if len(forms) != 1:
        raise TemxError(
            f"{where}: variable {name!r} must declare exactly one of value/range/list, got {sorted(forms) or 'none'}"
        )
    form = forms.pop()

    if form == "value":
        return Variable(name=name, value=spec["value"])
    if form == "range":
        r = spec["range"]
        if not (isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in r)):
            raise TemxError(f"{where}: variable {name!r} range must be [int, int], got {r!r}")
        lo, hi = r
        if lo > hi:
            raise TemxError(f"{where}: variable {name!r} range start ({lo}) is greater than end ({hi})")
        return Variable(name=name, range=(lo, hi))
    # list
    lst = spec["list"]
    if not isinstance(lst, list):
        raise TemxError(f"{where}: variable {name!r} 'list' must be a list, got {type(lst).__name__}")
    if not lst:
        raise TemxError(f"{where}: variable {name!r} 'list' must not be empty")
    return Variable(name=name, list=tuple(lst))


def _parse_node(raw: Any, where: str, path: str, defined_vars: set[str]) -> Node:
    if not isinstance(raw, dict):
        raise TemxError(f"{where}:{path}: node must be a mapping, got {type(raw).__name__}")

    has_dir = "dir" in raw
    has_file = "file" in raw
    if has_dir == has_file:
        raise TemxError(f"{where}:{path}: node must declare exactly one of 'dir' or 'file'")

    kind = "dir" if has_dir else "file"
    name = raw["dir"] if has_dir else raw["file"]
    if not isinstance(name, str) or not name:
        raise TemxError(f"{where}:{path}: {kind} name must be a non-empty string, got {name!r}")

    allowed = {"dir", "children"} if kind == "dir" else {"file", "content"}
    allowed.add("repeat")
    extra = set(raw) - allowed
    if extra:
        raise TemxError(f"{where}:{path}: unknown keys for {kind} node: {sorted(extra)}")

    repeat = raw.get("repeat")
    if repeat is not None:
        if not isinstance(repeat, str):
            raise TemxError(f"{where}:{path}: 'repeat' must be a string variable name, got {repeat!r}")
        if repeat not in defined_vars:
            raise TemxError(
                f"{where}:{path}: 'repeat' references undefined variable {repeat!r}. "
                f"Defined: {sorted(defined_vars) or 'none'}"
            )

    children: tuple[Node, ...] = ()
    if kind == "dir":
        ch_raw = raw.get("children") or []
        if not isinstance(ch_raw, list):
            raise TemxError(f"{where}:{path}: 'children' must be a list")
        children = tuple(
            _parse_node(item, where, path=f"{path}/{name}[{i}]", defined_vars=defined_vars)
            for i, item in enumerate(ch_raw)
        )

    content = None
    if kind == "file":
        content = raw.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            raise TemxError(f"{where}:{path}: file 'content' must be a string, got {type(content).__name__}")

    return Node(kind=kind, name=name, repeat=repeat, children=children, content=content)
