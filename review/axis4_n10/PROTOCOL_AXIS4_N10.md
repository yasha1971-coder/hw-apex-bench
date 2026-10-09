# PROTOCOL_AXIS4_N10 v1 - Axis 4 cohort region access on 10 HPRC assemblies (ace-core, CPU)

Status: frozen draft. Its SHA-256 is recorded outside this file (commit message and run log) before any input is built.
This is a SEPARATE protocol. It does not replace, amend or reinterpret `PROTOCOL_COHORT_REGION` (M3, 20 x 558,
`research/bench2610/PROTOCOL_COHORT_REGION.md`, SHA-256 888b5b54...a888). Results of this protocol are labelled
`axis4-n10` and are never mixed with, scaled to or presented as 558-assembly results.
Execution tool: A6 `tools/axis4.py` (prepare / run / verify) unchanged, see `review/axis3/AXIS4.md`.

## 1. Cohort (deterministic, no free choice)

Rule, applied by `make_n10.py` (`select`): walk `~/panvram/MANIFEST.tsv` in file order; keep a row when
- its name is `y1_<ID>` and its status is `ok`;
- `~/pubrepo/.wk/hprc50/list.tsv` has `<ID>` with the same source URL and the same source SHA-256 as the manifest row;
- `~/pubrepo/.wk/hprc50/<ID>.fa.gz` exists (source already local, nothing is downloaded);

and take the first 10. Every selected assembly is in the 558 manifest, so its refrel3 v1 q4k/q16k archives exist
(`~/pubrepo/.wk/hprc_cohort/v1/<name>.q4k.rr3`, `.q16k.rr3`, SHA-256 in the manifest).

Result (frozen order = cohort order): y1_HG00438.1, y1_HG00438.2, y1_HG00621.1, y1_HG00621.2, y1_HG00673.1,
y1_HG00673.2, y1_HG00735.1, y1_HG00735.2, y1_HG00741.1, y1_HG00741.2.
Per assembly, `inputs/selection_n10.tsv` records: source URL, source SHA-256, local source path, FASTA bytes and
FASTA XXH3 (manifest), q4k/q16k bytes and SHA-256. The FASTA SHA-256 is recorded in the A6 corpus manifest when the
FASTA is materialised (section 3); for the first four it is already known (`~/pubrepo/.wk/vB/cohort.json`):
d18be91b...7bb5, 21b9bede...6aa0, cc2d6a10...a967, 96af478e...4506.

## 2. Requests and truth

- Requests = the `PROTOCOL_COHORT_REGION` requests (`requests.tsv`, SHA-256 2eacaa0b...8d22) restricted to the 10
  assemblies: 20 regions x 10 assemblies = **200 requests** (`inputs/requests_n10.tsv`, frozen order: region j, then
  cohort order). The region rule (contig rank, length, relative offset; `random.Random(20261008)`) is that protocol's.
- A6 groups: group j (j = 0..19) maps each of the 10 assemblies to its own `(contig_id, start0, end0 = start0 +
  length)` of region j (`inputs/groups_n10.json`, 20 groups). Coordinates are 0-based half-open.
- Truth, three independent layers, all must agree, else STOP (no run):
  1. `inputs/truth_n10_case.tsv`: the 200 matching rows of the `PROTOCOL_COHORT_REGION` truth (`truth.tsv`, SHA-256
     136c688f...b1fe; case as in FASTA; q16k v1 decode with every check, cross-checked against samtools faidx on
     these sources).
  2. When the FASTA are materialised: for every request, SHA-256 of the case-preserved bytes cut from the FASTA by a
     sequential parser equals layer 1.
  3. A6 `prepare` computes the canonical (upper case) expected SHA-256 of every response from the frozen FASTA; the
     prepared SHA-256 is kept outside the evidence directory as the trust anchor for `verify`.
- Every response of every run: SHA-256 equals the prepared truth and 32 sampled responses are retained byte-for-byte
  (A6, `random.Random(20261003)`); any mismatch makes the row FAILED.

## 3. Inputs (one input root; nothing downloaded during prepare/run)

