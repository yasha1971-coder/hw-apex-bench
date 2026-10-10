# Changelog

## Unreleased

Merged into main through PR #63 without a version: no tag, GitHub Release or Zenodo deposit.
CITATION.cff and .zenodo.json keep their prepared version field unchanged.

- A10–A12.1: Pages builder, Axis 4 streaming truth v1.1 from compressed sources, native
  decoder worker configuration (BGZF thread pool; other readers NOT_SUPPORTED above one worker).
- A13a: Axis 4 run order — input hashing and native open, bounded recorded quiet wait, then
  the unchanged silence gates bracket only the timed groups.
- A13b: BGZF geometry under truth v1.1 from the BGZF archive and its `.fai`.
- A13c: real release assembly references catalog data roots by per-file hashes.
- A13d: leaderboard keeps a window-law family with failed data visible (`-Wnone` table).
- Axis 4 N10 (protocol v1.2, ace-core): first official cohort-region measurements,
  [results](review/axis4_n10/results_v12/RESULTS_N10.md), [protocol](review/axis4_n10/PROTOCOL_AXIS4_N10.md).

- A6: Axis 4 native cohort queries with frozen FASTA/request hashes, independent
  verification of every answer SHA and seed-selected stored answer bytes.
- A7: Axis 5 frozen corruption protocol, bounded native workers, independent
  classification and hash-bound evidence. Scientific integrity FAIL remains visible.
- A8: deterministic MD/CSV/JSON leaderboards, source evidence links and SHA-256,
  axis verification, duplicate and comparison-condition rejection.
- A9: offline release assembly, complete artifact manifest and independent
  re-verification; reproduction entry point; citation and deposit metadata.

Acceptance facts and limitations: [release notes](RELEASE_NOTES_v0.2.0.md).
Official ace-core results: [Axis 4 N10 v1.2](review/axis4_n10/results_v12/RESULTS_N10.md) (independent verify 96/96 PASS);
Axis 3 window-law B verdict evidence and Axis 5 (synthetic only) as listed in the release notes.
