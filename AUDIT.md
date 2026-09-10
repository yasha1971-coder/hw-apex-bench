# ACEAPEX latency audit — findings

Update 2026-09-10: the user selected API-only timing and both named ACEAPEX profiles. The [current table](README.md) follows the new raw-byte contract with `interactive` and `dense` at SHA `1b13df34ac8e839dd3232b59bc59560d689a435a`. Its [evidence](evidence/profiles-20260910/) is separate from this historical audit. The [exact EPYC 9V74 FAIL output](evidence/audit-20260909/FAILS.md) remains preserved. Findings and withdrawn conclusions below refer to the original sequence-region experiment.

The first-table performance conclusion remains withdrawn. The configuration mismatch is confirmed; the current reference library call is reproduced by the common harness after matching its trace and timing boundary.

Audit source commit: baede64fd37bd087eecf9a94333d8fbf33e23c33.
[Successful audit workflow](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/34417102681).
Machine: AMD EPYC 9V74, four logical CPUs; paired measurement processes pinned to CPU 0; zstd 1.5.7.

## Measured findings

* On the original benchmark SHA/API -O3, changing only FSE_CHUNK from 32768 to 4096 lowers the common harness median p50 from 0.290460 to 0.194559 ms. Both are medians of three 200-query runs on this machine.
* On reference ACEAPEX SHA 1b13df34ac8e839dd3232b59bc59560d689a435a, API -O2 and the same 4 KiB-FSE archive, unchanged libseek reports 0.154 ms. The common harness with the exact same query trace and API-only timing reports 0.153988 ms.
* On that reference API/archive, the ordinary common harness reports 0.185915 ms. It includes newline removal and uses a different query trace. This combined difference is about 32 microseconds; the complete variant matrix is preserved below.
* On chr1 at FSE_CHUNK=4096, the old src encoder with one requested thread, old depth encoder with eight, and current depth encoder with eight produce byte-identical archives (SHA-256 b2e3098b6492a21b25bc8cc2e1c8f55aba340d6820845320477025395afccc46). Those encoder/thread differences do not explain this corpus's latency discrepancy.
* One versus ten random warmups does not produce a threefold effect in the measured variants. Results are retained for both; no claim that warmup has zero effect is made.
* The original reproduce_paper5.sh, executed unmodified from the reference clone with the documented corpus and zstd paths, reports lowlat_region_p50_ms = 0.151 on this machine. The script's text cites 0.081 ms on EPYC 4344P. This CI run cannot establish a universal 0.082 ms absolute target.

## What the successful audit does and does not certify

The audit compared 39 archive/API/harness combinations, three repetitions each.
All four archives passed complete byte comparison. The verified harness variants
checked 19,200 timed responses byte-for-byte. The upstream libseek runs were
preserved unchanged and only perform their original negative-return check.

The audit workflow succeeded because the controlled experiment and evidence checks
completed. The ORIGINAL reproduction script exited 1: numpy was absent for two
parse claims, the batch speedup predicate failed at 4.8x, and its OUT variable was
overwritten with batch stdout before the final JSON filename was used. The lowlat
section ran and produced 0.151 ms. Its log, including these failures, is preserved.
No upstream fixes were made and the original script is not declared all-green.

The earlier 0.282-ms table used a different FSE configuration, old API revision,
different trace and a broader timed operation. It is not a matched reproduction of
the lowlat claim. The general speed conclusion stays withdrawn until a public
profile and operation contract are selected consistently for all codecs.

## Evidence

[Full measured matrix](evidence/audit-20260909/AUDIT_RESULTS.md).
[Raw measurements, gzip-compressed JSON](evidence/audit-20260909/audit-results.json.gz).
[Commands, versions and environment](evidence/audit-20260909/audit-metadata.json).
[Reference script log](evidence/audit-20260909/reproduce.log).
[Evidence receipt](evidence/audit-20260909/receipt.json).

The uncompressed raw JSON hash is cc9d56006166bce042416eabffcb421e56e427e3d786adc5474758e36748d246.
The receipt lists both compressed and uncompressed hashes. Workflow log transport
timestamps and UTF-8 log-chunk markers were removed during retrieval; the
reference log matches the SHA-256 recorded by the runner.

---

# ACEAPEX latency audit

Status: controlled audit completed; public comparison remains held. Configuration inventory and original experiment plan follow.

| Item | Stage-1 table | reproduce_paper5.sh lowlat claim |
|---|---|---|
| ACEAPEX commit | b1bee4df9c1c0a18d979df2a43947ef1b7adeb57 | Current script inspected at 1b13df34ac8e839dd3232b59bc59560d689a435a |
| Encoder source | src/aceapex_main.cpp | aceapex_depth.cpp |
| Encoder flags | -O3 -std=c++17 | -O3 -march=native -funroll-loops -std=c++17 |
| Encoder threads requested | 1 | 8 |
| ACEAPEX_BS | 16384 | 16384 |
| LIT_CHUNK | 65536 | 65536 |
| FSE_CHUNK | 32768 | 4096 |
| MIN_MATCH | 0 | 0 |
| Profile argument | none | none |
| Region API | aceapex_decompress_region | aceapex_decompress_region |
| Archive | loaded once into malloc buffer | loaded once into malloc buffer |
| Per-query file/process operations | none | none |
| Warmups | 10 random plus 2 boundary probes | 1 random |
| Query seed | 20260909 | 20260812 |
| API compilation | -O3 | -O2 |
| Timer includes FASTA newline removal | yes | no |
| Quantile indices, zero based | 99 / 197 | 100 / 198 |

Both benchmark entry points use environment variables, not --profile. The stage-1 environment is inherited unchanged by compression and region reading. The reference lowlat section explicitly sets FSE_CHUNK=4096 at both compression and region read.

## Experiment

1. Run both original harnesses against the same archive and API object on the same CPU, with repeated runs and rotated order.
2. Change only FSE_CHUNK, writing a new archive with matching decode settings.
3. Separate API compiler optimization, encoder source/thread count, trace/warmup and timed normalization differences.
4. Run the reference lowlat procedure from the pinned current ACEAPEX clone. Do not tune toward the published 0.082 ms absolute number; report this machine's measurements.
5. Preserve commands, versions, archive hashes, exactness checks and individual measurements. Re-open the public comparison only after the discrepancy is accounted for.

Existing ACEAPEX, GLYPH and context repositories remain untouched.
