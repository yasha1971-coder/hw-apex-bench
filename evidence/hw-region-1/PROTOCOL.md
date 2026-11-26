[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-1 execution protocol

The unchanged P1–P3 and Kill are in CALIBRATION.md, first and only file in
8108834615cbd651f79f77cb8d81fed24fa269f1, before any measurement. This branch
starts at main e8aa8488310d8cb7d5793f2e49a707c67f80b689. The owner has merged
HW-GIFT-1e and the external-text policy; their data are not new observations here.

Decision/consumer: Yakov and ACEAPEX maintainers need a current, same-run region
comparison and a measured explanation of any remaining latency gap. The best
same-function alternatives are native persistent zstd-seekable and BGZF. P1–P3
remain unchanged; no codec optimization is part of this experiment. Source
foundations and closed avenues will be cited by file:line in RESULTS.md.

## Pins, inputs and grid

ACEAPEX tag v2.6.5 (annotated tag 8fd46ca8c0c907cf352f15fb6de062d5531e6489,
commit ce6b6740c7aae8a01720d615ae024c181b7d52b6); zstd v1.5.7 at
f8745da6ff1ad1e7bab384bd1f9d742439278e99. HTSlib/libdeflate retain the exact
current bgzip adapter pins. Each source checkout and build is experiment-owned.
Record source/headers, compiler/flags, binary hashes and CLI/linked versions.
Record the literal C99 header version too: its version string may lag the tag;
do not edit upstream sources or substitute that string for the pinned identity.

Preserve the v2.2.0 adapter byte-for-byte as codecs/aceapex_v220.sh; bump the
active adapter pin/label/version to 2.6.5. Keep interactive level 2, one encoder
thread, LIT_CHUNK=65536 and FSE_CHUNK=4096. No persistent-DCtx, literal-chunk or
FSE-chunk optimization: those directions have already been examined. The current
upstream C99 reader already reuses its own DCtx and caches; measure that reader.
Zstd-seekable retains the current original hint policy, level 3 and checksums.
BGZF uses the existing matched-g HTSlib writer, level 6, flush per requested
block, with a required .gzi index. No format or codec algorithm is changed.

Corpora:

- Full UCSC hg38 chr1 FASTA, including header/case/newlines: 253935557 bytes,
  MD5 9465e0f0df6e2c6eb39729c39cee5465, SHA-256
  04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0.
- The original thirty 2097152-byte T2T windows, with coordinates, bytes and SHA
  from evidence/t2t-regions-20260916/manifest.json (canonical Git blob SHA-256
  c5bc7014ecd0d6c7855e7ad1b01afbd20b8a7f2e55c93c8e78098fa4c049a763).
  Recover exact saved windows; do not rerun selection or normalize them again.
  If the old ZIP is unavailable, download the exact canonical NCBI FASTA from
  corpora.json, verify compressed MD5/size and full expanded MD5/size, then
  extract only the frozen manifest coordinates using its original case-preserving
  bases-only representation. Accept them only if all thirty saved SHA values
  and lengths match. This reconstructs the same inputs, without a new selection.
- Full enwik8 and silesia.tar, with the existing corpora.json SHA/size identities,
  as same-run reference files at g=16384 only.

Chr1 plus the 30 windows: g=4096,16384,65536; BGZF actual requested ceiling at
the last point is 65280, which must be labelled rather than called exactly
matched. Reference files have one g=16384 point per codec. Total: 95 archive
cases per codec and 285 codec/corpus/g cells. Ratio is input bytes divided by
the complete archive and every required index byte. Record actual geometry.

## Request trace and fairness

R=16384. Generate and retain 1000 integer offsets per corpus, uniform on the
inclusive interval [0,input_bytes-R], with Python Random and seed 20261126 plus
the corpus SHA interpreted as a big integer. Generate twelve separate warmup
offsets before the 1000 offsets and retain both files and their hashes. Reuse
exactly the same two files across all formats and g for that corpus.

Use existing hc_open/hc_region/hc_close resident ABI: one persistent C99 ACE
handle, one ZSTD_seekable, or one BGZF handle per pass. Archives are resident
in RAM; BGZF reads from the existing memfd-backed handle. Create contexts and
prefault all output buffers outside timers. Twelve warmups precede every pass.
Only hc_region is inside the integer CLOCK_MONOTONIC interval; no Python,
shell, harness allocation, comparison or file I/O is timed. Codec-internal
allocation, workspace initialization and cache growth inside that API remain
inside its timer. Verify every returned region
against the exact source after the timer, preserve output bytes for independent
dd+cmp checks, and write raw samples only after the pass. No offsets are dropped.

Native persistent caches remain enabled and evolve along the fixed trace.
Report their effects; do not turn them off to manufacture decode work. Contexts
are fresh between independent passes, including the two method-check passes.
Quantiles use nearest rank: p50 is sorted observation 500, p99 is observation
990 of 1000 (one-based). All gates compare unrounded integer/fraction values.

## Method gates before main timing

Source/version, complete archive restore and every requested region must pass
byte equality; include an independent dd+cmp check of retained outputs. Reject
corrupt archives and invalid ranges rather than reporting a successful zero.
Verify known work counters (one standalone zstd frame means one call and its
actual returned bytes; cache/raw bypass does not invent zstd calls). A separate
counter build must restore the same bytes and follow the same warmup/offset
trace as its uninstrumented timed build. Count actual API invocations and
successful returned output bytes, never capacities or a geometric formula.

Keep physical materialized-chunk bytes/amplification separate from actual zstd
output bytes: ACE has non-zstd and packing paths. Use actual reconstruction
hooks for zstd-seekable and BGZF; a streaming output cursor alone can undercount
internally decoded bytes. Instrumentation is untimed, so it adds no work to the
published latency interval. Record per-request counters, including legitimate
zeros and API-family counts. Verify the ACE path uses the reused DCtx API used
for standalone constants; an unexpected API mixture is a method mismatch to
inspect, not permission to choose a convenient calibration after seeing times.

Negative amplification controls use fresh independent handles and the same R:
an aligned request versus one crossing an actual native decompression boundary.
At g=4096/R=16384 this is four versus five blocks, not one versus two. ACE's
outer LZ boundary need not be an entropy-chunk boundary; select the first valid
actual boundary deterministically from archive metadata outside all timers.
The crossing control must show higher measured amplification for every codec.

Then time each codec twice consecutively on chr1/g16384, with separate fresh
handles and the identical 12+1000 trace. Require abs(second_p50-first_p50)*20
<first_p50, strictly. Check all three before main cells. No stability retry
based on elapsed time; a failed method gate stops the study.

## Order and original Kill

Prepare/verify the primary chr1/g16384 archives first. After all method gates,
time ACE, zstd-seekable and BGZF for this primary case and checkpoint all three.
P1 HIT iff 1.4 <= ACE_p50/zstd_p50 <=2.2. Kill is strictly ratio<1.1, using
10*ACE_p50<11*zstd_p50. Outcome (a) uses ratio<=1.1 as the goal states; keep
that inclusive outcome boundary separate from the literal strict Kill.

Continue the comparative table, including references, even if Kill triggers:
the instruction limits decomposition beyond one cell, not the three-format
comparison. Standalone constants and the primary model cell are allowed; if
Kill triggers, do not compute decomposition/predictions for other ACE cells,
and report P2 NOT TESTED: Kill. Counter observations required for table columns
remain observations, not additional fitted decompositions.

Remaining order: chr1 g4096 then g65536; windows in frozen manifest order,
g4096/16384/65536; enwik8 then silesia at g16384. Rotate codec order by case
index modulo three: ACE/Zstd/BGZF, Zstd/BGZF/ACE, BGZF/ACE/Zstd. No result-based
reordering or timing retakes. Save and push each complete case checkpoint.

## Two-constant model (no ACE-time fit)

Use only zstd to build four standalone level-3 frames from the first 4096,
16384,65536,262144 bytes of the exact chr1 FASTA. Record plaintext/compressed
hashes. Each uses its own persistent ZSTD_DCtx, prefaulted output, twelve
warmups and 1000 individual decodes of that frame on the same core. Allocation,
frame construction and byte verification stay outside the timer. Each size is
a separate load-admitted timing unit. The API and linked library match ACE.

Fit y=c_call+c_byte*x to the four exact nearest-rank median ns and actual
decompressed byte sizes, with deterministic nonnegative least squares: evaluate
the unconstrained rational least-squares solution if both coefficients are
nonnegative; the c_call=0 boundary; the c_byte=0 boundary; and (0,0). Choose
smallest exact squared residual sum, tie-break by (c_call,c_byte). Preserve all
four observations/residuals and coefficients as exact fractions. Never refit
these constants to ACE timings or remove a frame-size point after seeing it.

For request i, use actual instrumented K_i calls and D_i zstd-output bytes:
m_i=K_i*c_call+D_i*c_byte. Predicted p50 is nearest-rank p50 of all 1000 m_i,
not a sum of independent medians. Sort predicted samples by (m_i,query_id)
and use rank 500's request j for additive terms: calls=K_j*c_call,
bytes=D_j*c_byte, residual=measured_p50-predicted_p50. Divide each term by
measured_p50 for signed shares; retain negative or >100% shares. No clipping.
This defines P3's calls share before observing any times.

P2 is conservatively evaluated on all 93 chr1/T2T ACE cells (three g values),
with chr1's three-cell verdict also shown separately: every target must satisfy
5*abs(predicted_p50-measured_p50)<=measured_p50. List every miss; do not pool
window latencies or average errors into a HIT. The two reference files are
additional labelled validation, not coefficient-fit data or extra P2 targets.
P3 uses the primary chr1/g16384 calls term >=0.5*measured_p50. For outcome (b)
name the largest absolute primary component and its signed share; identify
negative residuals as overprediction rather than hidden unexplained work.

## OVH admission, retries and delivery

Every timing unit uses blocking external flock /run/lock/ovh-bench.lock and
taskset CPU0. Wait for the shared lock; never bypass it. No build or archive
preparation holds that lock. T=1 decoder thread at both boundaries. Record
literal date -u, cat /proc/loadavg and nproc, CPU/kernel/governor/pin, process
snapshots and raw /proc/stat at start/end. Other-core deltas are observations.

LOADED iff Decimal(load1)-T>1.0 at either boundary, OR a foreign process exceeds
10% of one logical CPU in a fixed one-second observation immediately before
the start boundary, under the acquired lock and before warmups. Calculate
CPU from /proc ticks deltas and actual monotonic observation duration; never
use lifetime ps percentages or divide by host CPU count. Exclude only the
observer and its explicit controlling ancestry; do not whitelist other sessions,
builds or daemons. Record exited/new processes and inspection errors. At the
admission boundary only surviving processes have a current CPU percentage;
new processes use ticks accrued since birth, not a prior PID's lifetime count.
Uninspectable live-process data is ERROR, not silently CLEAN. The end foreign
CPU observation, if collected, does not introduce an extra exclusion predicate.

A logical unit is one 1000-query codec cell, one two-pass AA gate, or one
1000-decode standalone frame size. Retake only a LOADED unit, identical trace,
at most three attempts. Retain every attempt and report N retaken/M logical.
Three LOADED attempts stop BLOCKED: load with ps top eight. Source/byte/worker
errors are fatal even when loaded. Replay complete CLEAN units without timing;
inspect orphan/incomplete/error attempts rather than silently retrying them.

Independent controllers recalculate raw quantiles/gates/model/residuals, check
all hashes and source/version/region/counter proofs, and compare retained region
outputs with source slices using dd+cmp. No benchmark number is promoted from
another run. Outcome (a) updates dated README/SNAPSHOTS evidence while keeping
old rows; README is generated, so update its generator and manifest through the
existing publication contract rather than editing generated bytes by hand.
Outcome (b) reports the dominant measured term and signed share. The adapter
bump is requested; no upstream codec change is allowed. All absolute times
apply to this EPYC 4344P host and RAM archives. Draft PR #96 only, with the
exact ChatGPT first-line signature; no upstream message, Hacker News text or
merge. Apply docs/EXTERNAL_TEXTS.md to every external draft.
