# Matched-g ACEAPEX vs BGZF legal corridor

This experiment answers one question only: how density and resident 16 KiB
region latency change when ACEAPEX and BGZF use the same uncompressed
granularity on the same frozen corpus.

## Hard BGZF boundary

The interoperable BGZF virtual offset reserves 16 low bits for the
uncompressed offset within a BGZF block. The BGZF format therefore has no
compatible matched-g region above 64 KiB. In the pinned htslib implementation
used here the ordinary maximum uncompressed payload is 65,280 bytes
(`0xff00`), because the complete compressed BGZF member must also fit in
65,536 bytes.

This benchmark consequently defines the legal corridor as exactly:

- 65,280 B (reported as the ~64 KiB ceiling)
- 32,768 B
- 16,384 B
- 8,192 B
- 4,096 B

No benchmark code in this study accepts a BGZF g above 65,280 B. The top ACE
point is also 65,280 B, not 65,536 B, so every plotted point is exactly
matched in uncompressed granularity.

## Corpus and codec pins

Use the already frozen thirty 2 MiB T2T-CHM13v2.0 windows from
`evidence/t2t-regions-20260916/manifest.json`: ten centromeric HOR,
ten telomere-context, ten annotation-complement. Input SHA-256 must match every
retained manifest row before compression.

ACEAPEX source: `4915321bf118e564ef3883e58927992c7f9d8dc3`.
htslib source: `8f7231035d0409d525767c66d9f49f1f967ee1df`.
libdeflate source: `dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f`.
zstd source linked by ACE: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`.

ACE: level 2, `ACEAPEX_BS=g`, eight encoder threads, no explicit literal/FSE
profile override. BGZF: level 6, pinned htslib/libdeflate; compression is not a
timed axis. BGZF is forced to flush after each g-byte input chunk, then its
actual block ISIZE geometry is audited.

## Density

Density is ratio = total input bytes / total complete stored bytes.

For ACE the complete archive is counted. For BGZF both the BGZF archive and
its `.gzi` index are counted. No payload-only number substitutes for the
complete representation.

## Latency

Use the existing `harness/native_measure.c` resident ABI path for both
codecs. Archive loading and index loading happen before the timer. Each
configuration receives 12 warmups and 200 verified 16 KiB random region
requests using the existing seed 20260909. The identical trace is therefore
used for every codec and g on every 2 MiB window.

All 300 codec/window/g configurations are timed on one GitHub Actions runner,
pinned to one allowed CPU. Three passes use deterministic shuffled
configuration order. The primary p50 is the nearest-rank p50 pooled over the
30 windows and three passes: 18,000 samples per codec/g.

## Judge

Before any timing sample is accepted, every generated archive is opened by the
same native library path and fully decoded. The output must be byte-identical
to the retained frozen input. Region samples are also byte-verified by
`native_measure`. Any mismatch rejects the run.

## Output

Every legal g must have both values together:

- aggregate density ratio
- pooled resident region p50 in ms

Raw archive/index hashes, commands, block geometry, host/toolchain provenance,
all 180,000 latency samples, and pass order are retained. The interpretation
compares the slopes/relative changes across the whole legal corridor, not a
single cherry-picked point.
