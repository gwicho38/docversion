# docversion commits swept in the user's other work

**Symptom.** In a matter folder that is a git repo, `docversion init` or `bump` made a commit that also held the user's staged edits and untracked notes. A file named `[Draft] v1.docx` could also pull in `D v1.docx`. An intake form named in `init` was renamed even though `.docversionignore` listed it.

**Cause.** Commits ran `git add -A` on the whole folder. Path arguments went to git as pathspecs, so `[...]` was read as a glob. The ignore file applied to `sync` only.

**Fix.** `commit_paths` stages and commits only the touched paths, with `--literal-pathspecs`. It drops paths git would refuse (ignored and untracked, or missing and untracked). `init` honours `.docversionignore`; `--force` overrides.

**Lesson.** A tool that commits in a shared repo must name its paths, take them literally, and leave everything else alone. Test with a decoy file whose name a glob would match, and with an ignored path, because git fails the whole `add` on one ignored path.
