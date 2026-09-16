# Reproduce the regional ratio pilot

This is a separate experiment, not a replacement for the 435-row publication.
Requires Linux, Python 3, GCC/G++, Make, CMake, Git and zlib development headers.
No timing comparisons are made. The new build wrapper expresses the commands
used for the retained builds; it has been syntax-checked, not rerun end to end.
The recorded result itself completed all 90 archive/restoration pairs.

1. Obtain the versioned NCBI T2T FASTA in corpora.json. Verify compressed MD5
   `9280657210e4161147cbe13b022225b9`, then expand gzip. Check exactly
   3156259565 expanded bytes and MD5 `cd1e52ce400c027ed0b7ab4b9d613f5a`.
2. Use the assembly report and original BED files retained under
   evidence/t2t-regions-20260916. Their source URLs/hashes are also recorded in
   review/t2t-region-annotation-sources.json and corpora.json.
3. Run from the repository root, with new output directories:

```bash
bash review/t2t_regions/build.sh .work/t2t-rebuild
python3 review/t2t_regions/prepare.py --fasta t2t.fa \
  --report evidence/t2t-regions-20260916/GCA_009914755.4_T2T-CHM13v2.0_assembly_report.txt \
  --censat evidence/t2t-regions-20260916/chm13v2.0_censat_v2.1.bed \
  --telomeres evidence/t2t-regions-20260916/chm13v2.0_telomere.bed \
  --out .work/t2t-replay-windows
python3 review/t2t_regions/measure.py --windows .work/t2t-replay-windows \
  --out .work/t2t-replay-results \
  --ace .work/t2t-rebuild/aceapex \
  --bgzip .work/t2t-rebuild/htslib/bgzip \
  --seekable .work/t2t-rebuild/zstd/contrib/seekable_format/examples/seekable_compression \
  --zstd .work/t2t-rebuild/zstd/programs/zstd
```

Compare chromosome/group coordinates, input SHA-256 and archive bytes with the
retained manifest/results. Each row records the individual encode/decode command
and artifact hashes. Source paths in original receipts belong to the original
workspace; the commands above provide the portable path mapping. Stop on any
input mismatch rather than measuring a different input under the same label.

The fixed seed and eligibility rules exclude chromosomes without a 2 MiB
contiguous HOR array. This selection limit and terminal-window dilution are
part of the result. Plain sequence windows are not whole-FASTA byte slices.

`python3 review/t2t_regions/summarize.py` regenerates the standalone report from
retained rows, without invoking codecs. Historical results.jsonl is untouched.
