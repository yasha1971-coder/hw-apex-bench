# Local c_window(g) review — 2026-09-18

Reviewed PR43 source f4c898b0ed50c5c1061a2c08e254cf74a3e0dca6 and the retained
baseline/sweep bundles. No re-encoding, resampling or new timing was needed.

- Recomputed all300 derived values,30 aggregates and100 paired differences.
- Checked60 baseline archive hashes/lengths and logs against the retained bundle.
- Checked300 swept archives,30 frozen inputs and60 historical16KiB identities.
- Five baseline-validation tests passed, including malformed baseline rejection.
- Calculation uses1-sum(baseline_bytes)/sum(point_bytes), not mean percentages.
- Same fixed2MiB inputs; one LZ block or one nonempty zstd frame per baseline.
- Zstd empty terminal frame/seek table counted; ACE literal chunks remain64KiB.
- Corpus/revision/scope differences prevent splicing historical chr1 c_file(g)
  into this T2T c_window(g) curve. Whole-T2T comparison remains unmeasured.
- BGZF65280-byte blocks differ from ACE65536-byte blocks by0.392%; the original
  fixed16KiB comparison and the comparable64KiB comparison both remain visible.

Presentation remediation: explicit c_window(g) report headings, scope guide,
generated README distinction and numbered ledger. HWB-001 records selected-HOR
sensitivity; HWB-002 marks useful-reference reach as unproven. No trace of match
lengths/distances was measured. HWB-003 specifies the later resident-access study.

Integrity gate passed: historical435 publication, generated Pages,176 current
Markdown links. No raw evidence JSON/JSONL, codec, DOI or tag changed. README
presentation checksum alone was refreshed in the publication manifest.

Disposition: the retained local numerical curve passes this bounded review.
PR43 remains unmerged. Its README scope warning must be present in the resulting
main tree; resolve the presentation-manifest overlap with PR44 by regeneration,
never by selecting an old checksum. Do not promote the mechanistic hypothesis
to a confirmed claim or claim a complete whole-genome/latency experiment.
