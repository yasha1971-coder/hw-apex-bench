# ACEAPEX v2.2.0 CPU evidence — 2026-09-30

Source: [successful Actions run 36751391857](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/36751391857).
CPU artifact 11115186898, SHA-256 `be1ce4937041678bf396bfd3c98a821417d141f717073a50477920e151681717`.
Qualification artifact 11115131449, SHA-256 `08d498dda02886a76924f0f59f37c1b13c4bd5687398775d714ff477ef26998a`.

All 24 source artifact members are committed as unchanged UTF-8 text.
`receipt.json` maps original ZIP paths to repository paths and records each SHA-256.
No measurement was repeated; this evidence survives Actions artifact expiration.
`native/SHA256SUMS` preserves original runner paths and identifies build outputs;
those binaries are not included in the source artifact. `receipt.json` is the
manifest for files actually retained here.

[Per-axis report](../../docs/RESULTS/ACEAPEX_V220_20260930.md).

Offline verification (no builds, network, benchmarks or new codec executions):

```sh
python3 review/aceapex_v220/publish.py --check
```

`publication-check.json` reports sample reaggregation and verification, not new timings.
The original measured `results.json`, configuration and sample files are not rewritten.
