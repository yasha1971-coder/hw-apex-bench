# Axis 3 — cohort random access

Status: protocol/implementation only. No public README/Pages/release/paper update. Official measurements require the explicit ace-core runner.

## Question

For N assemblies of one species (HPRC), when random windows are requested across the whole cohort:
1. how many stored bytes are required per assembly, including indexes/sidecars required for random access;
2. how many verified windows per second can the implementation serve?

Compression density and access speed are reported together, never collapsed into one score.

## Frozen inputs

A cohort manifest is TSV with: `assembly_id`, `url`, `source_sha256`, optional `reference_role`. Source bytes are immutable after their SHA-256 is frozen.

Cohort sizes: N = 4, 50, and all assemblies present in the frozen HPRC manifest. The N=4 and N=50 subsets are deterministic prefixes of the manifest's explicit stable order; "all" means exactly every manifest row at the evidence commit.

Window lengths W = 256, 4096, 65536, 1048576 bytes. For each N × W generate exactly 10,000 requests using seed `20261003`. Sampling is uniform over all valid start positions across all assemblies/contigs eligible for W.

Each request file is TSV: `assembly_id contig start end`, 1-based inclusive. A sibling reference TSV contains SHA-256 of uppercase FASTA sequence bytes with line breaks removed. Generator algorithm/version, seed, manifest SHA-256 and request-file SHA-256 are part of the receipt.

## Metrics

For every codec/configuration/N/W row:
- total stored bytes and bytes/assembly, including all indexes/sidecars required by that row;
- build wall time and declared build threads;
- verified windows/s plus per-window latency p50 and p95;
- peak resident memory (RSS) for the measured scope;
- exact codec version/commit, command/API, CPU/GPU and hardware provenance;
- 10,000/10,000 bit-perfect status, otherwise the row is `FAILED`.

Scopes are separate tables and MUST NOT be ranked together:
- CPU in-process;
- GPU in-process, archive/device residency stated explicitly;
- CLI/process scope.

Warmup, cache policy and archive residency are recorded. A codec without a scope reports `n/a`, not a synthetic timing.

## First adapters

- AGC: reference-based cohort archive and a no-reference/independent configuration when supported by the pinned AGC version. Window extraction uses the narrowest supported AGC operation (`getctg`/set extraction as available); if AGC cannot return the exact requested window directly, the adapter records the extra decoded bytes and method.
- BGZF + htslib: each assembly independently BGZF-compressed and indexed; CPU in-process region access through htslib/faidx. Storage includes every .gz/.bgz plus .fai/.gzi required.
- 2-bit packing: capacity/reference baseline, exactly 2 bits/base only for A/C/G/T plus explicit side information necessary to represent all other FASTA symbols and contig boundaries losslessly. It is not called a codec-speed result unless an actual accessor is measured.
- ACEAPEX open: each assembly encoded independently; CPU in-process library region path plus explicit sidecars required for FASTA coordinate mapping.
- OpenZL v0.3.0 (frame v27): LZ levels 1 and 3, requested LZ windows 64 KiB (windowLog 16) and 1 MiB (windowLog 20). The upstream CLI exposes compression level and independent serial chunk size but not LZ windowLog, so the adapter is fail-closed until a parameterized-graph helper proves the exact window setting and bit-perfect synthetic round-trip for all four variants. After that CI gate, measure one-thread D_Q on ace-core; before it, measurements are forbidden.
- ACEAPEX-refrel3: reserved adapter gated by upstream `research/refrel/FORMAT.md` on ACEAPEX branch `refrel`. Until that file exists and declares the format frozen, status is `not-frozen` and measurements are forbidden. Predeclared variants are `q4k` (`RR_BS=4096`) and `q16k` (`RR_BS=16384`); for the window-law diagnostic, `Q_block = RR_BS`. No D_Q, size or access result may be inferred from research logs before freeze.

## Window-law diagnostic

Alongside every eligible in-process result, measure one-thread full-decode throughput `D_Q` and actual mean uncompressed decode granule `Q`, then report the prediction `R ≈ D_Q/(W+Q−1)`, predicted p50 `(W+Q−1)/D_Q`, measured p50 and signed error %. Detailed rules are in `WINDOW_LAW.md`. This is diagnostic evidence, not a ranking and never crosses CPU/GPU/CLI scope boundaries.

## Judge

Every returned window is normalized only according to the frozen reference rule (FASTA line breaks removed; bases uppercase) and SHA-256 compared with the sibling request reference. One mismatch, short read, decoder error, crash or missing request marks the whole measurement row `FAILED`. A failed row may retain diagnostics but MUST NOT publish throughput as a valid result.

## Synthetic CI

CI creates 2–3 deterministic ~1 MiB mini-assemblies derived from one common synthetic reference with substitutions/indels and multiple contigs. It validates:
- request-list determinism and SHA contract;
- every available adapter round-trips and returns bit-perfect windows;
- judge rejects one deliberately corrupted answer;
- storage accounting includes declared sidecars;
- result/manifest files contain no absolute paths under the home directory.

CI is correctness-only. Its timing is not benchmark evidence.

## Official runner

`review/axis3/run_axis3_ace_core.sh` is the only prepared CPU runner for the first official cohort run. It MUST NOT run automatically in CI. It downloads only manifest-pinned sources, verifies SHA-256 before use, records host/library versions and emits evidence under an explicit run directory.

No external publication without explicit user instruction.
