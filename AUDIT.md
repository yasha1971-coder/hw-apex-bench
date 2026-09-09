# ACEAPEX latency audit

Status: IN PROGRESS. The published performance comparison is held for review.

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
