#!/usr/bin/env python3
"""HWAB-NBD-1: region-read cost of nbdkit-xz-filter versus xz block size (stdlib + libnbd only).

For every archive (one per --block-size g, all made from the same raw image) a fresh nbdkit is started
(`nbdkit -f -U <socket> --filter=xz file <archive>`, xz-max-depth left at its default) under /usr/bin/time -v
(peak RSS of the nbdkit process), and a libnbd client issues 4 KiB reads:

  A  cold: a uniformly chosen block that contains data (>= 1 non-zero byte; the list is computed from the raw
     image before any read) and is not among the last 8 distinct blocks read, a 4 KiB-aligned read inside it;
  C  warm: right after each A read, a second 4 KiB read at another offset in the same block (it is cached);
  B  uniform: 4 KiB-aligned offsets uniform over the whole image (no cache control).

Every answer is compared with the same bytes of the raw image (SHA-256 of both) - the judge: any mismatch fails
the run. NBD overhead: `nbdkit file` on the raw image with the same A and B offsets.
Output: one JSON per (g, repeat) with per-request latencies (ns) and a summary; summary.json at the end.
"""
import argparse, hashlib, json, os, random, signal, socket, subprocess, sys, tempfile, time

GRANULE = 1 << 20          # data map granule: 1 MiB (the smallest g of the grid)
READ = 4096
COLD_DEPTH = 8             # nbdkit-xz-filter default xz-max-depth


