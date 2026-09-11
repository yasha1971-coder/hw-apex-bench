# Density versus independent-access granularity

Five measured sizes, one corpus, identical 16,384-byte API requests. No new measure or predetermined winner is claimed.

Run: 2026-09-10T23:38:56.105858+00:00; benchmark SHA: `d84f38af3b26d830fbc1cc654174f2bd673178ab`.
Corpus: chr1 hg38, 253935557 bytes, MD5 `9465e0f0df6e2c6eb39729c39cee5465`.

`c(g) = 100 × (1 − ratio_g / ratio_whole) = 100 × (1 − bytes_whole / bytes_g)`.
Ratio counts complete archives plus required indexes. This is ratio loss, not archive-size increase relative to the baseline. Negative values and nonmonotone curves are retained.

| Codec | requested g bytes | actual max block | ratio g | ratio whole | archive+index bytes g | baseline bytes | c(g) % | p50 ms | p99 ms | encoder threads |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aceapex-cg-default | 4096 | 4096 | 3.040990 | 3.212358 | 83504247 | 79049584 | 5.334654 | 63.310648 | 66.801747 | 8 |
| aceapex-cg-default | 16384 | 16384 | 3.159992 | 3.212358 | 80359553 | 79049584 | 1.630135 | 62.379022 | 65.579947 | 8 |
| aceapex-cg-default | 65536 | 65536 | 3.193151 | 3.212358 | 79525066 | 79049584 | 0.597902 | 62.743751 | 65.555416 | 8 |
| aceapex-cg-default | 262144 | 262144 | 3.203783 | 3.212358 | 79261153 | 79049584 | 0.266926 | 61.926912 | 65.111021 | 8 |
| aceapex-cg-default | 1048576 | 1048576 | 3.207551 | 3.212358 | 79168052 | 79049584 | 0.149641 | 62.188634 | 65.557620 | 8 |
| zstd-seekable-cg | 4096 | 4096 | 2.912620 | 3.238526 | 87184580 | 78410855 | 10.063391 | 0.053059 | 0.072185 | 1 |
| zstd-seekable-cg | 16384 | 16384 | 3.025774 | 3.238526 | 83924167 | 78410855 | 6.569397 | 0.069890 | 0.084708 | 1 |
| zstd-seekable-cg | 65536 | 65536 | 3.146897 | 3.238526 | 80693943 | 78410855 | 2.829318 | 0.097161 | 0.212167 | 1 |
| zstd-seekable-cg | 262144 | 262144 | 3.099202 | 3.238526 | 81935785 | 78410855 | 4.302064 | 0.208359 | 0.596194 | 1 |
| zstd-seekable-cg | 1048576 | 1048576 | 3.255040 | 3.238526 | 78013034 | 78410855 | -0.509942 | 0.859236 | 1.414754 | 1 |
| bgzip-cg | 4096 | 4096 | 2.992232 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 84864925 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 0.057928 | 0.072515 | 1 |
| bgzip-cg | 16384 | 16384 | 3.171358 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 80071563 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 0.070392 | 0.084338 | 1 |
| bgzip-cg | 65536 | 65280 | 3.382432 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 75074847 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 0.116408 | 0.246992 | 1 |
| bgzip-cg | 262144 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 1 |
| bgzip-cg | 1048576 | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported | 1 |

## Measured variation (not a monotone fit)

- aceapex-cg-default: c(g) range 0.149641–5.334654%; span 5.185013 percentage points over 4 KiB–1 MiB. Raw points, including reversals, are shown above.
- zstd-seekable-cg: c(g) range -0.509942–10.063391%; span 10.573333 percentage points over 4 KiB–1 MiB. Raw points, including reversals, are shown above.

BGZF: the adapter flushes at 4 KiB, 16 KiB or htslib's safe BGZF_BLOCK_SIZE at the 64 KiB request. Actual geometry is parsed from every archive. 256 KiB and 1 MiB independent BGZF blocks are unsupported. Strict c(g) is n/a at every point: this format/adapter cannot supply a one-block whole-input baseline. A 32 KiB DEFLATE history window is NOT a set of independent blocks.

ACEAPEX uses unchanged ee5a37e Makefile-built src/aceapex_main.cpp, default level 2 and 8 requested encoder threads. Only ACEAPEX_BS varies; this is NOT the interactive or dense profile. Its API includes the same src/aceapex_main.cpp, and both translation units are checked in the compiler trace.

