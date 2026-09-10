"""docversion CLI: rename-and-archive document versioning.

See README.md for the model. In short: `init` renames files to
`<name> v1<ext>` and archives a frozen copy under `versions/`; `bump`
freezes the current version and opens the next one as a byte-identical
copy (so Word Track Changes markup is never touched); `restore` brings
an old version back as a new current version.
"""

import shutil
from pathlib import Path

import click

from docversion import core, gitutil


def _resolve_key(manifest: dict, path: Path) -> str:
    key = core.find_doc_by_working_file(manifest, path.name)
    if key is None:
        base_stem, _ = core.split_version(path.stem)
        key = core.find_doc_by_key(manifest, core.key_for(base_stem))
    if key is None:
        raise click.ClickException(f"{path.name} is not tracked. Run `docversion init` on it first.")
    return key


@click.group()
def cli():
    """Filename-based document versioning that preserves file content untouched."""


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--note", default="initial import", help="Note for the v1 history entry.")
def init(files, note):
    """Register FILES as version 1 of a tracked document each."""
    directory = Path(files[0]).resolve().parent
    manifest = core.load_manifest(directory)
    versions_dir = directory / core.VERSIONS_DIR
    versions_dir.mkdir(exist_ok=True)

    for f in files:
        src = Path(f).resolve()
        if src.parent != directory:
            click.echo(f"skip {src.name}: not in {directory}")
            continue

        base_stem, existing_version = core.split_version(src.stem)
        key = core.key_for(base_stem)
        if core.find_doc_by_key(manifest, key):
            click.echo(f"skip {src.name}: already tracked as '{base_stem}'")
            continue

        version = existing_version or 1
        ext = src.suffix
        new_name = f"{base_stem} v{version}{ext}"
        new_path = directory / new_name
        if src != new_path:
            src.rename(new_path)

        archive_path = versions_dir / new_name
        shutil.copy2(new_path, archive_path)

        manifest["docs"][key] = {
            "display_name": base_stem,
            "working_file": new_name,
            "current_version": version,
            "history": [
                core.new_history_entry(
                    version, f"{core.VERSIONS_DIR}/{new_name}", note, core.sha256_of(new_path)
                )
            ],
        }
        click.echo(f"tracked: {base_stem}  ->  {new_name}  (v{version} archived)")

    core.save_manifest(directory, manifest)
    warning = gitutil.commit_all(directory, f"docversion: init {', '.join(Path(f).stem for f in files)}")
    if warning:
        click.echo(f"  ({warning})")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--note", default="", help="What changed in this version.")
def bump(file, note):
    """Freeze FILE's current version and open the next version for editing."""
    src = Path(file).resolve()
    directory = src.parent
    manifest = core.load_manifest(directory)
    key = _resolve_key(manifest, src)
    entry = manifest["docs"][key]

    if entry["working_file"] != src.name:
        raise click.ClickException(
            f"{src.name} is not the current version ({entry['working_file']} is). "
            f"Bump that file instead, or `restore` this version forward."
        )

    versions_dir = directory / core.VERSIONS_DIR
    versions_dir.mkdir(exist_ok=True)
    current_version = entry["current_version"]
    ext = src.suffix
    display = entry["display_name"]

    frozen_name = f"{display} v{current_version}{ext}"
    frozen_path = versions_dir / frozen_name
    shutil.copy2(src, frozen_path)  # always freshen: src may have been edited since init/last bump

    next_version = current_version + 1
    next_name = f"{display} v{next_version}{ext}"
    next_path = directory / next_name
    shutil.copy2(src, next_path)

    entry["history"].append(
        core.new_history_entry(
            current_version, f"{core.VERSIONS_DIR}/{frozen_name}", note or "(no note)", core.sha256_of(frozen_path)
        )
    )
    entry["current_version"] = next_version
    entry["working_file"] = next_name
    core.save_manifest(directory, manifest)

    gitutil.rm_cached(directory, src.name)
    src.unlink()
    warning = gitutil.commit_all(
        directory,
        f"docversion: {display} v{current_version} -> v{next_version}" + (f" — {note}" if note else ""),
    )
    if warning:
        click.echo(f"  ({warning})")
    click.echo(f"{display}: v{current_version} frozen -> now editing v{next_version} ({next_name})")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("version", type=int)
@click.option("--note", default="", help="Why this version is being restored.")
def restore(file, version, note):
    """Bring VERSION of FILE back as the new current version (non-destructive)."""
    src = Path(file).resolve()
    directory = src.parent
    manifest = core.load_manifest(directory)
    key = _resolve_key(manifest, src)
    entry = manifest["docs"][key]
    display = entry["display_name"]
    ext = Path(entry["working_file"]).suffix

    archive_path = directory / core.VERSIONS_DIR / f"{display} v{version}{ext}"
    if not archive_path.exists():
        raise click.ClickException(f"No archived v{version} found at {archive_path}")

    current_version = entry["current_version"]
    current_path = directory / entry["working_file"]
    versions_dir = directory / core.VERSIONS_DIR
    frozen_name = f"{display} v{current_version}{ext}"
    frozen_path = versions_dir / frozen_name
    if current_path.exists():
        shutil.copy2(current_path, frozen_path)  # always freshen: current may have been edited
        entry["history"].append(
            core.new_history_entry(
                current_version,
                f"{core.VERSIONS_DIR}/{frozen_name}",
                "(auto-frozen before restore)",
                core.sha256_of(frozen_path),
            )
        )

    next_version = current_version + 1
    next_name = f"{display} v{next_version}{ext}"
    next_path = directory / next_name
    shutil.copy2(archive_path, next_path)

    if current_path.exists() and current_path != next_path:
        gitutil.rm_cached(directory, current_path.name)
        current_path.unlink()

    entry["current_version"] = next_version
    entry["working_file"] = next_name
    core.save_manifest(directory, manifest)
    warning = gitutil.commit_all(
        directory,
        f"docversion: {display} restored v{version} as v{next_version}" + (f" — {note}" if note else ""),
    )
    if warning:
        click.echo(f"  ({warning})")
    click.echo(f"{display}: v{version} restored -> now editing v{next_version} ({next_name})")


@cli.command()
@click.argument("file", required=False, type=click.Path(exists=True))
def log(file):
    """Show version history for FILE, or all tracked docs in the cwd if omitted."""
    directory = Path(file).resolve().parent if file else Path.cwd()
    manifest = core.load_manifest(directory)
    if not manifest["docs"]:
        click.echo("No tracked documents in this directory.")
        return

    keys = list(manifest["docs"].keys())
    if file:
        key = _resolve_key(manifest, Path(file).resolve())
        keys = [key]

    for key in keys:
        entry = manifest["docs"][key]
        click.echo(f"\n{entry['display_name']}  (current: v{entry['current_version']}, {entry['working_file']})")
        for h in entry["history"]:
            click.echo(f"  v{h['version']}  {h['date']}  {h['note']}")


@cli.command()
def status():
    """List all tracked documents in the current directory."""
    directory = Path.cwd()
    manifest = core.load_manifest(directory)
    if not manifest["docs"]:
        click.echo("No tracked documents in this directory.")
        return
    for entry in manifest["docs"].values():
        click.echo(f"v{entry['current_version']:<3} {entry['working_file']}")


if __name__ == "__main__":
    cli()