def data_granules(raw, size):
    """indices of the 1 MiB granules of the raw image that hold at least one non-zero byte"""
    zero = bytes(GRANULE); out = []
    with open(raw, "rb") as f:
        for i in range((size + GRANULE - 1) // GRANULE):
            b = f.read(GRANULE)
            if b != zero[:len(b)]: out.append(i)
    return out


def data_blocks(granules, g):
    per = g // GRANULE
    return sorted({i // per for i in granules})


def pct(xs, q):
    s = sorted(xs); k = (len(s) - 1) * q; lo = int(k); hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


class Server:
    """nbdkit in the foreground on a private Unix socket, under /usr/bin/time -v for its peak RSS"""
    def __init__(self, nbdkit, args, workdir):
        self.sock = os.path.join(workdir, "nbd.sock"); self.tlog = os.path.join(workdir, "time.log")
        for p in (self.sock, self.tlog):
            if os.path.exists(p): os.unlink(p)
        cmd = ["/usr/bin/time", "-v", "-o", self.tlog, nbdkit, "-f", "-U", self.sock] + args
        self.p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(os.path.join(workdir, "nbdkit.err"), "w"))
        for _ in range(500):
            if os.path.exists(self.sock): break
            if self.p.poll() is not None: raise RuntimeError("nbdkit exited: " + open(os.path.join(workdir, "nbdkit.err")).read())
            time.sleep(0.01)
        else: raise RuntimeError("nbdkit socket did not appear")

    def stop(self):
        # SIGTERM to nbdkit (the child of time), then time writes its report
        try:
            kids = subprocess.run(["pgrep", "-P", str(self.p.pid)], capture_output=True, text=True).stdout.split()
            for k in kids: os.kill(int(k), signal.SIGTERM)
        except Exception: pass
        self.p.wait(timeout=60)
        rss = None
        for line in open(self.tlog):
            if "Maximum resident set size" in line: rss = int(line.split(":")[1])   # KiB
        return rss


def run_series(h, raw_f, plan):
    """plan: list of (kind, offset); returns {kind: [ns]} and the number of answer mismatches"""
    lat = {}; bad = 0
    for kind, off in plan:
        t0 = time.perf_counter_ns(); buf = h.pread(READ, off); t1 = time.perf_counter_ns()
        if hashlib.sha256(buf).digest() != hashlib.sha256(os.pread(raw_f, READ, off)).digest(): bad += 1
        lat.setdefault(kind, []).append(t1 - t0)
    return lat, bad


def plan_a_c(rng, blocks, g, n):
    """A cold reads with the warm C read after each; a block among the last COLD_DEPTH distinct blocks is redrawn"""
    plan = []; recent = []; per = g // READ
    for _ in range(n):
        while True:
            b = blocks[rng.randrange(len(blocks))]
            if b not in recent or len(blocks) <= COLD_DEPTH: break
        o1 = rng.randrange(per); o2 = rng.randrange(per - 1); o2 += o2 >= o1
        plan.append(("A", b * g + o1 * READ)); plan.append(("C", b * g + o2 * READ))
        recent.append(b); recent = recent[-COLD_DEPTH:]
    return plan


def plan_b(rng, size, n):
    return [("B", rng.randrange(size // READ) * READ) for _ in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--archive", action="append", required=True, help="g:path (g in MiB)")
    ap.add_argument("--n", type=int, default=1000); ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261121); ap.add_argument("--nbdkit", default="nbdkit")
    ap.add_argument("--out", required=True); ap.add_argument("--series", default="AC,B")
    ap.add_argument("--overhead", action="store_true", help="also nbdkit file on the raw image (NBD overhead)")
    ap.add_argument("--silence", default="", help="command run before every (g, repeat); non-zero exit stops the run")
    a = ap.parse_args()
    import nbd
    os.makedirs(a.out, exist_ok=True)
    size = os.path.getsize(a.raw); granules = data_granules(a.raw, size)
    arch = [(int(x.split(":")[0]), x.split(":", 1)[1]) for x in a.archive]
    meta = {"raw": a.raw, "raw_bytes": size, "granule": GRANULE, "data_granules": len(granules), "n": a.n, "repeats": a.repeats,
            "seed": a.seed, "read": READ, "cold_depth": COLD_DEPTH, "series": a.series, "nbdkit": subprocess.run([a.nbdkit, "--version"], capture_output=True, text=True).stdout.strip(),
            "libnbd": nbd.NBD().get_version(), "archives": {str(g): {"path": p, "bytes": os.path.getsize(p)} for g, p in arch},
            "data_blocks": {str(g): len(data_blocks(granules, g << 20)) for g, _ in arch}}
    json.dump({"granules": granules, **meta}, open(os.path.join(a.out, "data_map.json"), "w"))
    raw_f = os.open(a.raw, os.O_RDONLY); summary = {"meta": meta, "rows": {}}; total_bad = 0
    targets = [(g, ["--filter=xz", "file", p]) for g, p in arch] + ([(0, ["file", a.raw])] if a.overhead else [])
    for r in range(a.repeats):
        for g, args in targets:
            if a.silence and subprocess.run(a.silence, shell=True).returncode != 0:
                print(f"STOP: silence gate failed before g={g} repeat={r}"); sys.exit(3)
            gb = (g or 1) << 20; blocks = data_blocks(granules, gb)
            rng = random.Random(a.seed * 1000 + r * 100 + g)
            plan = []
            if "AC" in a.series: plan += plan_a_c(rng, blocks, gb, a.n)
            if "B" in a.series: plan += plan_b(rng, size, a.n)
            with tempfile.TemporaryDirectory(dir=a.out) as wd:
                s = Server(a.nbdkit, args, wd); h = nbd.NBD(); h.connect_unix(s.sock)
                if h.get_size() != size: raise RuntimeError(f"size {h.get_size()} != raw {size}")
                t0 = time.time(); lat, bad = run_series(h, raw_f, plan); wall = time.time() - t0
                h.shutdown(); rss = s.stop()
            total_bad += bad; key = f"g{g}M" if g else "file"
            row = {"g_mib": g, "repeat": r, "wall_s": wall, "peak_rss_kib": rss, "mismatches": bad,
                   **{f"{k}_p50_ms": pct(v, 0.5) / 1e6 for k, v in lat.items()}, **{f"{k}_p99_ms": pct(v, 0.99) / 1e6 for k, v in lat.items()}}
            json.dump({**row, "lat_ns": lat}, open(os.path.join(a.out, f"{key}_r{r}.json"), "w"))
            summary["rows"].setdefault(key, []).append(row)
            print(f"[{time.strftime('%H:%M:%S')}] {key} r{r}: " + " ".join(f"{k} p50 {pct(v, .5)/1e6:.3f} ms" for k, v in lat.items()) + f", rss {rss} KiB, bad {bad}, {wall:.0f} s", flush=True)
    summary["mismatches"] = total_bad
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print("MISMATCHES", total_bad); sys.exit(0 if total_bad == 0 else 1)


if __name__ == "__main__":
    main()
