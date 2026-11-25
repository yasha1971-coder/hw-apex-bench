# One optional paired speed observation

This stage is conditional in the original HW-GIFT-1c task. It characterizes the
storage/speed tradeoff of the already-proven one-line policy change; it does not
alter H1/H2, select a patch, or rerun HW-GIFT-1b latency measurements. Commit this
file and timing.py before any clocked operation. All eight size/byte cases and
the exact minimal proof must already be complete.

- Case chosen by the original task's principal anomaly: complete enwik8,
  level 3, 256 KiB frames, seek-table checksums enabled in both variants.
- Compare the original contrib writer with the private copy changing only
  `ZSTD_c_srcSizeHint` from maxFrameSize to zero. Same clean pinned zstd 1.5.7
  static library, compiler/options, native bridge and native decoder. Load both
  libraries locally with symbol binding kept inside each library.
- Before timing, an untimed selfcheck must reproduce both verified full-archive
  SHA/byte counts and restore the source exactly. Its code path reads no clock.
- One paired observation: original compression, patched compression, original
  full decompression, patched full decompression, in that fixed order. One
  observation per operation, no warmups or timing-dependent repetition. Encoder
  input/output call boundaries follow the original example's read hints and
  CStream input/output buffer sizes; API loops execute in the native bridge.
- CPU 0, one thread, ace-core. Input, compressed buffers and restored buffers
  reside in RAM. Allocate and prefault caller buffers, create/init fresh codec
  contexts and parse seek tables outside each inner timer. Lazy allocations
  performed inside codec calls remain inside. Hashes, return codes and complete
  byte comparisons are checked outside each inner timer.
- Each interval uses time.perf_counter_ns around exactly one native call: four
  intervals and eight clock reads per pair. No subprocess or file I/O is in an
  inner interval. No throughput/plateau, distribution or p99 claim follows from
  one pair. Report elapsed ns and the paired direction as one observation only.
- Use the existing blocking `flock /run/lock/ovh-bench.lock` helper, never a
  separate/nonblocking bypass. Retain literal date -u, /proc/loadavg and nproc
  at both pair boundaries, raw /proc/stat and other-core deltas. Only exact
  load1 > 2.0 at either boundary yields LOADED. CPU utilization is observational.
- Preserve every attempt. A LOADED pair alone is immediately retaken identically,
  at most three total attempts; the first CLEAN wins. Three LOADED attempts stop
  speed characterization as BLOCKED: load. Nonzero native/byte-check errors are
  fatal and are not load retries. Builds and the untimed selfcheck never hold
  the shared timing lock.

There is no speed PASS threshold or speed-based change to the causal verdict.
Report any observed compression/decompression cost, and distinguish it from
the proven density/byte equivalence and observed context/window memory sizes.
One pair cannot establish a general speed ranking. No additional measurements
or tuning are authorized by this stage.
