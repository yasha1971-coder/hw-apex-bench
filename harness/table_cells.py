"""Missing-value policy shared by generated Markdown reports."""
import re


def unavailable(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("An unavailable value needs a reason")
    reason = reason.strip()
    reason = re.sub(r"^n/a(?:\s*[:—-]\s*|\s+)", "", reason, flags=re.I)
    if not reason.strip() or reason.lower() == 'n/a':
        raise ValueError("An unavailable value needs a substantive reason")
    return "n/a — " + reason.replace("|", "\\|").replace("\n", " ")


def validate_tables(markdown):
    """Reject blanks and unexplained placeholders in table cells, not code."""
    fenced = False
    for number, line in enumerate(markdown.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced or not line.startswith("|"):
            continue
        cells = re.split(r"(?<!\\)\|", line)[1:-1]
        if all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
            continue
        for cell in cells:
            clean = cell.strip().strip("`")
            if clean.lower() in ("", "n/a", "—", "-") or re.fullmatch(r'n/a\s*[:—-]\s*', clean, re.I):
                raise ValueError(f"Unexplained table cell at line {number}: {cell!r}")
