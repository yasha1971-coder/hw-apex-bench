[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: owner-authorized casefix continuation

This amendment follows the owner's 2026-11-26 instruction after the retained
[original Kill](../RESULTS.md). That admission and all its raw outputs remain
unchanged. The original four-line [CALIBRATION](../CALIBRATION.md), first committed
alone in `7fdcbd78b27739cbe1739bf0a8650f395c2afbde`, is copied byte-for-byte here.
P1, P2 and P3 retain their original thresholds and probabilities. No timings from
HW-REGION-1 are reused as coordinate-query timings.

## Consumer, decision and source change

Yakov needs the equivalent, case-preserving genome-coordinate comparison before
making genome-access claims. The result will identify the latency/storage tradeoff
for the measured host and warm RAM archives; it is not a hardware-independent claim.

The lib2bit pin stays `58e20daa898a6fc338eae82e5d2ef7108d4fc07f` (MIT).
The [patch](../lib2bit-casefix.patch) changes exactly one line in `2bit.c:155`:
`if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);` becomes
`seq[pos] = tolower(seq[pos]);`. Clean original source is retained; original and
casefix are built in separate owned directories with identical compiler flags.
No other library source, algorithm, archive content or forecast changes.

## Inputs, coordinates and mandatory untimed admission

Use the original chr1 FASTA and all thirty frozen 2 MiB T2T sequences from
[HW-REGION-1 setup](../../hw-region-1/setup.json), verified by SHA256. chr1 remains
byte-identical; T2T FASTA is a single named sequence, 80 bases per LF-terminated
line, with sequence bytes and case unchanged. The original Apache-2.0
[writer](../writer.py) produces structurally verified `.2bit` with independent
N and soft-mask intervals. Count every reader-required file in stored bytes.

Reuse every original trace seed and its 12 warmups and 1000 requests, without
resampling. R = 16,384 bases. For chr1, map original FASTA byte offset b using
d=max(b-FAI.offset,0), s=(d//line_width)*line_bases+min(d%line_width,line_bases),
then s=min(s,sequence_length-R). Header offsets map to zero. Newline offsets map
to the next base. T2T original inputs are bases-only, so their starts are already
base coordinates. Record mapping statistics and exact trace bytes/hashes.

Before any timing, all four equivalent readers must return byte-equal reference
strings for all 31*(12+1000) requests. Also repeat the old lowercase-n witness
using casefix at chr1 start 121,749,276 (zero-based). Reference comes from the
plain FASTA through its FAI, removing CR/LF only; validation is outside timers.
Any failed required call, wrong length or unexpected byte difference is Kill:
stop immediately, retain the first mismatch and publish no timing table.

The unchanged reader is a diagnostic exception explicitly authorized by the
owner: only expected `n` -> actual `N` is allowed. The mask-disabled diagnostic
must equal the ASCII-uppercase reference. Neither diagnostic qualifies as an
equivalent reader. They cannot enter P1-P3 or fastest/smallest decisions.

This is qualification on the frozen sampled coordinate grid, not exhaustive
validation of lib2bit. Its separate known terminal-packed-byte read rejection
remains unpatched. Do not change starts, pad archives or add chromosomes to avoid
it; any actual required-grid failure still stops admission.

## Six rows and timer scope

The equivalent rows are ACEAPEX 2.6.5, zstd-seekable 1.5.7, BGZF/HTSlib 1.24
`faidx_fetch_seq64`, and `lib2bit-casefix (storeMasked=1)`. ACE is interactive
level 2, one encoder thread, LIT_CHUNK=65536/FSE_CHUNK=4096; zstd level 3; BGZF
level 6. FASTA block/frame target g=16384 bytes. P1-P3 use casefix exclusively.

Two separate diagnostics use the same `.2bit` bytes and original pinned library:
`lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs` is time-only;
`lib2bit (storeMasked=0): case-folded, not equivalent` is separate. Original
and casefix symbols are isolated in row-specific DSOs and fresh worker processes.

One fresh process per cell; one persistent native handle for its 12 warmups and
1000 requests. Inside each query timer: direct malloc-returning lib2bit/faidx
API, or ACE/zstd coordinate-to-FAI byte-span calculation, decode, and CR/LF
removal into a malloc-owned string. Stop the timer before validation, capture
copy and free. No old faidx shim with extra timed copy/free is substituted.

Warm archive/index files in page cache before open. ACE/zstd use a resident,
prefaulted archive buffer and preallocated scratch; BGZF and lib2bit retain their
native access paths against warm page cache. Open time excludes preload, includes
native table/index loading and scratch allocation, and is reported separately as
one observation (n=1), not a percentile. Record current RSS before/after open,
after queries, and process peak RSS in KiB. Peak is the whole isolated process,
including common truth/capture buffers and resident archive, not library-only
memory; do not subtract high-water marks. Full reference mappings are released
before open. Main profile order rotates by corpus index modulo six.

## Method checks before the main grid

After complete equivalence admission, run two independent chr1 passes per six
profiles. A/A requires abs(p50_B-p50_A)/p50_A < 0.05 for each, evaluated on integer
nanoseconds without rounding. Failure stops the main grid; no time-based retry.

For ACE/zstd/BGZF choose the first eligible actual chr1 archive boundary by
metadata alone. A starts at the first base on/after that byte boundary; B starts
one base earlier. Both return R bases; B must touch more native outer blocks
(and more reconstructed cold materialized work for ACE). Persist boundary IDs,
spans and archive hashes before measuring. No candidate is selected by timing.

For `.2bit`, use a separately declared method-only fixture: first R uppercase
ACGT bases, next R lowercase acgt bases, then at least R+16 uppercase bases;
no N, no terminal query. A=[0,R), B=[R/2,3R/2) crosses its actual mask boundary
and adds R/2 case conversions. This controls mask work without searching the
main data for a favorable elapsed time; main corpora and trace are unchanged.

Each control has an independent fresh handle for every A and B, 12 warmup pairs
then 1000 pairs in alternating AB/BA order, with opens outside query timers.
Crossing median must be strictly greater than aligned median for each of four
equivalent codecs. Otherwise stop the method; do not switch candidate or retry
based on elapsed time. Save all per-query values and pair roles.

## Host, lock, admission and retention

ace-core, AMD EPYC 4344P, timed worker pinned to CPU0, one timed thread. Controller,
builds and correctness use CPU15. Only timing uses the blocking shared
`flock /run/lock/ovh-bench.lock`; never hold the lock for builds or correctness.
Reuse the HW-REGION-1 admission policy: LOADED if load1-T > 1.0 at either
boundary (T=1), or any surviving foreign process exceeds 10% of one CPU in the
one-second pre-start observation. Exactly load1=2.0 and CPU=10% pass. Inspect
all live processes; uninspectable live process means ERROR, not a whitelist.

Record date -u, /proc/loadavg, nproc, CPU, kernel, governor and pin at both
boundaries. Record other-core /proc/stat deltas as observations only. A LOADED
unit alone is retaken with identical inputs/order, up to three attempts, all
retained. Three LOADED attempts => BLOCKED: load, save ps top eight, stop.
Unexpected worker/byte errors stop even on a loaded attempt. A/A pair, control
pass and main profile pass are separate logical units; never retry clean slow
results. Completed artifacts are verified and replayed without new timers.

New commands, binaries, captured strings, timings and receipts live under this
`casefix/` stage and owned `.work/hw-region-2/casefix/`; preserve original Kill.
Commit protocol, patch and all execution sources before any timed call. Push
checkpoint evidence as it completes. Report unchanged forecasts, all losses,
N/soft-mask overlap count and first coordinate. Publish only inside this repo;
keep PR #97 draft. No upstream message or merge.
