#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ORDER=[4096,8192,16384,32768,65280]
p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
rows=[]
for g in ORDER:
    r=json.loads((a.root/f"g{g}"/"result.json").read_text()); assert r["g"]==g
    ace=r["totals"]["aceapex"]; bg=r["totals"]["bgzip"]
    rows.append({
        "g":g,
        "ace_ratio":ace["ratio"],"bgzf_ratio":bg["ratio"],
        "ace_p50_ms":ace["p50_ms"],"bgzf_p50_ms":bg["p50_ms"],
        "density_gain_pct":r["density_gain_pct"],
        "latency_penalty_pct":r["latency_penalty_pct"],
        "equal_percent_margin_pct":r["density_gain_pct"]-r["latency_penalty_pct"],
        "bit_perfect":r["bit_perfect_archives"]==60,
        "samples_per_codec":ace["samples"]
    })
(a.out/"curve.json").write_text(json.dumps({"schema":"matched-g-curve-v1","rows":rows},indent=2)+"\n")
lines=[
"# ACEAPEX vs BGZF — exact matched-g legal corridor",
"",
"Same 30 frozen T2T 2 MiB windows; same resident 16 KiB region trace; three passes; full byte-perfect restore before timing.",
"",
"| g | ACE ratio | BGZF ratio | ACE p50 ms | BGZF p50 ms | density gain | latency penalty | equal-% margin |",
"|---:|---:|---:|---:|---:|---:|---:|---:|"
]
for r in rows:
    lines.append(f'| {r["g"]} | {r["ace_ratio"]:.6f} | {r["bgzf_ratio"]:.6f} | {r["ace_p50_ms"]:.6f} | {r["bgzf_p50_ms"]:.6f} | {r["density_gain_pct"]:+.2f}% | {r["latency_penalty_pct"]:+.2f}% | {r["equal_percent_margin_pct"]:+.2f} pp |')
lines += [
"",
"**Boundary:** no BGZF point above 65,280 uncompressed bytes is part of this compatible corridor.",
"",
"equal-% margin is only a diagnostic that subtracts relative latency penalty from relative density gain with equal percentage weight. It is not a universal application utility function.",
]
(a.out/"curve.md").write_text("\n".join(lines)+"\n")
print((a.out/"curve.md").read_text())
