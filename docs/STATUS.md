# Release, support and evidence status

Status checked on 2026-09-18. Start with [Getting started](GETTING_STARTED.md).

| Item | What a visitor can rely on |
|---|---|
| Published software | [v0.1](https://github.com/yasha1971-coder/hw-apex-bench/releases/tag/v0.1); source release, not an installer |
| Citation | DOI 10.5281/zenodo.22713364 is recorded for v0.1; no new version DOI is claimed |
| Current main | Includes later documentation, corpus checks and reviewed T2T density studies; not identical to the v0.1 tag |
| Historical homepage | 435 frozen records; primary plot is chr1, three formats/four configurations, resident reads on its recorded host |
| Fourth format | XZ has an adapter and correctness evidence; it is not a missing or estimated row in the historical table |
| T2T density | [Regional](RESULTS/T2T_REGIONS_20260916.md), [granularity](RESULTS/T2T_GRANULARITY_20260916.md) and [scope definitions](CG_SCOPES.md); selected equal-sized windows, not a whole-genome curve |
| New access/distance study | Publication unfinished. Local results are not a reviewed release and are not added to the historical plot |
| First-run platform | Ubuntu 24.04 Linux correctness CI. Other OS/architectures are not established by this check; no native Windows/macOS support claim |
| Independence | Maintainer-run CI is not evidence of three independent users; external adoption remains unverified |

## What decision does this help with?

If an application keeps data compressed and reads small byte ranges, compare
stored size, API latency and decoded work on the same input and machine.
Start with [one correctness check](GETTING_STARTED.md), then the optional small
comparison, then your representative data. Report both wins and losses.

Use [lzbench](https://github.com/inikep/lzbench) or
[TurboBench](https://github.com/powturbo/TurboBench) when bulk compression and
decompression are the main question. This project complements those workflows;
it does not establish that other tools lack random-access-related features.

Resident byte reads do not measure disk I/O, remote object-store requests,
application-level queries or end-to-end FASTQ/CRAM semantics. No universal block
size, transferable timing ratio, SLA or industrial certification is claimed.

## Help improve the tool

- [Report a first-run failure](https://github.com/yasha1971-coder/hw-apex-bench/issues/new?template=first-run.md): command, commit, OS and short error excerpt.
- [Describe a workload](https://github.com/yasha1971-coder/hw-apex-bench/issues/new?template=workload.md): the practical question matters more than a star.
- [Report a result or documentation problem](https://github.com/yasha1971-coder/hw-apex-bench/issues/new?template=result-question.md): include the exact row and comparison scope.

Do not upload private inputs or credentials. There is no promised response time.
New codecs and full-genome studies are deferred until the current evidence is
reviewed and published. The [roadmap](TOOL_ROADMAP.md) preserves the original plan.
