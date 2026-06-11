"""CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .builder import build
from .errors import TemxError
from .expander import expand
from .parser import parse_temx


def _parse_var_assignment(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"--var expects name=value, got {raw!r}")
    name, value = raw.split("=", 1)
    name = name.strip()
    if not name.isidentifier():
        raise argparse.ArgumentTypeError(f"--var name {name!r} is not a valid identifier")
    return name, value


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="templatexplorer",
        description="Build a nested directory tree from a .temx template.",
    )
    p.add_argument("template", type=Path, help="Path to the .temx YAML file")
    p.add_argument(
        "--out", type=Path, default=Path.cwd(),
        help="Output root directory (default: current working directory)",
    )
    p.add_argument(
        "--var", dest="vars", action="append", default=[], type=_parse_var_assignment, metavar="NAME=VALUE",
        help="Override or define a template variable. Repeatable.",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files at target paths.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Validate and print the planned tree without writing anything.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    overrides: dict[str, str] = {}
    for name, value in args.vars:
        overrides[name] = value

    try:
        template = parse_temx(args.template)
        plan = expand(template, overrides=overrides)
        written = build(plan, args.out, force=args.force, dry_run=args.dry_run)
    except TemxError as exc:
        print(f"templatexplorer: error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Plan ({len(plan)} item(s)) — dry run, nothing written:")
        for item in plan:
            tag = "[dir] " if item.kind == "dir" else "[file]"
            print(f"  {tag} {item.path}")
    else:
        print(f"Wrote {len(written)} item(s) under {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
