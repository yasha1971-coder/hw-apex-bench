# BGZF two-configuration contract

Pins are the existing repository pins, not new choices: htslib 1.24 at
`4b705e4fada8ee2b6b15746f725ee8ac51631803`, libdeflate 1.19 at
`dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f` (see `codecs/bgzip.sh`).

`default` uses stock bgzip, default compression and text boundary policy, with
one explicitly declared encoder thread. Nominal 64 KiB is a format-scale label,
not an assertion that every uncompressed member has length 65,536. This pinned
htslib has `BGZF_BLOCK_SIZE=0xff00` (65,280); actual sizes are read from every
BGZF member. No request is redefined to fit this label.

`matched-g` writes the same raw FASTA bytes with `bgzf_write`, explicitly flushing
after each g-byte input group using public `bgzf_flush`. g must be at most 65,280,
so the requested boundaries remain representable with ordinary BGZF blocks even
on incompressible input. Requests for larger exact g are rejected, not relabeled.
The native compressor settings and CRC behavior are unchanged. The final short
member is counted in the actual mean Q, while the empty EOF member is excluded.

Both variants read through the same pinned `faidx_fetch_seq64` library path in
one persistent process with no decompression pool. Internal coordinates are
start0+length; htslib is called with zero-based inclusive end=start0+length-1.
FASTA+samtools truth uses one-based inclusive coordinates. Bounds are checked
before calling htslib; unknown contigs, short output or clipping are failures.

Storage is the sum of BGZF archive, `.fai`, and `.gzi` needed for access. Each is
hashed and counted. Q is measured in uncompressed FASTA bytes from BGZF ISIZEs;
FASTA base windows are not silently treated as raw bytes for an eventual model.
Matched-g and default results stay separately labeled: neither replaces the
other and no favorable winner is selected after observing timings.

CI is correctness only. It compares both stock default and matched-g output
against direct FASTA slices and samtools. There is no ace-core or timing run.
