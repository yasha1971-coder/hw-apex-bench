# HW-GIFT-1b — BLOCKED: load

No performance medians or prediction outcome are reported while the experiment is incomplete.

Each blocked logical repeat exhausted exactly three total LOADED attempts. Every attempt used the shared blocking OVH-BENCH lock; at least one boundary's exact one-minute load average exceeded 1.0. A fourth attempt is prohibited. The first CLEAN result of a logical repeat is retained without remeasurement.

|reader|checkpoint|started M|retaken N|LOADED attempts|planned repeats|blocked frame B|read B|repeat|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|c|[enwik8-L3](blocked/c-enwik8-L3/BLOCKED.json)|46|1|3|60|16777216|65536|0|

1 of 46 started logical repeats were retaken. This counts logical repeats with at least two attempts, including a blocked repeat; it does not imply that they reached CLEAN. The two earlier whole-trial rejections (110 attempts) remain excluded and are not included in these new-trial counters.

## c / enwik8-L3 — last LOADED ps top 8

```text
    PID USER     %CPU COMMAND
3102557 aeterna   1.5 2.1.284
2310730 aeterna   1.4 2.1.284
3039745 root      1.3 sshd
 805134 aeterna   0.7 2.1.284
4181850 ubuntu    0.7 2.1.314
2171726 aeterna   0.4 2.1.284
3038845 ubuntu    0.3 python
```
