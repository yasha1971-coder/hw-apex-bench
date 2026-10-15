#!/usr/bin/env python3
"""Protocol v1.1 c0 and D_Q helpers; caller supplies persistent reader and clock."""
import statistics,time
from tools.axis3_window_engine import run_windows

def run_c0_probe(reader,requests,*,clock=time.perf_counter_ns):
 return run_windows(reader,requests,expected_count=10000,calibration=True,clock=clock)
def run_dq(reader,canonical_bytes,*,clock=time.perf_counter_ns):
 if reader.scope!='cpu-in-process' or reader.decoder_threads!=1: raise ValueError('one-thread in-process reader required')
 t0=clock();out=reader.decode_sequence();t1=clock()
 if t1<=t0 or type(out) is not bytes or len(out)!=canonical_bytes: raise ValueError('D_Q decode/domain mismatch')
 return {'canonical_bytes':canonical_bytes,'elapsed_ns':t1-t0,'D_Q_bytes_per_second':canonical_bytes*1e9/(t1-t0),'timed_boundary':'native full decode only; normalization/SHA outside'}
def compute_c0(probe_p50_us,D_Q,Q):
 c0=probe_p50_us/1e6-Q/D_Q
 return {'c0_seconds':c0,'status':'PASS' if c0>=0 else 'FAIL'}
