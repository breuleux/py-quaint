
import os
import cgi
import urllib.request
import inspect
from . import ast, parser, engine as mod_engine
from .parser import parse
from .document import (
    HTMLDocument, TextDocument, execute_documents
    )
from .util import (
    format_anchor,
    dedent,
    )
from .ast import (
    collapse,
    source,
    source_nows,
    )
from .engine import (
    codehl,
    Generator,
    Raw, Text, Markup,
    TransGen, GenFor, GenFrom,
    List, Definitions, Table, TableHeader,
    Gen,
    Section,
    Paragraph,
    AutoMerge,
    TOCGenerator,
    )
pyeval = eval

import csv
import json as pyjson
try:
    import yaml as pyyaml
except ImportError:
    pyyaml = None


def wrap_whitespace(f):
    def f2(engine, node, *args, **kwargs):
        result = f(engine, node, *args, **kwargs)
        rval = Gen(Text(node.whitespace_left),
                   result,
                   Text(node.whitespace_right))
        if hasattr(result, 'block'):
            rval.block = result.block
        return rval
    f2.__name__ = f.__name__
    return f2

class FromArg:
    def __init__(self, argname, f = None):
        self.argname = argname
        self.f = f


def make_tags(tag, attributes, engine, args):
    opening_tag = "<" + tag
    for attr, value in attributes.items():
        if attr == 'classes': attr = 'class'
        if isinstance(value, (list, set, tuple)):
            value = " ".join(value)
        elif isinstance(value, FromArg):
            argname, f = value.argname, value.f
            value = args[argname]
            if f:
                value = f(engine, value)
            else:
                value = value.raw()
        if value:
            opening_tag += ' %s="%s"' % (attr, value)
    opening_tag += ">"
    return Markup(opening_tag), Markup("</%s>" % tag)


def parts_wrapper(w0, *wrappers):

    if isinstance(w0, tuple):
        if w0[0] is True:
            backwards = True
            argnames = w0[1:]
        else:
            backwards = False
            argnames = w0
    else:
        argnames = None
        wrappers = (w0,) + wrappers

    @wrap_whitespace
    def wrap(engine, node, *args, **kwargs):

        if args and argnames is not None:
            if backwards:
                for arg, name in zip(reversed(args), reversed(argnames)):
                    kwargs[name] = arg
            else:
                for arg, name in zip(args, argnames):
                    kwargs[name] = arg

        gens = []
        for w in wrappers:
            w = dict(w)
            arg = w.pop('arg')
            tag = w.pop('tag', 'span')
            otag, ctag = make_tags(tag, w, engine, kwargs)
            if arg == '_':
                gens = [Gen(otag, Gen(*gens), ctag)]
            else:
                if arg.endswith('?'):
                    arg = arg[:-1]
                    if arg not in kwargs:
                        continue
                    target = kwargs[arg]
                    if isinstance(target, ast.Void):
                        continue
                if arg.endswith('?!'):
                    target = kwargs.get(arg[:-2], ast.Void())
                else:
                    target = kwargs[arg]
                gens.append(Gen(otag, engine(target), ctag))
        if len(gens) == 1:
            return gens[0]
        else:
            return Gen(*gens)

    return wrap


def wrapper(tag = "span", **attributes):
    return parts_wrapper(
        (True, 'other', 'expr'),
        dict(arg = "other?"),
        dict(arg = "expr",
             tag = tag,
             **attributes))



def text(engine, node):
    if isinstance(node, ast.AST):
        node = node.whitespace_left + node.raw() + node.whitespace_right
    return Text(node)

def raw(engine, node):
    if isinstance(node, ast.AST):
        node = node.whitespace_left + node.raw() + node.whitespace_right
    return Raw(node)


@wrap_whitespace
def op(engine, node, **_):
    args = [engine(node.args[0])]
    if isinstance(node.operator, str):
        oper = [node.operator] * (len(node.args) - 1)
    else:
        oper = node.operator
    for token, op in zip(node.args[1:], oper):
        args.append(Text(op))
        args.append(engine(token))
    return Gen(*args)

@wrap_whitespace
def rawop(engine, node, **_):
    args = [engine(node.args[0])]
    if isinstance(node.operator, str):
        oper = [node.operator] * (len(node.args) - 1)
    else:
        oper = node.operator
    for token, op in zip(node.args[1:], oper):
        args.append(Raw(op))
        args.append(engine(token))
    return Gen(*args)



