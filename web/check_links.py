"""Check current reader-facing Markdown paths; frozen historical receipts stay untouched."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
count=0
for p in [ROOT/'README.md',ROOT/'CONTRIBUTING.md',*sorted((ROOT/'docs').rglob('*.md'))]:
    if p.name=='HISTORY.md':
        continue  # chronological commands and paths describe prior commits
    for target in re.findall(r'\]\(([^\s)]+)\)',p.read_text()):
        if re.match(r'(?:[a-z]+:|#|/)',target):continue
        path=(p.parent/target.split('#')[0]).resolve()
        if not path.is_relative_to(ROOT) or not path.exists():
            raise ValueError(f'Broken local link: {p.relative_to(ROOT)} -> {target}')
        count+=1
print(f'Checked {count} current local Markdown links')
