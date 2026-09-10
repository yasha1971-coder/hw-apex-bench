# GPU evidence contract

GPU measurements are a separate device-resident path. They are never inferred
from CPU results and are not silently compared with a CPU codec operation.

Every published GPU point must name the GPU, VRAM, driver, CUDA version,
ACEAPEX commit, `G`, corpus MD5, block size, command, and correctness outcome.
An absent GPU adapter is `n/a` with a reason, never zero.

The declarations imported from `gpu-results.declared.json` were supplied without
raw pod logs. They therefore remain `declared`, even though the supplied outcome
is `MATCHES OK`. The published commands follow the CLI contract at the pinned
upstream commit:

```bash
env ACEAPEX_BS=<block_bytes> ./aceapex_depth c --in chr1.fa --out /tmp/chr1-<block_bytes>.aet --threads 8
env ACEAPEX_BS=<block_bytes> ./aceapex_depth d --in /tmp/chr1-<block_bytes>.aet --out /tmp/chr1-<block_bytes>.restore
./e2e_pipe streams.bin chr1.fa 16
./e2e_seek streams.bin chr1.fa 16 <start_block> <count>
./scan_bench streams.bin 0 <block_count>
```

The single supplied `streams.bin` MD5 is attached only to 16 KiB rows. It is not
copied to 4 KiB or 8 KiB rows because their block counts prove that they use a
different stream image. Those rows explicitly say that their per-point stream
hash was not supplied.

The supplied full-decode block counts are exactly one below
`ceil(253935557 / block_bytes)` at 4, 8 and 16 KiB. Both reported and derived
counts are retained. The full-decode command intentionally omits range arguments,
which is the documented whole-archive invocation; raw logs are required before
the count discrepancy can be resolved.

The old 172 GB/s and 0.36 ms values are excluded because they refer to a different
commit/configuration. Seek observations are not relabelled p50 or p99. FASTQ and
other points lacking corpus/block provenance remain outside the headline table.
