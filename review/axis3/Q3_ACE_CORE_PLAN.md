# Q3 large-input acceptance plan — NOT A BENCHMARK

Status: prepared, not executed. Applies to protocol v1.1; no performance measurements.

## Input and preflight

Create one synthetic FASTA with a single contig and **1,718,000,000 canonical bases** (> 1.6 GiB). Generate it deterministically with `python3 review/axis3/q3_plan.py generate --output "$Q3_ROOT/input.fa"` only on ace-core. The generator streams bounded chunks; it does not materialize the sequence in RAM. Use the same input for every codec. Record the FASTA SHA-256, canonical sequence SHA-256, generator version, and seed. Keep the original input unchanged.

Set `Q3_ROOT` to an empty directory with **at least 30 GiB free** before starting; this is a conservative reservation, not a measured storage requirement. Actual peak disk use must be recorded. Runtime is **unknown; needs ace-core measurement**. Never substitute a time estimate for a recorded duration.

## Acceptance matrix

Required rows: refrel3 q4k/q16k, BGZF default/matched-g, zstd-seekable, indexed LZ4, OZSEG/OpenZL four frozen variants, AGC t2t/noref, FASTA+faidx. Each row: native build receipt, encode, full decode and SHA of canonical bytes, boundary fetch at offsets 0, Q-1, Q, final valid window, and a window crossing the 2^31 byte boundary where possible. No clipping, no fallback. Record process exit, RSS peak, archive+index bytes and all output hashes. Missing adapter/toolchain is FAILED with reason, not a pass or an invented measurement.

This plan is not a runner for the native matrix. Native acceptance must be implemented and reviewed separately; do not mark Q3 complete based on this document or on the generator alone.