zstd uses the unchanged reference seekable_compression program, level 3, 1 thread, seek-table checksums enabled, for BOTH sides. The baseline has one nonempty frame spanning the input and a seek table. This is a newly measured baseline, not the earlier CLI-versus-seekable pair. Internal behavior induced by frame size remains part of this operational comparison.

Region measurements reuse harness/region_latency.c: resident archive/handle, 10 random warmups plus 2 boundary checks, 200 byte-verified queries, nearest-rank percentiles, API-only timer. API worker policies are codec-owned; no equal-thread full-decode claim is made. No FASTA transformation, batch speed, amplification or plateau throughput is inferred from this sweep.

## Provenance and both commands

All records, samples, versions, commands and source hashes are in results.jsonl (evidence group cg-five-point-v1).

### aceapex-cg-default

```json
{
  "configuration": {
    "codec": "aceapex-cg-default",
    "encoder_threads": 8,
    "level": 2,
    "profile": "default; no overrides except ACEAPEX_BS"
  },
  "hardware": {
    "logical_cpus": 4,
    "lscpu": "Architecture:                            x86_64\nCPU op-mode(s):                          32-bit, 64-bit\nAddress sizes:                           48 bits physical, 48 bits virtual\nByte Order:                              Little Endian\nCPU(s):                                  4\nOn-line CPU(s) list:                     0-3\nVendor ID:                               AuthenticAMD\nModel name:                              AMD EPYC 7763 64-Core Processor\nCPU family:                              25\nModel:                                   1\nThread(s) per core:                      2\nCore(s) per socket:                      2\nSocket(s):                               1\nStepping:                                1\nBogoMIPS:                                4890.83\nFlags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves user_shstk clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm\nVirtualization:                          AMD-V\nHypervisor vendor:                       Microsoft\nVirtualization type:                     full\nL1d cache:                               64 KiB (2 instances)\nL1i cache:                               64 KiB (2 instances)\nL2 cache:                                1 MiB (2 instances)\nL3 cache:                                32 MiB (1 instance)\nNUMA node(s):                            1\nNUMA node0 CPU(s):                       0-3\nVulnerability Gather data sampling:      Not affected\nVulnerability Ghostwrite:                Not affected\nVulnerability Indirect target selection: Not affected\nVulnerability Itlb multihit:             Not affected\nVulnerability L1tf:                      Not affected\nVulnerability Mds:                       Not affected\nVulnerability Meltdown:                  Not affected\nVulnerability Mmio stale data:           Not affected\nVulnerability Old microcode:             Not affected\nVulnerability Reg file data sampling:    Not affected\nVulnerability Retbleed:                  Not affected\nVulnerability Spec rstack overflow:      Vulnerable: Safe RET, no microcode\nVulnerability Spec store bypass:         Vulnerable\nVulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization\nVulnerability Spectre v2:                Mitigation; Retpolines; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected\nVulnerability Srbds:                     Not affected\nVulnerability Tsa:                       Vulnerable: No microcode\nVulnerability Tsx async abort:           Not affected\nVulnerability Vmscape:                   Not affected\n",
    "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39"
  },
  "versions": {
    "aceapex_sha": "ee5a37eda18b81c1300a1ee44a7e06b6be925bd2",
    "compiler": "g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
    "htslib": "1.19",
    "libzstd": "1.5.7 (same pinned static library for both codecs)",
    "zstd_sha": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
  }
}
```

Whole-input baseline: 79049584 bytes; ratio 3.212357917026.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=253935557 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-253935557.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=253935557 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-253935557.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-253935557.restore --threads 8
```

g=4096: 83504247 bytes; ratio 3.040989723553.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=4096 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-4096.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=4096 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-4096.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-4096.restore --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=4096 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-4096.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-4096-regions.jsonl
```

g=16384: 80359553 bytes; ratio 3.159992154262.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-16384.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-16384.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-16384.restore --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=16384 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-16384.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-16384-regions.jsonl
```

g=65536: 79525066 bytes; ratio 3.193151163182.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=65536 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-65536.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=65536 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-65536.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-65536.restore --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=65536 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-65536.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-65536-regions.jsonl
```

