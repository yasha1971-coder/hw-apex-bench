[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: separate binary-search reader result

## Why chr1 differs from the T2T windows

On chr1, lib2bit-casefix/storeMasked=1 has p50 **88.965 µs**, versus **6.823 µs** with storeMasked=0 (case-folded output, not equivalent). Pinned [softMask(), 2bit.c:139](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L133-L158) starts its mask-table scan at index 0 for every query and skips ended blocks until the query; its work therefore grows with the number of preceding mask blocks. The unchanged chr1 archive has **331,893** mask blocks; the 30 T2T windows have median **8509.5**, range **34–15,137** (middle windows: 7,994 and 9,025 blocks). Static replay of the frozen chr1 requests gives median **184,885** old loop entries versus **43** search-plus-body inspections; these are operation counts, not timed components. The separate binary-search reader returns identical case-preserved bytes, with p50/p99 **9.348 / 13.155 µs** and unchanged archive bytes. On the measured chr1 workload, the .2bit latency penalty is driven by lib2bit's linear mask lookup, not a requirement of the format; the T2T windows show the same format with much smaller mask tables.

ace-core AMD EPYC 4344P, CPU0, one timed thread; the identical archive and indexes warm in RAM/page cache. The original worker/native wrapper, compiler flags, chr1 reference, 12 warmups and 1000 offsets are retained. This reader addition was measured after the original grid; the two rows are separate clean passes, not interleaved pairs. New method/main timing boundaries: 2026-11-26T21:16:38.510520+00:00 → 2026-11-26T21:23:39.026959+00:00 UTC.

| chr1 reader | Stored B incl. indexes | p50 / p99 µs |
|---|---:|---:|
| ACEAPEX 2.6.5 interactive L2 | 60440787 | 41.357 / 61.724 |
| zstd-seekable 1.5.7 L3 | 83924190 | 46.997 / 66.293 |
| BGZF / HTSlib 1.24 L6 | 80071586 | 41.526 / 59.931 |
| lib2bit-casefix (storeMasked=1) | 64895635 | 88.965 / 171.828 |
| lib2bit-casefix + binary search (reader change, not upstream) | 64895635 | 9.348 / 13.155 |

P1 **HIT**, P2 **MISS**, P3 **HIT (30/30)** remain evaluated on the original casefix row. Separate B1: `4 × 9348 ≤ 88965` — **HIT**. No original CLEAN cell or T2T timing was repeated. All new attempts, including LOADED, are retained.

The ordinary casefix adapter remains unchanged. The lower_bound patch is reader development, not an upstream lib2bit release. A/A and the unchanged fresh-handle mask-boundary control passed; byte equality passed before and during timing. Open time is n=1 and peak RSS is whole-process, including preparation/capture buffers. These finite sampled observations do not establish cross-host speed or a format-only latency constant.

[Calibration](CALIBRATION.md) · [Protocol](PROTOCOL.md) · [Patch](lib2bit-binary-search.patch) · [Raw-data audit](audit.json) · [Mask counts and static replay](mask-counts.json) · [Machine-readable result](summary.json) · [Original complete comparison](../casefix/RESULTS.md).
