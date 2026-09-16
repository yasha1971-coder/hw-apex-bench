# T2T regional density: method and scope

Goal: test whether aggregate density hides poor compression on annotated
centromeric or telomeric sequences. The first 30-window pilot is complete: [results](RESULTS/T2T_REGIONS_20260916.md).
The reported 3.9% whole-assembly drop is owner context, not a result of this test.

## Inputs and region definitions

Use the exact NCBI FASTA in [the catalog](../corpora.json), verifying its expanded
size and MD5 before extraction. The consortium's [CHM13 index](https://github.com/marbl/CHM13)
links Cen/Sat v2.1 and telomere BED for v2.0. Retrieved file hashes and URLs are
in [the annotation receipt](../review/t2t-region-annotation-sources.json).
Resolve chr names to the NCBI accessions using the matching assembly report;
verify chromosome lengths and BED bounds. BED offsets refer to sequence bases,
not FASTA byte positions. Do not substitute the soft-masked analysis FASTA for
the pinned NCBI input without declaring a different corpus.

Cen/Sat includes multiple satellite and transition classes. Keep those classes
visible; neither their union nor every HOR array is automatically an active
centromere. Do not label HORs as active without a separate functional annotation.
Define the control pool as sequence outside the union of Cen/Sat and telomere
intervals, excluding ambiguous bases, with chromosome-matched selection fixed
before encoding. Call it the annotation-complement control, not proven euchromatin.

## Prevent a length confound

The telomere BED contains 50 intervals of 1,000–6,229 bases, all shorter than
16 KiB. Comparing them directly with megabase arrays mixes repeat effects,
block count and archive overhead. Do not concatenate distant intervals: this
creates artificial adjacency and can reward cross-interval matching.

Use equal-length comparisons, reporting the actual coordinates and input hashes.
For short telomeres, compare complete annotated intervals with same-length
control and centromeric windows; these are a short-input stratum. A separate
fixed-size window experiment can assess larger centromeric regions. Terminal
windows containing neighboring sequence must be labeled telomere-containing,
not pure telomere. Freeze sampling seed, counts, length schedule, chromosome
matching and any sequence normalization before compression; retain case if not
explicitly defining a separate normalized corpus.

## Codec and result boundary

The completed pilot pins the supplied original SHA 4915321 and encoding command;
future experiments must likewise record the exact revision,
including block, literal/FSE chunk, level, transform policy and thread settings.
The benchmark's historical adapter at 1b13df3 is a different experiment unless
that identity is explicitly intended. Keep pinned BGZF/libdeflate and zstd-seekable
baselines on the identical extracted inputs and record their configurations.
Restore every archive byte-exactly. Ratio is input bytes divided by all stored
archive and required index bytes. Keep individual window results and aggregate
as sum(input bytes)/sum(stored bytes), not a mean of ratios. Pair comparisons
by chromosome and length; report losses and distribution, not only a mean.

This measures separately compressed windows. It is not an allocation of bytes
inside one globally compressed T2T archive. No timing or historical rerun is
needed for this ratio-only experiment. Save new evidence separately from the
435 published records. Novelty and the cause of any loss remain unproved.
