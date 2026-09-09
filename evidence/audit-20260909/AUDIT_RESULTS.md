# Matched-archive ACEAPEX latency audit

Values below are the median of three per-run p50 values (200 queries per run).
Both quantile indices match the upstream libseek definition. No best-run selection.
All measurement subprocesses use the same CPU affinity. All archives passed full byte equality.

| Archive | API build | Harness | Median p50 ms | Min–max p50 ms |
|---|---|---|---:|---:|
| old_src_fse32 | old_O3 | libseek | 0.274000 | 0.272000–0.274000 |
| old_src_fse32 | old_O3 | bench_seq | 0.290460 | 0.289429–0.293926 |
| old_src_fse32 | old_O3 | bench_raw | 0.273966 | 0.271312–0.280415 |
| old_src_fse32 | old_O3 | paper_seq | 0.281708 | 0.277591–0.282869 |
| old_src_fse32 | old_O3 | paper_raw | 0.280966 | 0.275438–0.285774 |
| old_src_fse32 | old_O3 | bench_seq_warm1 | 0.285322 | 0.283520–0.288087 |
| old_src_fse32 | old_O2 | libseek | 0.285000 | 0.285000–0.291000 |
| old_src_fse32 | old_O2 | bench_seq | 0.281387 | 0.279374–0.281747 |
| old_src_fse32 | old_O2 | bench_raw | 0.271272 | 0.265263–0.272564 |
| old_src_fse32 | old_O2 | paper_seq | 0.281917 | 0.279113–0.285353 |
| old_src_fse32 | old_O2 | paper_raw | 0.268208 | 0.267766–0.269058 |
| old_src_fse32 | old_O2 | bench_seq_warm1 | 0.284672 | 0.283370–0.286304 |
| old_src_fse4 | old_O3 | libseek | 0.181000 | 0.179000–0.183000 |
| old_src_fse4 | old_O3 | bench_seq | 0.194559 | 0.193526–0.198494 |
| old_src_fse4 | old_O3 | bench_raw | 0.171684 | 0.169481–0.173887 |
| old_src_fse4 | old_O3 | paper_seq | 0.165885 | 0.165726–0.167799 |
| old_src_fse4 | old_O3 | paper_raw | 0.166217 | 0.164864–0.166567 |
| old_src_fse4 | old_O3 | bench_seq_warm1 | 0.195951 | 0.194488–0.196401 |
| old_src_fse4 | old_O2 | libseek | 0.195000 | 0.192000–0.196000 |
| old_src_fse4 | old_O2 | bench_seq | 0.181128 | 0.181038–0.182430 |
| old_src_fse4 | old_O2 | bench_raw | 0.172716 | 0.169631–0.173708 |
| old_src_fse4 | old_O2 | paper_seq | 0.165155 | 0.164684–0.166277 |
| old_src_fse4 | old_O2 | paper_raw | 0.152906 | 0.152145–0.153838 |
| old_src_fse4 | old_O2 | bench_seq_warm1 | 0.194628 | 0.193838–0.196842 |
| old_depth_fse4 | old_O3 | libseek | 0.180000 | 0.180000–0.186000 |
| old_depth_fse4 | old_O3 | bench_seq | 0.195480 | 0.193687–0.197523 |
| old_depth_fse4 | old_O3 | bench_raw | 0.173677 | 0.173037–0.174037 |
| old_depth_fse4 | old_O3 | paper_seq | 0.167278 | 0.164965–0.169791 |
| old_depth_fse4 | old_O3 | paper_raw | 0.168620 | 0.163833–0.169150 |
| old_depth_fse4 | old_O3 | bench_seq_warm1 | 0.196251 | 0.193757–0.197973 |
| old_depth_fse4 | old_O2 | libseek | 0.195000 | 0.193000–0.196000 |
| old_depth_fse4 | old_O2 | bench_seq | 0.183351 | 0.181649–0.183853 |
| old_depth_fse4 | old_O2 | bench_raw | 0.172746 | 0.170783–0.175120 |
| old_depth_fse4 | old_O2 | paper_seq | 0.166847 | 0.165656–0.167248 |
| old_depth_fse4 | old_O2 | paper_raw | 0.153978 | 0.152626–0.154168 |
| old_depth_fse4 | old_O2 | bench_seq_warm1 | 0.194589 | 0.193206–0.200447 |
| current_depth_fse4 | current_O2 | libseek | 0.154000 | 0.152000–0.156000 |
| current_depth_fse4 | current_O2 | paper_raw | 0.153988 | 0.153678–0.155019 |
| current_depth_fse4 | current_O2 | bench_seq | 0.185915 | 0.183712–0.186115 |

## Original reproduction script

Exit code: 1. A nonzero exit can include unrelated historical claims; inspect the complete log.

  declared lowlat_region_p50_ms       0.151

Archive SHA-256 digests, commands, raw verified samples and versions are in audit-results.json and audit-metadata.json.
No unqualified cross-codec performance conclusion is restored by this audit automatically.
