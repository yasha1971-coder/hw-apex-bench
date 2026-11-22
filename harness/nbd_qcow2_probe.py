#!/usr/bin/env python3
"""HWAB-NBD-2: region-read cost of compressed qcow2 (zstd, zlib) served by qemu-nbd, the same plan as HWAB-NBD-1
(harness/nbd_xz_probe.py), stdlib + libnbd only.

For every image (`kind:path`, kind = qcow2-zstd, qcow2-zlib, ...) a fresh read-only qemu-nbd is started
(`qemu-nbd -r -f qcow2 -k <socket> <image>`, cache and aio left at their defaults) under /usr/bin/time -v (peak RSS
of the server), and a libnbd client issues 4 KiB reads:

  A  cold: a uniformly chosen cluster that holds data (>= 1 non-zero byte in the raw image; the map is computed from
     the raw image before any read) and is not among the last 8 distinct clusters read, a 4 KiB-aligned read inside;
  C  warm: right after each A read, a second 4 KiB read at another offset in the same cluster.

The granule is the qcow2 cluster (--cluster, default 64 KiB, qemu-img's default). Every answer is compared with the
same bytes of the raw image (SHA-256 of both) - the judge: any mismatch fails the run. NBD overhead: `nbdkit file`
on the raw image with the same plan (--overhead). Output: one JSON per (image, repeat) with per-request latencies (ns)
and a summary; summary.json at the end.
"""
import argparse, json, os, random, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbd_xz_probe import Server, run_series, plan_a_c, pct   # same server wrapper, judge, plan and percentiles


def data_clusters(raw, size, cl):
    zero = bytes(cl); out = []
    with open(raw, "rb") as f:
        for i in range((size + cl - 1) // cl):
            b = f.read(cl)
            if b != zero[:len(b)]: out.append(i)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--image", action="append", required=True, help="kind:path")
    ap.add_argument("--cluster", type=int, default=65536); ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--repeats", type=int, default=5); ap.add_argument("--seed", type=int, default=20261122)
    ap.add_argument("--qemu-nbd", default="qemu-nbd"); ap.add_argument("--nbdkit", default="nbdkit")
    ap.add_argument("--out", required=True); ap.add_argument("--overhead", action="store_true")
    ap.add_argument("--silence", default="", help="command run before every (image, repeat); non-zero exit stops the run")
    a = ap.parse_args()
    import nbd
    os.makedirs(a.out, exist_ok=True)
    size = os.path.getsize(a.raw); cl = a.cluster; clusters = data_clusters(a.raw, size, cl)
    imgs = [(x.split(":", 1)[0], x.split(":", 1)[1]) for x in a.image]
    ver = lambda cmd: subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()[0]
    meta = {"raw": a.raw, "raw_bytes": size, "cluster": cl, "data_clusters": len(clusters), "n": a.n, "repeats": a.repeats,
            "seed": a.seed, "read": 4096, "qemu_nbd": ver([a.qemu_nbd, "--version"]), "nbdkit": ver([a.nbdkit, "--version"]),
            "libnbd": nbd.NBD().get_version(), "images": {k: {"path": p, "bytes": os.path.getsize(p)} for k, p in imgs}}
    json.dump({"clusters": clusters, **meta}, open(os.path.join(a.out, "data_map.json"), "w"))
    raw_f = os.open(a.raw, os.O_RDONLY); summary = {"meta": meta, "rows": {}}; total_bad = 0
    targets = [(k, [a.qemu_nbd, "-r", "-f", "qcow2", "-k", None, p]) for k, p in imgs]
    if a.overhead: targets.append(("file", None))
    for r in range(a.repeats):
        for ti, (key, cmd) in enumerate(targets):
            if a.silence and subprocess.run(a.silence, shell=True).returncode != 0:
                print(f"STOP: silence gate failed before {key} repeat={r}"); sys.exit(3)
            rng = random.Random(a.seed * 1000 + r * 100 + ti)
            plan = plan_a_c(rng, clusters, cl, a.n, size)
            with tempfile.TemporaryDirectory(dir=a.out) as wd:
                if cmd is None: s = Server(a.nbdkit, ["file", a.raw], wd)
                else: s = QemuServer([c if c is not None else os.path.join(wd, "nbd.sock") for c in cmd], wd)
                h = nbd.NBD(); h.connect_unix(s.sock)
                if h.get_size() != size: raise RuntimeError(f"size {h.get_size()} != raw {size}")
                t0 = time.time(); lat, bad = run_series(h, raw_f, plan); wall = time.time() - t0
                h.shutdown(); rss = s.stop()
            total_bad += bad
            row = {"image": key, "repeat": r, "wall_s": wall, "peak_rss_kib": rss, "mismatches": bad,
                   **{f"{k}_p50_ms": pct(v, 0.5) / 1e6 for k, v in lat.items()}, **{f"{k}_p99_ms": pct(v, 0.99) / 1e6 for k, v in lat.items()}}
            json.dump({**row, "lat_ns": lat}, open(os.path.join(a.out, f"{key}_r{r}.json"), "w"))
            summary["rows"].setdefault(key, []).append(row)
            print(f"[{time.strftime('%H:%M:%S')}] {key} r{r}: " + " ".join(f"{k} p50 {pct(v, .5)/1e6:.3f} ms" for k, v in lat.items()) + f", rss {rss} KiB, bad {bad}, {wall:.0f} s", flush=True)
    summary["mismatches"] = total_bad
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print("MISMATCHES", total_bad); sys.exit(0 if total_bad == 0 else 1)


class QemuServer(Server):
    """qemu-nbd in the foreground on a private Unix socket (-k), under /usr/bin/time -v; read-only (-r)"""
    def __init__(self, cmd, workdir):
        self.sock = cmd[cmd.index("-k") + 1]; self.tlog = os.path.join(workdir, "time.log")
        self.p = subprocess.Popen(["/usr/bin/time", "-v", "-o", self.tlog] + cmd, stdout=subprocess.DEVNULL,
                                  stderr=open(os.path.join(workdir, "qemu-nbd.err"), "w"))
        for _ in range(500):
            if os.path.exists(self.sock): break
            if self.p.poll() is not None: raise RuntimeError("qemu-nbd exited: " + open(os.path.join(workdir, "qemu-nbd.err")).read())
            time.sleep(0.01)
        else: raise RuntimeError("qemu-nbd socket did not appear")


if __name__ == "__main__":
    main()
