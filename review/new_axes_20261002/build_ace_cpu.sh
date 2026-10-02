#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:-"$ROOT/.work/axes-20261002/ace"}
SRC="$OUT/src"
SHA=207bf0042dfd410f908f3b8eeb7bc8701bdbf3ee
mkdir -p "$OUT"
rm -rf "$SRC"
git clone --quiet https://github.com/yasha1971-coder/aceapex.git "$SRC"
git -C "$SRC" checkout --quiet "$SHA"
make -C "$SRC" clean
make -C "$SRC" -j1
cp "$SRC/aceapex" "$OUT/aceapex-xxh3"
python3 - "$SRC/src/aceapex_main.cpp" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old="bool ok=(dv==hv3);"
if old not in s:
    raise SystemExit("expected XXH3 verdict site not found")
s=s.replace(old,"bool ok=true; /* hw-apex-bench no-check variant: final XXH3 verdict disabled */",1)
p.write_text(s)
PY
make -C "$SRC" clean
make -C "$SRC" -j1
cp "$SRC/aceapex" "$OUT/aceapex-no-xxh3"
sha256sum "$OUT/aceapex-xxh3" "$OUT/aceapex-no-xxh3" > "$OUT/SHA256SUMS"
printf "%s\n" "$SHA" > "$OUT/ACEAPEX_COMMIT"
