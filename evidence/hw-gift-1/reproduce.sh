#!/usr/bin/env bash
set -euo pipefail
# Run in a clean hw-gift-1 checkout with git push access to that branch.
# GIFT_INPUTS contains verified enwik8 and silesia.tar; GIFT_ZSTD is the v1.5.7 checkout.
# GIFT_STATE holds the build/logs/partial samples on persistent storage, outside git and /tmp.
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
branch=hw-gift-1
ref="refs/remotes/origin/$branch"
d=evidence/hw-gift-1
export GIFT_INPUTS GIFT_ZSTD GIFT_STATE
GIFT_INPUTS=$(realpath "${GIFT_INPUTS:?directory containing both raw corpora}")
GIFT_ZSTD=$(realpath "${GIFT_ZSTD:?pinned zstd checkout}")
mkdir -p "${GIFT_STATE:?durable state directory}"
GIFT_STATE=$(realpath "$GIFT_STATE")
test "$(git branch --show-current)" = "$branch"
sync_ref() { git fetch --no-tags origin "refs/heads/$branch:$ref"; }
sync_ref
git merge --ff-only "$ref"
# A failed push leaves the completed commit local. Only retry an inspected checkpoint commit.
if [[ $(git rev-parse HEAD) != "$(git rev-parse "$ref")" ]]; then
    echo "Local unpublished commits; inspect and push them before continuing (no remeasurement)." >&2
    exit 1
fi
git diff --cached --quiet
git diff --quiet -- "$d/reproduce.sh" "$d/chunks.py" "$d/sweep.py" "$d/pair.c" "$d/report.py" "$d/CALIBRATION.md" codecs/native/zstd_seekable.c
export GIFT_LIB="$GIFT_STATE/libgift.so" GIFT_ENC="$GIFT_ZSTD/contrib/seekable_format/examples/seekable_compression"
built=0
for chunk in enwik8-L3 enwik8-L19 silesia-L3 silesia-L19; do
    sync_ref
    test "$(git rev-parse HEAD)" = "$(git rev-parse "$ref")"
    if [[ -n $(git ls-tree "$ref" -- "$d/$chunk") ]]; then
        python3 -B "$here/chunks.py" remote "$chunk"
        echo "BRANCH_CHECKPOINT_VERIFIED_SKIP $chunk"
        continue
    fi
    if [[ "$built" == 0 ]]; then
        test "$(git -C "$GIFT_ZSTD" rev-parse HEAD)" = f8745da6ff1ad1e7bab384bd1f9d742439278e99
        make -s -C "$GIFT_ZSTD/lib" -j8 libzstd.a CFLAGS='-O3 -fPIC'
        make -s -C "$GIFT_ZSTD/contrib/seekable_format/examples" seekable_compression
        gcc -O3 -fPIC -shared -DXXH_NAMESPACE=ZSTD_ -I"$root/harness" -I"$GIFT_ZSTD/lib" -I"$GIFT_ZSTD/lib/common" -I"$GIFT_ZSTD/contrib/seekable_format" "$here/pair.c" "$root/codecs/native/zstd_seekable.c" "$GIFT_ZSTD/contrib/seekable_format/zstdseek_decompress.c" "$GIFT_ZSTD/lib/libzstd.a" -pthread -o "$GIFT_LIB"
        built=1
    fi
    python3 -B "$here/chunks.py" run "$chunk" 2>&1 | tee -a "$GIFT_STATE/$chunk.log"
    python3 -B "$here/chunks.py" verify "$chunk"
    mapfile -t files < <(python3 -B "$here/chunks.py" files "$chunk")
    test "${#files[@]}" -eq 10
    git add -- "${files[@]}"
    git commit --only -m "Record verified HW-GIFT-1 checkpoint $chunk" -- "${files[@]}"
    git push origin "HEAD:refs/heads/$branch"
    sync_ref
    python3 -B "$here/chunks.py" remote "$chunk"
done
python3 -B "$here/chunks.py" report
if ! git diff --quiet HEAD -- "$d/RESULTS.md" || ! git ls-files --error-unmatch "$d/RESULTS.md" >/dev/null 2>&1; then
    git add -- "$d/RESULTS.md"
    git commit --only -m "Report HW-GIFT-1 after all four verified checkpoints" -- "$d/RESULTS.md"
    git push origin "HEAD:refs/heads/$branch"
fi
