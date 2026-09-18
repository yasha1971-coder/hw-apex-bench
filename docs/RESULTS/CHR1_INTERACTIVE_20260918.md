# chr1 ACE interactive-profile control — 2026-09-18

Same full hg38 chr1, same current public `aceapex_decompress_region` path,
same **g = R = 16 KiB**. The only intended entropy-granularity change from the
frozen default baseline is the documented interactive profile:

- `LIT_CHUNK=65536` — same 64 KiB literal granularity as the DNA default;
- `FSE_CHUNK=4096` — versus 512 KiB in the default baseline;
- `MIN_MATCH` unset.

Full native restore was bit-perfect before profiling.

## Result

| Diagnostic | Default | Interactive | Change |
|---|---:|---:|---:|
| complete archive bytes | 69,122,682 | **69,409,878** | +287,196 (+0.415%) |
| complete ratio | 3.673694 | **3.658493** | **−0.414%** |
| p50 region latency | 903.599 µs | **109.626 µs** | **−87.87%** |
| p99 region latency | 1,239.546 µs | **199.060 µs** | −83.94% |
| temp bytes requested / request, p50 | 1,916,619 B | **914,724 B** | **−52.27%** |
| alloc-like calls / request, p50 | 16 | **17** | +1 |
| retired instructions / request | 8,796,014 | **1,480,154** | **−83.17%** |
| cycles / request | 2,865,229 | **410,718** | **−85.67%** |
| IPC | 3.070 | **3.604** | +0.534 |
| literal chunk | 64 KiB | **64 KiB** | unchanged |
| FSE chunk | 512 KiB | **4 KiB** | 128× smaller |
| RA amplification | not measured in default baseline | **6.216250×** | — |

Interactive decoded 20,369,408 entropy bytes for 3,276,800 requested bytes over
the same 200-request trace: **RA = 6.21625× exactly**, matching the retained
historical interactive value and confirming profile identity.

## Requested cut: entropy granularity versus block path

Block size, request size, public region API and literal chunk size are held
fixed. The measured instruction delta is:

**8,796,014 − 1,480,154 = 7,315,860 fewer instructions/request (−83.17%).**

The corresponding wall-clock reduction is **793.973 µs (−87.87%)** on this
ARM Neoverse-N2 runner class.

This is the requested coarse cut. It does not claim that every removed
instruction belongs to one entropy primitive; it establishes that changing
the FSE random-access granularity from 512 KiB to 4 KiB removes the great
majority of the current one-shot request work while leaving the 16 KiB block
path in place.

The density price on this exact full archive is **0.414% in ratio** (0.415%
more complete stored bytes).

## Temporary materialization

Interactive still requests **914,724 B p50** of temporary allocation capacity
to return a 16 KiB region, versus 1,916,619 B for default. So the profile cuts
temporary capacity by about half, but does not eliminate the one-shot
materialization architecture.

## Provenance

Actions run: **35363065302**  
Artifact: **10554508821**  
Artifact digest:
`sha256:c4c59492aa774444fbd574b7d8d6d217b148ae663b93010291b757b0dbfe5288`

ACEAPEX: `4915321bf118e564ef3883e58927992c7f9d8dc3`  
zstd: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`  
Host: ARM Neoverse-N2, Ubuntu 24.04 ARM GitHub-hosted runner, CPU 0 affinity.

The original run completed all measurements. Its first offline summarizer
rejected the perf CSV suffix `cycles:u`; the raw artifact was retained and
the table above was derived from those retained raw files without rerunning
the benchmark.

**Stop here.** No rans1_v4 integration, format change, decoder optimization,
or new sweep is part of this task.
