#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:?output directory}
mkdir -p "$OUT"
OUT=$(cd -- "$OUT" && pwd)
SRC="$OUT/agc"
PIN=e67e3fc865a459779118d3d4e9fbdf42c70ba75e
if [ -e "$SRC" ]; then
  test "$(git -C "$SRC" rev-parse HEAD)" = "$PIN"
  test -z "$(git -C "$SRC" status --porcelain)"
else
  git clone --quiet https://github.com/refresh-bio/agc.git "$SRC"
  git -C "$SRC" checkout --quiet "$PIN"
fi
git -C "$SRC" submodule update --init --recursive
make -C "$SRC" -j2 agc libagc
cat > "$OUT/axis3.mk" <<'MAKE'
include makefile
.PHONY: axis3_agc_shim
axis3_agc_shim: libagc
	$(CXX) $(CPP_FLAGS) $(OPTIMIZATION_FLAGS) $(ARCH_FLAGS) $(DEFINE_FLAGS) $(INCLUDE_DIRS) -fPIC -shared -I src/lib-cxx "$(HWA_SHIM)" $(OUT_BIN_DIR)/libagc.a $(LIBRARY_FILES) $(filter-out -static,$(LINKER_FLAGS)) $(LINKER_DIRS) -o "$(HWA_SO)"
MAKE
make -C "$SRC" -f "$OUT/axis3.mk" HWA_SHIM="$ROOT/review/axis3/agc_shim.cpp" HWA_SO="$OUT/libhwa_agc.so" axis3_agc_shim
cp "$SRC/bin/agc" "$OUT/agc-cli"
printf '%s\n' "$PIN" > "$OUT/AGC_COMMIT"
sha256sum "$OUT/agc-cli" "$OUT/libhwa_agc.so" > "$OUT/SHA256SUMS"
