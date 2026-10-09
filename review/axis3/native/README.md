# S2 native shims

These are reader primitives only. They do not launch processes and do not time work.
`refrel3_reader.cpp` must be compiled with the frozen upstream refrel3 include tree.
`openzl_reader.c` must be linked to the same OpenZL 0.3.0 static dependency set as
`build_openzl_v030.sh`. `lz4_indexed.c` is accepted only with an ace-core build
receipt proving LZ4 v1.10.0; this repository intentionally does not invent an
upstream commit SHA absent from the retained evidence.
