# Five-point c(g) baseline review

Reviewed input: the 435-row results.jsonl in PR #16 at
`1160850bda8385cc18d8960989cad15ecacd8b43`.
SHA-256: `cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100`.
Machine-readable findings: [cg-baseline-check.json](cg-baseline-check.json).
No codec was run, no archive was recompressed and no fresh restore was claimed.

## Findings

All ten supported c(g) points use their codec's identical whole-input baseline.
The input is 253935557 bytes, MD5 9465e0f0df6e2c6eb39729c39cee5465.
The sweep is 4096, 16384, 65536, 262144 and 1048576 bytes.

ACEAPEX: the retained header reports block_size=253935557 and num_blocks=1;
its offset table has one 64-byte entry. The baseline archive is 79049584 bytes,
SHA-256 9bde31bc0089ab71aad48561aae84acbe31fe780bb381211a75c38eff68b083a.
Across all five encoding commands only ACEAPEX_BS and the output archive name
change. The same executable, input, cleared environment and eight requested
threads are retained. The unchanged ee5a37e source defaults to level 2. Its
block-size override returns the requested value before the adaptive heuristic;
the hash-log policy depends on the unchanged input size. FSE chunks default to
512 KiB; unset LIT_CHUNK selects the same legacy four-part literal policy on
both sides. One block here means one LZ block, not one entropy-code stream.

Zstd-seekable: the baseline histogram is {253935557: 1, 0: 1}. There is exactly
one nonempty frame covering the complete input, plus an empty terminal frame.
Thus this is a one-data-frame baseline, NOT literally a one-physical-frame file.
The empty frame and both seek-table entries remain included in the measured
78410855 bytes; none were subtracted. Archive SHA-256:
d2d3c22e1063d0b3ad3f7fce85663a1ec92db8f6322b5704198bf92cdf2f360f.
The exact hash is also retained in cg-baseline-check.json.

The unchanged reference seekable encoder is used for the baseline and all five
points. Commands differ only in frameSize; level remains 3. Source calls
ZSTD_seekable_initCStream(cstream, cLevel, 1, frameSize), retaining checksum mode;
the same single-threaded program, input and library build are used throughout.
The seek-table byte accounting and sum of uncompressed frame lengths are checked.
The 1 MiB point has negative c(g); this result is preserved, not clipped to zero.

Consequently, the same-command, single-data-unit interpretation is supported by
the retained evidence. A stronger requirement of exactly one physical frame
would not be met by this zstd baseline. Do not remove the empty frame by changing
recorded byte counts, and do not silently describe the file as one physical frame.
Changing granularity can change internal encoder behavior and derived stream
sizes; this is operational c(g), not a proof that every internal heuristic or
working-set size stayed constant.

BGZF: all five positions have no strict baseline and an explicit n/a reason.
No whole-file gzip member is substituted for a same-container BGZF baseline.
The two unsupported block sizes are not promoted to measured results.

## Checks and limits

The additional audit compares tokenized encoding commands, allowing only the
specified granularity argument and ACEAPEX output filename to change. It checks
whole-corpus coverage, block/frame counts, checksums, archive accounting, ratio,
formula and the identical baseline across all five points. Eleven tests cover
retained data and rejection of changed level, threads, entropy override, input,
executable, granularity, partial-input baseline, multiple payload blocks,
checksum policy and a fabricated BGZF baseline.

The reviewed ACEAPEX source and the two zstd encoder source files match hashes
in the retained compiler provenance. This is a review of saved commands,
geometry, restore receipts and source; the original archive bytes were not
reopened in this segment. The existing restore and sample evidence is not
represented as a new correctness run.

Reproduce from this documentation branch (reads Git data, not the codecs):

```sh
git show 1160850bda8385cc18d8960989cad15ecacd8b43:results.jsonl > /tmp/cabench-cg-results.jsonl
python3 review/audit_cg_baseline.py --results /tmp/cabench-cg-results.jsonl --out /tmp/cg-baseline-check.json
CABENCH_CG_RESULTS=/tmp/cabench-cg-results.jsonl python3 -m unittest discover -s review -p test_cg_baseline.py
```

The publication gate remains separate: integrate the reviewed evidence with the
merged license footer, regenerate reports and validate the manifest before a
main-branch merge. Adapter work remains paused.
