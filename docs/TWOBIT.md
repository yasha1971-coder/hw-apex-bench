[written by ChatGPT (AI) at the author's request; checked by the author]

# Case-preserving .2bit coordinate adapter

[codecs/twobit.sh](../codecs/twobit.sh) reads base coordinates from a single
FASTA sequence. Its reader is MIT lib2bit pinned to
`58e20daa898a6fc338eae82e5d2ef7108d4fc07f`, with the sole
[soft-mask N casefix](../evidence/hw-region-2/lib2bit-casefix.patch).
The original Apache-2.0 [writer](../evidence/hw-region-2/writer.py) preserves
`ACGTNacgtn`, including overlapping N and lowercase intervals. Other alphabet
symbols and multiple FASTA records are rejected. No Kent/UCSC code or utility
is used.

On Linux with Python 3.10+, Git and GCC, build the reader outside its clean
dependency checkout:

```bash
bash codecs/twobit.sh seq-reader-build .work/twobit-sequence
```

This clones the exact pin and records copied original/patched sources, compiler,
commands, license and binary hashes in `.work/twobit-sequence/build.json`.
Alternatively, pass `--source-tree /path/to/clean/lib2bit` at the same pin.
`HB_PYTHON` selects the Python executable. Building and correctness operations
do not collect timings.

For a one-record chr1 FASTA, encode it and read 16,384 bases starting at
zero-based coordinate 1,000,000:

```bash
bash codecs/twobit.sh seq-build chr1.fa .work/chr1-2bit
bash codecs/twobit.sh seq-fetch .work/chr1-2bit/sequence.2bit chr1 1000000 16384 .work/chr1-region.seq
```

The sequence must contain the requested interval. `seq-fetch` accepts lengths
1–16,384 and uses half-open coordinates `[start, start+length)`. It verifies the
archive and reader provenance before returning case-preserved bases without
newlines. Use `--native-build WORKDIR/build.json` for a different reader build;
the retained HW-REGION-2 native-build receipt is also accepted on its original
executor. No study corpora are needed for the standalone build above.

The pinned library has a separate, unpatched rejection of reads reaching the
last packed byte. Such a query fails; the adapter does not clamp coordinates,
pad the archive or add another chromosome. The
[HW-REGION-2 protocol](../evidence/hw-region-2/casefix/PROTOCOL.md) qualifies the
frozen sampled grid, whose endpoints avoid that limitation.

This adapter has `input_domain=fasta-sequence`, `coordinate_domain=base`.
Generic nine-axis qualification requires exact original-file bytes, including
FASTA formatting, so all nine generic axes carry explicit n/a reasons. Default
byte-adapter discovery reports this exclusion; explicit generic `--check` or
`--plan --codec twobit` rejects the domain before building or opening fixtures.
Coordinate comparisons are retained separately in
[HW-REGION-2](../evidence/hw-region-2/RESULTS.md).