def indent(engine, node, i):
    contents = i.args
    return Gen(*map(engine, contents))

def paragraph(engine, node, par):
    contents = [engine(x) for x in par.args]
    # contents = [x if hasattr(x, 'merge') else Paragraph([x], True)
    #             for x in contents]
    return AutoMerge(contents)

def blocks(engine, node, pars):
    contents = [engine(x) for x in pars.args]
    # The first argument is not wrapped in <p> because otherwise line 1
    # and line 2 in the following example will be separate paragraphs:
    # * line 1
    #   line 2
    #
    #   line 3
    # There might be better ways to resolve that idiosyncracy.
    contents = contents[:1] + [x if (hasattr(x, 'merge')
                                     or (hasattr(x, 'block')
                                         and x.block))
                               else Paragraph([x])
                               for x in contents[1:]]
    return AutoMerge(contents)

@wrap_whitespace
def bracket(engine, node, body):
    return engine(body)

@wrap_whitespace
def parens(engine, node, body):
    return Gen("(", engine(body), ")")


em = wrapper("em")

strong = wrapper("strong")

quote = parts_wrapper(('source', 'quote'),
                      dict(arg = 'source?',
                           tag = 'div',
                           classes = 'source'),
                      dict(arg = 'quote',
                           tag = 'blockquote'),
                      dict(arg = '_',
                           tag = 'div',
                           classes = 'quote'))


def plain_or_code(engine, node):
    if ast.is_curly_bracket(node):
        return str(pyeval(node.args[1].raw(), engine.environment))
    elif ast.is_square_bracket(node):
        return node.args[1].raw()
    else:
        return node.raw()


def parse_link(link):
    if '/' in link or '.' in link:
        return Text(link)
    else:
        def get(links):
            return links.get(format_anchor(link), link)
        return GenFrom('links', get)


link_handlers = {}

def link_type(type):
    def wrap(f):
        link_handlers[type] = f
        def newf(engine, node, text, link):
            return special_link(engine, node, text, ast.quaintstr(type), link)
        return newf
    return wrap

@link_type('image')
def image_link(engine, node, text, link):
    return {'tag': 'img',
            'src': plain_or_code(engine, link),
            'alt': text.raw()}

@wrap_whitespace
def special_link(engine, node, text, type, link):
    if isinstance(link, ast.Void):
        link = text
    if isinstance(text, ast.Void):
        text = link
    f = link_handlers[type.raw().lower()]
    descr = f(engine, node, text, link)
    body = descr.pop('body', None)
    if body is None:
        body = engine(text)
    otag, ctag = make_tags(descr.pop('tag', 'a'), descr, engine, {})
    return Gen(otag, body, ctag)

@wrap_whitespace
def link(engine, node, text, link = None):
    if link is None or isinstance(link, ast.Void):
        link = text
    return Gen(Markup('<a href="'),
               parse_link(plain_or_code(engine, link)),
               Markup('">'),
               engine(text),
               Markup('</a>'))

@wrap_whitespace
def anchor(engine, node, text, label):
    label = label.raw()
    return Gen(GenFor('links', label, '#' + label),
               Markup('<span id="{label}">'.format(label = label)),
               engine(text),
               Markup('</span>'))



def extract_and_codehl(lang, code, do_dedent = True, unescape_brackets = False):

    if ast.is_square_bracket(code):
        wsl, code, wsr = code.args

    if isinstance(lang, ast.Void):
        lang = "text"
    else:
        lang = source(lang).strip().lower()

    code = source(code)
    if do_dedent:
        code = dedent(code)

    if unescape_brackets:
        code = code.replace(r'\[', '[').replace(r'\]', ']')
        code = code.replace(r'\{', '{').replace(r'\}', '}')

    return codehl(lang, code)


@wrap_whitespace
def ignore(engine, node, left, right = None):
    if right is None:
        return Raw("")
    else:
        return Gen(engine(left), Raw(""))


