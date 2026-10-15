# AGC library contract for Axis 3

Status: native synthetic CI must pass before measurements. No benchmark is run by this change.

## Pin and identity

AGC 3.2.4 is pinned to `e67e3fc865a459779118d3d4e9fbdf42c70ba75e`.
The wrapper calls the public `CAGCFile` API in `src/lib-cxx/agc-api.h`.
The reference implementation and its dependencies are not modified.
`build_agc_v324.sh` uses the upstream makefile for the CLI and `libagc.a`,
and reuses its compiler, optimization, architecture, include and dependency
variables for the thin native wrapper. The final link command is printed by make.

## Two stock creation modes, exactly one create each

`t2t` uses the separately manifest-pinned external T2T FASTA as AGC's reference
and passes all N cohort assemblies in the same `agc create` invocation.
`noref` means **no external reference**: AGC requires a reference input, so the
first member in the frozen cohort order is used as that input; the remaining
N-1 members follow it in the same create. It is not a reference-free algorithm.
There are no append calls and no independently compressed substitute archives.
All compression settings remain the pinned author's defaults except for the
explicitly declared build thread count. The synthetic test uses one thread.

The whole archive, including any embedded external reference, counts toward
stored bytes. N and bytes-per-assembly count queried cohort members only.
All reference/source checksums must be fixed in the manifest before a real run.
The synthetic reference tests the `t2t` code path; it is not called a real T2T result.

## Names and coordinates

Assembly/sample IDs are unique stable IDs from the ordered cohort manifest.
The builder creates temporary `assembly_id.fa` symlinks to preserve those
sample IDs without editing contig names or sequence bytes. The reserved external
reference sample name is `__reference_t2t`. Both assembly and contig names are
passed explicitly on every query; relying on a globally unique contig name is
forbidden. Shared names across different samples are tested.

The internal adapter interface is `(assembly_id, contig, start0, length)`.
AGC receives **zero-based inclusive** `[start0, start0 + length - 1]` via
`CAGCFile::GetCtgSeq`; its success code is zero. The equivalent CLI request is
`contig@assembly_id:start0-end0`. The samtools truth uses **one-based inclusive**
`contig:(start0 + 1)-(start0 + length)`. These translations are not interchangeable.

Unknown/ambiguous names, empty requests, coordinates beyond the contig, short
outputs, native errors or coordinates exceeding the public signed-int API fail.
The adapter never clips an invalid request or silently fetches a whole contig.

## In-process boundary and judge

Creation is an untimed CLI setup operation here. Reads use one persistent
prefetched `CAGCFile` context and the public library API, not a process per query.
The wrapper introduces no decoding workers. Opening/prefetch and file integrity
verification occur outside any later timed operation. The SHA-256 of the archive
may be checked against its build receipt before opening; this is application
integrity, not a claim that native AGC has a checksum for every corruption.

CI creates three related approximately 1 MiB assemblies with a shared contig
name and exercises both modes. Each library result is compared byte-for-byte
with the source FASTA slice, AGC `getctg` and samtools `faidx`. Exact first/last
bases and block-crossing requests are included. One mismatch is FAIL; no timing
is published from CI. Corruption certification and large-file regression are
separate Q1/Q3 gates and are not claimed by this initial adapter test.
