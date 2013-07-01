

import inspect
from . import ast, parser, engine as mod_engine
from .engine import (
    dedent,
    collapse,
    codehl,
    Generator,
    GeneratorFor as GenFor,
    GeneratorFrom as GenFrom,
    RawGenerator as Raw,
    TextGenerator as Text,
    WSGenerator as GenWS,
    MultiGenerator as Gen,
    SectionGenerator as Section,
    ParagraphGenerator as Paragraph,
    AutoMergeGenerator as AutoMerge,
    ListGenerator as List,
    TableGenerator as Table,
    TableHeader,
    TOCGenerator,
)
pyeval = eval


def wrap_whitespace(f):
    def f2(engine, node, *args, **kwargs):
        return Gen(Text(node.whitespace_left),
                   f(engine, node, *args, **kwargs),
                   Text(node.whitespace_right))
    f2.__name__ = f.__name__
    return f2

def source(node):
    return (node.whitespace_left
            + node.raw()
            + node.whitespace_right)

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
        opening_tag += ' %s="%s"' % (attr, value)
    opening_tag += ">"
    return Raw(opening_tag), Raw("</%s>" % tag)


def parts_wrapper(w0, *wrappers):

    if isinstance(w0, tuple):
        argnames = w0
    else:
        argnames = None
        wrappers = (w0,) + wrappers

    @wrap_whitespace
    def wrap(engine, node, *args, **kwargs):

        if args and argnames is not None:
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
    return parts_wrapper(('lhs', 'expr'),
                         dict(arg = "lhs?"),
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
def op(engine, node):
    args = [engine(node.args[0])]
    for token in node.args[1:]:
        args.append(engine(node.operator))
        args.append(engine(token))
    return Gen(Raw("<span>"), Gen(*args), Raw("</span>"))



def indent(engine, node, i):
    contents = i.args
    return Gen(Raw("<span>"), Gen(*map(engine, contents)), Raw("</span>"))

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
    contents = contents[:1] + [x if hasattr(x, 'merge') else Paragraph([x])
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
    if isinstance(node, ast.InlineOp) and node.operator == '{}':
        return str(pyeval(node.args[1].raw(), engine.environment))
    else:
        return node.raw()


def parse_link(link):
    if '/' in link or '.' in link:
        return Text(link)
    else:
        return GenFrom('links',
                       lambda links: links.get(link_escape(link), link))


link_handlers = {}

def link_escape(s):
    return s.lower().replace(' ', '-').replace('\n', '-').replace('~', '')

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
    return Gen(Raw('<a href="'),
               parse_link(plain_or_code(engine, link)),
               Raw('">'),
               engine(text),
               Raw('</a>'))

@wrap_whitespace
def anchor(engine, node, text, label):
    label = label.raw()
    return Gen(GenFor('links', label, '#' + label),
               Raw('<span id="{label}">'.format(label = label)),
               engine(text),
               Raw('</span>'))



def extract_and_codehl(lang, code, do_dedent = True):

    if isinstance(code, ast.InlineOp) and code.operator == '[]':
        wsl, code, wsr = code.args

    if isinstance(lang, ast.Void):
        lang = "text"
    else:
        lang = lang.raw().strip().lower()

    code = source(code)
    if do_dedent:
        code = dedent(code)
    return codehl(lang, code)


def ignore(engine, node, x):
    return Raw("")


@wrap_whitespace
def code(engine, node, lang, code):
    # inline code snippets
    code = extract_and_codehl(lang, code, False)
    return Gen(Raw('<span class="code code_inline"><code>'),
               # Note: pygments' HTMLFormatter puts a line break at
               # the end of the generated code. That line break
               # produces whitespace we might not want, so we remove
               # it.
               Raw(code[:-1] if code.endswith("\n") else code),
               Raw('</code></span>'))

def code_block(engine, node, lang, code):
    # blocks of code
    return Gen(Raw('<div class="code code_block"><pre>'),
               Raw(extract_and_codehl(lang, code, True)),
               Raw('</pre></div>'))

def header_n(n):
    def header(engine, node, title = None):
        if title is None:
            title, _ = node.args
        title = title.raw()
        anchor = link_escape(title)
        return Gen(GenFor('links', anchor, '#'+anchor),
                   Raw('<h%s id="' % n),
                   Text(anchor),
                   Raw('">'),
                   Section(title, engine(title)),
                   Raw("</h%s>" % n))
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

def olist(engine, node, item):
    return List(engine(item), ordered = True)


@wrap_whitespace
def eval(engine, node, env = None, body = None):
    if body is None:
        body = env

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
def feval(engine, node, f, x, y):
    code = dedent(source(f))
    f = pyeval(code, engine.environment)
    spec = inspect.getargspec(f)

    if spec.varargs:
        return f(engine, node, x, y)
    if len(spec.args) == 2 and isinstance(x, ast.Void):
        return f(engine, y)
    elif len(spec.args) == 3:
        if isinstance(x, ast.Void):
            return f(engine, node, y)
        elif isinstance(y, ast.Void):
            return f(engine, node, x)
        else:
            raise Exception("Too many arguments for", f)
    else:
        return f(engine, node, x, y)


def css(engine, node, x):
    return GenFor('css', x.raw())

def html(engine, node, code):
    if isinstance(code, ast.Op) and code.operator == '[]':
        code = code.args[1]
    return Raw(code.raw())

def setvar(engine, node, name, body):
    name = name.raw()
    engine.environment[name] = body
    return Raw("")



def grabdefs(engine, x):

    if isinstance(x, ast.Op):
        if x.operator == ':':
            key, value = x.args
            if isinstance(value, ast.Op) and value.operator == '{}':
                value = pyeval(value.args[1].raw(), engine.environment)
            else:
                value = value.raw()
            #return Meta(key.raw().lower(), value)
            return GenFor('meta', key.raw().lower(), value)
        elif x.operator in ('P', 'B', 'I'):
            return Gen(*[grabdefs(engine, arg) for arg in x.args])
        elif x.operator == '[]':
            return grabdefs(engine, x.args[1])
        else:
            raise Exception("?!?")

    elif isinstance(x, ast.Void):
        return Raw("")

    else:
        raise Exception("?!?")

def meta(engine, node, defs):

    if (isinstance(defs, str)
        or (isinstance(defs, ast.Op) and not defs.operator)):
        key = defs.raw()
        return GenFrom('meta', lambda doc: str(doc[key]))

    else:
        return grabdefs(engine, defs)

