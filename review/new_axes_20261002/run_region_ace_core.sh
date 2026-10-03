#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
WORK=${1:-"$ROOT/.work/axes-20261002"}
mkdir -p "$WORK/source" "$WORK/region"
ACE_SHA=${ACE_SHA:-091bb1e75aca7691e8b87db7f0fd8505e74739a0}
export ACE_SHA
bash "$ROOT/review/new_axes_20261002/build_ace_cpu.sh" "$WORK/ace"
bash "$ROOT/review/new_axes_20261002/build_region_helpers.sh" "$WORK/region/lib" "$WORK/ace/src" "$ACE_SHA"
{
  printf "aceapex_commit=%s\n" "$ACE_SHA"
  printf "ace_cpp_cxxflags="; cat "$WORK/region/lib/ACE_CPP_CXXFLAGS.txt"
  printf "ace_cli_makefile_cxxflags=-std=c++17 -O3 -march=native -funroll-loops -DACEAPEX_CLI\n"
  printf "ace_cpp_link_flags=-fPIC -shared -pthread -lzstd\n"
  g++ --version | head -1
} > "$WORK/region/RUN.txt"
if [ -f "$WORK/source/chr1.fa" ]; then :; else curl --fail --location --retry 3 https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr1.fa.gz -o "$WORK/source/chr1.fa.gz"; gzip -dc "$WORK/source/chr1.fa.gz" > "$WORK/source/chr1.fa"; fi
printf "%s  %s\n" 9465e0f0df6e2c6eb39729c39cee5465 "$WORK/source/chr1.fa" | md5sum -c -
if [ -f "$WORK/source/t2t.fa" ]; then :; else curl --fail --location --retry 3 https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/009/914/755/GCA_009914755.4_T2T-CHM13v2.0/GCA_009914755.4_T2T-CHM13v2.0_genomic.fna.gz -o "$WORK/source/t2t.fa.gz"; gzip -dc "$WORK/source/t2t.fa.gz" > "$WORK/source/t2t.fa"; fi
printf "%s  %s\n" cd1e52ce400c027ed0b7ab4b9d613f5a "$WORK/source/t2t.fa" | md5sum -c -
for corpus in chr1 t2t; do
  fasta="$WORK/source/$corpus.fa"
  samtools faidx "$fasta"
  env ACEAPEX_BS=16384 LIT_CHUNK=65536 AX_PROFILE=open "$WORK/ace/aceapex-xxh3" c --in "$fasta" --out "$WORK/region/$corpus.ace" --threads 1 --level 2
  "$WORK/ace/aceapex-xxh3" faidx "$WORK/region/$corpus.ace"
  bgzip -@16 -c "$fasta" > "$WORK/region/$corpus.fa.bgz"
  samtools faidx "$WORK/region/$corpus.fa.bgz"
  python3 "$ROOT/harness/region_latency.py" --mode ace-cpp-in-process --regions "$ROOT/regions/$corpus-10000x5000.tsv" --reference "$ROOT/regions/$corpus-10000x5000.sha256.tsv" --archive "$WORK/region/$corpus.ace" --fasta "$fasta" --library "$WORK/region/lib/ace-cpp-region.so" --codec "aceapex-open-cpp-region" --version "$ACE_SHA" --corpus "$corpus" --out "$WORK/region/$corpus.ace.cpp.in-process.json"
  python3 "$ROOT/harness/region_latency.py" --mode ace-c99-in-process --regions "$ROOT/regions/$corpus-10000x5000.tsv" --reference "$ROOT/regions/$corpus-10000x5000.sha256.tsv" --archive "$WORK/region/$corpus.ace" --fasta "$fasta" --library "$WORK/region/lib/ace-c99-context.so" --codec "aceapex-open-c99-decoder" --version "$ACE_SHA" --corpus "$corpus" --out "$WORK/region/$corpus.ace.c99.in-process.json"
  python3 "$ROOT/harness/region_latency.py" --mode process --regions "$ROOT/regions/$corpus-10000x5000.tsv" --reference "$ROOT/regions/$corpus-10000x5000.sha256.tsv" --archive "$WORK/region/$corpus.ace" --codec "aceapex-open-cli-faidx" --version "$ACE_SHA" --corpus "$corpus" --command "$WORK/ace/aceapex-xxh3" faidx "{archive}" "{region}" --out "$WORK/region/$corpus.ace.process.json"
  python3 "$ROOT/harness/region_latency.py" --mode bgzf-in-process --regions "$ROOT/regions/$corpus-10000x5000.tsv" --reference "$ROOT/regions/$corpus-10000x5000.sha256.tsv" --archive "$WORK/region/$corpus.fa.bgz" --library "$WORK/region/lib/bgzf-faidx-context.so" --codec bgzip-htslib --version "$(samtools --version | head -1)" --corpus "$corpus" --out "$WORK/region/$corpus.bgzf.in-process.json"
  python3 "$ROOT/harness/region_latency.py" --mode process --regions "$ROOT/regions/$corpus-10000x5000.tsv" --reference "$ROOT/regions/$corpus-10000x5000.sha256.tsv" --archive "$WORK/region/$corpus.fa.bgz" --codec bgzip-samtools --version "$(samtools --version | head -1)" --corpus "$corpus" --command samtools faidx "{archive}" "{region}" --out "$WORK/region/$corpus.bgzf.process.json"
done
python3 "$ROOT/review/new_axes_20261002/render_region.py" "$WORK/region" > "$WORK/region/REPORT.md"
{ uname -a; lscpu; samtools --version; bgzip --version; gcc --version | head -1; } > "$WORK/region/HOST.txt" 2>&1
