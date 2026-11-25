# LOCAL DRAFT — not submitted

## Title

Small seekable frames: unconditional srcSizeHint selects a different ratio/window policy

Pinned zstd 1.5.7 `f8745da6ff1ad1e7bab384bd1f9d742439278e99`; pyzstd 0.20.0 / backports.zstd 1.8.0 linked to zstd 1.5.7. Both writer paths were source-traced and their exact frame-0 SHA values reproduced with a small C program.

In [zstdseek_compress.c:234](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L234), the seekable writer supplies maxFrameSize as ZSTD_c_srcSizeHint. The source-size fallback selects different small-source compression parameters and windows. pyzstd does not set the hint on this path. Both stream with unknown pledged size and absent FCS. Feeding a whole frame in one CONTINUE call does not remove the difference.

The following one-line change on a private copy makes all tested data frames byte-identical to pyzstd:

```diff
- ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);
+ ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, 0);
```

|corpus/level|frame KiB|N frames|original contrib B|hint=0 contrib B|pyzstd B|change B|change %|remaining B|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|[enwik8-L3](cases/enwik8-L3-65536.json)|64|1526|39654522|39573564|39567460|-80958|-0.204158|6104|
|[enwik8-L3](cases/enwik8-L3-131072.json)|128|763|38510829|38386321|38383269|-124508|-0.323306|3052|
|[enwik8-L3](cases/enwik8-L3-262144.json)|256|382|37935213|37326215|37324687|-608998|-1.605363|1528|
|[enwik8-L3](cases/enwik8-L3-524288.json)|512|191|36535040|36535040|36534276|0|0.000000|764|
|[enwik8-L19](cases/enwik8-L19-65536.json)|64|1526|36265760|36244232|36238128|-21528|-0.059362|6104|
|[silesia-L3](cases/silesia-L3-65536.json)|64|3235|73587959|73434013|73421073|-153946|-0.209200|12940|
|[silesia-L3](cases/silesia-L3-262144.json)|256|809|69675977|69577856|69574620|-98121|-0.140825|3236|
|[silesia-L19](cases/silesia-L19-65536.json)|64|3235|65101245|64811561|64798621|-289684|-0.444975|12940|

Remaining bytes are exactly four optional seek-table checksum bytes per frame, with matching payload-length/descriptor changes. Complete native restore and table XXH64 checks passed for every archive. At 512 KiB there is no size saving; every data frame changes only the window-descriptor byte.

This is a storage/memory policy tradeoff rather than evidence for universally removing the hint. The L3/256 KiB minimal probe reports CCtx size 1566233 → 3663385 B and declared window 256 KiB → 2 MiB. One preregistered resident pair observed encode 340959823 → 312972138 ns and full decode 81793021 → 70095693 ns; one fixed-order pair is not a general speed comparison.

Would an explicit policy option or documentation of the small-frame ratio/window tradeoff be appropriate? The exact minimal C program, per-frame CSV, source pins, complete byte accounting and raw pair are retained with the HW-GIFT-1c evidence.

This file is a draft for owner review only. It has not been sent to facebook/zstd or any other external party.
