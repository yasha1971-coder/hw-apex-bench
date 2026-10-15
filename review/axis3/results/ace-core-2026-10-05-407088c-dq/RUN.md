# Axis 3 D_Q run - ace-core, 2026-10-05

- Harness: hw-apex-bench 407088cec5c715e769048bced23aa320871aac8a (PR #63 HEAD), clean worktree; nothing else run on the host during the timed runs.
- Host: AMD EPYC 4344P 8-Core Processor, 16 threads, 125 GB RAM, Ubuntu 22.04.5 LTS, kernel 5.15.0-163-generic; g++ (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0; cmake version 3.22.1.
- Silence gate before start (`silence_gate.txt`): load 0.40 (< 0.5), 74 GB free (> 20), no foreign heavy process; openhands (uvicorn, 0.7 % CPU) and glyph (0.0 %) recorded as background.
- Corpus: axis 3 HPRC N=4, the first four rows of the frozen cohort manifest (aceapex research/refrel/logs/cohort-v1-manifest-2026-10-04.tsv): y1_HG00438.1, y1_HG00438.2, y1_HG00621.1, y1_HG00621.2; every .fa.gz SHA-256 == manifest source_sha256 (HG00621.2 re-downloaded from the manifest URL); unpacked FASTA SHA-256 in `source_fasta.sha256` (12 139 733 805 B in total).
- Reference for refrel3: T2T-CHM13v2.0 (md5 cd1e52ce400c027ed0b7ab4b9d613f5a), decoded and resident; its SHA-256 is checked by every archive open.

## refrel3 (ACEAPEX-refrel3, frozen v1)

- Build: `review/axis3/build_refrel3.sh` (aceapex 5b6d5cec0f5962a561ac48822a1b5c48793a5b47, g++ -O3 -march=native -funroll-loops); binary SHA-256 in `refrel3v1.sha256`.
- Archives: `review/axis3/refrel3_adapter.sh build <T2T> q4k|q16k 16 <asm.fa> <out>`; all 8 archive SHA-256 == the manifest's q4k_sha256 / q16k_sha256 (`refrel3_archives.sha256`); build wall time and peak RSS in `build_times.tsv`. Archive bytes include the per-block XXH3 section (flag bit 0), as frozen in the manifest.
- D_Q tool: `dq_refrel3.cpp` (this directory), built against the same aceapex checkout with `refrel3v1_nomain.cpp` = refrel3v1.cpp with line 243 `int main(` renamed to `static int refrel3v1_main(` by sed (no other change); g++ -O3 -march=native -funroll-loops, linked to OpenSSL libcrypto.so.3 for SHA-256; binary SHA-256 in `dq_refrel3.binary.sha256`.
- Measured: `taskset -c 3 dq_refrel3 <T2T> 3 9 <4 archives + source SHA-256>`: one decode thread (full_v1 with threads = 1, verify = false: block and FASTA XXH3 not computed in the timed region), the 4 assemblies decoded in order to FASTA bytes in memory; SHA-256 of each output compared with the source after every run, outside the timed region. Raw lines: `dq_refrel3_q4k.log`, `dq_refrel3_q16k.log` (DQGEOM: bases, blocks, archive bytes; DQRUN: run, total s, output bytes, per-assembly s, SHA result).
- Q: independently decodable unit = one block of RR_BS bases (FORMAT.md); mean over the cohort weighted by bytes = total bases / total blocks (last block of each assembly shorter), also given in FASTA output bytes per block.

## OpenZL v0.3.0 - FAILED (build)

- Build: `review/axis3/build_openzl_v030.sh` (openzl 32246b48faee46807f84183dac4db479089f5445): zli and openzl-lz-helper built (`openzl_VERSION.txt`, `openzl-lz-helper.sha256`); the script's last step (dependency_versions.c) failed on this host: `lz4.h: No such file or directory` (no system liblz4-dev); it was compiled by hand with `-I openzl/deps/zstd/lib -I openzl/deps/lz4/lib` against the same static libraries: `openzl_dependency_versions.txt` (zstd 1.5.7, lz4 1.10.0).
- `review/axis3/openzl_adapter.sh build <variant> <asm.fa> <out>` for all 4 variants x 4 assemblies: graph reflection correct (level 1/3, windowLog 16/20, frame v27 on a 1 MiB check), but every assembly fails: `compress failed: Temporary OpenZL library limitation` (exit 2; `openzl_build_failures/`, `build_times.tsv`).
- Input size limit of the helper (l1_w64k, prefixes of HG00438.1.fa): 64 / 256 / 1024 MiB compress; 2047 / 2049 / 3000 MiB fail; bisection: 1503 MiB ok, 1519 MiB fails. All four assemblies are 2.94-3.07 GB. The synthetic CI (~1 MiB inputs) does not reach this limit.
- Q: OpenZL v0.3.0 has no public API to decode part of a frame, so the independently decodable unit of this adapter is the whole frame (one assembly). No D_Q row; status FAILED per PROTOCOL_AXIS3 judge rules.

## Run 2: all measurable formats under one silence gate (17:18 UTC)

`silence_gate.txt` (run 2: load 0.48, 74 GB free; run 1 gate kept as `silence_gate_run1.txt`). The five configurations ran one after another with nothing else on the host: refrel3 q4k, q16k (`dq_refrel3_q4k.log`, `dq_refrel3_q16k.log`; run 1 logs kept as `*_run1.log`), BGZF, zstd seekable, lz4 (`dq_bgzf.log`, `dq_zstd_seekable.log`, `dq_lz4.log`). Table: `SUMMARY.md`.

Foreign formats, same corpus (the 4 FASTA files of `source_fasta.sha256`), built by the pinned hw-apex recipes (`harness/check_adapter.py codecs/bgzip.sh` and `codecs/zstd_seekable.sh`, both PASS on this host) and `build_others.sh` (this directory; archive SHA-256 in `foreign_archives.sha256`, wall time and RSS in `build_times.tsv`):
- BGZF: htslib 1.24 (4b705e4) bgzip with libdeflate 1.19 (dd12ff2), `-l 6 -@ 1 -i -I <gzi>`, adapter level 6; Q = output / blocks with ISIZE > 0 counted by walking BSIZE (ceiling 65280); .gzi bytes counted in the archive size. Decode: htslib `bgzf_open` + `bgzf_read` loop, no `bgzf_mt`, archive in the page cache (htslib reads the file through its hFILE; warm-ups load the cache).
- zstd seekable: zstd 1.5.7 (f8745da) `contrib/seekable_format/examples/seekable_compression <fa> 16384 3` (level 3, 16 KiB frames, frame checksums), adapter granularity 16384; Q from the seek table (`ZSTD_seekable_getNumFrames`). Decode: `ZSTD_seekable_initBuff` on the archive in memory + `ZSTD_seekable_decompress` of the whole content.
- lz4 frame: lz4 1.10.0 (the OpenZL submodule's tag, built here: `lz4_VERSION.txt`), `-T1 -1 -B7 -BI --content-size --frame-crc` (level 1, 4 MiB independent blocks, content checksum; the PR #62 axis-10 lz4 adapter uses the CLI default block size and `--frame-crc`); Q = output / data blocks counted by walking block headers. Decode: `LZ4F_decompress` of the frame in memory (content checksum verified by the library).
- D_Q tool: `dq_others.c` (this directory; built against the static libraries above and libcrypto.so.3; binary SHA-256 in `dq_others.binary.sha256`), same protocol as `dq_refrel3.cpp`.
- CRAM: skipped - a format for read alignments against a reference, not applicable to assembly FASTA.
- refrel3 run 1 vs run 2 (same binaries, archives, protocol): q4k 13.076 -> 13.865 s median, q16k 12.811 -> 13.262 s; both runs are kept as measured.
