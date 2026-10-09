#!/usr/bin/env bash
set -euo pipefail
# Build the pinned AGC 3.2.4 CLI and the axis3 shim library for one explicit CPU platform.
# AGC_PLATFORM (required) selects AGC's PLATFORM (refresh.mk CHECK_OS_ARCH at e67e3fc):
#   sse2 | avx | avx2  -> PLATFORM=<value>, -m<value> -m64 (portable builds; CI uses avx2)
#   native             -> no PLATFORM, refresh.mk then compiles with -march=native (host-specific; local ace-core runs only,
#                         chosen explicitly and recorded in $OUT/AGC_PLATFORM)
#   avx512 is rejected: refresh.mk at e67e3fc emits -mavx512, which gcc does not accept (it expects -mavx512f).
# An empty or unknown AGC_PLATFORM is an error before anything is cloned or built.
AGC_PLATFORM=${AGC_PLATFORM:-}
case "$AGC_PLATFORM" in
  sse2|avx|avx2) PLATFORM_ARGS=("PLATFORM=$AGC_PLATFORM"); PLATFORM_BANNER="x86-64 with ${AGC_PLATFORM^^} extensions" ;;
  native) PLATFORM_ARGS=(); PLATFORM_BANNER="Unspecified platform - using native compilation for x86_64" ;;
  "") echo "build_agc_v324.sh: AGC_PLATFORM must be set (sse2 | avx | avx2 | native)" >&2; exit 2 ;;
  *) echo "build_agc_v324.sh: unknown AGC_PLATFORM '$AGC_PLATFORM' (valid: sse2 | avx | avx2 | native; avx512 is rejected because AGC e67e3fc emits -mavx512)" >&2; exit 2 ;;
esac
test "$(uname -m)" = x86_64 || { echo "build_agc_v324.sh: x86_64 host required (uname -m = $(uname -m))" >&2; exit 2; }
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:?output directory}
mkdir -p "$OUT"
OUT=$(cd -- "$OUT" && pwd)
SRC="$OUT/agc"
PIN=e67e3fc865a459779118d3d4e9fbdf42c70ba75e
if [ -e "$SRC" ]; then
  test "$(git -C "$SRC" rev-parse HEAD)" = "$PIN"
  test -z "$(git -C "$SRC" status --porcelain)"
  # objects of another platform must not be reused
  if [ "$(cat "$OUT/AGC_PLATFORM" 2>/dev/null || true)" != "$AGC_PLATFORM" ]; then make -C "$SRC" clean >/dev/null; fi
else
  git clone --quiet https://github.com/refresh-bio/agc.git "$SRC"
  git -C "$SRC" checkout --quiet "$PIN"
fi
git -C "$SRC" submodule update --init --recursive
rm -f "$OUT/AGC_PLATFORM" "$OUT/SHA256SUMS"
make -C "$SRC" -j2 "${PLATFORM_ARGS[@]}" agc libagc 2>&1 | tee "$OUT/build.log"
grep -Fq "*** $PLATFORM_BANNER ***" "$OUT/build.log" || { echo "build_agc_v324.sh: AGC did not report platform '$PLATFORM_BANNER'" >&2; exit 1; }
cat > "$OUT/axis3.mk" <<'MAKE'
include makefile
.PHONY: axis3_agc_shim
axis3_agc_shim: libagc
	$(CXX) $(CPP_FLAGS) $(OPTIMIZATION_FLAGS) $(ARCH_FLAGS) $(DEFINE_FLAGS) $(INCLUDE_DIRS) -fPIC -shared -I src/lib-cxx "$(HWA_SHIM)" $(OUT_BIN_DIR)/libagc.a $(LIBRARY_FILES) $(filter-out -static,$(LINKER_FLAGS)) $(LINKER_DIRS) -o "$(HWA_SO)"
MAKE
make -C "$SRC" -f "$OUT/axis3.mk" "${PLATFORM_ARGS[@]}" HWA_SHIM="$ROOT/review/axis3/agc_shim.cpp" HWA_SO="$OUT/libhwa_agc.so" axis3_agc_shim
cp "$SRC/bin/agc" "$OUT/agc-cli"
printf '%s\n' "$PIN" > "$OUT/AGC_COMMIT"
printf '%s\n' "$AGC_PLATFORM" > "$OUT/AGC_PLATFORM"
sha256sum "$OUT/agc-cli" "$OUT/libhwa_agc.so" > "$OUT/SHA256SUMS"
