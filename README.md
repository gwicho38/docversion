# docversion

Filename-based document versioning for a directory of files (Word docs,
PDFs, anything). Built for legal drafting workflows where Word Track
Changes markup must survive every version bump untouched — docversion
never opens or edits document content, it only copies bytes and renames
files.

## Model

- Each tracked document has a **working file** you keep editing
  (e.g. `Operating Agreement v3.docx`) and a manifest
  (`.docversion.json`) recording every past version.
- `init` renames existing files to `<name> v1<ext>` and freezes an
  immutable copy under `versions/`.
- `bump` freezes the current working file as its version, then opens
  the next version as a byte-identical copy — any Track Changes markup
  inside the file carries over unchanged.
- `restore` brings an older version back as a new current version
  (non-destructive: restoring is itself a version bump).
- `log` / `status` show history.
- Every state-changing command commits to git automatically if the
  directory is a repo.

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
# Register existing drafts as v1
docversion init "Operating Agreement.docx" "Employee Waiver.docx"

# ... edit "Operating Agreement v1.docx" in Word, Track Changes on ...

# Lock in v1, start editing v2
docversion bump "Operating Agreement v1.docx" --note "sent to client for review"

# ... edit "Operating Agreement v2.docx" ...

docversion bump "Operating Agreement v2.docx" --note "incorporated counsel comments"

# See the full history
docversion log "Operating Agreement v3.docx"

# Roll back to v1's content as a new v4 (non-destructive)
docversion restore "Operating Agreement v3.docx" 1

# List everything tracked in the current directory
docversion status
```

## Why not just git?

Git tracks history fine, but binary Office files diff as opaque blobs,
and legal teams commonly hand off documents by filename version
("v3", "REDLINE", "CLEAN") rather than by commit hash. docversion keeps
that filename-based workflow, layers a structured manifest on top of it,
and still commits every step to git so nothing is lost.

## License

MIT
