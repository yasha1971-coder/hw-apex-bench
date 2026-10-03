#!/usr/bin/env python3
import argparse,csv
from pathlib import Path
def predict_us(window,q,dq): return 1e6*(window+q-1)/dq
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--output",required=True);a=ap.parse_args();rows=[]
 with open(a.input,newline="") as fh:
  for r in csv.DictReader(fh,delimiter="\t"):
   q=float(r["Q"]);dq=float(r["D_Q_Bps"]);w=float(r["W"]);m=float(r["measured_p50_us"]);p=predict_us(w,q,dq);e=(m-p)/p*100;rows.append((r,p,e))
 out=["# Window-law diagnostic","", "R ~= D_Q/(W+Q-1); predicted p50 = (W+Q-1)/D_Q. D_Q is one-thread full-decode throughput; Q is mean uncompressed independently decoded block/granule.","","| format | corpus | scope | W | Q B | D_Q B/s | predicted p50 us | measured p50 us | error % |","|---|---|---|---:|---:|---:|---:|---:|---:|"]
 for r,p,e in rows: out.append(f"| {r['format']} | {r['corpus']} | {r['scope']} | {r['W']} | {float(r['Q']):.3f} | {float(r['D_Q_Bps']):.3f} | {p:.3f} | {float(r['measured_p50_us']):.3f} | {e:.2f} |")
 Path(a.output).write_text("\n".join(out)+"\n")
if __name__=="__main__":main()
