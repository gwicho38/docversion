"""ls-style argument resolution: literal paths, glob patterns, or a
tracked document's name (so you don't need to know its current version
number to reference it)."""

import glob as glob_mod
from pathlib import Path
from typing import List, Optional

import click

from docversion import core


def _glob(pattern: str, directory: Path) -> List[Path]:
    search = pattern if Path(pattern).is_absolute() else str(directory / pattern)
    return sorted(Path(p) for p in glob_mod.glob(search))


def expand_patterns(patterns, directory: Optional[Path] = None) -> List[Path]:
    """Expand PATTERNS (literal paths or globs) into existing file paths.

    Each pattern must match at least one file; duplicates are dropped
    while preserving first-seen order.
    """
    directory = directory or Path.cwd()
    results: List[Path] = []
    seen = set()

    for pattern in patterns:
        literal = Path(pattern)
        if not literal.is_absolute():
            literal = directory / pattern
        matches = [literal] if literal.exists() else _glob(pattern, directory)

        if not matches:
            raise click.ClickException(f"no files match: {pattern}")

        for m in matches:
            resolved = m.resolve()
            if resolved not in seen:
                seen.add(resolved)
                results.append(resolved)

    return results


def resolve_one(pattern: str, directory: Optional[Path] = None) -> Path:
    """Resolve PATTERN to exactly one file: a literal path, a glob that
    matches exactly one file, or a tracked document's name (mapped to
    its current working file via the manifest)."""
    directory = directory or Path.cwd()

    literal = Path(pattern)
    if not literal.is_absolute():
        literal = directory / pattern
    if literal.exists():
        return literal.resolve()

    matches = _glob(pattern, directory)
    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        raise click.ClickException(f"'{pattern}' matches multiple files: {names}. Be more specific.")

    manifest = core.load_manifest(directory)
    base_stem, _ = core.split_version(Path(pattern).stem)
    key = core.find_doc_by_key(manifest, core.key_for(base_stem))
    if key:
        return (directory / manifest["docs"][key]["working_file"]).resolve()

    raise click.ClickException(f"no file matches: {pattern}")
