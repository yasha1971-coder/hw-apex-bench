# BGZF backend equivalence — verified

The BGZF acceptance blocker in `native-full-comparison.json` is resolved by the
separate untimed experiment in `evidence/bgzf-libdeflate-20260911/`.
This does not rewrite the original full-run report or its zlib measurements.

Workflow34626693337 succeeded on commit2c8ebcd9daf770525d32d4cc9a827e61de81ec87.
Artifact10273679252 and its original ZIP are retained in the repository. Its digest,
qualification linkage and historical comparisons were checked independently.

| Build | Archive bytes | Archive SHA256 | Ratio including .gzi |
|---|---:|---|---:|
| Historical system HTSlib1.19 | 75009810 | c41f38ce60f54fc0560e53c60a7ba645a6946d5827cdc0d21f6a2acf96bb4784 | 3.3825582764886026 |
| Pinned HTSlib1.19 + libdeflate1.19 | 75009810 | c41f38ce60f54fc0560e53c60a7ba645a6946d5827cdc0d21f6a2acf96bb4784 | 3.3825582764886026 |
| Pinned HTSlib1.19 + zlib | 76512773 | af90c826674ec7a2780f8dacb2ac1fd1e5e9086c923c41121770f07f6e2e7335 | 3.316167684220197 |

All indexes are62232bytes; the libdeflate index also exactly matches the historical
system output SHA256 f2eee38438413fe9070e29e50f39c1626f5304253d90c1d9fddad60693a65869.
All three archives pass CLI and native full restoration, plus64 native regions each.
The libdeflate counter reports65235 actual bytes for the first16384-byte request.
The exact historical system binary SHA was required before any comparison; its
resolved libraries confirm libdeflate1.19. The pinned library commit is
`dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f` and compiled features confirm libdeflate=yes.

The3 missing archive checks now pass in this separate corrected-build experiment.
Together with the earlier98 exact checks, this closes the identified deterministic
BGZF regression for the tested chr1 configuration. It is not a claim that the
original236-row zlib run changed, that a single fresh run reproduced435 rows, or
that timings on different hosts must match. Historical default curves, GPU and
frontier scopes retain their existing exclusions. The native migration acceptance
blocker is closed; release/publication decisions remain separate.

Reproduction: on Ubuntu24.04 install the prerequisites listed in
`.github/workflows/bgzf-build-audit.yml`, then run `python3 review/audit_bgzf_build.py`
from a fresh checkout. The script fails on a changed historical system binary or
corpus MD5 and never invokes performance measurement workers. Exact build, encode
and verification commands, backend provenance and one actual untimed ratio JSONL
row are retained with the artifact.

Two initial urllib attempts failed before compression. Bounded IPv4 curl fetching
succeeded from the original UCSC soe URL. The cse alias failed TLS verification;
certificate checks were not bypassed. This is recorded in audit.json.

Method references: https://www.htslib.org/benchmarks/zlib.html recommends libdeflate
but does not promise universally smaller output; https://www.htslib.org/doc/1.19/bgzip.html
specifies CLI0–9. Pinned HTSlib maps CLI6 to libdeflate7. bgzip1.19 --version alone
does not print its backend, so compiled feature introspection is used instead.