| item | rule |
|---|---|
| FASTA | `gzip -dc hprc50/<ID>.fa.gz` once; source SHA-256 == manifest before, FASTA bytes == `fasta_bytes` and XXH3 == `fasta_xxh3` after, else STOP. Existing byte-identical copies (vB/fasta, same SHA-256) are hard-linked, not copied. |
| T2T reference | `~/golden/genome/t2t.fa` (SHA-256 51ab7d3c...6e4c), symlink, read only |
| refrel3 q4k, q16k | v1 archives of the manifest, symlinks; SHA-256 == manifest; `libhwa_refrel3.so` with its receipt |
| BGZF default | `review/axis3/bgzf_adapter.create(..., mode="default")`, htslib 1.24 (4b705e4) + libdeflate dd12ff2, build threads 1, `.fai` + `.gzi`. vB/bgzf_default archives for the first four are reused only with the same builder receipt (mode, htslib, libdeflate, threads) and SHA-256. |
| zstd seekable | `canon.py` (upper case, no headers/line ends) -> FIFO -> zstd 1.5.7 (f8745da) `seekable_compression <fifo> 16384 3` (frame 16 384 B, level 3) + `map.json`; same settings as vB `zstd_seekable_l3_f16k`, reused for the first four on SHA-256 match |
| faidx | family `fasta-faidx`, variant `plain`: the frozen FASTA + `FASTA.fai` built by `samtools faidx` (htslib 1.24) for all 10 |
| AGC t2t, noref | AGC 3.2.4 e67e3fc built with `AGC_PLATFORM=native bash review/axis3/build_agc_v324.sh <new dir>` (platform and library SHA-256 recorded); exactly one `review/axis3/agc_adapter.create` per mode over exactly these 10 in cohort order, `-t 16`; t2t = external T2T reference, noref = first member as reference. M6 used `-d -k 31 -l 20 -s 60000 -b 50 -t 16`; k/l/s/b equal the e67e3fc defaults (`src/app/application.h:63-66`) and `-d` only omits the stored command line, so the compression settings are identical. |

Storage is counted per A6 (distinct required paths once; shared T2T once).

## 4. Execution

- Variants (fixed order): refrel3 q4k, refrel3 q16k, BGZF default, zstd seekable, faidx plain, AGC t2t, AGC noref.
  Same scope (`cpu-in-process`, one persistent reader), same timing boundary (A6: one complete group = in-process
  fetch, upper-case normalisation, SHA-256 judgement, coordinate translation), same 200 requests for every variant.
- Threads: 1 (A6 `decoder_threads = 1`). A 16-thread row is part of this protocol's intent, but A6 refuses any reader
  that is not one-thread in process (`tools/axis4.py:257`); the 16-thread row is NOT RUN until a separately frozen
  tool version exists. It is never emulated by other means.
- Per variant: 3 warm-up + 9 recorded `axis4 run` invocations, each into a new output directory; all 12 evidence
  files are retained and each passes `axis4 verify` with the external prepared SHA-256. Reported per variant: median /
  min / max of the 9 per-run sums of group seconds, the 9 raw values, answers/s, storage bytes.
- Measurements strictly one at a time; nothing else of ours runs during a run.
- Silence gate before and after every run (A6's own gate, unchanged): host ace-core, load1 < 0.5, available data-disk
  bytes > 20 000 000 000, CPU sample >= 1 s, no foreign process >= 10 % of one CPU. A failed gate means wait and retry;
  the gate is never weakened or skipped. No run while refrel-v2 jobs exist
  (`pgrep -f "rv2 |rr3bench|run_law|run_bench|h4big"` empty for 5 minutes).

## 5. Method check (before the main run)

One format (refrel3 q4k, threads 1) on 10 % of the requests: `inputs/groups_n10_check.json` (groups 0 and 1 =
20 requests), its own `prepare`, one `run`, `verify` PASS. Not reported as a result. Any failure: STOP, fix, repeat.

## 6. Disk budget

`inputs/budget_n10.json` (from `make_n10.py --free-bytes <df -B1 avail>`): exact bytes for the FASTA to materialise,
upper estimates for BGZF / zstd / AGC (ratios of the four existing builds; AGC from the measured N=4 and N=5 archives),
plus the gate's 20 000 000 000 B that must still be free at measurement time. If the budget does not fit, the
protocol is BLOCKED; no existing file is deleted or moved by the executor.

## 7. Reporting

Release evidence is labelled `axis4-n10` with this protocol's SHA-256, the prepared SHA-256, every input SHA-256,
library SHA-256 and build receipts, all gate records and logs. Axis 5 stays synthetic-only in v0.2.0 (A9).
