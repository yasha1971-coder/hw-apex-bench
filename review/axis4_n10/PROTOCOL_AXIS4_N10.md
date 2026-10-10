# PROTOCOL_AXIS4_N10 v1.2 - Axis 4 cohort region access on 10 HPRC assemblies (ace-core, CPU)

Status: FROZEN v1.2, before any Axis 4 N10 measurement. A file cannot contain its own hash: the SHA-256 of this
file is recorded in the sidecar `PROTOCOL_AXIS4_N10.md.sha256` and in the freezing commit message.
v1.2 changes ONLY the tool version (section "Tool"); cohort, requests, truth v1.1, inputs, rows, repetitions, gate
thresholds and reporting are those of v1.1 (sha256 51989922...c479). Under v1.1 no timed row completed: the method
check was refused 6/6 by the old A6 after-gate (own reader-open CPU in load1) and the BGZF reader could not open
under truth v1.1; both are tool defects fixed by A13a/A13b. v1 and v1.1 are superseded.
This is a SEPARATE protocol. It does not replace, amend or reinterpret `PROTOCOL_COHORT_REGION` (M3, 20 x 558,
`research/bench2610/PROTOCOL_COHORT_REGION.md`, SHA-256 888b5b54...a888). Results are labelled `axis4-n10-v1.2` and are
never mixed with, scaled to or presented as 558-assembly results.
Tool: hw-apex-bench `38cb566` = A6 `tools/axis4.py` with A11 (streaming truth, `docs/AXIS4_STREAMING.md`), A12.1
(native decoder workers, `docs/AXIS4_THREADS.md`) at `34db4e2`, plus A13a `91b8b31` (run order: input hashing and
native open, bounded recorded quiet wait, gate before, timed groups, gate after, close), A13b `b332e0b` (BGZF geometry
from the BGZF archive and .fai under truth v1.1) and A13c `38cb566` (release references data roots by hash).
`tools/axis4.py prepare` is unchanged by A13, so the frozen prepared-v2 (sha256 22006f26...04e2) is reused.

## 1. Cohort (deterministic, unchanged from v1)

Rule (`make_n10.py`, `select`): walk `~/panvram/MANIFEST.tsv` in file order; keep a row when its name is `y1_<ID>`,
status `ok`, `~/pubrepo/.wk/hprc50/list.tsv` has `<ID>` with the same source URL and source SHA-256, and
`hprc50/<ID>.fa.gz` exists; take the first 10. Every one is in the 558 manifest (refrel3 v1 q4k/q16k exist).
Frozen order: y1_HG00438.1, y1_HG00438.2, y1_HG00621.1, y1_HG00621.2, y1_HG00673.1, y1_HG00673.2, y1_HG00735.1,
y1_HG00735.2, y1_HG00741.1, y1_HG00741.2. Provenance per assembly: `inputs/selection_n10.tsv` (sha256 d6fbdf99...a053).

## 2. Requests and truth (truth_version 1.1)

- Requests: `PROTOCOL_COHORT_REGION` requests restricted to the 10: 20 x 10 = **200** (`inputs/requests_n10.tsv`,
  sha256 de259175...94a2); 20 A6 groups (`inputs/groups_n10.json`, 98f5e820...11c9); coordinates 0-based half-open.
- Truth source: the original compressed `.fa.gz` (hard links of the hprc50 files, 0 new bytes), manifest
  `axis4-corpus-v1.1`, `fasta` = path/bytes/sha256 of the compressed file, which must equal the MANIFEST source hash.
  `python3 -m tools.axis4 prepare ... --truth-version 1.1` -> `axis4-prepared-v2`; its SHA-256 is kept outside the
  evidence directory as the trust anchor of `verify`.
- Truth equivalence, required BEFORE any measurement (`stage_v11.sh` -> `truth_v11_check.py`, independent of
  `tools/axis4_stream.py`: zlib over every gzip member through EOF, own FASTA parser):
  1. compressed SHA-256 of each source == `selection_n10.tsv` source_sha256 (10/10);
  2. case-preserved SHA-256 of each of the 200 answers == `inputs/truth_n10_case.tsv` (sha256 344f4bc7...1f73,
     the `PROTOCOL_COHORT_REGION` truth): **200/200**;
  3. upper-case SHA-256 of each answer == the expected SHA in `axis4-prepared-v2`: **200/200**.
  Anything less: STOP, no run. The logs and `truth_v11_check.tsv` are retained with SHA256SUMS.
- Every response of every run: SHA-256 equals the prepared truth; 32 sampled responses retained byte-for-byte
  (`random.Random(20261003)`); `verify` re-streams the `.fa.gz` independently. Any mismatch: row FAILED.

## 3. Inputs (one data root; nothing downloaded during prepare/run)

