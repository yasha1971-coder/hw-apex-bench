#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd); OUT=${1:?output}; : "${LZ4_ROOT:?set LZ4_ROOT to retained LZ4 v1.10.0 source/build tree}"
# LZ4_VERSION_STRING expands other macros; read the three numeric components.
# Require exactly one numeric definition per component; do not guess on bad headers.
version=$(python3 - "$LZ4_ROOT/lib/lz4.h" <<'PY_VERSION'
import re
import sys
from pathlib import Path
header = Path(sys.argv[1]).read_text()
parts = []
for name in ("MAJOR", "MINOR", "RELEASE"):
    values = re.findall(r"^\s*#\s*define\s+LZ4_VERSION_" + name + r"\s+([0-9]+)\b", header, re.M)
    if len(values) != 1:
        raise SystemExit("expected one numeric LZ4_VERSION_" + name)
    parts.append(str(int(values[0])))
print(".".join(parts))
PY_VERSION
)
test "$version" = 1.10.0 || { echo "LZ4 receipt requires v1.10.0, got $version" >&2; exit 2; }
cc -O3 -fPIC -shared -I"$LZ4_ROOT/lib" "$ROOT/review/axis3/native/lz4_indexed.c" "$LZ4_ROOT/lib/lz4.c" -o "$OUT"
printf 'version=%s\nsource=%s\n' "$version" "$LZ4_ROOT" > "$OUT.receipt"
