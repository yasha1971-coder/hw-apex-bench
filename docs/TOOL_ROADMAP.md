# From measured tables to an extensible instrument

The nine-axis gate is `./run.sh --audit-axes`. Its generated report is
[AXES_RESULTS.md](AXES_RESULTS.md). The gate accounts for supported measurements
and explicit format limitations; it does not invent a BGZF whole-file block or a
native batch API. The recovered five-point curve remains a review candidate.

## Implementation sequence

1. Account for all nine axes on the original three formats; preserve every source
   observation, explain unavailable cells, validate plateaus and same-run ratios.
2. Define a versioned adapter interface. Move codec decisions out of the core;
   discover `codecs/*.sh`. Capabilities and unsupported reasons belong to adapters.
3. Implement `./run.sh --check codecs/example.sh`, testing build, complete restore,
   boundary/unaligned region reads and capability honesty on a small checked corpus.
   Run that small check in CI; full benchmark workflows become manual-only.
4. Add xz/liblzma as a fourth adapter without changing the harness. Use native
   `.xz` blocks and the on-disk Index; include the Index in archive accounting.
5. Add the twenty-line contribution guide, license for original project code,
   third-party notices and CITATION.cff. Do not relabel upstream source licenses.
6. Add CRAM only with a suitable alignment corpus, an explicit lossless contract,
   and verified operation equivalence; unsupported raw-byte requests remain n/a.
7. Prepare v0.1 after the checks and review. Obtain a real Zenodo DOI at release;
   do not invent one or describe it as issued before deposit succeeds.

## Adapter boundary to implement next

Each adapter provides `codec_name`, `codec_version`, `codec_build`,
`codec_compress`, `codec_decompress`, `codec_region`, and `codec_supports`.
Unsupported axes need structured reasons as well as the supported-axis list.
The harness validates the list and rejects an adapter whose declared callbacks
are absent or fail correctness checks. A failed build is an error, not n/a.

Shell functions orchestrate builds and correctness commands. They cannot be the
per-request timed boundary: a shell process per read would measure process startup.
An additional versioned native callback interface must expose a resident handle,
region read and full decode; optional native batch and work counters are explicit.
The common in-process timer calls these callbacks. Third-party codec code may be
embedded in its one adapter file; the core must never branch on its codec name.

`--codec NAME --axis AXIS` must resolve prerequisites and include an appropriate
same-run baseline, or report why its ratio is unavailable. The result schema will
carry one axis per record, an explicit comparison direction and provenance links.
Historical JSONL must be preserved; any schema migration needs a lossless,
deterministic conversion with source hashes and no promoted evidence levels.

## CRAM operation caveat

CRAM represents alignment records. Lossless alignment data does not by itself
promise the original SAM whitespace, BAM encoding bytes, or arbitrary byte-offset
reads from a FASTA file. An alignment/coordinate benchmark must be a separate
operation group until the same byte-exact contract is demonstrated.

The blanket statement that HTSlib CRAM quantizes qualities by default is not a
valid assumption. Set and record preservation options, verify the actual round
trip, and account for any reference/index dependencies. The samtools documentation
explains preservation of MD/NM with `store_md=1` and `store_nm=1`.

Primary references:
- https://www.htslib.org/doc/samtools-view.html
- https://academic.oup.com/bioinformatics/article/38/6/1497/6499262
- https://tukaani.org/xz/liblzma-api/index_8h.html

These are acceptance conditions for the next stages, not claims of completed
adapter, xz, CRAM, CI or release work.

## Publication gate

PR #16 integrates the recovered evidence with licensed main and the reviewed
negative-c(g) note. After merge and publication validation, resume the adapter
interface as the next bounded step. PR #17 remains a draft requiring reconciliation
with published data; its qualification work is not a completed timing migration.