g=262144: 79261153 bytes; ratio 3.203783283344.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-262144.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-262144.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-262144.restore --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=262144 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-262144.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-262144-regions.jsonl
```

g=1048576: 79168052 bytes; ratio 3.207550907025.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=1048576 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex c --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-1048576.archive --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=1048576 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex/aceapex d --in /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-1048576.archive --out /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-1048576.restore --threads 8
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS ACEAPEX_BS=1048576 /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency aceapex /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-1048576.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/aceapex-cg-default-1048576-regions.jsonl
```
### zstd-seekable-cg

```json
{
  "configuration": {
    "codec": "zstd-seekable-cg",
    "encoder_threads": 1,
    "level": 3,
    "profile": null
  },
  "hardware": {
    "logical_cpus": 4,
    "lscpu": "Architecture:                            x86_64\nCPU op-mode(s):                          32-bit, 64-bit\nAddress sizes:                           48 bits physical, 48 bits virtual\nByte Order:                              Little Endian\nCPU(s):                                  4\nOn-line CPU(s) list:                     0-3\nVendor ID:                               AuthenticAMD\nModel name:                              AMD EPYC 7763 64-Core Processor\nCPU family:                              25\nModel:                                   1\nThread(s) per core:                      2\nCore(s) per socket:                      2\nSocket(s):                               1\nStepping:                                1\nBogoMIPS:                                4890.83\nFlags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves user_shstk clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm\nVirtualization:                          AMD-V\nHypervisor vendor:                       Microsoft\nVirtualization type:                     full\nL1d cache:                               64 KiB (2 instances)\nL1i cache:                               64 KiB (2 instances)\nL2 cache:                                1 MiB (2 instances)\nL3 cache:                                32 MiB (1 instance)\nNUMA node(s):                            1\nNUMA node0 CPU(s):                       0-3\nVulnerability Gather data sampling:      Not affected\nVulnerability Ghostwrite:                Not affected\nVulnerability Indirect target selection: Not affected\nVulnerability Itlb multihit:             Not affected\nVulnerability L1tf:                      Not affected\nVulnerability Mds:                       Not affected\nVulnerability Meltdown:                  Not affected\nVulnerability Mmio stale data:           Not affected\nVulnerability Old microcode:             Not affected\nVulnerability Reg file data sampling:    Not affected\nVulnerability Retbleed:                  Not affected\nVulnerability Spec rstack overflow:      Vulnerable: Safe RET, no microcode\nVulnerability Spec store bypass:         Vulnerable\nVulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization\nVulnerability Spectre v2:                Mitigation; Retpolines; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected\nVulnerability Srbds:                     Not affected\nVulnerability Tsa:                       Vulnerable: No microcode\nVulnerability Tsx async abort:           Not affected\nVulnerability Vmscape:                   Not affected\n",
    "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39"
  },
  "versions": {
    "aceapex_sha": "ee5a37eda18b81c1300a1ee44a7e06b6be925bd2",
    "compiler": "g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
    "htslib": "1.19",
    "libzstd": "1.5.7 (same pinned static library for both codecs)",
    "zstd_sha": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
  }
}
```

Whole-input baseline: 78410855 bytes; ratio 3.238525545985.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 253935557 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-253935557.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-253935557.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-253935557.restore
```

g=4096: 87184580 bytes; ratio 2.912620064236.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 4096 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-4096.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-4096.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-4096.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-4096.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-4096-regions.jsonl
```

g=16384: 83924167 bytes; ratio 3.025773934700.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 16384 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-16384.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-16384.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-16384.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-16384.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-16384-regions.jsonl
```

g=65536: 80693943 bytes; ratio 3.146897369980.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 65536 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-65536.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-65536.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-65536.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-65536.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-65536-regions.jsonl
```

g=262144: 81935785 bytes; ratio 3.099202100767.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 262144 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-262144.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-262144.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-262144.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-262144.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-262144-regions.jsonl
```

g=1048576: 78013034 bytes; ratio 3.255040138549.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_compression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa 1048576 3
mv /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa.zst /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-1048576.archive
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/seekable_decompression /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-1048576.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-1048576.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency zstd-seekable /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-1048576.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/zstd-seekable-cg-1048576-regions.jsonl
```
### bgzip-cg

