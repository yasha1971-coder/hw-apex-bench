#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path

REGION_LEN = 5000
COUNT = 10000
SEED = 20261002

def read_fasta(path):
    seqs = {}
    name = None
    parts = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="ascii", newline=None) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    seqs[name] = "".join(parts).upper().encode("ascii")
                name = line[1:].split()[0]
                if name in seqs:
                    raise SystemExit("duplicate FASTA contig: " + name)
                parts = []
            else:
                if name is None:
                    raise SystemExit("sequence before FASTA header")
                parts.append(line)
    if name is not None:
        seqs[name] = "".join(parts).upper().encode("ascii")
    if not seqs:
        raise SystemExit("empty FASTA")
    return seqs

def make_regions(seqs, corpus, outdir):
    eligible = [(name, seq) for name, seq in seqs.items() if len(seq) >= REGION_LEN]
    total_starts = sum(len(seq) - REGION_LEN + 1 for _, seq in eligible)
    if total_starts <= 0:
        raise SystemExit("no eligible contigs")
    rng = random.Random(SEED)
    rows = []
    hashes = []
    cumulative = []
    acc = 0
    for name, seq in eligible:
        acc += len(seq) - REGION_LEN + 1
        cumulative.append((acc, name, seq))
    for i in range(COUNT):
        pick = rng.randrange(total_starts)
        prev = 0
        for limit, name, seq in cumulative:
            if pick < limit:
                start0 = pick - prev
                start1 = start0 + 1
                end1 = start1 + REGION_LEN - 1
                region = seq[start0:start0 + REGION_LEN]
                rows.append((name, start1, end1))
                hashes.append(hashlib.sha256(region).hexdigest())
                break
            prev = limit
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{corpus}-10000x5000.tsv"
    sha = outdir / f"{corpus}-10000x5000.sha256.tsv"
    header = [
        f"# seed={SEED}",
        "# prng=python-random-MT19937",
        f"# count={COUNT}",
        f"# region_length={REGION_LEN}",
        "# coordinates=1-based-inclusive",
        "# sampling=uniform-over-all-valid-start-positions-across-eligible-contigs",
        "contig\tstart\tend",
    ]
    tsv.write_text("\n".join(header) + "\n" + "\n".join(f"{a}\t{b}\t{c}" for a,b,c in rows) + "\n")
    sha_header = [
        f"# seed={SEED}",
        "# digest=sha256(uppercase FASTA bases, line breaks removed)",
        "index\tcontig\tstart\tend\tsha256",
    ]
    sha.write_text("\n".join(sha_header) + "\n" + "\n".join(
        f"{i}\t{a}\t{b}\t{c}\t{h}" for i, ((a,b,c),h) in enumerate(zip(rows, hashes))
    ) + "\n")
    return tsv, sha

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fasta", type=Path, required=True)
    ap.add_argument("--corpus", choices=("chr1","t2t"), required=True)
    ap.add_argument("--outdir", type=Path, default=Path("regions"))
    args = ap.parse_args()
    seqs = read_fasta(args.fasta)
    tsv, sha = make_regions(seqs, args.corpus, args.outdir)
    print(json.dumps({
        "regions": str(tsv),
        "regions_sha256": hashlib.sha256(tsv.read_bytes()).hexdigest(),
        "reference": str(sha),
        "reference_sha256": hashlib.sha256(sha.read_bytes()).hexdigest(),
    }, sort_keys=True))

if __name__ == "__main__":
    main()
