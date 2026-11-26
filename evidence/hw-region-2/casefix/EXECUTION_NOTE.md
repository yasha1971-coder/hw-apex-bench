[written by ChatGPT (AI) at the author's request; checked by the author]

# Pre-timing execution clarification

An OVH retry unit is one worker pass. Each A/A pair consists of two separately
load-admitted fresh-process passes, with the same fixed 12+1000 coordinates.
Each pass has at most three load-only attempts; the pair is judged once both
first-CLEAN passes exist. A clean A/A failure is never retried. Thus the full
experiment has 12 accepted A/A passes, four boundary passes and 186 main passes.
This clarifies the logical A/A-pair wording in PROTOCOL.md; thresholds, query
work, coordinates, predictions and the already committed controller are unchanged.

This note is committed before the first timed call. Untimed equivalence admission
continues using the unchanged frozen build/source cohort.
