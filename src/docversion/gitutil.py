"""Thin git wrappers. Every state-changing docversion command commits if
the working directory is inside a git repo; otherwise these are no-ops."""

import subprocess
from pathlib import Path
from typing import Optional


def is_git_repo(directory: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
    )
    return result.returncode == 0


def rm_cached(directory: Path, filename: str) -> None:
    if not is_git_repo(directory):
        return
    subprocess.run(
        ["git", "-C", str(directory), "rm", "--cached", "-q", "--", filename],
        capture_output=True,
    )


def commit_all(directory: Path, message: str) -> Optional[str]:
    if not is_git_repo(directory):
        return None
    subprocess.run(["git", "-C", str(directory), "add", "-A"], capture_output=True)
    result = subprocess.run(
        ["git", "-C", str(directory), "commit", "-m", message],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr):
        return f"git commit skipped: {result.stderr.strip()}"
    return None
