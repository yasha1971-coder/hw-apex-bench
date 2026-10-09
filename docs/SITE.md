# v0.2.0 evidence-derived static site

## Build contract

Run from the applied benchmark clone:

```sh
set -euo pipefail
python3 -m tools.build_site RELEASE_DIRECTORY --out site --manifest-sha256 EXTERNAL_MANIFEST_SHA256
```

The canonical A9 filename is `leaderboard.json`, lowercase. The complete release
must pass `release_v020.verify`, including all axis verifiers, SHA anchors,
companions, metadata and regenerated tables. Existing/overlapping output, changed
input, invented values, a bad manifest or missing file/fragment refuses without
returning a partial site. An external manifest SHA guards against a subsequent
consistent rewrite; hashes alone do not authenticate authorship.

Overview, axis/methodology pages, individual row pages and downloads are included.
Each row shows all original evidence fields as escaped JSON, source SHA, associated
files and verify/reproduction commands. Scientific FAIL remains visible. Unknown
machine IDs remain separate and absent values are Not recorded, never zero.
The exact release bytes and all dependencies are under `downloads/release`.
Native libraries are hashed only, never loaded; no new measurements are run.

All relative links in `metadata/METHODOLOGY.md` must identify metadata artifacts
with their original repository-relative layout. A minimal A9 release may omit
linked code/schema files: it correctly refuses until these unchanged files are
added to `release-input-v1.artifacts` and the release is rebuilt. A10
`site_synthetic.prepare` adds this link closure without editing source files,
amending evidence or relaxing A9 verification. Its Axis 3 is the explicitly
synthetic unit-contract fixture; Axis 4/5 are preserved native A6/A7 evidence.
For this historical synthetic input, RUN.md comes from the SHA-pinned A9
snapshot in the golden fixture, not from a server-overlaid working runbook.
The generic site builder still uses the exact methodology/link artifacts supplied
by its release. No current server file is overwritten or attributed retrospectively.

Raw Markdown HTML is escaped. Unsafe schemes, external image/style/script loads
and active HTML/JS/SVG artifacts refuse. No recorded input command is executed.
URLs are relative, supporting offline viewing and GitHub repository subpaths.
The downloaded manifest is exact: verify the complete `downloads/release` tree,
not a manifest downloaded alone. Keep the full site artifact for reproduction.

## Accessibility and determinism

Tables have captions and row/column header scopes, with labelled keyboard-focusable
overflow regions. Pages have language, title, navigation, landmarks, skip links
and visible focus. PASS/FAIL are text, not color-only indications. Text/background
color pairs are tested for WCAG AA contrast in light and dark palettes; the dark
theme uses `prefers-color-scheme`. CSS is local; no JS, CDN or browser library is
required. Optional sorting is intentionally omitted; stable source order works
without scripting.

Numeric cells use A8 exact decimal formatting, source SHA and canonical row IDs;
the checker compares displayed values against verified rows and rejects unbound
numbers. Methodology definitions/criteria are hash-bound document text, not
measurement values. Row-page names hash canonical fields. Build time, host path,
runtime Git HEAD and platform font snapshots are not added. `SITE_SHA256SUMS`
covers every site file except itself; its SHA identifies the complete byte tree.
Repeated and relocated inputs must match the committed synthetic golden tree.

Python prerequisites are pinned: jsonschema 4.26.0, PyYAML 6.0.3, html5lib 1.1,
Markdown 3.8.2. Installation is a separate prerequisite step; generation,
acceptance and browsing are offline. Error-free HTML5 parsing does not claim
complete browser or WCAG certification.

## pages.yml permission review

| Scope | Permission/condition | Reason |
|---|---|---|
| workflow | permissions `{}` | No inherited authority |
| build | contents: read only | Checkout, no deployment authority in PR |
| checkout | pinned SHA; persist-credentials: false | No retained Git credential |
| prerequisites | pinned versions | Installed before offline generation |
| synthetic build | release verify, golden, HTML/link checks | No benchmark execution |
| upload-artifact | pinned SHA; include-hidden-files: true | Complete PR/main hashes including .zenodo.json/.nojekyll; only generated site-acceptance, not checkout or credentials |
| upload-pages-artifact | main ref and not pull_request | No deployable PR artifact |
| deploy | main ref and not pull_request; needs build | workflow_dispatch also restricted to main |
| deploy permissions | pages: write; id-token: write only | Deployment/OIDC, no contents/statuses write |
| environment | github-pages | Repository environment protections apply |
| removed steps | configure-pages, status POST, legacy numeric greps | No setting mutation or obsolete row assertions |

This replaces the Pages root with an explicitly labelled synthetic v0.2.0 site.
Official ace-core results are not silently substituted. Historical data,
`web/build.py` and the separate publication-integrity workflow remain unchanged.
Pages must already use GitHub Actions; this patch does not enable it or alter
repository settings. Local acceptance performs no push or deployment.

Protected `review/axis3/build_agc_v324.sh`, `.github/workflows/axis3-agc.yml` and
the entire `review/axis3/RUN.md` are never edited. RUN.md is only copied unchanged
as a hash-bound methodology-link artifact. Server overlays remain outside A10.
