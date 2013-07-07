
# from .operparse import Source
from .parser import parse
from .builders import make_documents, default_engine
from .engine import HTMLMetaNode, HTMLDocument, evaluate, collapse
from . import ast, extensions



def get_extension(ext):

    if isinstance(ext, tuple):
        return ext

    if not isinstance(ext, str):
        return (ext, None)

    try:
        pack = __import__(ext, fromlist = ["the interface to __import__ is weird"])
        return (getattr(pack, 'quaint_ext'), None)
    except ImportError:
        pass

    parts = ext.split(".")
    if len(parts) > 1:
        packname = ".".join(parts[:-1])
        fname = parts[-1]
        try:
            pack = __import__(packname, fromlist = ["the interface to __import__ is weird"])
            return (getattr(pack, fname), None)
        except ImportError:
            pass

    try:
        return (getattr(extensions, ext), None)
    except AttributeError:
        raise Exception("Could not find extension '%s'" % ext)


def full_html(source, extensions = [], engine = None):
    ptree = parse(source)
    documents = make_documents('html', 'js', 'css', 'links', 'xlinks', 'sections', 'meta')
    engine = engine or default_engine()
    for extension in extensions:
        extension, options = get_extension(extension)
        options = options or {}
        extension(engine, documents, **options)
    evaluate(HTMLMetaNode(ptree), engine, documents)
    return documents['html'].data



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