@wrap_whitespace
def code(engine, node, lang, code):
    # inline code snippets
    code = extract_and_codehl(lang, code, False, True)
    return Gen(Markup('<span class="code code_inline"><code>'),
               # Note: pygments' HTMLFormatter puts a line break at
               # the end of the generated code. That line break
               # produces whitespace we might not want, so we remove
               # it.
               Raw(code[:-1] if code.endswith("\n") else code),
               Markup('</code></span>'))

def code_block(engine, node, lang, code):
    # blocks of code
    return Gen(Markup('<div class="code code_block"><pre>'),
               Raw(extract_and_codehl(lang, code, True, False)),
               Markup('</pre></div>'))

def show_and_run(engine, node, code):
    return Gen(Markup('<div class="quaintio"><div class="quaintin"><span>'),
               code_block(engine, node, "quaint", code),
               Markup('</span></div><div class="quaintout"><span>'),
               engine(code),
               Markup('</span></div></div>'))

def show_as_and_run(lang):
    def f(engine, node, code):
        return Gen(code_block(engine, node, lang, code),
                   engine(code))
    return f



def header_n(n):
    @wrap_whitespace
    def header(engine, node, title = None):
        if title is None:
            title, _ = node.args
        anchor = format_anchor(format_text(engine, title).strip())
        title = format_html(engine, title)
        return Gen(GenFor('links', anchor, '#'+anchor),
                   Markup('<h%s id="' % n),
                   Markup(anchor),
                   Markup('">'),
                   Section(anchor, Raw(title), n),
                   Markup("</h%s>" % n))
    return header

header1 = header_n(1)
header2 = header_n(2)
header3 = header_n(3)
header4 = header_n(4)
header5 = header_n(5)
header6 = header_n(6)

toc = TOCGenerator()


def table_row(engine, node, row):
    return Table(map(engine, collapse(row, '|')))

def table_header(engine, node, row):
    return Table(TableHeader(*map(engine, collapse(row, '+'))))

def ulist(engine, node, item):
    return List(engine(item))

def olist(engine, node, start = None, item = None):
    if start is None or ast.is_void(start):
        start = True
    else:
        start = source_nows(start)
    return List(engine(item), ordered = start)

def dlist(engine, node, term, definition):
    return Definitions((engine(term), engine(definition)))


@wrap_whitespace
def safe_eval(engine, node, body):
    var = source_nows(body)
    x = engine.environment[var]
    if isinstance(x, (ast.ASTNode, ast.quaintstr)):
        x = engine(x)
    elif not isinstance(x, Generator):
        x = Text(str(x))
    return x

@wrap_whitespace
def safe_feval(engine, node, f, x):
    var = source_nows(f)
    f = engine.environment[var]
    return f(engine, node, x)


@wrap_whitespace
def eval(engine, node, body):

    code = dedent(source(body))

    try:
        x = pyeval(code, engine.environment)
    except SyntaxError:
        exec(code, engine.environment)
        x = Raw("")
    else:
        if isinstance(x, (ast.ASTNode, ast.quaintstr)):
            x = engine(x)
        elif not isinstance(x, Generator):
            x = Text(str(x))

    return x


@wrap_whitespace
def feval(engine, node, f, x):
    code = dedent(source(f))
    f = pyeval(code, engine.environment)
    return f(engine, node, x)


def extract_props(node, results):

    if isinstance(node, str):
        results['tag'] = node

    elif ast.is_oper(node, ''):
        for arg in node.args:
            extract_props(arg, results)

    elif ast.is_oper(node, '.'):
        assert(ast.is_void(node.args[0]))
        assert(isinstance(node.args[1], str) or ast.is_oper(node.args[1], '_', '-'))
        results['class'].add(source_nows(node.args[1]))

    elif ast.is_oper(node, '#'):
        assert(ast.is_void(node.args[0]))
        assert(isinstance(node.args[1], str) or ast.is_oper(node.args[1], '_', '-'))
        results['id'] = source_nows(node.args[1])

    elif ast.is_oper(node, '='):
        results[source_nows(node.args[0])] = source_nows(node.args[1])

    elif ast.is_square_bracket(node):
        extract_props(node.args[1], results)

    elif ast.is_void(node):
        results['tag'] = 'div'

    else:
        raise Exception("Unknown directive", node)

    return results


