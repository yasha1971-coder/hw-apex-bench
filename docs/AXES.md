# Reading the axes

## Amplification: how much work buys one answer?

A decoder may expand more bytes than the caller receives.
In the published BGZF row it expands 4.821094 times the requested output on average.
One is attainable when the requested bytes match the decoded work; an unaligned
request can instead touch several blocks. Smaller amplification does not alone
predict faster reads, because codecs do different work per decoded byte.

## Break-even: when might a full decode cost less?

Compare repeated individual region reads with a single full decode.
The BGZF model reports 3435 queries as the first integer exceeding full-decode time.
It uses the measured median per-read cost, not a new experiment with that many reads.
Overlapping ranges, caching and batch APIs can change the decision.

## c(g): what does independent addressing cost?

Compare density at a chosen granularity against a file compressed as one block,
while holding the other settings fixed. The separately audited zstd curve includes -0.509942%: a negative cost, meaning splitting improved density at that point.
Local entropy statistics can outweigh lost long matches; the number alone does
not isolate that mechanism. BGZF has no comparable single-parameter baseline.

## H_alpha: where do the requests land?

Entropy describes how spread out request starts are across the codec's blocks.
It is zero when every start lands in one block and is largest for a uniform
block distribution; twice as many equally likely blocks adds one bit.
The BGZF uniform profile at 5000 requests has 11.285997 bits.
Uniform byte offsets need not be uniform over variable-size blocks.

## Density and speed answer different questions

Ratio measures original bytes per stored byte, including required indexes.
Encoding and full decoding throughput measure how quickly a whole input is processed.
A plateau separates a sustained rate from a small-input or data-edge observation.

## Typical and slow region reads

p50 describes the middle read; p99 describes the slow tail of the observed sample.
Both use resident archives and a timer around the library API.
Neither includes downloading the archive or starting a command-line process.

## A workload, not just a codec

Batch throughput depends on where requests land and whether native batching exists.
The five profiles are discrete measured workloads; the explorer never invents an
intermediate workload. Loop and native-batch results remain separately labelled.

[Procedures](METHOD.md) · [Full results](RESULTS/README.md) · [Provenance](PROVENANCE.md)
