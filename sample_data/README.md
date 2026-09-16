# sample_data/

- `documents/` — small, synthetic placeholder text files that seeded
  `Document` rows reference via `file_ref`. They contain no real form
  content and exist only so the reference points at something real. See
  `docs/security-and-limitations.md`.
- `demo_scenarios.json` — written by `make seed` / `python -m
  app.seed.seed`. Records the IDs of a few notable seeded records (an
  overdue case, a pending-approval document, etc.) so `docs/demo-guide.md`
  can point at specific, reproducible examples. Regenerated on every reseed;
  not meant to be hand-edited.
