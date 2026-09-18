# Practical project review — 2026-09-18

Maintainer assessment, not an independent usability study or certification.
Scale: 0 absent; 3 obstructed; 6 usable with stated limitations; 8 verified and
clear; 10 independently demonstrated across intended users/platforms. Scores
are judgments tied to findings, not measured product quality percentages.

| Criterion | Before | After this change | Evidence and remaining boundary |
|---|---:|---:|---|
| Concrete use case | 7 | 7 | README contrasts resident byte access with bulk decode; no application I/O claim |
| First-page orientation | 7 | 8 | Prior audit recorded live Pages HTTP 200; early own-data/status links, graph and static table, corrected wording |
| Safe CLI discovery | 3 | 7 | Help/unknown arguments previously entered historical module setup; now offline help/error, preserved --stage commands and stubbed routing/environment tests |
| First successful run | 6 | 6 | Existing documented Linux XZ qualification and fresh-container CI; no prebuilt cross-platform package |
| Evidence and honest comparisons | 8 | 8 | Frozen 435 digest, qualification, explicit losses; PR #45 merged BGZF scope correction |
| Current versus historical state | 4 | 7 | Status matrix and historical-plan/audit notices; no new DOI or access-study publication claimed |
| Automated review coverage | 5 | 7 | Publication CI now runs on every PR; dispatcher-only changes receive stubbed tests and real adapter correctness checks with timing steps skipped |
| Codec extension | 7 | 7 | Shell contract plus native ABI, XZ example and correctness gate; no fresh third-party contribution observed |
| Support entry points | 6 | 7 | Existing first-run/workload templates plus result/provenance question template |
| Licensing and citation | 7 | 7 | Apache/CC BY, NOTICE, version citation; concept DOI and new deposit not verified |
| Public availability of new access evidence | 3 | 3 | Still unpublished; do not mix unfinished artifacts into this usability change |
| Independent adoption | 2 | 2 | No verified three external runs/one review; cannot fix by changing prose |

The two remaining sub-six items require evidence delivery and real users, not
inflated scores. The owner paused new measurements; no whole-T2T c(g), codec
addition or outreach is performed in this change. Publication of existing raw
files remains a separate bounded task. No traffic analytics were available,
so zero stars cannot be attributed to a specific cause or converted to a
conversion-rate claim. Do not solicit stars as a substitute for usefulness.

## External comparisons checked

- [lzbench](https://github.com/inikep/lzbench): direct file examples, separate
  build/manual guidance, codec/platform matrix. Adopt explicit entry points;
  do not imitate its codec count without demand.
- [TurboBench](https://github.com/powturbo/TurboBench): help, releases and output
  options are discoverable. Its README claims are not independent validation
  of either project's performance.
- [libdeflate](https://github.com/ebiggers/libdeflate): clearly bounded library
  purpose, build command, API and release notes. Adopt scope clarity; it is a
  library, not a direct nine-axis benchmark competitor.

We inspected repository files, CI triggers, entry-point dispatch and live HTML.
The existing explorer test exercises JS selections in a minimal DOM; this is
not a mobile screenshot, screen-reader audit or end-to-end user study.

## Validation

Offline help, typo and invalid-stage cases never invoke Python. Existing entry
points (including all five historical stages) pass exact arguments to a stub and
clear codec environment overrides. No real harness or codec runs in these tests.
Publication validation, Markdown links, Pages export and explorer logic checks
are required before publication; measured JSONL and release identifiers stay fixed.

Recovery validation passed: 20 dispatcher cases, 435 immutable records, 197 local
links, generated-page equality and 810 explorer states. GitHub CI is recorded in
the delivery PR; no fresh codec performance result is claimed.
