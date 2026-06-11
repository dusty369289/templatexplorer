"""Expand a parsed Template into a flat list of plan items."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from .errors import TemxError
from .parser import Node, Template, Variable


@dataclass(frozen=True)
class PlanItem:
    kind: str  # 'dir' or 'file'
    path: PurePosixPath  # relative, posix-style; builder maps to OS sep
    content: str | None = None


def expand(template: Template, overrides: dict[str, str] | None = None) -> list[PlanItem]:
    """Walk the template AST and produce a concrete plan.

    `overrides` maps variable names to string values (typically from CLI --var).
    An override of an undeclared variable becomes a static variable.
    An override of a declared variable replaces its value(s) with the single string.
    """
    overrides = overrides or {}
    base_ctx: dict[str, object] = {}
    for name, var in template.variables.items():
        if name in overrides:
            base_ctx[name] = _coerce_override(var, overrides[name])
        elif var.range is None and var.list is None:
            base_ctx[name] = var.value
    # Overrides for vars not declared at all: treat as plain strings.
    for name, raw in overrides.items():
        if name not in template.variables:
            base_ctx[name] = raw

    plan: list[PlanItem] = []
    for node in template.root:
        _expand_node(node, parent=PurePosixPath(), ctx=base_ctx, template=template, overrides=overrides, out=plan)
    return plan


def _coerce_override(var: Variable, raw: str) -> object:
    """If the declared variable is an int (range or int value), try to parse the override as int."""
    if var.range is not None:
        try:
            return int(raw)
        except ValueError:
            return raw
    if var.value is not None and isinstance(var.value, int) and not isinstance(var.value, bool):
        try:
            return int(raw)
        except ValueError:
            return raw
    return raw


def _expand_node(
    node: Node,
    parent: PurePosixPath,
    ctx: dict[str, object],
    template: Template,
    overrides: dict[str, str],
    out: list[PlanItem],
) -> None:
    iter_values = _resolve_iter(node, template, overrides)
    for value in iter_values:
        child_ctx = ctx if value is _NO_VALUE else {**ctx, node.repeat: value}  # type: ignore[dict-item]
        rendered_name = _render(node.name, child_ctx, where=f"{node.kind} name {node.name!r}")
        _check_name(rendered_name, where=f"{node.kind} name {node.name!r}")
        here = parent / rendered_name

        if node.kind == "dir":
            out.append(PlanItem(kind="dir", path=here))
            for ch in node.children:
                _expand_node(ch, parent=here, ctx=child_ctx, template=template, overrides=overrides, out=out)
        else:
            content = _render(node.content or "", child_ctx, where=f"file {node.name!r} content")
            out.append(PlanItem(kind="file", path=here, content=content))


_NO_VALUE = object()


def _resolve_iter(node: Node, template: Template, overrides: dict[str, str]) -> list[object]:
    if node.repeat is None:
        return [_NO_VALUE]
    var = template.variables.get(node.repeat)
    if var is None:
        # Should never happen — parser rejects unknown repeat — but defensive for overrides-only vars.
        raise TemxError(f"'repeat' references undefined variable {node.repeat!r}")
    if node.repeat in overrides:
        # Override collapses a loop to a single value.
        return [_coerce_override(var, overrides[node.repeat])]
    return var.values()


def _render(template_str: str, ctx: dict[str, object], *, where: str) -> str:
    try:
        return template_str.format(**ctx)
    except KeyError as exc:
        missing = exc.args[0]
        raise TemxError(f"{where}: undefined variable {missing!r} (available: {sorted(ctx) or 'none'})") from exc
    except (IndexError, ValueError) as exc:
        raise TemxError(f"{where}: format error: {exc}") from exc


_FORBIDDEN_NAME_CHARS = set("/\\\0")


def _check_name(name: str, *, where: str) -> None:
    if not name:
        raise TemxError(f"{where}: rendered to an empty string")
    if name in (".", ".."):
        raise TemxError(f"{where}: rendered to {name!r}, which would escape the output tree")
    if any(c in _FORBIDDEN_NAME_CHARS for c in name):
        raise TemxError(
            f"{where}: rendered to {name!r}, which contains a path separator or null byte"
        )
