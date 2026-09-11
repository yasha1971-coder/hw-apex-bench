"""Keep verbose provenance JSON outside Markdown without losing its exact bytes."""
import hashlib,json,re
from pathlib import Path
DETAILS=Path(__file__).resolve().parents[1]/'docs/RESULTS/details'
PATTERN=re.compile(r'```json\n(.*?)\n```',re.S)

def externalize(text,write=False):
    def replace(match):
        raw=(match.group(1)+'\n').encode()
        json.loads(raw)
        name=hashlib.sha256(raw).hexdigest()+'.json'
        if write:
            DETAILS.mkdir(parents=True,exist_ok=True)
            (DETAILS/name).write_bytes(raw)
        return '[Provenance JSON](details/'+name+')'
    return PATTERN.sub(replace,text)

def restore(text):
    def replace(match):
        name=match.group(1)
        raw=(DETAILS/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()+'.json'!=name:
            raise ValueError('Provenance excerpt digest mismatch')
        return '```json\n'+raw.decode()[:-1]+'\n```'
    return re.sub(r'\[Provenance JSON\]\(details/([0-9a-f]{64}\.json)\)',replace,text)
