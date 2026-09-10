import subprocess
from pathlib import Path

from click.testing import CliRunner

from docversion import core
from docversion.cli import cli


def make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def vname(display: str, version: int, ext: str = ".docx") -> str:
    return core.versioned_name(display, version, ext)


def test_init_renames_and_archives(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Operating Agreement.docx"
    doc.write_bytes(b"draft content with track changes")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(doc)])
    assert result.exit_code == 0, result.output

    assert not doc.exists()
    working = tmp_path / vname("Operating Agreement", 1)
    archived = tmp_path / "versions" / vname("Operating Agreement", 1)
    assert working.exists()
    assert archived.exists()
    assert archived.read_bytes() == b"draft content with track changes"

    manifest = core.load_manifest(tmp_path)
    entry = manifest["docs"]["operating agreement"]
    assert entry["current_version"] == 1
    assert entry["working_file"] == vname("Operating Agreement", 1)
    assert len(entry["history"]) == 1


def test_bump_preserves_content_and_advances_version(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Waiver.docx"
    doc.write_bytes(b"v1 body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])

    v1_path = tmp_path / vname("Waiver", 1)
    v1_path.write_bytes(b"v1 body edited with tracked changes")

    result = runner.invoke(cli, ["bump", str(v1_path), "--note", "sent for review"])
    assert result.exit_code == 0, result.output

    assert not v1_path.exists()
    v2_path = tmp_path / vname("Waiver", 2)
    assert v2_path.exists()
    assert v2_path.read_bytes() == b"v1 body edited with tracked changes"

    frozen_v1 = tmp_path / "versions" / vname("Waiver", 1)
    assert frozen_v1.read_bytes() == b"v1 body edited with tracked changes"

    manifest = core.load_manifest(tmp_path)
    entry = manifest["docs"]["waiver"]
    assert entry["current_version"] == 2
    assert entry["working_file"] == vname("Waiver", 2)
    assert entry["history"][-1]["note"] == "sent for review"


def test_bump_rejects_non_current_file(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Contract.docx"
    doc.write_bytes(b"body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    v1_path = tmp_path / vname("Contract", 1)
    v1_path.write_bytes(b"body edited")  # ensure a real change so bump advances
    runner.invoke(cli, ["bump", str(v1_path)])  # now current is v2

    # v1 file no longer exists on disk; recreate a stale copy under its old name
    stale = tmp_path / vname("Contract", 1)
    stale.write_bytes(b"stale")
    result = runner.invoke(cli, ["bump", str(stale)])
    assert result.exit_code != 0
    assert "not the current version" in result.output


def test_restore_brings_back_old_version_as_new_current(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "NDA.docx"
    doc.write_bytes(b"original")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    v1_path = tmp_path / vname("NDA", 1)
    runner.invoke(cli, ["bump", str(v1_path)])  # -> v2 exists now, still "original"

    result = runner.invoke(cli, ["restore", str(tmp_path / vname("NDA", 2)), "1"])
    assert result.exit_code == 0, result.output

    v3_path = tmp_path / vname("NDA", 3)
    assert v3_path.exists()
    assert v3_path.read_bytes() == b"original"

    manifest = core.load_manifest(tmp_path)
    entry = manifest["docs"]["nda"]
    assert entry["current_version"] == 3


def test_git_commits_are_created(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Memo.docx"
    doc.write_bytes(b"content")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert "docversion: init" in log.stdout


def test_init_accepts_glob_pattern(tmp_path, monkeypatch):
    make_git_repo(tmp_path)
    (tmp_path / "Alpha.docx").write_bytes(b"a")
    (tmp_path / "Beta.docx").write_bytes(b"b")
    (tmp_path / "notes.txt").write_bytes(b"n")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "*.docx"])
    assert result.exit_code == 0, result.output

    manifest = core.load_manifest(tmp_path)
    assert set(manifest["docs"].keys()) == {"alpha", "beta"}
    assert (tmp_path / "notes.txt").exists()  # untouched, not a .docx


def test_bump_accepts_name_without_version_suffix(tmp_path, monkeypatch):
    make_git_repo(tmp_path)
    doc = tmp_path / "Charter.docx"
    doc.write_bytes(b"body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    (tmp_path / vname("Charter", 1)).write_bytes(b"body edited")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["bump", "Charter", "--note", "v2 draft"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / vname("Charter", 2)).exists()


def test_sync_onboards_new_files_matching_pattern(tmp_path):
    make_git_repo(tmp_path)
    (tmp_path / "Alpha.docx").write_bytes(b"a")
    (tmp_path / "notes.txt").write_bytes(b"n")

    runner = CliRunner()
    result = runner.invoke(cli, ["sync", str(tmp_path), "*.docx"])
    assert result.exit_code == 0, result.output

    manifest = core.load_manifest(tmp_path)
    assert "alpha" in manifest["docs"]
    assert (tmp_path / "notes.txt").exists()  # untouched


def test_sync_skips_unchanged_tracked_doc(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Beta.docx"
    doc.write_bytes(b"body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])

    result = runner.invoke(cli, ["sync", str(tmp_path), "*.docx"])
    assert result.exit_code == 0, result.output
    assert "1 unchanged" in result.output

    manifest = core.load_manifest(tmp_path)
    assert manifest["docs"]["beta"]["current_version"] == 1
    assert (tmp_path / vname("Beta", 1)).exists()


def test_sync_bumps_changed_tracked_doc(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Gamma.docx"
    doc.write_bytes(b"body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    (tmp_path / vname("Gamma", 1)).write_bytes(b"body edited with tracked changes")

    result = runner.invoke(cli, ["sync", str(tmp_path), "*.docx"])
    assert result.exit_code == 0, result.output
    assert "1 bumped" in result.output

    manifest = core.load_manifest(tmp_path)
    entry = manifest["docs"]["gamma"]
    assert entry["current_version"] == 2
    assert (tmp_path / vname("Gamma", 2)).read_bytes() == b"body edited with tracked changes"


def test_sync_default_directory_is_cwd(tmp_path, monkeypatch):
    make_git_repo(tmp_path)
    (tmp_path / "Delta.docx").write_bytes(b"d")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code == 0, result.output
    assert "delta" in core.load_manifest(tmp_path)["docs"]


def test_log_shows_history(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Report.docx"
    doc.write_bytes(b"content")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    v1_path = tmp_path / vname("Report", 1)
    v1_path.write_bytes(b"content edited")
    runner.invoke(cli, ["bump", str(v1_path), "--note", "second draft"])

    result = runner.invoke(cli, ["log", str(tmp_path / vname("Report", 2))])
    assert result.exit_code == 0, result.output
    assert "second draft" in result.output
    assert "v1" in result.output


def test_versions_of_same_doc_have_distinct_filenames(tmp_path):
    make_git_repo(tmp_path)
    doc = tmp_path / "Distinct.docx"
    doc.write_bytes(b"body")
    runner = CliRunner()
    runner.invoke(cli, ["init", str(doc)])
    v1_path = tmp_path / vname("Distinct", 1)
    v1_path.write_bytes(b"body edited")
    runner.invoke(cli, ["bump", str(v1_path)])

    manifest = core.load_manifest(tmp_path)
    entry = manifest["docs"]["distinct"]
    assert entry["working_file"] != vname("Distinct", 1)
    assert entry["working_file"] == vname("Distinct", 2)
