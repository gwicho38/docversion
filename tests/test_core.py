import json
from pathlib import Path

import pytest

from docversion import core


def test_split_version_extracts_trailing_v_number():
    assert core.split_version("Operating Agreement v3") == ("Operating Agreement", 3)


def test_split_version_no_suffix_returns_none():
    assert core.split_version("Operating Agreement") == ("Operating Agreement", None)


def test_split_version_ignores_v_inside_word():
    assert core.split_version("Version Notes") == ("Version Notes", None)


def test_split_version_handles_hashed_suffix():
    assert core.split_version("Operating Agreement v3-9f2c7a1e") == ("Operating Agreement", 3)


def test_version_suffix_is_deterministic():
    a = core.version_suffix("Operating Agreement", 3)
    b = core.version_suffix("Operating Agreement", 3)
    assert a == b
    assert len(a) == core.HASH_LEN
    assert all(c in "0123456789abcdef" for c in a)


def test_version_suffix_differs_by_version_number():
    a = core.version_suffix("Operating Agreement", 1)
    b = core.version_suffix("Operating Agreement", 2)
    assert a != b


def test_version_suffix_differs_by_title():
    a = core.version_suffix("Operating Agreement", 1)
    b = core.version_suffix("Employee Waiver", 1)
    assert a != b


def test_versioned_name_includes_number_and_hash():
    name = core.versioned_name("Operating Agreement", 3, ".docx")
    assert name.startswith("Operating Agreement v3-")
    assert name.endswith(".docx")
    assert name == f"Operating Agreement v3-{core.version_suffix('Operating Agreement', 3)}.docx"


def test_versioned_name_round_trips_through_split_version():
    name = core.versioned_name("Operating Agreement", 3, ".docx")
    stem = name[: -len(".docx")]
    assert core.split_version(stem) == ("Operating Agreement", 3)


def test_key_for_is_case_insensitive():
    assert core.key_for("Operating Agreement") == core.key_for("operating agreement")


def test_sha256_of_matches_known_content(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    import hashlib

    assert core.sha256_of(f) == hashlib.sha256(b"hello").hexdigest()


def test_save_then_load_manifest_round_trips(tmp_path):
    manifest = {"docs": {"foo": {"working_file": "foo v1.docx", "current_version": 1, "history": []}}}
    core.save_manifest(tmp_path, manifest)
    assert (tmp_path / core.MANIFEST_NAME).exists()
    loaded = core.load_manifest(tmp_path)
    assert loaded == manifest


def test_load_manifest_missing_file_returns_empty_docs(tmp_path):
    loaded = core.load_manifest(tmp_path)
    assert loaded == {"docs": {}}


def test_find_doc_by_key_present_and_absent():
    manifest = {"docs": {"foo": {}}}
    assert core.find_doc_by_key(manifest, "foo") == "foo"
    assert core.find_doc_by_key(manifest, "bar") is None


def test_find_doc_by_working_file():
    manifest = {"docs": {"foo": {"working_file": "Foo v2.docx"}}}
    assert core.find_doc_by_working_file(manifest, "Foo v2.docx") == "foo"
    assert core.find_doc_by_working_file(manifest, "missing.docx") is None


def test_load_ignore_patterns_missing_file_returns_empty(tmp_path):
    assert core.load_ignore_patterns(tmp_path) == []


def test_load_ignore_patterns_skips_blanks_and_comments(tmp_path):
    (tmp_path / core.IGNORE_FILE_NAME).write_text(
        "\n# a comment\ntask-intake.docx\n\n*intake*.docx\n"
    )
    assert core.load_ignore_patterns(tmp_path) == ["task-intake.docx", "*intake*.docx"]


def test_is_ignored_literal_match():
    assert core.is_ignored("task-intake.docx", ["task-intake.docx"])
    assert not core.is_ignored("Other.docx", ["task-intake.docx"])


def test_is_ignored_glob_match():
    assert core.is_ignored("client-intake.docx", ["*intake*.docx"])
    assert not core.is_ignored("Report.docx", ["*intake*.docx"])


def test_new_history_entry_has_expected_shape():
    entry = core.new_history_entry(1, "versions/Foo v1.docx", "initial import", "deadbeef")
    assert entry["version"] == 1
    assert entry["file"] == "versions/Foo v1.docx"
    assert entry["note"] == "initial import"
    assert entry["sha256"] == "deadbeef"
    assert "date" in entry
