
from . import ast, lib, document, engine as mod_engine


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


bare_bindings = [
    # MetaNodes
    (mod_engine.MetaNode, lambda engine, node: node(engine)),
    
    # Basic AST types
    (ast.Void, 'text'),
    (ast.Nullary, 'text'),
    (str, 'text'),
    (ast.Op, 'op'),

    # Paragraphs and indent blocks
    (("P", "par"), 'paragraph'),
    (("B", "pars"), 'blocks'),
    (("I", "i"), 'indent'),

    # Brackets
    # The outermost brackets are shed by create_pattern
    # so the following will match [body]
    ("[[body]]", 'bracket'),

    # Juxtaposition
    ((('', None, None), 'x'), 'juxt'),
    ]


default_bindings = bare_bindings + [

    # Brackets
    # The outermost brackets are shed by create_pattern
    # so the following will match [body]
    ("{body}", 'eval'),
    ("{f}: x", 'feval'),

    # Emphasis
    ('_ expr', 'em'),
    ('__ expr', 'strong'),

    # Links
    ('text :: maybe shed1 link', 'link'),
    ('maybe text :: type : maybe shed1 link', 'special_link'),
    ('?label :: maybe shed1 link', 'regqlink'),
    ('text ::? maybe shed1 link', 'qlink'),
    ('text :: ?link', 'qlink'),
    ('text ::= maybe link', 'elink'),

    # Code
    ('maybe lang ` shed1 code', 'code'),
    ('maybe lang % code', 'code_block'),

    # Headers
    (test_sequence_of('=', ast.BlockOp), 'header1', "="),
    (test_sequence_of('-', ast.BlockOp), 'header2', "-"),
    ('wide [= title]', 'header1'),
    ('wide [== title]', 'header2'),
    ('wide [=== title]', 'header3'),
    ('wide [==== title]', 'header4'),
    ('wide [===== title]', 'header5'),
    ('wide [====== title]', 'header6'),

    # Lists
    ('wide [* item]', 'ulist'),
    ('wide [maybe start # item]', 'olist'),
    ('wide [. # item]', 'olist'),
    ('wide [term := definition]', 'dlist'),

    # Tables
    ('wide [+ row]', 'table_header'),
    ('wide [| row]', 'table_row'),

    # Others
    ('cond ?? yes', 'ifthenelse'),
    ('cond ?? yes !! no', 'ifthenelse'),
    ('maybe tag .. maybe body', 'domnode'),
    ('wide [maybe source >> quote]', 'quote'),
    ('maybe left ;; right', 'ignore'),
    ('name <- shed1 body', 'setvar'),
    ('name <= shed1 file', 'load_in_var'),
    ('name <= [maybe type] :: file', 'load_in_var'),

    ]

def apply_bindings(bindings, engine):
    env = engine.environment
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



def bare_environment():
    safe = """text op paragraph blocks indent bracket juxt""".split()
    env = {}
    for k in safe:
        env[k] = getattr(lib, k)
    return env

def bare_engine(error_handler = mod_engine.inline_error_handler,
                bindings = bare_bindings):
    engine = mod_engine.Engine(error_handler)
    engine.environment = bare_environment()
    apply_bindings(bindings, engine)
    return engine




def default_environment():
    env = {}
    for k in dir(lib):
        env[k] = getattr(lib, k)
    return env

def default_engine(error_handler = mod_engine.inline_error_handler,
                   bindings = default_bindings):
    engine = mod_engine.Engine(error_handler)
    engine.environment = default_environment()
    apply_bindings(bindings, engine)
    engine.environment['engine'] = engine
    return engine



def q_environment():
    safe = """raw text op juxt
paragraph blocks indent
bracket parens
em strong
link special_link anchor
code code_block
header1 header2 header3 header4 header5 header6
ulist olist dlist
table_header table_row
domnode quote ignore setvar load_in_var ifthenelse
toc
meta html css json yaml show_args include
insert_document
""".split()

    env = {}
    for k in safe:
        env[k] = getattr(lib, k)
    env['eval'] = lib.safe_eval
    env['feval'] = lib.safe_feval
    return env

def q_engine(error_handler = mod_engine.inline_error_handler,
             bindings = default_bindings):
    engine = mod_engine.Engine(error_handler)
    engine.environment = q_environment()
    apply_bindings(bindings, engine)
    engine.environment['engine'] = engine
    return engine




class AddDocumentsMetaNode(mod_engine.MetaNode):
    def process(self, engine, node, *docnames):
        return AddDocuments(engine(node), *docnames)


class AddDocuments(mod_engine.Generator):

    def __init__(self, gen, *docnames):
        self.docnames = docnames
        self.gen = gen

    def docmaps(self, current):
        current = document.complete_documents(current, *self.docnames)
        results = [(current, self, self.deps(), self.generators())]
        results += self.gen.docmaps(current)
        return results


class HTMLMetaNode(mod_engine.MetaNode):
    def process(self, engine, node):
        return engine(node)




def strip_ext(path):
    if path.endswith('.py.q'):
        return path[:-5]
    elif path.endswith('.q'):
        return path[:-2]
    else:
        return path

class MultiMetaNode(mod_engine.MetaNode):
    def process(self, engine, docs, nodes):
        return MultiDocumentGenerator(
            docs,
            [(name, engine(node))
             for name, node in nodes])

class MultiDocumentGenerator(mod_engine.Generator):

    def __init__(self, docnames, gens):
        self.docnames = set(docnames)
        self.gens = [(strip_ext(name), name, gen)
                     for name, gen in gens]

    def docmaps(self, current):
        mydocs = dict(current)
        rval = [(mydocs, self, self.deps(), self.generators())]
        for name, realname, gen in self.gens:
            subdocs = dict(current)
            subdocs.update(document.make_documents('html', *self.docnames))
            if 'meta' in self.docnames:
                subdocs['meta']['realpath'] = realname
                subdocs['meta']['path'] = name
            rval += gen.docmaps(subdocs)
            for docname, doc in subdocs.items():
                mydocs['_' + docname + '_' + name] = doc
        return rval

    def deps(self):
        return {'globalinfo': {'_' + docname + '_' + name
                               for docname in self.docnames
                               for name, _, _ in self.gens},
                'files': {'_html_' + name for name, _, _ in self.gens}}

    def generate_globalinfo(self, docs):
        dest = docs['globalinfo']
        for name, realname, gen in self.gens:
            dest[name] = {}
            for docname in self.docnames:
                dest[name][docname] = docs['_' + docname + '_' + name]

    def generate_files(self, docs):
        dest = docs['files']
        for name, realname, gen in self.gens:
            dest[name] = docs['_html_' + name]

