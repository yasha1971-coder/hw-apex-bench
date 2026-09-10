"""Deterministic shared raw-byte traces. No codec-specific trace selection."""
import bisect, collections, math
SIZES = (100, 600, 2000, 5000)
PROFILES = ("uniform", "sorted", "clustered", "hot-set", "zipf1.2")
LENGTH = 16384
SEED = 20260910
class RNG:
    def __init__(self, seed): self.state = seed
    def next(self):
        mask = (1 << 64) - 1
        self.state = (self.state + 0x9E3779B97F4A7C15) & mask
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
        return z ^ (z >> 31)
    def below(self, n):
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            x = self.next()
            if x < limit: return x % n
    def uniform(self): return (self.next() >> 11) / float(1 << 53)

def traces(size):
    end = size - LENGTH
    if end < 1024 * 1024: raise ValueError("Corpus too small for these profiles")
    count = max(SIZES)
    r = RNG(SEED)
    uniform = [r.below(end + 1) for _ in range(count)]
    blocks = end // LENGTH + 1
    hot_rng = RNG(SEED + 1)
    hot = []
    while len(hot) < 64:
        b = hot_rng.below(blocks)
        if b not in hot: hot.append(b)
    hotset = []
    for _ in range(count):
        off = hot[hot_rng.below(64)] * LENGTH
        hotset.append(off + hot_rng.below(min(LENGTH, end - off + 1)))
    cluster_rng = RNG(SEED + 2)
    clustered = []
    for i in range(count):
        if i % 32 == 0: anchor = cluster_rng.below(end - 1048576 + 1)
        clustered.append(anchor + cluster_rng.below(1048576))
    weights = [(i + 1) ** -1.2 for i in range(blocks)]
    total = math.fsum(weights); cumulative = []; c = 0.0
    for w in weights:
        c += w / total; cumulative.append(c)
    cumulative[-1] = 1.0
    zipf_rng = RNG(SEED + 3)
    zipf = []
    for _ in range(count):
        b = bisect.bisect_right(cumulative, zipf_rng.uniform())
        off = b * LENGTH
        zipf.append(off + zipf_rng.below(min(LENGTH, end - off + 1)))
    arrays = {"uniform": uniform, "clustered": clustered, "hot-set": hotset, "zipf1.2": zipf}
    result = {(name, n): (sorted(uniform[:n]) if name == "sorted" else arrays[name][:n])
              for name in PROFILES for n in SIZES}
    assert len(set(hot)) == 64
    assert all(0 <= x <= end for q in result.values() for x in q)
    assert all(sorted(result["uniform", n]) == result["sorted", n] for n in SIZES)
    assert set(x // LENGTH for x in hotset) <= set(hot)
    return result, hot

def entropy(offsets, block):
    counts = collections.Counter(x // block for x in offsets)
    n = len(offsets)
    return -math.fsum((c / n) * math.log2(c / n) for c in counts.values())
