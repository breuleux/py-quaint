

from . import ast, engine as mod_engine
from .engine import (
    strip,
    dedent,
    collapse,
    codehl,
    Generator,
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
    contents = [x if hasattr(x, 'merge') else Paragraph([x], True)
                for x in contents]
    return AutoMerge(contents)

def blocks(engine, node, pars):
    contents = [engine(x) for x in pars.args]
    contents = [x if hasattr(x, 'merge') else Paragraph([x])
                for x in contents]
    return AutoMerge(contents)

def bracket(engine, node, body):
    return Gen(engine(node.args[0]),
               engine(body),
               engine(node.args[2]))


class FromArg:
    def __init__(self, argname, f = None):
        self.argname = argname
        self.f = f

def wrapper(tag = "span", **attributes):

    @wrap_whitespace
    def wrap(engine, node, lhs = None, expr = None, **args):
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
                    value = strip(value.raw())
            opening_tag += ' %s="%s"' % (attr, value)
        opening_tag += ">"
        return Gen(engine(lhs) if lhs else Raw(""),
                   Raw(opening_tag),
                   engine(expr),
                   Raw("</%s>" % tag))
    return wrap



# def wrapper(tag = "span", classes = []):
#     if isinstance(classes, str):
#         classes = [classes]
#     def wrap(engine, node, lhs = None, expr = None):
#         if classes:
#             cls = ' class="%s"' % " ".join(classes)
#         else:
#             cls = ''
#         return Gen(engine(lhs) if lhs else Raw(""),
#                    Raw("<%s%s>" % (tag, cls)),
#                    engine(expr),
#                    Raw("</%s>" % tag))
#     return wrap

# def classes(*classes):
#     return wrapper(


@wrap_whitespace
def em(engine, node, em):
    # emphasis (italics)
    return Gen(Raw("<em>"), engine(em), Raw("</em>"))

@wrap_whitespace
def strong(engine, node, em):
    # strong emphasis (bold)
    return Gen(Raw("<strong>"), engine(em), Raw("</strong>"))



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
    print(repr(code), repr(codehl(lang, code)))
    return codehl(lang, code)


@wrap_whitespace
def code(engine, node, lang, code):
    # inline code snippets
    # wsl, wsr, code = mod_engine.extract_and_codehl(engine, lang, code, True)
    code = extract_and_codehl(lang, code, False)
    return Gen(Raw('<span class="highlight"><code>'),
               # Note: pygments' HTMLFormatter puts a line break at
               # the end of the generated code. That line break
               # produces whitespace we might not want, so we remove
               # it.
               Raw(code[:-1] if code.endswith("\n") else code),
               Raw('</code></span>'))

def code_block(engine, node, lang, code):
    # blocks of code
    # wsl, wsr, code = mod_engine.extract_and_codehl(engine, lang, code, False)
    return Gen(Raw('<div class="highlight"><pre>'),
               Raw(extract_and_codehl(lang, code, True)),
               Raw('</pre></div>'))

def header_n(n):
    def header(engine, node):
        contents, _ = node.args
        return Gen(Raw("<h%s>" % n),
                   Section(contents.raw(), engine(contents)),
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



def eval(engine, node, body):
    code = dedent(body.raw())

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

    if node:
        return Gen(engine(node.args[0]), x, engine(node.args[2]))
    else:
        return x

def feval(engine, node, f, x, y):
    code = dedent(f.raw())
    f = pyeval(code, engine.environment)
    return f(engine, node, x, y)





def css(engine, node, _, x):
    return Gen(Raw("<style>"), Raw(x.raw()), Raw("</style>"))

def setvar(engine, node, name, body):
    name = strip(name.raw())
    engine.environment[name] = body
    return Raw("")


