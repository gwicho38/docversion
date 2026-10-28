"""Thin git wrappers. Every state-changing docversion command commits the
paths it touched if the working directory is inside a git repo;
otherwise these are no-ops.

docversion never commits a path it did not touch. Other staged entries
stay staged and untracked files stay untracked. Every git call that
takes paths uses --literal-pathspecs, so a name such as "[Draft] v1.docx"
is never read as a glob that also matches "D v1.docx"."""

import os
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Union

NOTHING_TO_COMMIT = ("nothing to commit", "nothing added to commit", "no changes added to commit")


def is_git_repo(directory: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
    )
    return result.returncode == 0


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(directory), "--literal-pathspecs", *args],
        capture_output=True,
        text=True,
    )


def _is_tracked(directory: Path, path: str) -> bool:
    return _git(directory, "ls-files", "--error-unmatch", "--", path).returncode == 0


def _is_ignored(directory: Path, path: str) -> bool:
    """check-ignore reads plain paths, not pathspecs, and rejects
    --literal-pathspecs (exit 128), so it runs without that flag."""
    result = subprocess.run(
        ["git", "-C", str(directory), "check-ignore", "-q", "--", path],
        capture_output=True,
    )
    return result.returncode == 0


def _committable(directory: Path, paths: Iterable[Union[str, Path]]) -> List[str]:
    """Keep each path that git can stage: a tracked path (a deletion is
    recorded too), or a path that exists and is not git-ignored. A path
    that neither exists nor is tracked would make git exit 128, so it is
    dropped. Paths are made relative to DIRECTORY; duplicates are dropped."""
    kept: List[str] = []
    for path in paths:
        rel = os.path.relpath(path, directory) if Path(path).is_absolute() else str(path)
        if rel in kept:
            continue
        if _is_tracked(directory, rel):
            kept.append(rel)
        elif os.path.lexists(directory / rel) and not _is_ignored(directory, rel):
            kept.append(rel)
    return kept


def commit_paths(directory: Path, paths: Iterable[Union[str, Path]], message: str) -> Optional[str]:
    """Stage and commit only PATHS (relative to DIRECTORY, or absolute).

    Returns None on success, when DIRECTORY is not in a git repo, or when
    there is nothing to commit (git exit 1). Returns a warning line when
    git refuses the commit, for example when a pre-commit hook fails."""
    if not is_git_repo(directory):
        return None
    kept = _committable(directory, paths)
    if not kept:
        return None
    added = _git(directory, "add", "-A", "--", *kept)
    if added.returncode != 0:
        return f"git commit skipped: {added.stderr.strip()}"
    result = _git(directory, "commit", "-m", message, "--", *kept)
    if result.returncode == 0:
        return None
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 1 and any(text in output for text in NOTHING_TO_COMMIT):
        return None
    return f"git commit skipped: {output}"