| item | rule |
|---|---|
| truth sources | `src/<id>.fa.gz` hard links to `hprc50` (A11 v1.1) |
| plain FASTA (faidx reader only; also the build input of BGZF/zstd/AGC) | `gzip -dc` once; bytes == `fasta_bytes`, XXH3 == `fasta_xxh3` of the MANIFEST, else STOP; byte-identical existing copies (vB/fasta) hard-linked |
| T2T reference | `~/golden/genome/t2t.fa` (51ab7d3c...6e4c), symlink, read only |
| refrel3 q4k, q16k | v1 archives of the manifest (symlinks, SHA-256 == manifest), `libhwa_refrel3.so` + receipt |
| BGZF default | `review/axis3/bgzf_adapter.create(..., mode="default")`, htslib 1.24 (4b705e4) + libdeflate dd12ff2, build threads 1, `.fai` + `.gzi`; vB/bgzf_default reused for the first four only on equal receipt and SHA-256 |
| zstd seekable | `canon.py` (upper case, no framing) -> FIFO -> zstd 1.5.7 (f8745da) `seekable_compression <fifo> 16384 3` + `map.json` (= vB `zstd_seekable_l3_f16k`); vB reused for the first four on SHA-256 |
| faidx plain | the plain FASTA + `FASTA.fai` from `samtools faidx` (htslib 1.24), all 10 |
| AGC t2t, noref | AGC 3.2.4 e67e3fc, `AGC_PLATFORM=native bash review/axis3/build_agc_v324.sh <new dir>` (platform + library SHA-256 recorded); one `agc_adapter.create` per mode over exactly these 10 in cohort order, `-t 16`; t2t = external T2T, noref = first member as reference. k/l/s/b = e67e3fc defaults = M6 values; M6's `-d` only omits the stored command line |

## 4. Execution rows

| variant | decoder threads 1 | decoder threads 16 |
|---|---|---|
| refrel3 q4k | measured | NOT_SUPPORTED row |
| refrel3 q16k | measured | NOT_SUPPORTED row |
| BGZF default | measured | measured (htslib pool, A12.1) |
| zstd seekable | measured | NOT_SUPPORTED row |
| faidx plain | measured | NOT_SUPPORTED row |
| AGC t2t | measured | NOT_SUPPORTED row |
| AGC noref | measured | NOT_SUPPORTED row |

- Every run passes `--decoder-threads N` explicitly (evidence `axis4-evidence-v5`). A NOT_SUPPORTED row is one
  `axis4 run --decoder-threads 16` whose evidence records NOT_SUPPORTED without starting a decoder; it has no timing,
  is retained, and is never emulated or converted into a performance row.
- Same scope (`cpu-in-process`, one persistent reader per run), same timing boundary (A6: one complete group =
  in-process fetch, upper-case normalisation, SHA-256 judgement, coordinate translation), same 200 requests, same
  prepared-v2 for every row.
- Per measured row: 3 warm-up + 9 recorded `axis4 run` invocations, each into a new directory; all 12 evidence files
  retained and each passes `axis4 verify` with the external prepared SHA-256. Reported: median / min / max of the 9
  per-run sums of group seconds, the 9 raw values, answers/s, storage bytes, CPU model and affinity from evidence.
- Order: rows in the table order, threads 1 before 16. Strictly one run at a time.
- Silence gate before and after the timed groups of every run (A6's own, thresholds unchanged): host ace-core,
  load1 < 0.5, available data-disk bytes > 20 000 000 000, CPU sample >= 1 s, no foreign process >= 10 % of one CPU.
  A13a order: input hashing and native open, then a bounded wait (same gate every 15 s, at most 1800 s, every refused
  sample recorded in evidence `admission`), gate before, timed groups, gate after, close. A run whose gate does not
  PASS is retained and the slot is retried; the gate is never weakened or skipped. No run while refrel-v2 jobs exist
  (`pgrep -f "rv2 |rr3bench|run_law|run_bench|run_diag|perf stat"` empty for 5 minutes).

## 5. Method check (before the main run)

refrel3 q4k, `--decoder-threads 1`, on 10 % of the requests: `inputs/groups_n10_check.json` (groups 0 and 1 = 20
requests), its own `prepare --truth-version 1.1`, one `run`, `verify` PASS. Not reported. Any failure: STOP, fix, repeat.

## 6. Disk budget

`budget_v11.json` (`budget_v11.py --free-bytes <df -B1 avail>`): truth needs 0 bytes; the plain FASTA is still
required by the faidx reader (and serves as the build input of BGZF/zstd/AGC); exact bytes for the FASTA to
materialise, upper estimates for BGZF/zstd/AGC, plus the gate's 20 000 000 000 B free at measurement time. If it does
not fit, the protocol is BLOCKED; the executor deletes or moves no existing file (user cleanup: `cleanup_axis4.sh`).

## 7. Reporting

Release evidence is labelled `axis4-n10-v1.2` with this protocol's SHA-256, the prepared-v2 SHA-256, every input
SHA-256, library SHA-256 and build receipts, all gate records and logs. Axis 5 stays synthetic-only in v0.2.0 (A9).
