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


def test_new_history_entry_has_expected_shape():
    entry = core.new_history_entry(1, "versions/Foo v1.docx", "initial import", "deadbeef")
    assert entry["version"] == 1
    assert entry["file"] == "versions/Foo v1.docx"
    assert entry["note"] == "initial import"
    assert entry["sha256"] == "deadbeef"
    assert "date" in entry
