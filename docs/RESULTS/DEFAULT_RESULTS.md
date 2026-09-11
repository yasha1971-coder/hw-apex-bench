# Default refresh at a194893

Same chr1 bytes and runner; complete archive plus required index sizes. One encoder thread requested for every row.

| Configuration | block bytes | literal mode | archive+index bytes | ratio | region p50 ms | region p99 ms |
|---|---:|---|---:|---:|---:|---:|
| bgzip+htslib | 65280 | format-native | 75074847 | 3.382432 | 0.126420 | 0.259061 |
| zstd-seekable | 16384 | format-native | 83924167 | 3.025774 | 0.074302 | 0.089144 |
| ACEAPEX default | 1048576 | fixed chunks | 68054036 | 3.731381 | 2.724145 | 4.682256 |
| ACEAPEX interactive | 16384 | fixed chunks | 69409878 | 3.658493 | 0.161664 | 0.304029 |
| ACEAPEX dense | 262144 | fixed chunks | 67167236 | 3.780646 | 1.422735 | 2.686640 |
| ACEAPEX explicit legacy | 1048576 | legacy coarse partitions | 79168052 | 3.207551 | n/a — no literal chunking | n/a — no literal chunking |

The no-chunking marker describes efficient fine-grained access, not the absence of a callable region API. Historical slow region-API observations remain valid and are not relabeled as full-decode benchmarks.

Default on this DNA input and explicit legacy are distinct rows. No text/Silesia result is inferred from chr1. No encode/full-decode throughput is claimed by this refresh.

The reported owner ratio 3.72329 is not an acceptance target: complete-file accounting may differ from CLI payload accounting.

## Provenance

[Provenance JSON](details/3fc2d6b8cac42fe27a71553f275adb840af4db578bc5fea836381041effc5fe7.json)

## Exact commands

bgzip+htslib
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/cg_bgzip /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-0 65536
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS bgzip -d -c /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-0 > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-0
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/region_latency bgzip+htslib /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/regions-0.jsonl
```

zstd-seekable
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa 16384 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-1 > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-1 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/regions-1.jsonl
```

ACEAPEX default
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-2 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-2 --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-2 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-2 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/regions-2.jsonl
```

ACEAPEX interactive
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 FSE_CHUNK=4096 LIT_CHUNK=65536 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-3 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 FSE_CHUNK=4096 LIT_CHUNK=65536 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-3 --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-3 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 FSE_CHUNK=4096 LIT_CHUNK=65536 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-3 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/regions-3.jsonl
```

ACEAPEX dense
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 FSE_CHUNK=32768 LIT_CHUNK=1048576 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-4 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 FSE_CHUNK=32768 LIT_CHUNK=1048576 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-4 --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-4 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 FSE_CHUNK=32768 LIT_CHUNK=1048576 MIN_MATCH=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-4 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/regions-4.jsonl
```

ACEAPEX explicit legacy
```sh
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS LIT_CHUNK=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-5 --threads 1
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS LIT_CHUNK=0 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/archive-5 --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/default-refresh/restore-5 --threads 1
```

