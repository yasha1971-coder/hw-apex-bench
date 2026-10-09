"""One isolated native decode. Original target SHA check is deliberately external."""
from pathlib import Path
import sys

from review.axis3 import native_readers as native
from review.axis3.agc_adapter import AgcReader
from review.axis3.bgzf_adapter import BgzfReader
from review.axis3.verdict_data import checked_file, load_json


def decode(root, prepared_path, target):
    root = Path(root).resolve(strict=True)
    prepared = load_json(Path(prepared_path))
    spec = prepared['reader']
    library = checked_file(root, spec['library'])
    family = spec['family']
    aid = prepared['queries'][0]['assembly_id']
    if family == 'refrel3':
        reader = native.Refrel3Reader(library, checked_file(root, spec['reference']), target, aid)
    elif family == 'zstd-seekable':
        reader = native.ResidentOffsetReader(library, target,
                                             checked_file(root, spec['archives'][0]['contig_map']))
    elif family in ('bgzf', 'fasta-faidx'):
        reader = native.BgzfReaderAdapter(BgzfReader(library, target), aid)
    elif family == 'agc':
        reader = native.AgcReaderAdapter(AgcReader(library, target))
    else:
        raise ValueError('unsupported native format')
    try:
        for q in prepared['queries']:
            data = reader.fetch(q['assembly_id'], q['contig_id'], q['start0'], q['end0']).upper()
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    finally:
        getattr(reader, 'inner', reader).close()


if __name__ == '__main__':
    decode(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
