#!/bin/bash
# HWAB-ZEEK-1b main run: one machine, silence gate before each corpus run
P=/tmp/hwref/z1/pick1.sh; M=/tmp/hwref/z1/main
G=64K,256K,1M,2M,4M,8M,16M
bash $P silesia.tar $M/default/silesia.tar
bash $P enwik8 $M/default/enwik8
for c in silesia.tar enwik8 t2t_chrX.fa; do bash $P $c $M/r4K/$c --g $G --region-size 4K; done
for c in silesia.tar enwik8 t2t_chrX.fa; do bash $P $c $M/r64K/$c --g $G --region-size 64K; done
echo ALLDONE
