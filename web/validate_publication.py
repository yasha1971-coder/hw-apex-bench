"""Verify committed evidence and regenerate reports before publishing a snapshot."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))


def reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_jsonl(data):
    """Strict UTF-8 JSONL; never repair, skip, or replace corrupt evidence."""
    lines = data.decode("utf-8").splitlines()
    if not lines:
        raise ValueError("Empty results.jsonl")
    rows = []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line, parse_constant=reject_constant,
                             object_pairs_hook=unique_object)
            if not isinstance(row, dict):
                raise ValueError("Expected a measurement object")
        except ValueError as error:
            raise ValueError(f"results.jsonl line {number}: {error}") from error
        rows.append(row)
    return rows


def verify_files(root, files):
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Manifest path escapes repository: {name}")
        data = path.read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ValueError(f"Publication integrity mismatch: {name}")


def validate(root=ROOT):
    from report import render
    from stage2_report import render_stage2

    manifest = json.loads((root / "evidence/published-results.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "cabench-publication-v1":
        raise ValueError("Unknown publication manifest schema")
    for required in ("results.jsonl", "README.md", "docs/BATCH_RESULTS.md"):
        if required not in manifest["files"]:
            raise ValueError(f"Missing publication digest: {required}")
    verify_files(root, manifest["files"])
    rows = load_jsonl((root / "results.jsonl").read_bytes())
    if len(rows) != manifest["result_records"]:
        raise ValueError("Publication record count mismatch")
    if sorted({row["run_id"] for row in rows}) != manifest["run_ids"]:
        raise ValueError("Publication run identity mismatch")
    # Existing validators enforce codec configuration, byte-restore evidence,
    # same-run comparisons, equal-worker batches and plateau qualification.
    for name, generated in (("README.md", render(rows)),
                            ("docs/BATCH_RESULTS.md", render_stage2(rows)[1])):
        if (root / name).read_bytes() != generated.encode("utf-8"):
            raise ValueError(f"Committed {name} differs from results.jsonl")
    from table_cells import validate_tables
    for name in ('README.md', 'docs/BATCH_RESULTS.md'):
        validate_tables((root / name).read_text(encoding='utf-8'))
    if 'docs/AXES_RESULTS.md' in manifest['files']:
        from axes import render_coverage
        if (root / 'docs/AXES_RESULTS.md').read_text(encoding='utf-8') != render_coverage(rows):
            raise ValueError('Committed docs/AXES_RESULTS.md differs from results.jsonl')
    if 'docs/CG_CURVE_RESULTS.md' in manifest['files']:
        from cg_curve import render as render_cg
        curve = [r for r in rows if r.get('evidence_group') == 'cg-five-point-v1']
        if (root / 'docs/CG_CURVE_RESULTS.md').read_text(encoding='utf-8') != render_cg(curve):
            raise ValueError('Committed curve report differs from results.jsonl')
        validate_tables((root / 'docs/CG_CURVE_RESULTS.md').read_text(encoding='utf-8'))
    return rows


if __name__ == "__main__":
    checked = validate()
    print(f"Publication verified: {len(checked)} JSONL records; digests and reports match")
