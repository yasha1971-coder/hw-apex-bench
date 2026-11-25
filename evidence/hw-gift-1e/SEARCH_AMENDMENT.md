# Pre-build source-ancestry amendment

The original ancestry gate rejected plan-001 before reservation, checkout, build,
selfcheck or candidate timing. v1.5.4 (945f2775) is not an ancestor of e2965edd;
their merge base is 515266e31b2369f82594d47ff4666f0612382bb7. The named init-once
changes are on a side branch that later enters v1.5.7. Treating that branch as a
direct descendant of the release tag was an incorrect Git-history assumption.
Retain the rejected plan and record it as a pre-build rejection, not a failed
build or timing attempt. Only the two tag core builds have occurred.

Before any candidate build or timing, permit the absence of v1.5.4 ancestry ONLY
for the three already preregistered source-informed SHAs e2965edd, 9420bce8 and
91f4c23e (full SHAs in the amendment receipt). Each must still be an ancestor of
v1.5.7. All other candidates retain the original tag-ancestry requirement. The
fixed order, S1 forecast, full-grid P1/P2/Kill outcomes, total twelve-build limit,
FAST/SLOW classifier, input, bridge, writer, decoder, compiler, timing boundary,
five paired rounds and load-only retake policy are unchanged.

The full tag grid and fresh prefix endpoint data remain valid and are not
remeasured. Their original code snapshots, admissions, classifier and raw
receipts are retained. A new committed candidate admission maps the original
code hashes to the amended admission/path-policy code. Untouched sampler,
worker, round, native-interface and classifier function AST hashes must agree
between snapshots and current code. Only admission/ancestry checks and result
qualification change; there are no candidate timing observations to influence
this correction.

The next plan is plan-002 for the same e2965edd candidate, following a committed
step-001 rejection receipt. If an adjacent SLOW/FAST pair is observed, report a
measured first-parent transition on this source branch, its exact title, whether
it lies on the tag ancestry path, and whether the fast child enters v1.5.7. Do
not describe a side-branch edge as a direct v1.5.4-to-v1.5.7 bisect boundary or
as a globally earliest fast commit. This amendment changes the interpretation
of the search path, not the previously observed version comparison.
