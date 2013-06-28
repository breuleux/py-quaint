
from . import ast, lib, engine as mod_engine


def default_environment():
    __all__ = ("raw text gen ws_gen"
               "em strong code code_block").split()
    d = {}
    for fname in __all__:
        d[fname] = getattr(lib, fname)
    return d


def test_sequence_of(c, cls = ast.Op):
    c = set(c)
    def test(x):
        if isinstance(x, cls) and set(x.operator) == c:
            return {}
        else:
            return None
    return test


def default_bindings(engine):

    env = engine.environment

    bindings = [

        # Basic AST types
        (ast.Void, 'raw'),
        (ast.Nullary, 'text'),
        (str, 'text'),
        (ast.Op, 'op'),

        # Paragraphs and indent blocks
        (("P", "par"), 'paragraph'),
        (("B", "pars"), 'blocks'),
        (("I", "i"), 'indent'),

        # Brackets
        (('[]', [ast.Void, 'body', ast.Void]), 'bracket'),
        ("{body}", 'eval'),
        ("maybe x <f> maybe y", 'feval'),

        # Emphasis
        ('_ expr', 'em'),
        ('__ expr', 'strong'),

        # Code
        ('maybe lang ` code', 'code'),
        ('maybe lang % code', 'code_block'),

        # Headers
        (test_sequence_of('=', ast.BlockOp), 'header1', "="),
        (test_sequence_of('-', ast.BlockOp), 'header2', "-"),

        # Lists
        ('* item', 'ulist'),
        ('# item', 'olist'),

        # Tables
        ('+ row', 'table_header'),
        ('| row', 'table_row'),

        # Others
        ('name <- body', 'setvar'),

        ]

    for b in bindings:
        if len(b) == 3:
            handler, fn, first_character = b
        else:
            handler, fn = b
            first_character = True
        if isinstance(fn, str):
            fn = env[fn]
        engine.register(handler, fn, first_character)

    return engine


def default_environment():
    env = {}
    for k in dir(lib):
        env[k] = getattr(lib, k)
    return env


def default_engine():
    engine = mod_engine.Engine()
    engine.environment = default_environment()
    default_bindings(engine)
    engine.environment['engine'] = engine
    return engine

