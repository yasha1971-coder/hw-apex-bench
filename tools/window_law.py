#!/usr/bin/env python3
"""Frozen Axis-3 window-law diagnostic. No benchmark execution occurs here."""
from __future__ import annotations
import argparse,json,math,sys
from fractions import Fraction
from pathlib import Path
TOLERANCE_PERCENT=20
VERDICT_WINDOWS={1024,8192,65536}

def num(v,n):
    if isinstance(v,bool): raise ValueError(f'{n}: finite positive number required')
    try:r=Fraction(str(v))
    except Exception as e: raise ValueError(f'{n}: finite positive number required') from e
    if r<=0: raise ValueError(f'{n}: must be > 0')
    return r

def diagnose(dq_bps,w_bytes,q_bytes,measured_p50_us,probe_w1_p50_us):
    d=num(dq_bps,'D_Q_Bps'); w=num(w_bytes,'W_bytes'); q=num(q_bytes,'Q_bytes')
    m=num(measured_p50_us,'measured_p50_us'); probe=num(probe_w1_p50_us,'probe_w1_p50_us')
    if w.denominator!=1 or not 1 <= w <= 65536: raise ValueError('W must be an integer byte count in 1..65536')
    c0=probe-q*1_000_000/d
    a=(w+q-1)*1_000_000/d
    b=c0+a
    if b<=0: err=None
    else: err=100*(m-b)/b
    model_fail=c0<0
    eligible = int(w) in VERDICT_WINDOWS
    role = 'VERDICT' if eligible else ('CALIBRATION_ONLY' if w == 1 else 'DIAGNOSTIC_ONLY')
    verdict = ('FAIL' if model_fail or err is None or abs(err)>TOLERANCE_PERCENT else 'PASS') if eligible else role
    out={'schema':'window-law-diagnostic-v2','D_Q_Bps':float(d),'W_bytes':int(w),'Q_bytes':float(q),
         'probe_w1_p50_us':float(probe),'c0_us':float(c0),'primary_model':'c0+(W+Q-1)/D_Q',
         'primary_predicted_p50_us':float(b),'primary_signed_error_percent':None if err is None else float(err),
         'secondary_model':'(W+Q-1)/D_Q','secondary_predicted_p50_us':float(a),
         'tolerance_percent':TOLERANCE_PERCENT,'verdict':verdict,'coefficient_fitting':False,
         'c0_negative':model_fail,'w1_in_verdict_set':False,
         'model_status':'FAIL' if model_fail else 'VALID',
         'window_role':role,'verdict_eligible':eligible}
    if any(isinstance(v,float) and not math.isfinite(v) for v in out.values()): raise ValueError('non-finite output')
    return out

def process_record(row):
    if row.get('scope','cpu-in-process')!='cpu-in-process' or row.get('threads',1)!=1: raise ValueError('one-thread CPU in-process only')
    r=diagnose(*(row[k] for k in ('D_Q_Bps','W_bytes','Q_bytes','measured_p50_us','probe_w1_p50_us')))
    for k in ('format','corpus','run_id','scope','threads','evidence_sha256','protocol_sha256','seed'):
        if k in row:r[k]=row[k]
    return r

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--dq-bps');p.add_argument('--window',type=int);p.add_argument('--q');p.add_argument('--measured-p50-us');p.add_argument('--probe-w1-p50-us')
    a=p.parse_args(argv)
    try:
        if a.input:
            rows=[process_record(json.loads(x)) for x in a.input.read_text().splitlines() if x.strip()]
        else:
            vals=(a.dq_bps,a.window,a.q,a.measured_p50_us,a.probe_w1_p50_us)
            if any(v is None for v in vals):p.error('provide all scalar parameters')
            rows=[diagnose(*vals)]
        for r in rows: print(json.dumps(r,sort_keys=True,allow_nan=False))
    except (ValueError,KeyError,OSError) as e:p.exit(2,f'WINDOW_LAW_ERROR: {e}\n')
    return 0 if all(r['model_status'] != 'FAIL' and
                    (not r['verdict_eligible'] or r['verdict'] == 'PASS') for r in rows) else 1
if __name__=='__main__':sys.exit(main())
