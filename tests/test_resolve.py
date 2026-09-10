from pathlib import Path

import pytest
from click import ClickException

from docversion import resolve


def touch(path: Path, content: bytes = b"x"):
    path.write_bytes(content)
    return path


def test_expand_patterns_literal_path(tmp_path):
    f = touch(tmp_path / "Foo.docx")
    result = resolve.expand_patterns([str(f)], directory=tmp_path)
    assert result == [f.resolve()]


def test_expand_patterns_glob_matches_multiple_sorted(tmp_path):
    touch(tmp_path / "B.docx")
    touch(tmp_path / "A.docx")
    touch(tmp_path / "C.txt")
    result = resolve.expand_patterns(["*.docx"], directory=tmp_path)
    assert [p.name for p in result] == ["A.docx", "B.docx"]


def test_expand_patterns_dedupes_across_patterns(tmp_path):
    f = touch(tmp_path / "Foo.docx")
    result = resolve.expand_patterns([str(f), "*.docx"], directory=tmp_path)
    assert len(result) == 1


def test_expand_patterns_no_match_raises(tmp_path):
    with pytest.raises(ClickException):
        resolve.expand_patterns(["nope*.docx"], directory=tmp_path)


def test_resolve_one_literal_path(tmp_path):
    f = touch(tmp_path / "Foo.docx")
    assert resolve.resolve_one(str(f), directory=tmp_path) == f.resolve()


def test_resolve_one_glob_single_match(tmp_path):
    f = touch(tmp_path / "Operating Agreement v3.docx")
    result = resolve.resolve_one("Operating Agreement*", directory=tmp_path)
    assert result == f.resolve()


def test_resolve_one_glob_ambiguous_raises(tmp_path):
    touch(tmp_path / "Foo v1.docx")
    touch(tmp_path / "Foo v2.docx")
    with pytest.raises(ClickException, match="multiple"):
        resolve.resolve_one("Foo*", directory=tmp_path)


def test_resolve_one_falls_back_to_tracked_name(tmp_path):
    from docversion import core

    working = touch(tmp_path / "Operating Agreement v3.docx")
    manifest = {
        "docs": {
            "operating agreement": {
                "display_name": "Operating Agreement",
                "working_file": "Operating Agreement v3.docx",
                "current_version": 3,
                "history": [],
            }
        }
    }
    core.save_manifest(tmp_path, manifest)

    result = resolve.resolve_one("Operating Agreement", directory=tmp_path)
    assert result == working.resolve()


def test_resolve_one_no_match_raises(tmp_path):
    with pytest.raises(ClickException):
        resolve.resolve_one("Nothing Here", directory=tmp_path)
