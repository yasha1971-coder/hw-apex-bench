# Axis 4 protocol v1.1: compressed streaming truth

## Version and source contract

The retained protocol-v1 A6–A10 evidence uses `axis4-evidence-v3` and
`axis4-prepared-v1`. These identifiers, the old JSON Schema, old source bytes and
verification remain supported. There is no identifier rewrite or synthetic
conversion of historical evidence. Protocol v1.1 uses
[axis4-evidence-v4](../schemas/axis4-evidence-v4.schema.json) and
`axis4-prepared-v2`, with explicit `truth_version: "1.1"`.

The corpus still lists `assemblies[].fasta` as a path/bytes/sha256 reference. For
`.fa.gz`, this identity refers to the **compressed file**. Prepare checks that
identity before reading and again after consuming the complete source. Input
ledger rechecks remain mandatory during run and independent verification.

Select streaming truth with `axis4-corpus-v1.1`, or `--truth-version 1.1`.
A `.gz`, `.bgz` or `.bgzf` source automatically selects v1.1 even in a v1 manifest.
Plain v1 inputs without this selection retain their original prepare behavior.
In streaming mode, gzip magic also identifies compressed streams without these
suffixes. A gzip suffix with invalid gzip bytes refuses.

```sh
set -euo pipefail
python3 -m tools.axis4 prepare --root DATA_ROOT --manifest cohort.json \
  --groups groups.json --out prepared-v11 --truth-version 1.1
python3 -m tools.axis4 run --root DATA_ROOT --plan plan-v11.json --out run-v11
python3 -m tools.axis4 verify --evidence DATA_ROOT/run-v11/evidence.json \
  --input-root DATA_ROOT --prepared-sha256 EXTERNAL_PREPARE_SHA256
```

`plan-v11.json` must reference the returned prepared path/bytes/sha256, with the
existing `axis4-plan-v1` structure and the separately built native reader inputs.
The external prepare SHA anchors truth and the exact query list. Official runs
still require their original ace-core silence gates before and after timing;
synthetic runs cannot claim official performance.

## Three byte identities

1. `fasta.sha256` / `truth_sources[].source.sha256`: original source-file bytes,
   including every gzip header/member/trailer if compressed.
2. `truth.uncompressed_sha256`: every decompressed FASTA byte before any
   normalization, including headers, case, wrapping, CRLF and final-newline state.
3. `canonical_sha256`: concatenated uppercase sequence bytes, without FASTA
   framing; the same response domain as protocol v1.

Prepare records decompressed byte count and SHA while scanning. Evidence repeats
these identities in `truth_sources`, together with source references and encoding.
The independent verifier recomputes the complete decompressed identity, canonical
identity, contig order/lengths and every requested response hash. It validates all
32 seed-selected byte files (or all responses when fewer than 32).

Prepare uses a sorted active-window sweep. Verify independently intersects
canonical coordinates with streamed pieces; it never calls prepare's extractor,
uses native codecs, or trusts recorded classifications/hashes as its reference.
Only transport and FASTA framing are shared. All original response translation,
duplicate/order/sample/input/storage/provenance/gate checks remain in force.

Concatenated gzip members and BGZF are ordinary complete gzip streams here.
Every member is consumed through EOF, including data outside requested windows,
so truncated trailers, bad CRC/ISIZE and later-member damage refuse. No seek,
uncompressed FASTA spool, temporary FASTA or whole-assembly allocation is used by
the streaming truth implementation. Variable wrapping and an absent final LF work.
Empty/duplicate names, malformed sequence framing and oversized headers refuse.

## Memory criterion, frozen before acceptance

[axis4_stream.py](../tools/axis4_stream.py) bounds each read to 65536 bytes,
including a chromosome stored on a single sequence line. FASTA headers have a
strict 4096-byte limit. Memory is O(query metadata + contig metadata + fixed I/O
buffers + bytes of at most 32 sampled windows), not O(assembly sequence bytes).
Prepare retains request hashes without retaining response bytes. Verify retains
only sampled windows. Many contigs or more/larger windows naturally cost metadata
or sampled-window memory; this is not a claim of constant memory for all workloads.

[axis4_stream_memory.py](../tools/axis4_stream_memory.py) generates only compressed
synthetic inputs, with a repeated fixed pattern, one long sequence line and four
fixed 1024-byte windows. Sizes are 1, 8 and 64 MiB of sequence. Each size runs in a
fresh subprocess. Acceptance requires both prepare and verify traced allocation
peaks <= 2097152 bytes; each verifies window correctness. Raw elapsed nanoseconds,
RSS and SHA256 are recorded in `memory.json`, without invented numeric headlines.
The criterion is an empirical regression check, not an asymptotic proof by itself.

```sh
set -euo pipefail
python3 -m tools.axis4_stream_memory --out NEW_MEMORY_DIRECTORY
python3 -m tools.axis4_stream_synthetic --out NEW_CORRECTNESS_DIRECTORY
```

The memory measurement is **truth-only**, excluding native decoder workspace,
archive construction and dependency imports. Native reader implementations may
allocate their own buffers; reference-based formats may require their native
reference representation and plain-faidx uses a plain archive. This change removes
the need for an uncompressed FASTA **truth source**, not those decoder requirements.
The optional synthetic `--native-root` acceptance selects a retained
zstd-seekable fixture and proves prepare/run/verify with zero plain FASTA files.
Default synthetic acceptance is explicitly a unit fixture, never a native timing.

## Compatibility with the v0.2.0 release pipeline

Leaderboard accepts v4 through the same independent Axis 4 judge. Corpus comparison
uses the decompressed source SHA in v1.1; gzip container choices do not create a
different biological source identity. Existing schema-specific table separation
remains in force. Release verification and the site builder therefore support v4
through the updated leaderboard adapter, with no evidence conversion.

The A10 website golden is a historical release: its embedded Axis 4 source files
remain the original hash-bound versions. The synthetic site helper selects those
SHA-checked snapshots rather than attributing A11 code to an A6/A7 historical run.
This does not change production builder inputs or server RUN.md. All three
protected original AGC/RUN paths remain untouched.
