# templatexplorer

Build a nested directory tree from a declarative `.temx` template.

Think `cookiecutter` distilled to a single YAML file you can write by hand — useful
for project scaffolds, repetitive directory layouts (Advent of Code days, weekly
log folders, per-environment configs), or any time you'd otherwise `cp -r` and
hand-edit.

## Install

```bash
git clone https://github.com/<you>/templatexplorer.git
cd templatexplorer
pip install -e .          # or just: pip install pyyaml
```

## Use

```bash
python templatexplorer.py path/to/template.temx [--out DIR] [--var k=v ...] [--force] [--dry-run]
```

- **No `--out`** → builds into the current working directory.
- **`--var name=value`** → override a declared variable, or define a new one. Repeatable.
- **`--force`** → overwrite existing files at planned paths (existing directories are reused either way).
- **`--dry-run`** → validate + print the planned tree without touching disk.

Exit codes: `0` on success, `1` on any template/build error, `2` on argparse misuse.

## `.temx` format

YAML with two top-level keys:

```yaml
variables:        # optional
  <name>: <spec>
  ...

root:             # required: a list of nodes
  - <node>
  ...
```

### Variables

Three forms, one per variable:

| Form | YAML | Use case |
|---|---|---|
| Static value | `year: 2026` *(shorthand)* or `year: { value: 2026 }` | Constant used in names/contents. |
| Integer range | `day: { range: [1, 25] }` | Both ends **inclusive**. |
| List | `env: { list: [dev, staging, prod] }` | Replicate over arbitrary values. |

Variable names must be valid Python identifiers.

### Nodes

Every node is either a directory or a file:

```yaml
- dir: <name>          # directory node
  repeat: <varname>    # optional: replicate this dir once per value of <varname>
  children:            # optional: nested nodes
    - ...

- file: <name>         # file node
  repeat: <varname>    # optional
  content: |           # optional: file body (defaults to empty)
    ...
```

A node may declare exactly one of `dir`/`file`. A `dir` may have `children`; a
`file` may have `content`. Both may have `repeat`.

### Variable substitution

Names and file contents use Python `str.format()` syntax. Format specifiers work
the way you'd expect:

```yaml
- file: "day{day:02d}.py"   # day01.py, day02.py, …
  repeat: day
  content: |
    DAY = {day}
```

To write a literal `{` or `}`, double it: `{{` / `}}`.

### Scoping

Static variables are always in scope. Loop variables (introduced by `repeat:`)
are in scope only inside that node and its descendants. After the loop, the
variable is no longer defined — a sibling node trying to reference it will error.

Loops nest naturally: an inner `repeat` sees its outer loop's variable.

```yaml
variables:
  week: { range: [1, 4] }
  day:  { range: [1, 7] }

root:
  - dir: "week-{week}"
    repeat: week
    children:
      - file: "day-{day}-of-week-{week}.md"
        repeat: day
```

### CLI overrides

`--var name=value` either overrides a declared variable or defines a new one.
Overriding a `range`- or `list`-typed variable collapses its loop to that single
value (handy for `--var day=07` to scaffold only day 7).

Integer-typed variables (range or `int` static) coerce override strings to int
before formatting, so `{day:02d}` still works.

## Example: Advent of Code scaffold

```bash
python templatexplorer.py examples/aoc.temx --var year=2026
```

Produces:

```
advent-of-code-2026/
├── README.md
├── solve.py
├── days/
│   ├── __init__.py
│   ├── day01.py
│   ├── …
│   └── day25.py
└── inputs/
    ├── .gitkeep
    ├── day01.txt
    ├── day01_test.txt
    ├── …
    └── day25_test.txt
```

See `examples/aoc.temx` for the template.

## Safety

- Names that render to `..`, `.`, contain a path separator, or are empty are rejected.
- Output paths are checked for containment under `--out` after resolution.
- Without `--force`, an existing file at a planned target aborts the whole build
  before any change is made (atomic-ish: either all-or-nothing at the planning layer).

## Tests

```bash
python -m pytest -q
```