```json
{
  "configuration": {
    "codec": "bgzip-cg",
    "encoder_threads": 1,
    "level": 6,
    "profile": null
  },
  "hardware": {
    "logical_cpus": 4,
    "lscpu": "Architecture:                            x86_64\nCPU op-mode(s):                          32-bit, 64-bit\nAddress sizes:                           48 bits physical, 48 bits virtual\nByte Order:                              Little Endian\nCPU(s):                                  4\nOn-line CPU(s) list:                     0-3\nVendor ID:                               AuthenticAMD\nModel name:                              AMD EPYC 7763 64-Core Processor\nCPU family:                              25\nModel:                                   1\nThread(s) per core:                      2\nCore(s) per socket:                      2\nSocket(s):                               1\nStepping:                                1\nBogoMIPS:                                4890.83\nFlags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid aperfmperf tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy svm cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves user_shstk clzero xsaveerptr rdpru arat npt nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold v_vmsave_vmload umip vaes vpclmulqdq rdpid fsrm\nVirtualization:                          AMD-V\nHypervisor vendor:                       Microsoft\nVirtualization type:                     full\nL1d cache:                               64 KiB (2 instances)\nL1i cache:                               64 KiB (2 instances)\nL2 cache:                                1 MiB (2 instances)\nL3 cache:                                32 MiB (1 instance)\nNUMA node(s):                            1\nNUMA node0 CPU(s):                       0-3\nVulnerability Gather data sampling:      Not affected\nVulnerability Ghostwrite:                Not affected\nVulnerability Indirect target selection: Not affected\nVulnerability Itlb multihit:             Not affected\nVulnerability L1tf:                      Not affected\nVulnerability Mds:                       Not affected\nVulnerability Meltdown:                  Not affected\nVulnerability Mmio stale data:           Not affected\nVulnerability Old microcode:             Not affected\nVulnerability Reg file data sampling:    Not affected\nVulnerability Retbleed:                  Not affected\nVulnerability Spec rstack overflow:      Vulnerable: Safe RET, no microcode\nVulnerability Spec store bypass:         Vulnerable\nVulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization\nVulnerability Spectre v2:                Mitigation; Retpolines; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected\nVulnerability Srbds:                     Not affected\nVulnerability Tsa:                       Vulnerable: No microcode\nVulnerability Tsx async abort:           Not affected\nVulnerability Vmscape:                   Not affected\n",
    "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39"
  },
  "versions": {
    "aceapex_sha": "ee5a37eda18b81c1300a1ee44a7e06b6be925bd2",
    "compiler": "g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
    "htslib": "1.19",
    "libzstd": "1.5.7 (same pinned static library for both codecs)",
    "zstd_sha": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
  }
}
```

g=4096: 84864925 bytes; ratio 2.992232150090.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/cg_bgzip /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-4096.archive 4096
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS bgzip -d -c /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-4096.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-4096.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency bgzip+htslib /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-4096.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-4096-regions.jsonl
```

g=16384: 80071563 bytes; ratio 3.171357564233.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/cg_bgzip /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-16384.archive 16384
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS bgzip -d -c /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-16384.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-16384.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency bgzip+htslib /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-16384.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-16384-regions.jsonl
```

g=65536: 75074847 bytes; ratio 3.382431894933.
```bash
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/cg_bgzip /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-65536.archive 65536
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS bgzip -d -c /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-65536.archive > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-65536.restore
cd /home/runner/work/hw-apex-bench/hw-apex-bench && env -u ACEAPEX_BS -u ACEAPEX_DUMP -u DIRECT8 -u FORCED_BIN -u FSE_CHUNK -u GZIP -u HASH_LOG -u LD_PRELOAD -u LIT_CHUNK -u LIT_LANES -u LIT_LEVEL -u MIN_MATCH -u NO_REP -u ZSTD_CLEVEL -u ZSTD_NBTHREADS /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/region_latency bgzip+htslib /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-65536.archive /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/chr1.fa latency > /home/runner/work/hw-apex-bench/hw-apex-bench/.work/cg-curve/bgzip-cg-65536-regions.jsonl
```

Stop for review. This curve does not establish a corpus-independent law, a novel repetitiveness measure or exclusive superiority. Physical archive splitting is a separate experiment.
