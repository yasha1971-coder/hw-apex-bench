# Corpus identity and admission

The catalog is [corpora.json](../corpora.json). A catalog entry specifies an
expected input; it is not evidence that a measurement or independent download
verification has completed. The historical default remains chr1 hg38. Adding
T2T does not automatically run it: the current historical entry points select
chr1 explicitly, and native measurements accept a prepared file via `--input`.

## T2T-CHM13v2.0

Assembly GCA_009914755.4, complete genomic FASTA from the versioned NCBI URL in
the catalog. Owner-reported compressed size: 932,696,125 bytes. After gzip
expansion: 3,156,259,565 bytes; MD5 `cd1e52ce400c027ed0b7ab4b9d613f5a`.
The NCBI checksum listing reports compressed MD5
`9280657210e4161147cbe13b022225b9`; its metadata was retrieved on 2026-09-16.
Keep headers, line endings, wrapping and sequence order unchanged. Download
with HTTP errors treated as failures, decompress, then verify both expanded
size and MD5 before any codec runs. The values were initially supplied from ace-core. The subsequent regional
experiment independently verified both compressed and expanded MD5 and the
expanded size; see its [retained receipt](../evidence/t2t-regions-20260916/receipt.json).
Thirty frozen windows were measured. This does not establish a whole-T2T c(g) curve.

## ERR174310: source-resolved byte-prefix recipe

The owner's input is the first 5,368,709,120 bytes of the uncompressed
`ERR174310_1.fastq`, not paired files, not concatenated mates, and not a prefix
of compressed bytes. The reported full file size is 53,868,884,409 bytes.
Preparation: `head -c 5368709120 ERR174310_1.fastq > ERR174310_5gb.fastq`.
Expected prefix MD5: `d628e1c9fb9466fcbd82109c3c7f9f10`.

The final FASTQ record is cut. Treat this candidate as arbitrary bytes for
lossless compression; it is not valid FASTQ input for record-aware codecs.

On 2026-09-16 the [ENA file report](https://www.ebi.ac.uk/ena/portal/api/filereport?accession=ERR174310&result=read_run&fields=run_accession,fastq_ftp,fastq_md5,fastq_bytes&format=json)
returned this source for mate 1:

- URL: https://ftp.sra.ebi.ac.uk/vol1/fastq/ERR174/ERR174310/ERR174310_1.fastq.gz
- Compressed bytes: 18,575,686,207.
- Compressed MD5: `b6099227bfb6d15c97395975eeeccd28`.

A streamed gzip-prefix check on 2026-09-16 matched the owner's first
104,857,600 expanded bytes exactly: MD5 `366e770acdf9892b9c5611fdeba9e6e6`
and first line `@ERR174310.1 HSQ1008_141:5:1101:1454:3564/1`.
See the [prefix receipt](../review/err174310-prefix-100mib.json).
The stream was closed at the prefix boundary; the full gzip CRC and the
5 GiB prefix were not verified. ENA metadata alone did not establish this match.
A matching accession alone does not establish identical serialized FASTQ bytes.
Before measurement, retrieve the source, verify its checksum, decompress without
rewriting records, and verify the exact prefix size and MD5 above. A mismatch
must be reported as a different input, never silently substituted. The catalog now records this source and prefix recipe following the successful
100 MiB check. The full-prefix MD5 remains owner-reported, not independently
verified; do not measure an input until its size and MD5 pass. Only the compressed data needed to expand the first 100 MiB was read in this
follow-up; the full 18.6 GB compressed source was not downloaded.

## Cross-host interpretation

Within-run codec ratios require the same corpus and an agreed measurement
protocol; their stability across hosts is a separate empirical question.
A best-of-five process decode into tmpfs is not interchangeable with a median
of five resident library decodes. Retain the aggregation, timer boundary,
threads, configuration and separate htslib/libdeflate versions when comparing.
The owner reports htslib 1.13 with libdeflate 1.10 on ace-core; this is contextual
information, not a new benchmark row or an amendment to historical provenance.
