"""docversion must commit only the files it touched, and an explicit
`init` must honour .docversionignore (RED first, 2026-10-28).

Why: legal matter folders are git repos shared with other tools. The
intake skill stages exact paths only, and the intake forms listed in
.docversionignore must never be renamed."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from docversion import core
from docversion.cli import cli


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True).stdout


def make_repo(path: Path) -> None:
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("base\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "base")


def head_files(path: Path) -> set:
    return set(git(path, "show", "--name-only", "--no-renames", "--format=", "HEAD").splitlines())


def test_init_does_not_commit_unrelated_untracked_file(tmp_path, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes.txt").write_text("user work, not for docversion\n")
    (tmp_path / "Agreement.docx").write_bytes(b"draft")

    result = CliRunner().invoke(cli, ["init", "Agreement.docx"])
    assert result.exit_code == 0, result.output

    assert "notes.txt" not in head_files(tmp_path)
    assert "?? notes.txt" in git(tmp_path, "status", "--porcelain")


def test_bump_does_not_commit_unrelated_staged_change(tmp_path, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Waiver.docx").write_bytes(b"v0")
    assert CliRunner().invoke(cli, ["init", "Waiver.docx"]).exit_code == 0

    (tmp_path / "README.md").write_text("user edit, staged by the user\n")
    git(tmp_path, "add", "README.md")

    working = core.versioned_name("Waiver", 0, ".docx")
    result = CliRunner().invoke(cli, ["bump", working, "--note", "sent"])
    assert result.exit_code == 0, result.output

    committed = head_files(tmp_path)
    assert "README.md" not in committed
    assert core.versioned_name("Waiver", 1, ".docx") in committed
    assert "M  README.md" in git(tmp_path, "status", "--porcelain")


def test_bump_commit_records_old_working_file_removal(tmp_path, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Waiver.docx").write_bytes(b"v0")
    assert CliRunner().invoke(cli, ["init", "Waiver.docx"]).exit_code == 0
    v0 = core.versioned_name("Waiver", 0, ".docx")
    assert CliRunner().invoke(cli, ["bump", v0]).exit_code == 0

    tracked = set(git(tmp_path, "ls-files").split("\n"))
    assert v0 not in tracked
    assert git(tmp_path, "status", "--porcelain").strip() == ""


def test_explicit_init_skips_ignored_file(tmp_path, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".docversionignore").write_text("matter-intake.docx\n")
    form = tmp_path / "matter-intake.docx"
    form.write_bytes(b"intake form")

    result = CliRunner().invoke(cli, ["init", "matter-intake.docx"])
    assert result.exit_code == 0, result.output

    assert form.exists(), "an ignored intake form must keep its name"
    assert core.load_manifest(tmp_path)["docs"] == {}
    assert "ignored" in result.output


def test_explicit_init_force_tracks_ignored_file(tmp_path, monkeypatch):
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".docversionignore").write_text("*.docx\n")
    (tmp_path / "Letter.docx").write_bytes(b"x")

    result = CliRunner().invoke(cli, ["init", "--force", "Letter.docx"])
    assert result.exit_code == 0, result.output
    assert "letter" in core.load_manifest(tmp_path)["docs"]


def test_scoped_commit_with_unborn_head_commits_no_unrelated_file(tmp_path, monkeypatch):
    """R5.4: a repo with no commits yet. The scoped commit succeeds or
    prints a warning. It never commits the user's staged or untracked files."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("staged by the user\n")
    git(tmp_path, "add", "README.md")
    (tmp_path / "notes.txt").write_text("user work\n")
    (tmp_path / "Agreement.docx").write_bytes(b"draft")

    result = CliRunner().invoke(cli, ["init", "Agreement.docx"])
    assert result.exit_code == 0, result.output

    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=tmp_path).returncode == 0
    if has_head:
        committed = head_files(tmp_path)
        assert "README.md" not in committed
        assert "notes.txt" not in committed
        assert core.versioned_name("Agreement", 0, ".docx") in committed
    else:
        assert "git commit skipped" in result.output
    status = git(tmp_path, "status", "--porcelain")
    assert "A  README.md" in status
    assert "?? notes.txt" in status


def test_init_bracket_name_commits_only_that_file(tmp_path, monkeypatch):
    """R5.7a: '[Draft] v1.docx' as a git glob also matches 'D v1.docx'.
    The commit must hold the named file only; the decoys stay untracked."""
    make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "[Draft] v1.docx").write_bytes(b"draft")
    git(tmp_path, "--literal-pathspecs", "add", "--", "[Draft] v1.docx")
    git(tmp_path, "commit", "-q", "-m", "user adds draft")
    new_name = core.versioned_name("[Draft]", 1, ".docx")
    decoys = ["D v1.docx", "D" + new_name[len("[Draft]"):]]
    for decoy in decoys:
        (tmp_path / decoy).write_bytes(b"not for docversion")

    result = CliRunner().invoke(cli, ["init", "[Draft] v1.docx"])
    assert result.exit_code == 0, result.output

    committed = head_files(tmp_path)
    assert committed == {
        "[Draft] v1.docx",
        new_name,
        f"versions/{new_name}",
        ".docversion.json",
    }
    untracked = git(tmp_path, "ls-files", "--others", "--exclude-standard").splitlines()
    for decoy in decoys:
        assert decoy in untracked


def test_folder_inside_larger_repo_commits_only_its_touched_paths(tmp_path, monkeypatch):
    """R5.7b: a tracked folder inside a larger repo. The commit holds only
    the paths docversion touched in that folder."""
    make_repo(tmp_path)
    matter = tmp_path / "matter"
    matter.mkdir()
    (matter / "Waiver.docx").write_bytes(b"v0")
    git(tmp_path, "add", "matter/Waiver.docx")
    git(tmp_path, "commit", "-q", "-m", "user adds waiver")
    (matter / "notes.txt").write_text("user work in the same folder\n")
    (tmp_path / "other.txt").write_text("user work elsewhere\n")
    (tmp_path / "README.md").write_text("user edit\n")
    git(tmp_path, "add", "README.md")
    monkeypatch.chdir(matter)

    result = CliRunner().invoke(cli, ["init", "Waiver.docx"])
    assert result.exit_code == 0, result.output

    v0 = core.versioned_name("Waiver", 0, ".docx")
    assert head_files(tmp_path) == {
        "matter/Waiver.docx",
        f"matter/{v0}",
        f"matter/versions/{v0}",
        "matter/.docversion.json",
    }
    status = git(tmp_path, "status", "--porcelain")
    assert "M  README.md" in status
    assert "?? matter/notes.txt" in status
    assert "?? other.txt" in status
