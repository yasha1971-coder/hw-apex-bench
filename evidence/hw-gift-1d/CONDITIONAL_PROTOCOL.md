# Development freeze after enwik8, before silesia

This is a separately recorded development step. CALIBRATION.md and P1/P2/P3/Kill
remain unchanged. All 21 enwik8 A/B cells are complete and checkpointed through
`d65a503b1e92bfa8e38b27483934355b931c81aa`; the independent saved-data training
audit is PASS. No silesia cell has been constructed or inspected.

The preregistered selector and the independent audit both choose **X = 1024
bytes**, the smallest candidate. Every candidate 1024/4096/16384/65536 passed
the training speed constraint. The largest nohint/original median ratio was
9,240,232,650 / 8,585,556,422 = approximately 1.076253209 (L19, 4 KiB).

Actual private-copy patch to the existing srcSizeHint argument:

```c
ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, zcs->maxFrameSize < 1024 ? (int)zcs->maxFrameSize : 0);
```

The original and nohint binaries/build receipts remain unchanged. The conditional
copy has a separate build receipt bound to this committed document and to the
base build. Both sides retain checksum-bearing seek tables.

Development predictions, before building or timing the conditional variant:

- Conditional/original compression median <=1.10 in every one of the 21 new
  enwik8 A/C cells and 21 silesia A/B/C cells, five interleaved rounds each.
- Conditional archive bytes and SHA exactly match original for G<1024, and
  nohint for G>=1024: a predicted zero-byte difference from the selected policy.
- Every produced archive restores bit for bit. All mechanical load exclusions,
  three-attempt limit and retained attempts remain the frozen PROTOCOL rules.
- Any implementation or holdout violation is a MISS; X will not be adjusted.
  Baseline enwik8 A/B, new enwik8 A/C and silesia A/B/C repetitions stay separate.

Interpretation is limited before confirmation. X=1024 is the smallest candidate
in the declared interval, not an observed boundary of hint necessity: even at
256 B all three training levels had nohint/original medians <=1.10. P1 is already
a literal MISS (L10/256 B: original 348,459,318 ns; nohint 329,174,338 ns, instead
of >=3x slower). P2 already fails on enwik8 L10 at 64/256 KiB: nohint is faster
but its archives are respectively 455,153 / 272,875 bytes larger. Across all
training cells nohint is larger in nine configurations.

Consequently, this conditional rule is an experimental speed-budget policy;
its P3 size check compares against nohint, not original. A P3 HIT would not
establish a universal rule that preserves both original size and speed, nor
justify saying the hint is needed below X or only costs bytes above X. The final
report and unsent issue must preserve these counterexamples and any holdout
failure. The historical M1 benefit is context, not a substitute for these data.
