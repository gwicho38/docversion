"""Pure, git-free logic for docversion: manifest I/O and naming rules."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

MANIFEST_NAME = ".docversion.json"
VERSIONS_DIR = "versions"
HASH_LEN = 8
VERSION_SUFFIX_RE = re.compile(r"^(?P<stem>.*?)(?: v(?P<version>\d+)(?:-[0-9a-f]{6,16})?)$")


def load_manifest(directory: Path) -> dict:
    path = directory / MANIFEST_NAME
    if path.exists():
        return json.loads(path.read_text())
    return {"docs": {}}


def save_manifest(directory: Path, manifest: dict) -> None:
    path = directory / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_suffix(display_name: str, version: int) -> str:
    """Deterministic short hash of (title, version number) — same inputs
    always produce the same tag, so a version's filename is reproducible,
    but visibly different from every other version of the same document."""
    digest = hashlib.sha256(f"{display_name}::{version}".encode()).hexdigest()
    return digest[:HASH_LEN]


def versioned_name(display_name: str, version: int, ext: str) -> str:
    """The on-disk filename for DISPLAY_NAME's VERSION, e.g.
    'Operating Agreement v3-9f2c7a1e.docx'."""
    return f"{display_name} v{version}-{version_suffix(display_name, version)}{ext}"


def split_version(stem: str):
    m = VERSION_SUFFIX_RE.match(stem)
    if m:
        return m.group("stem"), int(m.group("version"))
    return stem, None


def key_for(stem_no_version: str) -> str:
    return stem_no_version.strip().lower()


def find_doc_by_key(manifest: dict, key: str) -> Optional[str]:
    return key if key in manifest["docs"] else None


def find_doc_by_working_file(manifest: dict, filename: str) -> Optional[str]:
    for key, entry in manifest["docs"].items():
        if entry["working_file"] == filename:
            return key
    return None


def new_history_entry(version: int, archive_rel_path: str, note: str, sha256: str) -> dict:
    return {
        "version": version,
        "file": archive_rel_path,
        "date": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "sha256": sha256,
    }
