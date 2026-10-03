#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--references",required=True);ap.add_argument("--answers",required=True);ap.add_argument("--result",required=True);a=ap.parse_args()
 refs=[x.split("\t")[-1] for x in Path(a.references).read_text().splitlines() if x and not x.startswith("#") and not x.startswith("index")]
 ans=[x.strip() for x in Path(a.answers).read_text().splitlines() if x.strip()]
 ok=len(refs)==len(ans)
 bad=[]
 if ok:
  for i,(want,seqhex) in enumerate(zip(refs,ans)):
   try: seq=bytes.fromhex(seqhex)
   except ValueError: bad.append(i);continue
   if hashlib.sha256(seq.upper()).hexdigest()!=want: bad.append(i)
 ok=ok and not bad
 r={"status":"PASS" if ok else "FAILED","expected":len(refs),"received":len(ans),"mismatches":bad[:20]}
 Path(a.result).write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r))
 raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
