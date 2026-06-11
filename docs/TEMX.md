# The `.temx` format

A `.temx` file is a YAML document that declares a tree of directories and files to
materialise on disk, parameterised by variables and loops. This document is the
authoritative specification of the format and its evaluation semantics.

> Audience: people writing `.temx` files by hand and people implementing
> tooling against them.

## Contents
1. [Schema overview](#1-schema-overview)
2. [Variables](#2-variables)
3. [Nodes](#3-nodes)
4. [Variable substitution](#4-variable-substitution)
5. [Loops and scoping](#5-loops-and-scoping)
6. [CLI overrides](#6-cli-overrides)
7. [Path safety](#7-path-safety)
8. [Collisions and atomicity](#8-collisions-and-atomicity)
9. [Encoding and platform notes](#9-encoding-and-platform-notes)
10. [Grammar summary](#10-grammar-summary)
11. [Worked examples](#11-worked-examples)
12. [Error catalogue](#12-error-catalogue)
13. [Cookbook](#13-cookbook)

---

## 1. Schema overview

The document is a YAML mapping with exactly two recognised top-level keys:

```yaml
variables:        # OPTIONAL — maps name -> spec
  ...

root:             # REQUIRED — list of nodes
  - ...
```

- Any other top-level key is a hard error.
- `root` must be present even if empty (`root: []`).
- `variables` defaults to `{}` when omitted.

## 2. Variables

A variable has a **name** (valid Python identifier) and a **spec**. There are
three spec forms; each variable picks exactly one.

| Form | Example | Type emitted | Iterable? |
|---|---|---|---|
| **Static value (shorthand)** | `year: 2026` | The YAML scalar verbatim | No |
| **Static value (explicit)** | `year: { value: 2026 }` | Same as above | No |
| **Integer range** | `day: { range: [1, 25] }` | `int` (inclusive both ends) | Yes |
| **List** | `env: { list: [dev, prod] }` | YAML items verbatim | Yes |

Constraints:
- Name must be a valid Python identifier (regex `[A-Za-z_][A-Za-z0-9_]*`) and not
  one of `true`, `false`, `null`, `yes`, `no`.
- `value` / `range` / `list` are mutually exclusive — declaring more than one is
  an error.
- `range` must be `[int, int]` with `start <= end`. **Both ends are inclusive**:
  `range: [1, 3]` yields `1, 2, 3`. Booleans are not accepted as ints.
- `list` must be non-empty.

### Shorthand sugar

If a variable's spec is a plain YAML scalar (`year: 2026`, `name: alice`),
it is treated as `{ value: <scalar> }`. Anything else (mapping, list) must use
explicit form.

> The shorthand `flag: true` becomes a `bool` static value. Whether you can use
> `bool` in a format string is up to Python's format machinery — usually you
> can (`{flag}` renders `"True"`), but `{flag:02d}` would error. Prefer explicit
> typing for anything you'll format with specifiers.

> **`value: null` is rejected.** A null variable would silently render as the
> literal string `"None"`, which is almost never what's intended. Use `value: ''`
> (empty string) or drop the variable.

## 3. Nodes

A node is either a **directory** or a **file**:

```yaml
- dir: <name>          # directory node
  repeat: <varname>    # OPTIONAL — replicate this dir per value of <varname>
  children:            # OPTIONAL — list of nested nodes (default: [])
    - ...

- file: <name>         # file node
  repeat: <varname>    # OPTIONAL
  content: |           # OPTIONAL — file body (default: empty string)
    ...
```

Rules:
- Exactly one of `dir` or `file` per node.
- `dir` nodes may have `children` but never `content`.
- `file` nodes may have `content` but never `children`.
- Any other key on either kind is an error.
- `name` must be a non-empty string.
- `repeat` must reference a variable declared in the `variables` block. (CLI
  overrides do not retroactively define variables for the purpose of `repeat`.)

Files with `content` omitted are created as empty zero-byte files. This is
useful for placeholders like `input.txt` or `.gitkeep`.

## 4. Variable substitution

Names and file contents are Python format strings. They are rendered with
`str.format()` against the active variable context.

```yaml
- file: "day{day:02d}.py"
  repeat: day
  content: |
    DAY = {day}
    YEAR = {year}
```

Supported:
- Simple field replacement: `{name}`
- Format specifiers: `{day:02d}`, `{pct:.2%}`, `{name:>10}`, etc.
- Literal braces by doubling: `{{` and `}}`.

Not supported (rejected at expand time):
- **Attribute access** (`{x.foo}`) — would leak Python object internals.
- **Index access** (`{x[0]}`) — would let templates dig into list/dict values.

If a `{name}` reference does not match any in-scope variable, expansion fails
with an error listing the available names.

## 5. Loops and scoping

A node with `repeat: <var>` is materialised once per value of `<var>`. During
each iteration the loop variable is bound to its current value and made
available to:

- the node's own `dir`/`file` name string,
- the node's `content` (for files),
- all of the node's descendant nodes.

After the loop completes, the variable is **no longer in scope**. A sibling node
that tries to reference it will error.

### Static variables are always in scope

Statically declared variables (`value:` form, or shorthand scalar) are visible
to every node from root to leaf. Use them for project-level constants such as
the year, project name, etc.

### Nested loops compose naturally

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

The inner loop sees both `day` (its own loop var) and `week` (the outer one).

### Shadowing

If a loop variable has the same name as a declared static variable, the loop
binding shadows the static one inside the loop body and reverts on exit.

### Independent loops

Two sibling nodes that both `repeat: day` each run their own independent
iteration over the same variable. The loop variable does not persist between
them.

## 6. CLI overrides

`--var name=value` (repeatable) injects values from the command line. Semantics:

| Scenario | Behaviour |
|---|---|
| `name` is a declared static variable | Replaces its value with the override (string). |
| `name` is a declared `range` or `list` variable | Collapses its loop to a single value (the override). Useful for "build day 7 only". |
| `name` is not declared at all | Defines `name` as a string-typed static for the run. Templates can reference `{name}` and it will resolve. |

Type coercion:
- If the declared variable is **`range`-typed**, the override string is parsed as
  `int`.
- If the declared variable's static `value` is an `int`, ditto.
- If the declared variable is **`list`-typed and every list item is an `int`**, ditto.
- Otherwise the override is treated as a string. Format specifiers that expect
  numbers will error against string overrides.

If `int` parsing fails, the override stays a string, which then surfaces a
clear error if it hits a numeric format spec.

Order of resolution at render time, from most specific to least:
1. **Loop variable** in the current scope (if shadows a static or override).
2. **CLI override** for the named variable.
3. **Declared static** value.

## 7. Path safety

Rendered names go through these checks before any disk action:

- May not be empty.
- May not equal `.` or `..`.
- May not contain `/`, `\`, or `\0`.

The output root is resolved via `Path.resolve()` and every target's resolved
path is verified to be contained within the resolved output root. Symlinks that
escape the root are rejected.

## 8. Collisions and atomicity

Default policy (no `--force`): if **any** planned file target already exists,
the entire build is rejected before any change is written. Existing
*directories* at planned directory paths are fine — the build writes into them
and leaves their unrelated contents intact.

`--force` allows the build to proceed and **overwrites existing files at planned
paths**. It does not delete files that the template doesn't declare; it does
not recursively wipe directories.

**Symlinks at planned paths.** A symlink at a planned file or directory target
is treated as a collision even with `--force` — the build refuses to write
through it. This applies whether the symlink points inside or outside the
output root: in the outside case the plan-time containment check fires; in the
inside case the lstat-based collision check or the `O_NOFOLLOW` open does. To
proceed, remove the symlink and re-run.

**Case-insensitive filesystems.** On macOS (default APFS / HFS+) and Windows,
two template paths differing only in case (`Day1/x` vs `day1/x`) will not be
detected as a collision by templatexplorer (which compares paths case-sensitively),
but the OS will treat them as the same target — the second write wins silently.
Avoid case-only differences in template paths if you target those platforms.

`--dry-run` runs the entire pipeline (parse, expand, plan, collision check) but
performs no filesystem writes. Combine with `--force` to see what would be
written.

Internal consistency: the planner rejects templates that produce two file
entries at the same logical path, or that mix `dir` and `file` at the same path.
(Two `dir` entries at the same path are fine and merged.)

## 9. Encoding and platform notes

- File contents are written as UTF-8.
- File **names** are subject to the underlying filesystem's rules. On Windows,
  names containing `:`, `*`, `?`, `"`, `<`, `>`, `|` will fail at write time;
  the `.temx` format does not validate these because they are legal POSIX.
- Spaces in names are fully supported (`Day 7/main.py`).
- Trailing whitespace and dots in names are filesystem-defined; avoid them.

## 10. Grammar summary

```
document        := mapping { "variables" : variables-map ?
                             "root" : node-list }
variables-map   := mapping { name : variable-spec }*
variable-spec   := scalar                          # shorthand value
                 | mapping { "value" : scalar }
                 | mapping { "range" : [int, int] }
                 | mapping { "list" : non-empty-list }
node-list       := [ node* ]
node            := dir-node | file-node
dir-node        := mapping { "dir"      : non-empty-string,
                             "repeat"   : variable-name ?,
                             "children" : node-list ? }
file-node       := mapping { "file"     : non-empty-string,
                             "repeat"   : variable-name ?,
                             "content"  : string ? }
variable-name   := python-identifier — { "true", "false", "null", "yes", "no" }

# Note: the reserved-word filter applies to VARIABLE names only. File/dir
# names in `dir:` / `file:` strings are arbitrary non-empty strings that
# survive the path-safety checks in §7.
```

## 11. Worked examples

### 11.1 Advent of Code (2022 style)

Per-day folders with input files and a stub solver. Each `main.py` references
its own day folder name in path literals — pure substitution does the right
thing.

```yaml
variables:
  year: { value: 2026 }
  day:  { range: [1, 25] }

root:
  - dir: "aoc-{year}"
    children:
      - dir: "Day {day}"
        repeat: day
        children:
          - file: input.txt
          - file: input_test.txt
          - file: main.py
            content: |
              def load_input(path):
                  return open(path).read().strip().split("\n")

              def part1(data): ...
              def part2(data): ...

              if __name__ == "__main__":
                  testdata = load_input("Day {day}/input_test.txt")
                  data = load_input("Day {day}/input.txt")
                  print("Part 1:", part1(data))
                  print("Part 2:", part2(data))
```

Build: `python templatexplorer.py aoc.temx --var year=2022`.

### 11.2 Weekly log

```yaml
variables:
  weeks: { range: [1, 52] }

root:
  - dir: logs
    children:
      - file: "week-{weeks:02d}.md"
        repeat: weeks
        content: |
          # Week {weeks} log

          ## Mon
          ## Tue
          ## Wed
          ## Thu
          ## Fri
```

### 11.3 Per-environment config scaffold

```yaml
variables:
  env: { list: [dev, staging, prod] }
  region: { list: [eu, us, ap] }

root:
  - dir: deploy
    children:
      - dir: "{env}"
        repeat: env
        children:
          - dir: "{region}"
            repeat: region
            children:
              - file: config.yaml
                content: |
                  env: {env}
                  region: {region}
```

Produces 3 × 3 = 9 leaf `config.yaml` files, each with the correct labels.

## 12. Error catalogue

| Error fragment | Cause | Fix |
|---|---|---|
| `missing required key 'root'` | Document has no `root:`. | Add at least `root: []`. |
| `top level must be a mapping` | Document is a list/scalar. | Use a mapping with `root:` and optional `variables:`. |
| `unknown top-level keys` | Typo or unsupported key. | Remove or rename to `variables` / `root`. |
| `variable ... must declare exactly one of value/range/list` | Multiple forms set, or none. | Pick one. |
| `variable ... range must be [int, int]` | Floats / strings / single value. | Use two ints, `start <= end`. |
| `'repeat' references undefined variable` | Loop var not declared in `variables`. | Declare it. |
| `unknown keys for dir node` / `... for file node` | Mixing dir and file fields. | Drop the wrong field. |
| `undefined variable '...'` | A `{name}` in a name/content has no matching variable in scope. | Declare it, override with `--var`, or move the reference into the loop's scope. |
| `rendered to '...': contains a path separator` | A substitution produced `/` or `\` in a name segment. | Sanitise the input or split into nested dirs. |
| `target path(s) already exist` | Without `--force`, a planned file collides with an existing one. | Re-run with `--force` to overwrite, or remove the existing file. |
| `attribute or index access is not allowed in templates` | A format string contains `{x.foo}` or `{x[0]}`. | Resolve the value before passing it in (rare). |
| `cannot have value: null` / `cannot be null` | A variable spec was `value: null` or shorthand `null`. | Use `value: ''` or remove the variable. |
| `is a symlink; refusing to write through it` | A planned target is a symlink. | Remove the symlink and re-run. |
| `rendered to whitespace-only string` | A substitution produced a name like `"   "`. | Provide a non-blank value. |

## 13. Cookbook

### Skip zero-padding for a sortable folder name
Use a format spec: `"day-{i:03d}"`. Lexicographic sort then matches numeric
order.

### Build just one item from a 1..N range
`--var day=12` — collapses the loop.

### Override the project name without editing the template
Pass `--var project=foo` and reference `{project}` in names/contents. No need
to declare it in `variables:` first.

### A literal `{` in a filename
Double it: `"file {{literal}}.txt"` → `file {literal}.txt`.

### A file you want created empty
Omit `content:` entirely. The file is created as zero bytes.

### Run the template into the current directory
Omit `--out`. Default is CWD.
