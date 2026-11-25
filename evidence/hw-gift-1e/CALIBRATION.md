 P1 On zstd v1.5.4 with the seekable writer as of v1.5.4 (no hint line), enwik8 full,
    256 B frames, level 10: compression is at least 5x slower than the same v1.5.4 writer with
    the PR #3544 hint line applied.
 P2 On zstd v1.5.7 the same pair differs by less than 1.2x (1d observed 0.94x on 16 MiB).
 Kill: P1 fails (v1.5.4 shows < 2x) -> our harness does not reproduce pijul's case; stop and
 report what differs (machine, input, harness), do not draft the "fixed in core" claim.

Method check before main runs: build both tags from source, record `zstd -V` and library
version strings; byte round trip of every archive; same-writer-twice timing differs < 5%.

Runs: tags v1.5.4 and v1.5.7; writer variants A (hint line present) and B (hint line absent)
on each tag; enwik8 full and first 16 MiB; frame sizes 256 B and 1 KiB; level 10 (also level 3
on 256 B only). Under the OVH-BENCH lock, RAM-resident, 5 repeats, interleaved A B A B,
median and min.

Step 4 (only if P1 HIT and P2 HIT): bisect the core library between v1.5.4 and v1.5.7 with the
B writer on the 16 MiB / 256 B / L10 cell; stop at <= 12 builds; report the first fast commit
and its title. If more than 12 builds would be needed, report the narrowed range instead.

Deliver: evidence/hw-gift-1e/RESULTS.md, branch hw-gift-1e, draft PR. Then rewrite
evidence/hw-gift-1d/ZSTD_ISSUE_DRAFT.md as evidence/hw-gift-1e/ZSTD_ISSUE_DRAFT.md: first the
PR #3544 reason and whether it still reproduces (with versions), then the 1d trade-off by
level (L3: size both ways, speed +/-7%; L10: hint 1.3-2.4x slower at 4-256 KiB but 0.8-2.0%
smaller; L19: hint 3-8% faster, up to 0.45% larger), then one question to the maintainers.
Draft only, not sent.
