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

```json
{
  "benchmark_commit": "d25d8d16f45a073f167bfb2082f663a909a48ea1",
  "corpus": {
    "bytes": 253935557,
    "id": "chr1-hg38-fasta",
    "md5": "9465e0f0df6e2c6eb39729c39cee5465",
    "md5_scope": "uncompressed FASTA",
    "md5_verified": true,
    "url": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr1.fa.gz"
  },
  "hardware": {
    "logical_cpus": 4,
    "lscpu": "Architecture:                            x86_64\nCPU op-mode(s):                          32-bit, 64-bit\nAddress sizes:                           48 bits physical, 48 bits virtual\nByte Order:                              Little Endian\nCPU(s):                                  4\nOn-line CPU(s) list:                     0-3\nVendor ID:                               AuthenticAMD\nModel name:                              AMD EPYC 9V74 80-Core Processor\nCPU family:                              25\nModel:                                   17\nThread(s) per core:                      2\nCore(s) per socket:                      2\nSocket(s):                               1\nStepping:                                1\nBogoMIPS:                                5192.27\nFlags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves user_shstk clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm\nVirtualization:                          AMD-V\nHypervisor vendor:                       Microsoft\nVirtualization type:                     full\nL1d cache:                               64 KiB (2 instances)\nL1i cache:                               64 KiB (2 instances)\nL2 cache:                                2 MiB (2 instances)\nL3 cache:                                32 MiB (1 instance)\nNUMA node(s):                            1\nNUMA node0 CPU(s):                       0-3\nVulnerability Gather data sampling:      Not affected\nVulnerability Ghostwrite:                Not affected\nVulnerability Indirect target selection: Not affected\nVulnerability Itlb multihit:             Not affected\nVulnerability L1tf:                      Not affected\nVulnerability Mds:                       Not affected\nVulnerability Meltdown:                  Not affected\nVulnerability Mmio stale data:           Not affected\nVulnerability Old microcode:             Not affected\nVulnerability Reg file data sampling:    Not affected\nVulnerability Retbleed:                  Not affected\nVulnerability Spec rstack overflow:      Vulnerable: Safe RET, no microcode\nVulnerability Spec store bypass:         Vulnerable\nVulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization\nVulnerability Spectre v2:                Mitigation; Retpolines; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected\nVulnerability Srbds:                     Not affected\nVulnerability Tsa:                       Vulnerable: No microcode\nVulnerability Tsx async abort:           Not affected\nVulnerability Vmscape:                   Not affected\n",
    "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39"
  },
  "run_id": "2026-09-11T07:33:20.356324+00:00",
  "versions": {
    "aceapex_sha": "a194893b676a089e5916063d62c45e77483d2c10",
    "compiler": "g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
    "htslib": "1.19",
    "libzstd": "1.5.7 (same pinned static library for both codecs)",
    "zstd_sha": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
  }
}
```

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