@wrap_whitespace
def domnode(engine, node, tag, body):
    props = extract_props(tag, {'tag': 'div', 'class': set()})
    tagname = props.pop('tag')
    otag, ctag = make_tags(tagname, props, engine, [])
    result = Gen(otag, engine(body), ctag)
    if 'id' in props:
        result = Gen(GenFor('links', props['id'], '#'+props['id']), result)
    if tagname != 'span':
        result.block = True
    return result
    



def css(engine, node, x):
    return GenFor('css', x.raw())

def js(engine, node, x):
    return GenFor('js', x.raw())

def html(engine, node, code):
    if ast.is_square_bracket(code):
        code = code.args[1]
    return Raw(code.raw())

def setvar(engine, node, name, body):
    name = name.raw()
    engine.environment[name] = body
    return Raw("")


load_handlers = {}

def load_type(type):
    def wrap(f):
        load_handlers[type] = f
        return f
    return wrap

def urlload(url, engine):
    if isinstance(url, ast.InlineOp) and url.operator in ['://', ':']:
        file = source_nows(url)
    else:
        file = 'file:' + engine.expand_path(source_nows(url))
    return urllib.request.urlopen(file).read().decode('utf-8')

@load_type('yaml')
def load_yaml(engine, node, file):
    if not pyyaml:
        raise ImportError("yaml is not installed!")
    results = pyyaml.safe_load(urlload(file, engine))
    return results

@load_type('json')
def load_json(engine, node, file):
    results = pyjson.loads(urlload(file, engine))
    return results

@load_type('csv')
def load_csv(engine, node, file):
    results = list(csv.reader(urlload(file, engine).split('\n'), skipinitialspace = True))
    return results


def load_in_var(engine, node, name, file, type = None):
    if type is None or isinstance(type, ast.Void):
        type = source_nows(file).split(".")[-1]
    results = load_handlers[type](engine, node, file)
    engine.environment[source_nows(name)] = results
    return Raw("")


def import_data(engine, data):
    if not isinstance(data, dict):
        raise Exception("the data should be a dictionary")
    for k, v in data.items():
        engine.environment[k] = v


def yaml(engine, node, expr):
    if not pyyaml:
        raise ImportError("yaml is not installed!")
    results = pyyaml.safe_load(source(expr))
    import_data(engine, results)
    return Raw("")

def json(engine, node, expr):
    results = pyjson.loads(source(expr))
    import_data(engine, results)
    return Raw("")

def meta(engine, node, defs):
    if not pyyaml:
        raise ImportError("yaml is not installed!")
    results = pyyaml.safe_load(defs.raw())
    if isinstance(results, str):
        return GenFrom('meta', lambda doc: str(doc.get(results, "???")))
    elif isinstance(results, dict):
        return Gen(*[GenFor('meta', k, v) for k, v in results.items()])
    else:
        raise Exception("Meta-information must be a dictionary", results)


def show_args(engine, node, **params):
    args = []
    for k, v in sorted(params.items()):
        args += [Raw("<tr><td>"),
                 Raw(k),
                 Raw("</td><td>"),
                 Raw(repr(source(v))),
                 Raw("</td></tr>")]
    return Gen(Raw('<table class="show_args">'),
               Raw("<tr><th colspan=2>"),
               Raw(node.operator),
               Raw("</th></tr>"),
               Gen(*args),
               Raw("</table>"))

def include(engine, node, file):
    return engine(parse(engine.open(source_nows(file)).read()))

def insert_document(engine, node, docname):
    return GenFrom(source_nows(docname), lambda doc: doc.format_html())


def transgen(target, sources):
    if isinstance(sources, str):
        sources = [sources]
    def gen(engine, node, body):
        engine = engine.clone()
        engine.error_handler = mod_engine.default_error_handler
        def ev(*documents):
            for src, doc in zip(sources, documents):
                engine.environment[src] = doc
            result = format_html(engine(body))
            return result
        return TransGen(target, sources, ev)
    return gen

def genfrom(*docs):
    return transgen('html', docs)



def format_html(engine, node = None):
    html = HTMLDocument()
    docs = {'html': html}
    if node is None:
        execute_documents(engine, docs)
    else:
        execute_documents(engine(node), docs)
    return html.format_html()

def format_text(engine, node):
    text = TextDocument()
    docs = {'text': text}
    if node is None:
        execute_documents(engine, docs)
    else:
        execute_documents(engine(node), docs)
    return text.data


