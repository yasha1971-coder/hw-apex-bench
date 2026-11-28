[written by ChatGPT (AI) at the author's request; checked by the author]

# TB-LVL-0: level-name resolution before measurement

The requested `aceapex_fast 1-18` mixes TurboBench selector numbers and the ACE
API level range. At pinned TurboBench4aa97c8, the registered fast selectors are
only1-8, and the wrapper passes selector+10 to ACE. The owner-specified ACE pin
is c53f3a0. The original forecast explicitly names fast13-18, consistent with
the API level names rather than TurboBench selectors.

ChatGPT resolves the executable grid by source inspection: measure all eight
supported `aceapex_fast,1` through `aceapex_fast,8` (API11-18), plus the four
default levels and every other originally requested row. There are50 distinct
configurations and150 main external roundtrips. P2's API13-18 are TurboBench
fast3-8. Names9-18 in the literal fast-selector request are unsupported at this
pin; do not invent aliases, silently clamp levels or change codec sources.

The owner was asked for clarification, but has not answered at this commit.
This is an explicit source-derived interpretation, NOT an owner confirmation.
It replaces the self-imposed global hold in CALIBRATION/PROTOCOL; measurement
may start only after this amendment, its JSON record, and the complete execution
sources are committed. Any later owner steering must remain visible and must
not retroactively change observed results or the original forecasts.

P1 (75%) and P2 (55%), their thresholds and predicates, input, pinned source,
three-round median method, OVH exclusions and hard release time are unchanged.
The calibration's `bro tli4` spelling means the four already named brotli
levels4/6/9/11; it does not add or remove a comparator.

Source: [pinned fast registry and wrapper](https://github.com/powturbo/TurboBench/blob/4aa97c8c37311e399ea3e7782c18c652c5bdb69f/plugin.cc).
The exact selector/API mapping is also recorded in the build registry evidence
and each main row. No performance number had been observed for this task when
this naming resolution was written.
