#!/usr/bin/env bash
set -euo pipefail
# Sequence-coordinate interface only; never advertises byte-region hc ABI.
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"
codec_name() { echo 'twobit-casefix-sequence'; }
codec_version() { echo 'lib2bit@58e20daa898a6fc338eae82e5d2ef7108d4fc07f+softMask-casefix'; }
twobit_python() { "${HB_PYTHON:-python3}" "$HB_ROOT/codecs/twobit.py" "$@"; }
codec_configuration() { twobit_python configuration; }
codec_supports() { :; }
codec_unavailable() { twobit_python unavailable; }
codec_inputs() { twobit_python inputs; }
codec_build_artifacts() { echo '[]'; }
codec_constraints() { echo '{"granularity":16384,"min_input_bytes":1,"min_input_reason":"FASTA sequence domain; not arbitrary bytes"}'; }
twobit_wrong_domain() { echo 'FASTA sequence/base-coordinate adapter: use seq-reader-build, seq-build and seq-fetch; generic byte operations are unavailable' >&2; return 2; }
codec_build() { twobit_wrong_domain; }
codec_compress() { twobit_wrong_domain; }
codec_decompress() { twobit_wrong_domain; }
codec_region() { twobit_wrong_domain; }
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
case "${1:-}" in
  supports) codec_supports;;
  unavailable) codec_unavailable;;
  configuration) codec_configuration;;
  seq-reader-build|seq-build|seq-fetch) exec "${HB_PYTHON:-python3}" "$HB_ROOT/codecs/twobit.py" "$@";;
  *) twobit_wrong_domain;;
esac
