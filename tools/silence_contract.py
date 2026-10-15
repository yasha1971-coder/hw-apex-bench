"""Pure preflight decision function; gathering real ace-core telemetry is separate.

Thresholds are explicit: one-minute load strictly below 0.5; available data-disk
space strictly above 20,000,000,000 bytes. Foreign CPU activity must be reported
from two process CPU-tick samples, not guessed from process names.
"""
DISK_MIN_BYTES=20000000000
LOAD_MAX=0.5
FOREIGN_HEAVY_CPU_PERCENT=10.0


def judge(snapshot):
    reasons=[]
    if snapshot['host']!='ace-core':reasons.append('wrong host')
    if not snapshot['load1']<LOAD_MAX:reasons.append('load1 is not below 0.5')
    if not snapshot['disk_available_bytes']>DISK_MIN_BYTES:reasons.append('insufficient available data-disk space')
    if snapshot['sampling_seconds']<1:reasons.append('CPU sample interval too short')
    if any(p['cpu_percent']>=FOREIGN_HEAVY_CPU_PERCENT and not p['own_process'] for p in snapshot['processes']):
        reasons.append('foreign heavy CPU process')
    return {'status':'PASS' if not reasons else 'FAILED','reasons':reasons,'snapshot':snapshot,
            'thresholds':dict(load1_strictly_below=LOAD_MAX,disk_strictly_above_bytes=DISK_MIN_BYTES,
                              foreign_cpu_percent_at_least=FOREIGN_HEAVY_CPU_PERCENT)}
