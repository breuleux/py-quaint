
import os
from .parser import parse
from .builders import (
    AddDocumentsMetaNode,
    HTMLMetaNode, MultiMetaNode,
    make_documents, default_engine
    )
from .engine import (
    TemplateMetaNode, HTMLDocument, evaluate, collapse
    )
from . import ast, extensions, builders, engine as mod_engine


__fullhtml_template_text = open(os.path.join(os.path.dirname(__file__),
                                             'default_template.q')).read()

__fullhtml_template = None


def fullhtml_template():
    global __fullhtml_template
    if __fullhtml_template is None:
        __fullhtml_template = parse(__fullhtml_template_text)
    return __fullhtml_template


def get_extension(ext):

    if isinstance(ext, tuple):
        return (get_extension(ext[0])[0], ext[1])

    if not isinstance(ext, str):
        return (ext, None)

    try:
        pack = __import__(ext, fromlist = ["the interface to __import__ is weird"])
        return (getattr(pack, 'quaint_extend'), None)
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


def apply_extensions(engine, extensions):
    for extension in extensions:
        extension, options = get_extension(extension)
        if options is None:
            extension(engine)
        elif isinstance(options, (list, tuple)):
            extension(engine, *options)
        else:
            extension(engine, **options)


def make_source(source):
    if isinstance(source, ast.AST):
        ptree = source
    else:
        ptree = parse(source)
    return ptree

def make_engine(engine, extensions):
    engine = engine or default_engine()
    apply_extensions(engine, extensions)
    return engine


htdocs = ('js', 'css', 'links', 'xlinks', 'sections',
          'meta', 'errors')

def full_html(source, extensions = [], engine = None, template = None):
    files = site([('result', source, template)], extensions, engine)
    return files['result'].data


def site(sources, extensions = [], engine = None):
    nodes = []
    for name, source, template in sources:
        ptree = make_source(source)
        tptree = make_source(template or fullhtml_template())
        node = AddDocumentsMetaNode(HTMLMetaNode(TemplateMetaNode(tptree, ptree)),
                                    *htdocs)
        nodes.append((name, node))
    documents = make_documents('files', 'globalinfo')
    node = MultiMetaNode(('meta', 'sections'), nodes)

    evaluate(node, make_engine(engine, extensions), documents)
    return documents['files'].data

