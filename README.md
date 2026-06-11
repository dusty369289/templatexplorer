# templatexplorer

> Build a nested directory tree from a single YAML template. Like
> `cookiecutter`, but tiny, declarative, and YAML-only.

You write a `.temx` file describing the tree, the variables, and any
repetition. `templatexplorer` materialises it.

```bash
python templatexplorer.py examples/aoc.temx --var year=2022
```

…produces:

```
aoc-2022/
├── Day 1/
│   ├── input.txt
│   ├── input_test.txt
│   └── main.py
├── Day 2/
│   ├── input.txt
│   ├── input_test.txt
│   └── main.py
... (25 days total)
└── Day 25/
    ├── input.txt
    ├── input_test.txt
    └── main.py
```

…where each `main.py` is a fresh solver stub with the day number baked into
its input-file paths.

---

## When this is useful

- **Advent of Code** — scaffold all 25 days in one command.
- **Weekly / per-environment / per-region layouts** — anything that's "the
  same N times with one thing changing".
- **Project starters** — a single readable YAML beats a Python `cookiecutter`
  template for small scaffolds.
- **Replacing `cp -r && rename`** — when you'd otherwise duplicate a folder
  and hand-edit the names and contents inside.

If you want hooks, Jinja conditionals, post-build scripts — pick a heavier
tool. This is intentionally small.

## Install

Just clone and run. The only runtime dependency is `PyYAML`.

```bash
git clone https://github.com/<you>/templatexplorer.git
cd templatexplorer
pip install pyyaml      # or: pip install -e .
python templatexplorer.py --help
```

Python 3.10+.

## CLI

```
python templatexplorer.py TEMPLATE [--out DIR] [--var NAME=VALUE]... [--force] [--dry-run]
```

| Flag | Default | Effect |
|---|---|---|
| `TEMPLATE` | — | Required. Path to a `.temx` file. |
| `--out DIR` | current directory | Where the tree is built. |
| `--var NAME=VALUE` | none | Override a declared variable, or define a new one. Repeatable. |
| `--force` | off | Overwrite existing files at planned paths. |
| `--dry-run` | off | Validate + print the plan without writing anything. |

Exit codes: `0` success, `1` template or build error (`stderr` has the
message), `2` argparse misuse.

## A 30-second `.temx` walkthrough

```yaml
variables:
  year: { value: 2026 }       # static — substituted anywhere {year} appears
  day:  { range: [1, 25] }    # loop variable — inclusive both ends

root:
  - dir: "aoc-{year}"
    children:
      - dir: "Day {day}"
        repeat: day            # replicate this dir for each day in 1..25
        children:
          - file: input.txt    # empty file
          - file: main.py
            content: |
              # solver for day {day} of {year}
              ...
```

Two top-level keys:
- `variables` — name → spec. Three forms: `value:` (static), `range: [a, b]`
  (inclusive int range), `list: [...]` (any).
- `root` — a list of nodes. Each node is either a `dir:` (may have `children:`)
  or a `file:` (may have `content:`). Either may have `repeat: <varname>` to
  replicate the subtree.

Names and contents use **Python format-string syntax**: `{day}`, `{day:02d}`,
escape literal braces with `{{` / `}}`.

The **full spec** — every rule, every edge case, the grammar, the error
catalogue, and more examples — lives in [`docs/TEMX.md`](docs/TEMX.md). Read
it once and you'll know the format.

## Safety

- Rendered names that resolve to `..`, `.`, or contain path separators are
  rejected before any disk action.
- Output targets are checked to stay inside `--out` after `Path.resolve()`,
  defending against symlink escapes.
- Without `--force`, a single existing file at a planned target aborts the
  entire build — you don't get a half-written tree.

## Testing

```bash
python -m pytest -q
```

Currently 92 tests covering the parser, expander, builder, CLI, and an
end-to-end build of the bundled AoC example. Includes a dedicated suite of
regressions for findings from the senior code review.

## Layout

```
templatexplorer.py            # entry-point shim
templatexplorer/              # package
  parser.py                   # YAML → AST (Variable, Node, Template)
  expander.py                 # AST → flat list of PlanItem(kind, path, content)
  builder.py                  # apply PlanItem list to filesystem
  cli.py                      # argparse front door
  errors.py                   # TemxError
docs/TEMX.md                  # full format specification
examples/aoc.temx             # the 2022-style AoC scaffold
tests/                        # pytest suite
```

## Status

Pre-1.0. Format is stable enough to use; if it changes incompatibly it'll be
called out in the changelog.

## License

MIT.
