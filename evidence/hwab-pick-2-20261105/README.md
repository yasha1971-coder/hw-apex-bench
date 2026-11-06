# HWAB-PICK-2 — pick on the reference corpora (2026-11-05, ace-core)

main aefa77a + corpora.json entries (this branch). One run per corpus, one machine (ace-core, AMD EPYC 4344P),
real silence gate (tools/silence_contract.py via review/axis3/verdict_data.capture_silence) PASS before each run.

| corpus | corpora.json | bytes | sha256 | gate load1 | pick |
|---|---|---:|---|---:|---|
| silesia.tar | silesia_tar | 211 947 520 | a667bac8…63eb2 | 0.00 | silesia.tar/pick.md |
| enwik8 | enwik8 | 100 000 000 | 2b49720e…c024a8 | 0.236 | enwik8/pick.md |
| T2T chromosome 1 record | t2t_chm13v2_0_chr1_record | 251 492 222 | d8838e0b…56136 | 0.271 | t2t_chr1.fa/pick.md |

Command: `./run.sh --pick <corpus> --output-dir <dir>` (default selection: Pareto ratio / p50 within each codec).
Logs: `<corpus>.log` (table + time), `silence-<corpus>.json`. Adapter receipts: `check/` (`./run.sh --check
codecs/<codec>.sh`, gate PASS before each; the first xz attempt was refused by the gate at load1 0.89 and repeated).
Archives and the native-measure binary are not committed (size); their SHA-256 are in each `archive-state.json`.

Result: the ★ set is the same on all three corpora — every measured row is ★ (within a codec, ratio and p50 both
grow with g, so no row dominates another). Prediction (CALIBRATION, before the run): the ★ set differs on at least 2
of 3 corpora — missed; kill criterion met: pick is not put into README.
