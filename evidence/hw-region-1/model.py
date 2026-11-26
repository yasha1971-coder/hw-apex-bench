"""Exact saved-data NNLS and additive model; no native calls or clocks."""
from fractions import Fraction


def require(ok, message):
    if not ok:
        raise ValueError(message)


def nearest(values, percentile):
    require(len(values)==1000 and percentile in (50,99), 'fixed 1000-request quantile required')
    return sorted(values)[499 if percentile==50 else 989]


def fit(points):
    """Four positive integer (decoded bytes, median ns) points only."""
    require(len(points)==4 and [p[0] for p in points]==[4096,16384,65536,262144], 'wrong calibration sizes/order')
    require(all(type(x) is int and type(y) is int and x>0 and y>0 for x,y in points), 'invalid calibration point')
    n = len(points)
    sx,sy = sum(x for x,y in points),sum(y for x,y in points)
    sxx,sxy = sum(x*x for x,y in points),sum(x*y for x,y in points)
    slope = Fraction(n*sxy-sx*sy,n*sxx-sx*sx)
    intercept = (Fraction(sy)-slope*sx)/n
    candidates = [(Fraction(0),Fraction(sxy,sxx)),(Fraction(sy,n),Fraction(0)),(Fraction(0),Fraction(0))]
    if slope>=0 and intercept>=0:
        candidates.append((intercept,slope))
    def score(pair):
        a,b = pair
        return sum((a+b*x-y)**2 for x,y in points)
    a,b = min(candidates,key=lambda pair:(score(pair),pair[0],pair[1]))
    return dict(schema='hw-region-1-model-fit-v1',method='nonnegative exact least squares; four standalone zstd medians only',
        c_call_ns=str(a),c_byte_ns=str(b),squared_error_ns2=str(score((a,b))),
        points=[dict(decoded_bytes=x,observed_median_ns=y,predicted_ns=str(a+b*x),residual_ns=str(Fraction(y)-a-b*x)) for x,y in points])


def predict(coefficients, timed_rows, counter_rows):
    require(len(timed_rows)==len(counter_rows)==1000, 'one complete trace required')
    a,b = Fraction(coefficients['c_call_ns']),Fraction(coefficients['c_byte_ns'])
    require(a>=0 and b>=0, 'negative NNLS coefficient')
    values,latencies = [],[]
    for index,(timed,counted) in enumerate(zip(timed_rows,counter_rows)):
        require(timed['query']==counted['query']==index and timed['offset']==counted['offset'], 'trace/counter identity mismatch')
        k,d,t = counted['zstd_calls'],counted['zstd_bytes'],timed['elapsed_ns']
        require(type(k) is int and k>=0 and type(d) is int and d>=0 and type(t) is int and t>0, 'invalid observed model input')
        values.append((a*k+b*d,index,k,d))
        latencies.append(t)
    prediction,query,k,d = sorted(values,key=lambda item:(item[0],item[1]))[499]
    observed = nearest(latencies,50)
    calls,byte_term = a*k,b*d
    residual = Fraction(observed)-prediction
    return dict(schema='hw-region-1-model-cell-v1',observed_p50_ns=observed,
        predicted_p50_ns=str(prediction),representative_query=query,representative_zstd_calls=k,
        representative_zstd_output_bytes=d,calls_term_ns=str(calls),bytes_term_ns=str(byte_term),
        residual_ns=str(residual),calls_share=str(calls/observed),bytes_share=str(byte_term/observed),
        residual_share=str(residual/observed),relative_error=str(abs(prediction-observed)/observed),
        within_twenty_percent=5*abs(prediction-observed)<=observed,
        calls_at_least_half=2*calls>=observed)


def primary_verdict(ace_p50, zstd_p50):
    require(type(ace_p50) is int and type(zstd_p50) is int and min(ace_p50,zstd_p50)>0, 'missing primary medians')
    ratio = Fraction(ace_p50,zstd_p50)
    return dict(schema='hw-region-1-primary-v1',ACE_p50_ns=ace_p50,zstd_p50_ns=zstd_p50,ratio=str(ratio),
        P1=dict(passed=Fraction(7,5)<=ratio<=Fraction(11,5),verdict='HIT' if Fraction(7,5)<=ratio<=Fraction(11,5) else 'MISS'),
        Kill=dict(triggered=ratio<Fraction(11,10)),outcome='a' if ratio<=Fraction(11,10) else 'b')
