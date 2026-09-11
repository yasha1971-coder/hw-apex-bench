# Plateau throughput contract

This stage measures CPU encode and full decode without treating one pass over
the available corpus as a plateau.

`chr1.fa` is verified first and then byte-concatenated with itself at 1, 2, 4
and, when needed, 8 copies. Corpus construction, hashing, archive loading,
allocation, prefaulting and correctness checks are outside the timed region.

For every codec/configuration:

- encode is the median of three encoder-process wall-clock runs;
- full decode is one warmup followed by five timed library calls;
- the archive is resident and the output is preallocated and prefaulted;
- each decoded output is compared byte-for-byte with the scaled input;
- decimal MB/s is `input bytes / wall seconds / 1e6`;
- encoder and decoder thread policies are recorded independently.

Plateau is reached only when the latest three scale medians have a max/min
spread no greater than 5%, and the coefficient of variation of repetitions at
each of those scales is no greater than 5%. The first scale at which all eight
curves (encode and decode for four configurations) satisfy the rule ends the
growth. Otherwise the run reaches the declared CI resource edge at 8 copies,
2,031,484,456 input bytes. Growth beyond that size is outside this run's
memory/time budget; it is not silently treated as a plateau.

A curve that has not flattened has no headline throughput value. Its summary
status is `data_edge`, its value is null, and all observed points remain in
`results.jsonl` and `.work/throughput-raw.json`. Relative-to-bgzip relations are
PASS/FAIL only when both absolute plateau values exist; otherwise they are n/a
with a reason.

GPU is a separate path. No GPU value is inferred from this CPU experiment.
