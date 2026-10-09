# Axis 5 A7: application corruption protocol v1

This document freezes the criteria BEFORE the first A7 corruption run.
Synthetic experiments establish correctness and failure behaviour, not performance.

## Frozen population and operations

Seed 20261003; 20 independent cases per kind; five kinds in the order bit,
byte, truncate, swap, substitute: 100 mutations per reader variant. Each mutation
is executed with archive SHA-256 validation ON and OFF: 200 observations.
A fresh copy of the first archive in cohort order is the target; AGC targets its
single cohort archive. All original FASTA, library, reference, sidecars and build
receipts remain immutable and hash-locked. A separate archive is the donor;
its bytes and SHA are frozen at prepare, and identical donor/target is forbidden.

For case index i in each kind, derive SHA256(ASCII `axis5-v1:20261003:kind:i`).
The first eight bytes, big endian, map proportionally into [0,archive length).
bit flips bit digest[8] mod 8; byte XORs 1+digest[8] (always changes one byte).
truncate keeps 1+position mod (length-1) bytes. Blocks are archive-byte blocks,
NOT codec frames: width=min(256,floor(length/2),donor length). There are
floor(length/width) complete target blocks. Swap chooses block a=position mod
block count and b=(a+1+digest[9] mod (block count-1)) mod block count.
Substitute replaces block a by donor block digest[9] mod floor(donor length/width).
If swap/substitution would leave bytes identical, deterministically scan further
candidate blocks; prepare refuses if no nonidentical candidate exists. Metadata
and sidecars are not repaired after corruption. Physical block operations may
therefore damage codec framing; they do not imply semantic frame replacement.

Archives must be 2..64 MiB (lower bound 2 bytes), donor 1..64 MiB, total requested
canonical output <=8 MiB. Requests are every complete contig in frozen order:
first assembly only for per-assembly formats, whole cohort for AGC. This bounded
experiment is not an official HPRC performance run. Baseline native decoding
must match independently scanned FASTA bytes before any corrupted case is run.

## Isolation and observations

One native worker process group per OFF observation, one decoder thread,
10-second wall timeout including interpreter/startup/open/fetch/close, 2048 MiB
address-space limit, core dumps disabled, output/stderr files limited to
max(1 MiB,2*expected output bytes+1 MiB). Timeout kills the entire process group
and waits for the leader. Native C/C++ readers are used, no CLI decoder fallback.
ON hashes the mutated archive against the ORIGINAL prepare SHA before opening
any decoder; mismatch is recorded explicitly with decoder_started=false.
OFF skips only that ORIGINAL target-archive check, not provenance recording.
Native internal integrity checks remain enabled in both modes.
Keep every mutated archive, native output (including partial output), stderr,
return code, signal, timeout flag, and their byte lengths and SHA-256 in evidence.

## Independent classification, precedence and frozen PASS/FAIL

* detected: ON original archive SHA mismatch, explicit validation stage; no worker.
* hang: worker exceeded the watchdog (even though killed with SIGKILL).
* crash: worker terminated by signal, without watchdog expiry.
* refusal: nonzero normal exit (including Python shim exceptions).
* silent_error: zero exit, output bytes differ from independent FASTA truth,
  including missing/short/extra bytes.
* harmless: zero exit and exact independent FASTA bytes.

These six disjoint outcomes exhaust all cases; arbitrary nonzero exit is never
called detected. Each mode's counts must sum to 100. The verifier anchors prepare
by an externally supplied SHA, checks all original input hashes, regenerates all
mutations, and independently scans FASTA and classifies EVERY observation. It
rejects missing/duplicate/reordered cases, changed classifications, counts,
coordinates, outputs, mutations, hashes, protocol or baseline.

Harness acceptance PASS requires complete independently verified evidence and
passing tests/clean-patch acceptance. Per-mode integrity verdict PASS iff zero
silent_error outcomes; otherwise FAIL. Hang/crash/refusal are reported separately
and do not become silent errors. Hash-ON is a generic application SHA guard,
not a claim about a codec's built-in checksum. Observed integrity FAIL is an
experimental result and does not itself fail faithful harness acceptance.
Hash evidence proves byte consistency, not authenticity of OS telemetry or
execution; signatures/remote attestation are outside this protocol.
