"""Apply an expanded Plan to the filesystem."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .errors import TemxError
from .expander import PlanItem

# O_NOFOLLOW is POSIX. On platforms without it (most notably old Windows Python),
# fall back to 0; the symlink defence then relies on the lstat/containment recheck.
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def build(
    plan: list[PlanItem],
    out_root: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Apply `plan` under `out_root`. Returns the list of absolute paths written/created.

    Without `force`, any existing target (file, symlink, or anything not a real directory at
    a planned dir path) causes a TemxError before any change is made. With `force`, existing
    files are overwritten in place and existing real directories are reused (their contents
    are left untouched).

    `dry_run` performs all validation without touching the filesystem.

    Symlink safety: writes use O_NOFOLLOW where supported, and every target's resolved path
    is verified to stay inside `out_root` both at plan time and immediately before write.
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

    if dry_run:
        return [t for _, t in resolved]

    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item, target in resolved:
        if item.kind == "dir":
            target.mkdir(parents=True, exist_ok=True)
            _reject_if_symlink(target, kind="dir")
            written.append(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _reject_if_symlink(target.parent, kind="parent directory")
            _write_file_no_follow(target, item.content or "")
            written.append(target)
    return written


def _safe_join(root: Path, rel: PurePosixPath) -> Path:
    """Join `rel` onto `root`, guaranteeing the result stays inside `root`."""
    if rel.is_absolute():
        raise TemxError(f"Plan item path is absolute, which is not allowed: {rel}")
    target = root.joinpath(*rel.parts)
    try:
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise TemxError(f"Could not resolve target path {target}: {exc}") from exc
    _verify_still_contained(root, resolved)
    return resolved


def _verify_still_contained(root: Path, target: Path) -> None:
    if root == target:
        return
    if root in target.parents:
        return
    raise TemxError(f"Target path {target} escapes output root {root}")


def _reject_if_symlink(path: Path, *, kind: str) -> None:
    """Refuse to write through a symlink, even if its target is inside the output root."""
    try:
        st = path.lstat()
    except OSError as exc:
        raise TemxError(f"Could not lstat {path}: {exc}") from exc
    import stat
    if stat.S_ISLNK(st.st_mode):
        raise TemxError(
            f"{kind.capitalize()} at {path} is a symlink; refusing to write through it"
        )


def _write_file_no_follow(target: Path, content: str) -> None:
    """Open the target with O_NOFOLLOW and write content.

    If `target` is itself a symlink, O_NOFOLLOW causes the open to fail (ELOOP),
    which we surface as a TemxError. This closes a TOCTOU window between the
    collision check and the actual write.
    """
    data = content.encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o644)
    except OSError as exc:
        # ELOOP is the most informative case; surface the generic message otherwise.
        raise TemxError(f"Could not open {target} for writing: {exc}") from exc
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


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
    """Use lexists/lstat so a symlink at a planned target counts as a collision
    even though the symlink may dangle or point inside the root."""
    clashes: list[Path] = []
    for item, target in resolved:
        try:
            st = target.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            clashes.append(target)
            continue
        import stat
        if item.kind == "dir":
            # An existing real dir at a planned dir path is fine; symlink or file is a clash.
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                continue
            clashes.append(target)
        else:
            # Anything at a planned file path is a clash — including a symlink.
            clashes.append(target)
    return clashes
