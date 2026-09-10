# What the c(g) pairs actually measure

## Strict baseline rule

For strict c(g), only the independent block size may change. Encoder revision,
corpus, effective search and entropy settings, threads and algorithmic modes
must otherwise be fixed. Deterministic behavior caused by moving the block
boundary belongs to the treatment. Current profile percentages below remain
measured operational losses. zstd 1.5.7 has a matched strict pair; the supplied
ACEAPEX default pair at 7216280 is recorded separately from the 1b13df3 profiles.
Historical raw JSONL is not rewritten.

New runs distinguish `configuration_ratio_loss_percent` (measured number) from
`independence_cost_strict_percent` (null / n/a until a matched baseline exists).

For zstd the strict pair is explicitly **zstd 1.5.7 -3, one continuous frame**
versus **zstd 1.5.7 -3, independent 16 KiB frames**. Complete output files are
counted, including the seek table. Its measured strict c(g) is 7.180634%. The
historical 6.68% used 1.4.8; that is a separate point, not a replacement.

The historical ACEAPEX 0.410% is payload-only. It excludes the 68-byte header
and the 64-byte `BlockOffsets` record per block, so it is not the cross-codec
archive ratio. Supplied complete-file sizes yield 1.631528% for ACEAPEX default
at 7216280 on ace-core. It does not replace the 1.714456% operational observation
for `--profile interactive` at 1b13df3.

Measured source: `1a406213bb4d46b3cfbf26b10f11ce5bd1986be8`.
ACEAPEX: `1b13df34ac8e839dd3232b59bc59560d689a435a`.
Corpus: chr1 hg38, 253935557 bytes, MD5 `9465e0f0df6e2c6eb39729c39cee5465`.

| Pair | ratio blocked | ratio continuous | blocked + index bytes | continuous bytes | signed loss % |
|---|---:|---:|---:|---:|---:|
| bgzip / gzip | 3.382558276489 | 3.395854265262 | 75072042 | 74778108 | 0.391536 |
| zstd seekable / one frame | 3.025773934700 | 3.259851962595 | 83924167 | 77897880 | 7.180634 |
| ACEAPEX interactive | 3.658493060599 | 3.722310445126 | 69409878 | 68219876 | 1.714456 |
| ACEAPEX dense | 3.780646221619 | 3.793413104059 | 67167236 | 66941182 | 0.336554 |
| ACEAPEX default @ 7216280 (ace-core, declared) | 3.141615050482 | 3.193721514584 | 80829622 | 79510864 | 1.631528 |

`loss = 100 * (1 - ratio_blocked / ratio_continuous)`.
All four additional continuous-baseline restores passed exact byte comparison.
Full recorded commands, including restores, are in results.jsonl and
[the measured raw records](evidence/independence-20260910/independence-raw.json).

The added ace-core point was supplied with exact file sizes and commands, but
without compiler/libzstd versions, archive hashes or a byte-equal restore
receipt. It is therefore displayed as declared provenance, not as independently
reproduced by this repository's runner.

## Supplied strict ACEAPEX pair

```bash
git checkout 7216280298baa976152f6978ea1ac9c7b65fc4ad
make
ACEAPEX_BS=16384     ./aceapex c --in chr1.fa --out /tmp/g16.aet  --threads 8
ACEAPEX_BS=253935557 ./aceapex c --in chr1.fa --out /tmp/gall.aet --threads 8
stat -c%s /tmp/g16.aet /tmp/gall.aet
```

Only `ACEAPEX_BS` changes. “Whole” means one block spanning all 253935557 input
bytes; block logic remains active. The 16 KiB file contains 15499 table records,
991936 bytes in total, which is 1.227% of the complete 80829622-byte archive.

The source tree at this SHA contains two divergent encoder files. Root
`aceapex_depth.cpp` has the `local_pos < ORIGIN_CAP` guard, but the Makefile sets
`SRCS = src/aceapex_main.cpp`; the compiled source lacks that guard at the
corresponding `origin[src_local]` read. The GitHub runner's one-block command
exits with signal 11. PR #9 records stack limit, memory, compiler and an ASan
rerun rather than treating the guarded, unbuilt root file as proof about the
Makefile binary.

## Expanded compression commands

Run from the benchmark checkout after its dependency/corpus setup. These expand
the recorded wrappers; they are not a claim that a second experiment was run.
The original measured commands are retained alongside each ratio in README.

