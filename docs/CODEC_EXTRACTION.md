# Native codec extraction: mechanical first step

The base is published main `0e8246f8b14b74191b3bf8cc6f14b71be85779ce`.
The existing `codecs/bgzip.sh`, `codecs/zstd_seekable.sh`, and `codecs/aceapex.sh`
already own build/compress/restore CLI commands. They are unchanged in this step.
No pinned version, setting, command or result row is replaced with PR #17's code.

Sixteen existing native sections are copied into three files:
`harness/native/bgzip.inc`, `zstd_seekable.inc`, and `aceapex.inc`.
They contain resident setup, region calls, shared full/region decode paths and
ACEAPEX native batch calls. The call sites use preprocessor inclusion so the
original expressions, timing boundaries and return checks are preserved. This
transitional layout adds no callback call, dynamic loader or shell process to
any timed interval. These fragments are deliberately not standalone translation
units and are not the proposed final public adapter interface.

The extraction manifest records the original source blobs, exact section hashes
and the base commit. The verifier expands every inclusion, rejects extra code
outside the sections and compares the reconstructed sources byte-for-byte with
published main. It also compares all 435 results.jsonl records byte-for-byte.

```sh
python3 harness/verify_native_extraction.py
python3 -m unittest discover -s harness -p test_native_extraction.py
```

For a shallow clone, fetch the base commit first (CI does this automatically):
`git fetch --no-tags --depth=1 origin 0e8246f8b14b74191b3bf8cc6f14b71be85779ce`.
Five tests reject changed native calls, clock selection, injected code and modified
measurement bytes, and accept the exact move.

An additional local GCC -O3 comparison produced byte-identical assembly before
and after extraction for region latency, COUNT_DECODER region counting, batch,
break-even and full-decode throughput. The hashes, compiler and header revisions
are in `harness/native/assembly-check.json`. Both sides used identical headers;
this is structural compiler equivalence, not a new measurement or qualification
of a different htslib version. No executable was run.

README and reports regenerate identically from the retained JSONL; licenses and
the publication manifest are unchanged. Fresh timing runs cannot be expected to
reproduce timestamp/sample bytes, so unchanged historical records are not claimed
to be a fresh benchmark result.

This is only the first extraction segment. Dispatch, shared state, counter
selection and native-range types still remain in the historical harness. The
controlled c(g)/default refresh paths also retain their existing orchestration.
The next segment compares the moved implementations and existing n/a reasons,
then derives capabilities and the smallest actual interface. No seven-function
contract, generic --check, fourth codec or final plugin ABI is asserted here.
