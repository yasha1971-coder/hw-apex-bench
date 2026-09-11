"""Declared decoder parameters are part of a qualified configuration."""
from contextlib import contextmanager
import os


def parameters(config):
    values=config.get('reader_environment',{})
    if not isinstance(values,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in values.items()):
        raise ValueError('reader_environment must map strings to strings')
    if any(k in {'PATH','GLIBC_TUNABLES'} or k.startswith(('LD_','HB_')) or '=' in k or '\0' in k+v for k,v in values.items()):
        raise ValueError('reader parameters cannot change loader or build state')
    return values


@contextmanager
def scope(config):
    values=parameters(config);previous={k:os.environ.get(k) for k in values}
    os.environ.update(values)
    try: yield
    finally:
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