```bash
unset ACEAPEX_BS LIT_CHUNK FSE_CHUNK MIN_MATCH LIT_LEVEL LIT_LANES NO_REP DIRECT8 FORCED_BIN ACEAPEX_DUMP LD_PRELOAD

# bgzip: 3.382558276489, including the GZI index
bgzip -l 6 -@ 1 -i -I .work/chr1.fa.gz.gzi -c .work/chr1.fa > .work/chr1.fa.gz
# gzip continuous member: 3.395854265262
gzip -n -6 -c .work/chr1.fa > .work/whole-bgzip-htslib.archive

# zstd seekable: 3.025773934700
.work/zstd/contrib/seekable_format/examples/seekable_compression .work/chr1.fa 16384 3
# zstd continuous frame: 3.259851962595
.work/zstd/programs/zstd -3 -T1 --no-check -f .work/chr1.fa -o .work/whole-zstd-seekable.archive

# ACEAPEX interactive: 3.658493060599
.work/aceapex-cli c --in .work/chr1.fa --out .work/chr1-interactive.aet --threads 1 --level 2 --profile interactive
# ACEAPEX interactive whole block: 3.722310445126
env ACEAPEX_BS=253935557 .work/aceapex-cli c --in .work/chr1.fa --out .work/whole-aceapex-interactive.archive --threads 1 --level 2 --profile interactive

# ACEAPEX dense: 3.780646221619
.work/aceapex-cli c --in .work/chr1.fa --out .work/chr1-dense.aet --threads 1 --level 2 --profile dense
# ACEAPEX dense whole block: 3.793413104059
env ACEAPEX_BS=253935557 .work/aceapex-cli c --in .work/chr1.fa --out .work/whole-aceapex-dense.archive --threads 1 --level 2 --profile dense
```

## Effective ACEAPEX environment — code-proven

| Pair | blocked BS | baseline BS | LIT_CHUNK, both | FSE_CHUNK, both | MIN_MATCH, both |
|---|---:|---:|---:|---:|---:|
| interactive | 16384 | 253935557 | 65536 | 4096 | 0 |
| dense | 262144 | 253935557 | 1048576 | 32768 | 0 |

The harness removes every override listed above. The CLI preset then sets BS,
LIT and FSE with overwrite=0; only the baseline's explicit BS overrides it.
MIN_MATCH is unset in both measured encoder environments. The pinned encoder
sets `g_mm = mm ? atoi(mm) : 0`, so its effective value is exactly zero.
Explicit `MIN_MATCH=0` would select the same branch; it was not the literal
recorded environment. The archive header check confirmed BS=253935557 and one block.

## Flattening correction — code-proven, effect size unmeasured

Both archives use the SAME binary and source. However, `aceapex_depth.cpp` uses
`ORIGIN_CAP = (1u<<20)` and guards eligible non-rep flattening by
`c_off <= local_pos && local_pos < ORIGIN_CAP`. Origin propagation is capped too.
Thus a whole-file block may flatten eligible matches in its first MiB, not after
that. Small blocks restart local_pos; their positions stay below this cap.
The earlier description “flattening is disabled for a large block” was too broad.
The source comment was not precise enough; the actual guard is authoritative.

The observed 1.714456% includes this behavior difference along with changed
match availability and block/table costs. A separately isolated flattening
contribution is **n/a: no matched ablation performed**. A pure independence-only
cost for the ACEAPEX pairs is therefore **n/a**, not the published operational loss.
No upstream code has been modified to manufacture a matching result.

## gzip and zstd interpretation

DEFLATE has a 32768-byte backward-distance limit, not independent 32 KiB access
blocks. References can cross DEFLATE block boundaries. One gzip member is a
continuous finite-window baseline, not an unlimited-dictionary baseline.
See [RFC 1951, section 3.2.3](https://www.rfc-editor.org/rfc/rfc1951.html#section-3.2.3).
The 0.391536% bgzip/gzip delta also includes member headers, index overhead,
history resets and implementation differences. It is valid for this pair,
not a universal structural penalty or proof of a single cause.

The zstd result is 7.180634% for the pinned version, level and exact corpus.
Proximity to 6.68% does not establish why they differ. To reconcile that number
or ACEAPEX's historical 0.41%, the historical SHA, both archive sizes, commands,
effective LIT/FSE/MIN_MATCH values and corpus checksum are still needed.
Matching whole-file BS and MIN_MATCH alone does not establish a matched protocol.
