
from . import engine as mod_engine, lib


def default_environment():
    __all__ = ("raw text gen ws_gen"
               "em strong code code_block").split()
    d = {}
    for fname in __all__:
        d[fname] = getattr(lib, fname)
    return d
        

def default_bindings(env):
    engine = mod_engine.Engine()

    bindings = [('void v _ em', 'em'),
                ('void v __ em', 'strong'),
                ('maybe lang ` code', 'code'),
                ('maybe lang % code', 'code_block')]

    for handler, fn in bindings:
        if isinstance(fn, str):
            fn = env[fn]
        engine.register(handler, fn)

    return engine

