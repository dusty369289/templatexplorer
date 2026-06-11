"""Apply an expanded Plan to the filesystem."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .errors import TemxError
from .expander import PlanItem


def build(
    plan: list[PlanItem],
    out_root: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Apply `plan` under `out_root`. Returns the list of absolute paths written/created.

    Without `force`, any existing target (file or non-empty/empty dir entry) causes a TemxError
    before any change is made. With `force`, existing files are overwritten in place and
    existing directories are reused (their non-template contents are left untouched).

    `dry_run` performs all validation without touching the filesystem.
    """
    out_root = out_root.resolve()
    if out_root.exists() and not out_root.is_dir():
        raise TemxError(f"Output path exists but is not a directory: {out_root}")

    _check_internal_duplicates(plan)

    resolved: list[tuple[PlanItem, Path]] = []
    for item in plan:
        target = _safe_join(out_root, item.path)
        resolved.append((item, target))

    if not force:
        clashes = _detect_collisions(resolved)
        if clashes:
            preview = "\n  ".join(str(p) for p in clashes[:10])
            more = f"\n  ... and {len(clashes) - 10} more" if len(clashes) > 10 else ""
            raise TemxError(
                f"{len(clashes)} target path(s) already exist. Re-run with --force to overwrite.\n  {preview}{more}"
            )

    written: list[Path] = []
    if dry_run:
        return [t for _, t in resolved]

    out_root.mkdir(parents=True, exist_ok=True)
    for item, target in resolved:
        if item.kind == "dir":
            target.mkdir(parents=True, exist_ok=True)
            written.append(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content or "", encoding="utf-8")
            written.append(target)
    return written


def _safe_join(root: Path, rel: PurePosixPath) -> Path:
    """Join `rel` onto `root`, guaranteeing the result stays inside `root`.

    `rel` parts have already been screened for path separators and `..` by the expander,
    but we double-check with a resolved containment test in case of symlink shenanigans.
    """
    if rel.is_absolute():
        raise TemxError(f"Plan item path is absolute, which is not allowed: {rel}")
    target = root.joinpath(*rel.parts)
    # We resolve `strict=False` because the target need not exist yet.
    try:
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise TemxError(f"Could not resolve target path {target}: {exc}") from exc
    if root != resolved and root not in resolved.parents:
        raise TemxError(f"Target path {resolved} escapes output root {root}")
    return resolved


def _check_internal_duplicates(plan: list[PlanItem]) -> None:
    """Reject two plan items that would write to the same logical path with conflicting kinds,
    or two files at the same path (last-write-wins would be silently destructive)."""
    seen: dict[PurePosixPath, str] = {}
    for item in plan:
        prev = seen.get(item.path)
        if prev is None:
            seen[item.path] = item.kind
            continue
        if prev != item.kind:
            raise TemxError(f"Template produces conflicting kinds at {item.path}: '{prev}' and '{item.kind}'")
        if item.kind == "file":
            raise TemxError(f"Template produces two files at the same path: {item.path}")
        # Two dirs at the same path is fine — common when both branches declare a parent.


def _detect_collisions(resolved: list[tuple[PlanItem, Path]]) -> list[Path]:
    clashes: list[Path] = []
    for item, target in resolved:
        if not target.exists():
            continue
        if item.kind == "dir":
            # An existing dir is fine; we'd just write into it.
            if target.is_dir():
                continue
            clashes.append(target)
        else:
            # File or anything else — collision.
            clashes.append(target)
    return clashes
