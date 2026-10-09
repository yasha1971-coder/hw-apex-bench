#!/usr/bin/env bash
# one job: <format> <assembly>; archives into arch/, wall time + peak RSS appended to build_times.tsv
set -euo pipefail
fmt=$1; n=$2
B=check-bgzf/bgzip-9b52312455/deps/htslib/bgzip
S=check-zstd/zstd_seekable-31ddddfe5a/deps/zstd/contrib/seekable_format/examples/seekable_compression
L=lz4-1.10.0/lz4
case $fmt in
  bgzf) /usr/bin/time -f "bgzf	l6	$n	%e s	%M KB" -a -o build_times.tsv sh -c "$B -l 6 -@ 1 -i -I arch/$n.bgz.gzi -c src/$n.fa > arch/$n.bgz";;
  zsk)  /usr/bin/time -f "zstd_seekable	l3_frame16384	$n	%e s	%M KB" -a -o build_times.tsv $S zsk/$n.fa 16384 3; mv zsk/$n.fa.zst arch/$n.zsk;;
  lz4)  /usr/bin/time -f "lz4	l1_B7_BI_content-checksum	$n	%e s	%M KB" -a -o build_times.tsv $L -q -T1 -1 -B7 -BI --content-size --frame-crc src/$n.fa arch/$n.lz4;;
esac
