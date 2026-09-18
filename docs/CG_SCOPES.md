# Two scopes of granularity cost

Both use complete stored files and the same ratio-loss definition. Names below
make the input boundary explicit; they do not rename fields in frozen evidence.
Always include g, input, codec revision and the one-block baseline with a claim.

| Name | Input and baseline | Example at g = 16 KiB | Status |
|---|---|---|---|
| c_file(g), whole-input granularity cost | Complete hg38 chr1 FASTA, 253935557 bytes; one whole-input block/nonempty frame | ACEAPEX ee5a37e: 1.632%; matched zstd-seekable: 6.569% | Published historical evidence |
| c_window(g), window-local granularity cost | Same frozen 2 MiB base-only T2T window; one block/nonempty frame per window | ACEAPEX 4915321: HOR 60.565%, controls 1.492% | PR #43, separate review required |

The window-group aggregate is one minus the sum of baseline bytes divided by
the sum of point bytes. It is not the mean of percentages, nor a single archive
of concatenated windows. HOR and controls each contain ten selected windows.
One ACE LZ block does not mean one literal entropy chunk.

The file example is chr1, not the complete human genome or T2T. The window
example also changes corpus, representation, input length, sampling and ACE
revision/policy. Do not divide these percentages or overlay them as one curve.
The zstd 6.569% matched baseline is distinct from the historical 7.181%
CLI-versus-seekable comparison. See the [baseline audit](AUDITS/CG_BASELINE_REVIEW.md)
and [strict ACE reproduction](AUDITS/STRICT_CG.md).

A 60.565% ratio loss is relative to that codec's own one-window baseline; it is
not a 60.565% loss against BGZF, a genome-wide figure, or measured latency.
At approximately 64 KiB ACE can beat BGZF in absolute density and still lose
density relative to its own 2 MiB baseline. The actual BGZF blocks are 65280
bytes versus ACE 65536 bytes (0.392% larger), comparable but not identical.
See the [published sweep](RESULTS/T2T_GRANULARITY_20260916.md) and
[local-baseline PR #43](https://github.com/yasha1971-coder/hw-apex-bench/pull/43).

Greater sensitivity on HOR does not measure a distribution of useful match
lengths or distances. Larger blocks also change metadata and entropy coding.
Region latency and decoded-byte amplification on these windows are a separate,
not-yet-run experiment. No matched whole-T2T c_file(g) curve is available.
