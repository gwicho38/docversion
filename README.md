# docversion

Filename-based document versioning for a directory of files (Word docs,
PDFs, anything). Built for legal drafting workflows where Word Track
Changes markup must survive every version bump untouched — docversion
never opens or edits document content, it only copies bytes and renames
files.

## Model

- Each tracked document has a **working file** you keep editing
  (e.g. `Operating Agreement 9f2c7a1e_v3.docx`) and a manifest
  (`.docversion.json`) recording every past version.
- Version filenames end in `<hash>_v<N>`, where the hash is derived
  from `title + version number` (deterministic, not random) — so two
  versions of the same document never look almost-identical, and it's
  obvious at a glance that a new file actually landed.
- Versions start at **v0**.
- `init` renames existing files to `<name> <hash>_v0<ext>` and freezes
  an immutable copy under `versions/`.
- `bump` freezes the current working file as its version, then opens
  the next version as a byte-identical copy — any Track Changes markup
  inside the file carries over unchanged. It always advances the
  version, whether or not the content actually changed. `--note`
  labels the new version, the same way `init --note` labels v0. The
  history keeps one row per version.
- `restore` brings an older version back as a new current version
  (non-destructive: restoring is itself a version bump). It looks the
  old version up from the manifest's history, not by recomputing a
  filename, so it isn't tied to any particular naming scheme.
- `sync [DIR] [PATTERNS...]` is the one-click version of the above:
  onboards any new file matching PATTERNS (default `*.docx`) as v0,
  then bumps every already-tracked document — every run. Pass
  `--skip-unchanged` to skip a doc whose content is identical to its
  current version instead of always bumping it.
- `log` / `status` show history.
- Every state-changing command commits to git automatically if the
  directory is a repo. The commit holds only the files that command
  touched (see "Git commits" below).
- `.docversionignore` lists file name patterns, one per line, that
  docversion leaves alone. `sync` never onboards a matching file, and
  `init` skips one and says so. `init --force` tracks it anyway.
- `FILE` arguments (for `bump`, `restore`, `log`) accept a literal
  path, a glob that matches exactly one file, or just the document's
  tracked name — you don't need to know its current version number.

## Install

```bash
uv tool install docversion
```

or from source:

```bash
git clone https://github.com/gwicho38/docversion
cd docversion
uv sync
uv run docversion --help
```

## Usage

```bash
# Register existing drafts as v0
docversion init "Operating Agreement.docx" "Employee Waiver.docx"

# ... edit the resulting "Operating Agreement <hash>_v0.docx" in Word ...

# Lock in v0, start editing v1 (works with or without edits — bump always advances)
docversion bump "Operating Agreement" --note "client review round"

# ... edit "Operating Agreement <hash>_v1.docx" ...

docversion bump "Operating Agreement" --note "counsel comments round"

# See the full history (reference by tracked name — no version number to remember)
docversion log "Operating Agreement"

# Roll back to v0's content as a new v3 (non-destructive)
docversion restore "Operating Agreement" 0

# List everything tracked in the current directory
docversion status

# One-click sync: onboard new *.docx files as v0, then bump every tracked doc
docversion sync
docversion sync ~/Matters/some-matter "*.docx" "*.pdf"

# Same, but skip a doc whose content hasn't changed instead of always bumping it
docversion sync --skip-unchanged

# Keep intake forms out of versioning, then track one on purpose
echo "matter-intake.docx" >> .docversionignore
docversion init matter-intake.docx           # prints "skip matter-intake.docx: ignored by .docversionignore ..."
docversion init --force matter-intake.docx   # tracked
```

## Git commits

When the folder is inside a git repo, `init`, `bump` and `restore`
commit their changes, and `sync` commits each step it runs. Each commit
holds only the files that step touched: the old and new working file,
the copy under `versions/`, and `.docversion.json`.

- Anything else you staged stays staged, and untracked files stay
  untracked. docversion does not sweep your other work into its commit.
- File names are taken literally. A name such as `[Draft] v1.docx` is
  never read as a pattern that also matches `D v1.docx`.
- A file that git ignores (for example, `versions/` listed in
  `.gitignore`) is left out of the commit. The rest still commits.
- "Nothing to commit" is not an error. If git refuses the commit (for
  example, a pre-commit hook fails), docversion prints
  `git commit skipped: …` and keeps the file changes.

## Finder Quick Action

`finder-quick-action/Version Up Documents.workflow` right-clicks a folder
in Finder and runs `docversion sync` on it. It prompts for a file
pattern (default `*.docx`) so you can target just the files you mean.

To install: double-click the `.workflow` bundle (macOS will offer to
install it as a Service), or copy it yourself:

```bash
cp -R "finder-quick-action/Version Up Documents.workflow" ~/Library/Services/
```

It shells out to whatever `docversion` is on `PATH` (checks
`~/.local/bin`, `/usr/local/bin`, `/opt/homebrew/bin`), so install the
CLI first. Output and errors go to
`~/Library/Logs/docversion-quickaction.log`; a macOS notification fires
when it finishes. If the menu item doesn't show up after installing,
check Finder's right-click **Services → Customize…** (or System
Settings → Keyboard → Services) — new Services sometimes start
unchecked.

## Why not just git?

Git tracks history fine, but binary Office files diff as opaque blobs,
and legal teams commonly hand off documents by filename version
("v3", "REDLINE", "CLEAN") rather than by commit hash. docversion keeps
that filename-based workflow, layers a structured manifest on top of it,
and still commits every step to git so nothing is lost.

## License

MIT
