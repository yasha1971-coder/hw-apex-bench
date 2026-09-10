"""Batch/H_alpha and modelled break-even; later axes intentionally remain deferred."""
import hashlib, json, math, os, pathlib, shlex, statistics, subprocess, sys
from configurations import CODECS, configuration, clean_environment
from access_profiles import SIZES, PROFILES, LENGTH, SEED, traces, entropy

def add_stage2(rows, meta, archives, D, inc, htflags, compile, run):
    root = D.parent
    meta = dict(meta)
    z = D / "zstd"
    for name in ("batch", "breakeven"):
        compile(["gcc", "-O3", "-Wall", "-Wextra", *inc, *htflags, "-c", root / "harness" / (name + ".c"), "-o", D / (name + ".o")])
        compile(["g++", D / (name + ".o"), D / "aceapex_api.o", D / "seek.o", z / "lib/libzstd.a", "-pthread", *htflags, "-o", D / name])
    originals = {"batch_test_ci.c": "5d6b8f86821d8d5eb431a1f9a8aab2e891de14da", "breakeven.c": "32402bd688bd45b5f0caed8f1ee5752f82953ea4"}
    for name, expected in originals.items():
        blob = subprocess.check_output(["git", "hash-object", str(root / "harness/upstream" / name)], text=True).strip()
        if blob != expected: raise RuntimeError("Upstream snapshot hash differs: " + name)
    meta["upstream_harness_blobs"] = originals
    meta["python"] = sys.version
    meta["stage2_protocol"] = {"trace_seed": SEED, "queries": "identical original-file byte ranges across codecs", "batch_repeats": 3,
        "aggregation": "median of 3 wall-clock runs; no best-run selection", "h_alpha": "Shannon entropy of request-start blocks, using each row's block bytes",
        "full_decode_repeats": 5, "full_decode_warmups": 1, "full_decode_purpose": "duration for break-even; not a plateau throughput claim"}
    queries, hot = traces((D / "chr1.fa").stat().st_size)
    td = D / "traces"; td.mkdir(exist_ok=True)
    trace_meta = {}
    for (profile, n), offsets in queries.items():
        text = "".join(f"{x} {LENGTH}\n" for x in offsets)
        p = td / f"{profile}-{n}.ranges"; p.write_text(text)
        trace_meta[profile, n] = {"query_trace_sha256": hashlib.sha256(text.encode()).hexdigest(), "trace_file": str(p), "H_alpha_16k": entropy(offsets, LENGTH)}
    (D / "batch-traces.json").write_text(json.dumps({"seed": SEED, "hot_blocks_16k": hot,
        "traces": [{"profile": p, "n": n, "offsets": q, **trace_meta[p, n]} for (p, n), q in queries.items()]}, separators=(",", ":")) + "\n")
    raw = []
    def execute(codec, args, output_name):
        config = configuration(codec)
        env = clean_environment(os.environ); env.update(config.get("reader_environment", {}))
        prefix = "env " + shlex.join(k + "=" + v for k, v in config.get("reader_environment", {}).items()) + " " if config.get("reader_environment") else ""
        target = D / output_name
        with target.open("w") as f: run(args, stdout=f, env=env)
        samples = [json.loads(s) for s in target.read_text().splitlines()]
        if not samples or not all(s["verified"] for s in samples): raise RuntimeError("Unverified stage2 sample")
        common = dict(meta, codec=codec, configuration=config, commands=[prefix + shlex.join(map(str, args))],
            correctness="pass", sample_sha256={target.name: hashlib.sha256(target.read_bytes()).hexdigest()},
            archive_sha256=next(r["archive_sha256"] for r in rows if r["codec"] == codec and r["metric"] == "ratio"))
        return samples, common

    # Each full decode uses resident input and a preallocated, prefaulted output.
    for codec in CODECS:
        api = configuration(codec)["implementation"]
        args = [D / "breakeven", api, archives[codec], D / "chr1.fa"]
        samples, common = execute(codec, args, "full-" + codec.replace("+", "-") + ".jsonl")
        assert len(samples) == 5 and [s["repeat"] for s in samples] == list(range(5))
        assert all(s["verified_bytes"] == (D / "chr1.fa").stat().st_size for s in samples)
        full = statistics.median(s["wall_ms"] for s in samples)
        assert full > 0
        thread_policy = "8 reconstruction workers; literal workers up to 8; API has no thread argument" if api == "aceapex" else "single decoder thread"
        rows.append(dict(common, metric="full_decode_ms", value=full, unit="ms", status="declared", thread_policy=thread_policy))
        region = next(r for r in rows if r["codec"] == codec and r["metric"] == "region_p50")
        intersection = full / region["value"]
        rows.append(dict(common, metric="break_even_n", value=math.floor(intersection) + 1, unit="requests", status="derived",
            intersection_n=intersection, formula="floor(full_decode_ms / region_p50_ms) + 1", region_p50_ms=region["value"], full_decode_ms=full,
            region_commands=region["commands"], region_sample_sha256=region["sample_sha256"], thread_policy=thread_policy,
            model="Independent reads with constant median cost, no reuse; batch amortization is not this model"))
        raw.append({"codec": codec, "kind": "full_decode", "samples": samples, "commands": common["commands"]})

    threads = min(4, os.cpu_count() or 1)
    for pi, profile in enumerate(PROFILES):
        for ni, n in enumerate(SIZES):
            # Rotate codec order across workloads; paired loop/native order rotates inside C.
            shift = (pi + ni) % len(CODECS)
            for codec in CODECS[shift:] + CODECS[:shift]:
                config = configuration(codec); api = config["implementation"]
                args = [D / "batch", api, archives[codec], D / "chr1.fa", trace_meta[profile, n]["trace_file"], n, threads]
                samples, common = execute(codec, args, f"batch-{codec.replace('+','-')}-{profile}-{n}.jsonl")
                native = api == "aceapex"
                assert len(samples) == (6 if native else 3)
                common.update(access_profile=profile, n=n, requested_bytes=LENGTH, H_alpha=entropy(queries[profile, n], config["block"]),
                    entropy_block_bytes=config["block"], **trace_meta[profile, n])
                for method in (("loop", "batch") if native else ("loop",)):
                    ss = [s for s in samples if s["method"] == method]
                    assert [s["repeat"] for s in ss] == list(range(3))
                    assert all(s["verified_responses"] == n for s in ss)
                    if method == "batch": assert all(s["matches_single_api"] for s in ss)
                    wall = statistics.median(s["wall_ms"] for s in ss)
                    rows.append(dict(common, metric="batch_throughput", method=method, value=n * 1000 / wall, unit="ranges/s", status="declared",
                        wall_ms=wall, threads_requested=threads if method == "batch" else 1,
                        thread_policy="N<512: one worker; otherwise min(requested, nonempty groups)" if method == "batch" else "sequential single API calls",
                        native_batch_available=native, native_batch_reason="supported" if native else "n/a: no native batch API in this adapter"))
                if native:
                    paired = [next(s["wall_ms"] for s in samples if s["repeat"] == r and s["method"] == "loop") /
                              next(s["wall_ms"] for s in samples if s["repeat"] == r and s["method"] == "batch") for r in range(3)]
                    value = statistics.median(paired)
                    rows.append(dict(common, metric="batch_speedup_over_loop", method="batch/loop", value=value, unit="dimensionless",
                        status="pass" if value >= 1 else "fail", predicate=">=1", paired_speedups=paired, threads_requested=threads))
                raw.append({"codec": codec, "kind": "batch", "profile": profile, "n": n, "samples": samples, "commands": common["commands"]})
    batch_rows = [r for r in rows if r["metric"] == "batch_throughput"]
    for r in batch_rows:
        base = next(b for b in batch_rows if b["codec"] == "bgzip+htslib" and b["access_profile"] == r["access_profile"] and b["n"] == r["n"])
        value = r["value"] / base["value"]
        rows.append(dict(r, metric="batch_throughput_relative_to_bgzip", value=value, unit="dimensionless", status="pass" if value >= 1 else "fail",
            predicate=">=1", baseline_codec="bgzip+htslib", baseline_method="loop", baseline_commands=base["commands"]))
    (D / "stage2-raw.json").write_text(json.dumps(raw, separators=(",", ":")) + "\n")
    return rows
