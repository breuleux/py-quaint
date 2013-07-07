
# from .operparse import Source
from .parser import parse
from .builders import make_documents, default_engine
from .engine import HTMLMetaNode, HTMLDocument, evaluate, collapse
from . import ast, extensions


# def extract_data(p):
#     if ast.is_oper(p, ","):
#         args = collapse(p, ",")
#         return [extract_data(x) for x in args]
#     else:
#         mod = ""
#         while ast.is_oper(p, ".", "_"):
#             mod += source(p.args[0]) + p.operator
#             p = p.args[1]
#         if p
        
        


def get_extension(ext):

    if isinstance(ext, tuple):
        return ext

    if not isinstance(ext, str):
        return ext

    try:
        pack = __import__(ext, fromlist = ["the interface to __import__ is weird"])
        return getattr(pack, 'quaint_ext')
    except ImportError:
        pass

    parts = ext.split(".")
    if len(parts) > 1:
        packname = ".".join(parts[:-1])
        fname = parts[-1]
        try:
            pack = __import__(packname, fromlist = ["the interface to __import__ is weird"])
            return getattr(pack, fname)
        except ImportError:
            pass

    try:
        return getattr(extensions, ext)
    except AttributeError:
        raise Exception("Could not find extension '%s'" % ext)


def full_html(source, extensions = [], engine = None):
    ptree = parse(source)
    main = HTMLDocument()
    documents = make_documents('js', 'css', 'links', 'xlinks', 'sections', 'meta',
                               main = main)
    engine = engine or default_engine()
    for extension in extensions:
        get_extension(extension)(engine, documents)
    evaluate(HTMLMetaNode(ptree), engine, documents)
    return main.data



# Quaint(engine = 'py.q/q/bare',
#        extensions = [blah])



# class Quaint:

#     def __init__(self, extensions = []):
#         self.extensions = []
#         for extension in extensions:
#             if isinstance(extension, str):
#                 pass
#             elif isinstance(extension, dict):
#                 extension = lambda engine, docs: 
#             else:
#                 self.extensions.append(extension)

#     def make(self, docs):
#         pass

#     def __call__(self, docs):
#         return self.make(docs)


# Quaint().make({"test.html": "I am _amazing"})


