# Default refresh requested after a194893

Pin: `a194893b676a089e5916063d62c45e77483d2c10`. Build Makefile's
`src/aceapex_main.cpp`, with the same source included by the region API.
Run `bash run.sh --default-refresh` for chr1 with its checked MD5.

The candidate table includes bgzip+htslib, seekable zstd, ACEAPEX default,
interactive, dense, and an explicitly labeled LIT_CHUNK=0 legacy endpoint.
All run on the same host; full archive/index accounting and byte-exact restores
are required. Each eligible region path gets the same 200 16 KiB requests.
Actual literal chunking is read from the archive header, never guessed from the
word 'default'. A no-chunking row prints `n/a — no literal chunking` for the
fine-grained region metric. The API's existence and historical slow timings are
not denied or rewritten as full-decode measurements.

Candidate JSONL is `.work/default-refresh/results.jsonl`, with its generated
`docs/RESULTS/DEFAULT_RESULTS.md`. The reviewed root publication remains unchanged until
this separate evidence group is audited and integrated. Historical c(g) and
62.379022 ms measurements remain bound to their old revision/configuration.

The owner reports 3.72329 versus 3.18065, with unchanged text/Silesia defaults.
These are declarations pending independent matching of corpus, library version,
complete-file accounting and settings. This chr1 run does not measure text or
Silesia, and does not publish plateau throughput or claim their results.

Provenance note for the paper: the independent slow-region measurement exposed
an uncovered default configuration. The owner reports reproducing the slowdown
and correcting the default. Preserve this sequence rather than retracting the
measurement that found the issue.

Structural claim boundary: a format family can support a range of encoder
configurations; a profile is selected during encoding. Do not imply that an
existing ACEAPEX archive can change literal granularity without reconstruction.
Do not call zstd's format choice 'irreversible' without specifying that changing
frame boundaries generally needs decoding/re-encoding too. Seekable zstd uses
standard zstd frames plus an index stored in a skippable frame.

The Makefile CLI at this SHA silently ignores `--profile`. These rows therefore
use explicit environment settings from `harness/configurations.py` for both
encoding and reading, with archive geometry checked against those settings.
Attempt 34574475551 completed default and baselines but failed at profile restore
because the harness had mismatched writer/reader settings. It is not a complete
comparison and is retained as an unsuccessful attempt, not evidence of a codec
failure with correctly matched settings.

Completed comparison: [DEFAULT_RESULTS.md](RESULTS/DEFAULT_RESULTS.md). Exact retained
JSONL and receipt are in `evidence/default-a194893/`; replay with
`python3 harness/audit_default.py evidence/default-a194893 docs/RESULTS/DEFAULT_RESULTS.md`.
Workflow 34574867600 passed. Default is 16.33% denser than explicit legacy by
matched complete-file ratios; all ACEAPEX rows lose single-region latency to
both baselines in this run. The owner's +17.1% uses a separately reported setup.
