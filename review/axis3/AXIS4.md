# Axis 4 A6: frozen cohort requests and independent evidence

This CLI measures complete query groups across an explicitly selected cohort.
It does not infer contig homology. Every group names a coordinate tuple for every
assembly. Compare rows only when their prepared SHA, group order, execution scope
and timing boundary agree. A single codec run is not a cross-codec conclusion.

The byte domain is uppercase sequence without FASTA framing; coordinates are
0-based half-open. Native byte outputs are uppercased before hashing. Stored
sample bytes are those canonical responses.

## Input preparation

Use one input directory containing FASTA files, retained archives, required
indexes, native libraries and build receipts. References have exactly
path, bytes, sha256; paths are normalized relative to that directory.
No files are downloaded or codecs built by prepare/run.

The corpus manifest has this form:

~~~json
{
  "schema": "axis4-corpus-v1",
  "evidence_kind": "official",
  "assemblies": [
    {
      "assembly_id": "sample1",
      "source_url": "https://source.example/sample1.fa.gz",
      "source_sha256": "<optional actual downloaded-object sha256>",
      "fasta": {"path": "sample1.fa", "bytes": 123, "sha256": "<FASTA sha256>"}
    }
  ]
}
~~~

Replace placeholders with actual values. Source-object SHA is optional; the
FASTA SHA and size are mandatory and verified. Source URLs describe provenance,
not a download command. List the full ordered cohort.

groups.json is a nonempty array. Each element maps every selected assembly ID
to exactly assembly_id, contig_id, start0, end0. Example coordinate shape:

~~~json
[
  {
    "sample1": {"assembly_id": "sample1", "contig_id": "chr1", "start0": 0, "end0": 1048576}
  }
]
~~~

Prepare computes the whole-file SHA of every FASTA, its contig geometry,
canonical identity and expected SHA for every query. It locks the manifest,
original group list, protocol SHA and sample seed. It never opens a codec.

~~~sh
set -euo pipefail
python3 -m tools.axis4 prepare --root "$INPUT_ROOT" \
  --manifest cohort.json --groups groups.json --out axis4-prepared \
  --sample-seed 20261003
~~~

Retain the returned prepared file reference and its SHA outside the later
evidence directory. That SHA is the trust anchor required by verify; accepting
an edited prepare and its new hash would establish a different experiment.

## Native plan

plan.json contains exactly schema, prepared, reader:

~~~json
{
  "schema": "axis4-plan-v1",
  "prepared": {"path": "axis4-prepared/prepared.json", "bytes": 123, "sha256": "<prepare sha256>"},
  "reader": {
    "family": "refrel3",
    "variant": "q4k",
    "library": {"path": "libhwa_refrel3.so", "bytes": 123, "sha256": "<library sha256>"},
    "build_receipt": {"path": "build.json", "bytes": 123, "sha256": "<receipt sha256>"},
    "reference": {"path": "reference.fa", "bytes": 123, "sha256": "<reference sha256>"},
    "archives": [
      {"assembly_id": "sample1", "archive": {"path": "sample1.rr3", "bytes": 123, "sha256": "<archive sha256>"}}
    ]
  }
}
~~~

The compressed reader specification and exact pins are shared with
[the verdict reader](verdict_readers.py): refrel3 q4k/q16k, BGZF default/matched-g,
zstd-seekable, indexed LZ4, segmented OpenZL and AGC t2t/noref.
For AGC, A6 opens libagc directly without B-specific Q/D_Q geometry. Its receipt
must bind archive_sha256, mode, cohort_order, create_calls=1 and append_calls=0.
Use the existing build receipts, including source_commit, codec_version,
compiler, flags, dependencies, library_sha256 and decoder_threads=1.
Per-assembly archive order must equal frozen assembly order.

Additional family fasta-faidx, variant plain uses the same pinned htslib shim.
Its archives entries contain assembly_id, archive (the frozen FASTA itself)
and fai (the existing path FASTA.fai). It opens the existing index without
rebuilding it. No subprocess or predecoded truth fallback is available.

Storage counts distinct required archive/reference/index/map paths once.
The native library, build receipt and source truth for compressed formats are
provenance inputs, not compressed storage. Shared reference storage is included
once. Library SHA and source pins are retained independently of this ledger.

## Run and verify

~~~sh
set -euo pipefail
python3 -m tools.axis4 run --root "$INPUT_ROOT" --plan plan.json --out axis4-evidence
python3 -m tools.axis4 verify \
  --evidence "$INPUT_ROOT/axis4-evidence/evidence.json" \
  --input-root "$INPUT_ROOT" --prepared-sha256 "$PREPARED_SHA256"
~~~

Official runs require ace-core. Before native open and after native close,
capture and retain the existing silence gate: load1 < 0.5, free disk >
20,000,000,000 bytes, process CPU sample >= 1 second, no foreign process using
>=10% of a CPU. Two endpoint samples are not continuous monitoring. There is
no skip-gate CLI flag. Inputs are checked before and after execution.

The timing boundary is one complete group: persistent in-process fetch,
uppercase normalization, SHA-256 judgement and coordinate translation.
File writes, reader creation, silence capture and input hashing are outside
the group timer. Do not compare these seconds with decoder-only latencies.

Every observed response SHA is retained. Only min(32, response_count) canonical
byte responses are retained, selected by random.Random(sample_seed).sample from
the frozen group/assembly order. The seed and selected IDs are in evidence.
Memory does not retain all responses; verify scans one FASTA at a time and
retains only hashes and sampled bytes.

verify validates JSON Schema, the external prepare SHA, all frozen source
files, exact row coverage/order, coordinates and translations, every response
SHA, every sampled byte, input/storage ledgers, build receipt, group timing
arithmetic and both gate records. FASTA extraction is a separate sequential
parser, not FastaTruth/FAI/native decode. Changing FASTA headers also fails
the whole-file identity check, even when queried bases are unchanged.

Failures after output creation leave evidence.json with status FAILED,
seconds null and performance_valid false. Verification refuses failed evidence.
A file hash proves consistency, not that telemetry or a build receipt was
authored by a trusted party.

## Synthetic correctness

Set evidence_kind=synthetic in a tiny corpus manifest. Preparation limits this
mode to 8 MiB of canonical sequence and 1024 responses. Gate records say
NOT_APPLICABLE, and performance_valid is always false. The label is preserved
through verify and cannot be promoted by merely editing the evidence field.

For acceptance using a real retained native library and clean source checkout:

~~~sh
set -euo pipefail
python3 -m tools.axis4_synthetic --root "$SYNTHETIC_OUT" \
  --family refrel3 --variant q4k \
  --library "$RR3_DIR/libhwa_refrel3.so" --encoder "$RR3_DIR/refrel3v1" \
  --source-root "$RR3_DIR/aceapex"
~~~

Repeat with q16k and a new output directory. The helper drives the actual
prepare/run/verify CLI, checks 40 responses and 32 samples, and rejects a forged
SHA for an unsampled response. It also supports zstd-seekable, bgzf and
fasta-faidx and AGC noref/t2t with their corresponding encoder and source checkout. Its receipt
identifies the loaded library/source/dependencies; keep compiler build logs
alongside it. It is correctness evidence only.

The workflow retains q4k/q16k synthetic artifacts and continues to enforce
NATIVE_SKIP_GATE over every collected test. Unset optional libraries may skip
only the specifically discovered NativeAvailability cases; configured missing
or broken libraries must fail. Symbol availability tests alone are not codec
round-trip acceptance. The synthetic CLI test supplies that evidence for its
listed family and variant.
