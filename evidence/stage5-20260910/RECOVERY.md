# Recovery of the stage-5 publication

The merge of PR #12 (`5c43e8633d00c520d46bf7e3460f7a4c4881c2e7`)
contained an invalid UTF-8 `results.jsonl`. Pages run
[34540057488](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/34540057488)
failed before deployment in `web/build.py` with `UnicodeDecodeError` at byte 1.

| Object | Bytes | SHA-256 |
|---|---:|---|
| Broken Git blob | 600063 | `9de7b2906ae13cb1a0b179e4a793544af864249a87c59654c81f38ef521ec7ed` |
| Restored results.jsonl | 11505154 | `4123976f7c546208c92d344a5fc27f21760b14eb84741d51415c8c5b7e97be3e` |
| Original Actions ZIP | 1176281 | `14a6f26b15670cc96bc5370547219981e5e70c0eed07cf80195f6069fabdc8da` |

The unchanged source ZIP is the artifact from successful workflow
[34526588649](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/34526588649),
artifact ID `10172846109`, name `stage1-evidence`, measured source
`9cad83e8a5c9a5f3bafb7ef2c70c8d0ead4276fb`. Its SHA-256 was independently
matched against GitHub's artifact `digest` metadata before recovery. The ZIP is
retained separately for the owner as `cabench-stage5-source-artifact.zip`.
Automatic approval review rejected making the complete raw CI archive public
because it contains logs, traces and environment data. This repair therefore
publishes the recovered results and provenance manifest without the raw ZIP.

The repaired file is byte-for-byte identical to the ZIP member `results.jsonl`:
420 records, including 36 zstd-frontier and 11 GPU-declaration records. No number,
timestamp, status, command, dependency SHA or hardware descriptor was edited.
The mechanism that produced the bad Git blob has not been established.

Both committed reports regenerate exactly from the recovered JSONL with the
committed generators. The original ZIP's README predates two explanatory wording
changes in PR #12 (the full-decode worker note and the review-boundary sentence);
its measured tables are preserved. `BATCH_RESULTS.md` also matches the ZIP exactly.

Verification from the repository root:

```sh
python3 web/validate_publication.py
python3 -m unittest discover -s web -p test_publication.py -v
python3 web/build.py /tmp/cabench-pages/index.html
```

The first command checks the explicit publication manifest, strict UTF-8 JSONL,
record/run identities, the existing benchmark report validators, and exact report
regeneration. `web/build.py` performs the same checks before building a page.
PR validation and Pages deployment both use this boundary.

The manifest identifies a reviewed publication snapshot. A new benchmark run does
not overwrite it automatically. To publish another run, audit its raw artifact,
regenerate its reports, and update `evidence/published-results.json` in the same
reviewed change. The original ZIP remains separate historical evidence.
