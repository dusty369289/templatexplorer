# templatexplorer

> Build a nested directory tree from a single YAML template.

You write a `.temx` file describing the tree, the variables, and any
repetition. `templatexplorer` materialises it on disk.

A `.temx` is short enough to read at a glance and powerful enough to handle
real scaffolds: per-module directories, env × region config matrices, a year
of weekly journal files, a Python package with its `src/` and `tests/`
folders pre-wired — anything where the answer to "how do I make this?" is
"like that one I already made, but with these names changed".

---

## Install

The only runtime dependency is `PyYAML`. Python 3.10+.

```bash
git clone https://github.com/<you>/templatexplorer.git
cd templatexplorer
pip install pyyaml         # or: pip install -e .
python templatexplorer.py --help
```

## A 30-second walkthrough

```yaml
# greet.temx — say hello to a list of people, each in their own folder.
variables:
  greeting:
    value: "Hello"
  who:
    list: [alice, bob, carol]

root:
  - dir: "greetings"
    children:
      - dir: "{who}"
        repeat: who
        children:
          - file: "message.txt"
            content: |
              {greeting}, {who}!
```

```bash
$ python templatexplorer.py greet.temx
Wrote 7 item(s) under /current/dir
$ tree greetings
greetings/
├── alice/   └── message.txt        # "Hello, alice!"
├── bob/     └── message.txt        # "Hello, bob!"
└── carol/   └── message.txt        # "Hello, carol!"
```

That's the whole concept: `variables` declare the things that change,
`root` describes the tree, `repeat:` replicates a subtree per value,
`{name}` interpolates.

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

## Examples

The `examples/` directory ships seven ready-to-use templates. Each starts
with a comment describing what it builds and how to invoke it.

| Template | What it builds | Key features shown |
|---|---|---|
| `python-package.temx` | A `src/` + `tests/` Python package with `pyproject.toml`, README, LICENSE | Static variables, multiline content |
| `weekly-journal.temx` | 52 dated markdown notes (`week-01.md` … `week-52.md`) | Integer range, zero-padding format spec |
| `multi-env-config.temx` | Per-env × per-region config matrix (3 × 3 = 9 leaf configs) | Two nested `list` loops |
| `monorepo-services.temx` | Multiple microservices, each with Dockerfile/src/tests | `list:` variable over names |
| `react-components.temx` | A set of React components, each in its own folder (tsx + test + css) | `list:` over component names |
| `course-modules.temx` | N modules each with notes, slides, exercises, quiz | Nested `range:` loops |
| `blog-posts.temx` | A year of post stubs in month folders | Format specs in folder names |
| `aoc-scaffold.temx` | One folder per Advent of Code day, with input/test files and a stub solver | Loop + content substitution |

Run any of them:

```bash
python templatexplorer.py examples/weekly-journal.temx --var year=2026
python templatexplorer.py examples/python-package.temx --var pkg=widget
python templatexplorer.py examples/multi-env-config.temx --out ./infra
```

## Format reference

The exhaustive spec — every rule, every edge case, the grammar, the error
catalogue, the cookbook — lives in [`docs/TEMX.md`](docs/TEMX.md). Read it
once and you'll know the format.

Quick mental model:

```yaml
variables:        # optional: declare the parts that change
  name: <spec>    # static value, integer range, or list

root:             # required: a list of dir/file nodes
  - dir: <name>
    repeat: <var> # optional: replicate per value
    children:     # nested nodes
      - ...
  - file: <name>
    content: |    # optional file body
      ...
```

- **`{name}`** in any name or content substitutes the variable.
- **`{day:02d}`** etc. — full Python format-spec support.
- **`{{` / `}}`** — literal braces.
- Names that resolve to `..`, `.`, contain a path separator, or are blank
  are rejected before any disk action.

## Safety

- Names rendering to `..`, `.`, blanks, or path separators are rejected.
- Targets are checked to stay inside `--out` after `Path.resolve()`,
  defending against symlink escapes.
- Symlinks at planned paths are treated as collisions even with `--force`;
  `O_NOFOLLOW` ensures writes can't follow a planted symlink mid-build.
- Without `--force`, a single existing file at a planned target aborts the
  whole build — no half-written trees.
- Attribute (`{x.attr}`) and index (`{x[0]}`) access in templates is
  rejected at expand time to prevent leaking Python internals.

## Testing

```bash
python -m pytest -q
```

Over 120 tests covering the parser, expander, builder, CLI, every shipped
example, and an explicit regression suite for every finding from the
project's senior code review (so any future drift fails loudly).

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
examples/*.temx               # ready-to-use templates (see table above)
tests/                        # pytest suite
```

## Status

Pre-1.0. Format is stable enough to use; incompatible changes will be called
out in the changelog.

## License

MIT.
