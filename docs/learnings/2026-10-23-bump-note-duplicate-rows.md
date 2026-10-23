# Bump note recorded under the frozen version

**Symptom.** After `init` then `bump --note X`, `docversion log` showed two `v0` rows and no `v1` row.

**Cause.** `bump` appended a new history row using the frozen version number. `init` had already written a row for that version. `restore` did the same with an "(auto-frozen before restore)" row and never wrote a row for the new version.

**Fix.** One row per version. `record_frozen` refreshes the existing row; `record_opened` adds the row for the new version with the note.

**Lesson.** When a record is keyed by an identifier (here, the version number), write through a helper that updates in place, not a bare `append`. A test that asserts the list of keys (`[0, 1, 2]`) catches duplicates that a "last row has my note" test misses.
