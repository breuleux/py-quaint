
import cgi
import re
from . import ast
from .parser import parse, all_op, rx_choice, whitespace_re
from .operparse import Source
from collections import defaultdict

import pygments
import pygments.lexers
import pygments.formatters


def create_pattern(ptree, properties):

    if isinstance(ptree, str):
        ptree = ptree.strip()

        if properties == ['maybe']:
            return ptree

        elif properties == []:
            def not_void(x):
                return not isinstance(x, ast.Void)
            f = not_void

        elif properties == ['void']:
            def is_void(x):
                return isinstance(x, ast.Void)
            f = is_void

        else:
            raise Exception("Illegal properties or mix of properties", properties)

        return (f, ptree)

    elif isinstance(ptree, ast.Op):

        if ptree.operator == '[]':
            return create_pattern(ptree.args[1], properties)

        elif ptree.operator:

            if 'wide' in properties: wide = True
            elif 'short' in properties: wide = False
            else: wide = None

            if 'line' in properties: line = True
            elif 'inline' in properties: line = False
            else: line = None

            descr = (ptree.operator, wide, line)
            return (descr, [create_pattern(sub, []) for sub in ptree.args])

        else:
            properties = [arg.strip() for arg in ptree.args[:-1]]
            return create_pattern(ptree.args[-1], properties)

    elif isinstance(ptree, ast.Void):
        return ast.Void

    else:
        raise Exception("Cannot parse pattern", ptree)


def match_pattern(pattern, value):

    if isinstance(pattern, str):
        return {pattern: value}

    elif isinstance(pattern, tuple):
        f, subp = pattern
        if isinstance(f, str):
            f = (f, None, None)

        if isinstance(f, tuple):
            op, wide, line = f
            if isinstance(value, ast.Op):
                if (op != value.operator
                    or wide and not value.wide
                    or wide is False and value.wide
                    or line and not isinstance(value, ast.BlockOp)
                    or line is False and not isinstance(value, ast.InlineOp)):
                    return None
                if isinstance(subp, str):
                    return {subp: value}
                else:
                    if len(subp) != len(value.args):
                        return None
                    rval = {}
                    for p, v in zip(subp, value.args):
                        d = match_pattern(p, v)
                        if d is None:
                            return None
                        rval.update(d)
                    return rval
            else:
                return None

        elif isinstance(f, type):
            if isinstance(value, f):
                return match_pattern(subp, value)
            else:
                return None

        elif f(value):
            return match_pattern(subp, value)

        else:
            return None

    elif isinstance(pattern, type):
        if isinstance(value, pattern):
            return {}
        else:
            return None

    else:
        return pattern(value)


# class PatternBank:

#     def __init__(self):
#         self.patterns = {}

#     # def add(self, pattern, rule):

#     #     if isinstance(pattern, type):
#     #         self.patterns[pattern] = ({}, rule)

#     #     if isinstance(pattern, ast.InlineOp):
#     #         if 

#     #         self.patterns[("I", ast.text)]

#     def match(self, value):

#         keys = value.__class__.__mro__
#         if isinstance(value, ast.Op):
#             keys = (value.text,) + keys

#         for key in keys:
#             if key not in self.patterns:
#                 continue
#             candidates = self.patterns[key]
#             for candidate in candidates:
#                 if isinstance(candidate, str):
#                     return {candidate: value}
#                 elif isinstance(candidate, tuple):
            


# ['void v _ em']




def simple_match(pattern, value, results = None):

    if results is None:
        results = {}

    if isinstance(value, ast.quaintstr):
        return None

    if pattern.signature() != value.signature():
        return None

    if isinstance(pattern, ast.Op):
        for p, v in zip(pattern.args, value.args):
            if isinstance(p, str):
                results[p.strip()] = v
            else:
                if simple_match(p, v, results) is None:
                    return None
    else:
        return {}

    return results



class Engine:

    def __init__(self):
        self.ctors = defaultdict(list)
        self.environment = {}

    def match(self, ptree):

        if isinstance(ptree, ast.Op):
            candidates = self.ctors.get(ptree.operator and ptree.operator[0], [])
        else:
            candidates = []

        for c in ptree.__class__.__mro__:
            candidates += self.ctors.get(c, [])

        candidates += self.ctors.get(True, [])
        for pattern, f in candidates:
            args = pattern(ptree)
            if args is not None:
                return (f, args)
        return None

    def register(self, pattern, function, first_character = True):

        if isinstance(pattern, str):
            pattern = create_pattern(parse(Source(pattern, url = None)), [])

        if isinstance(pattern, tuple) or isinstance(pattern, type):
            def p(ptree):
                return match_pattern(pattern, ptree)
            if isinstance(pattern, tuple):
                head = pattern[0]
                if isinstance(head, tuple):
                    head = head[0]
                if isinstance(head, str):
                    first_character = head and head[0]
            elif isinstance(pattern, type):
                first_character = pattern
        else:
            p = pattern

        self.ctors[first_character].insert(0, (p, function))

    def __setitem__(self, item, value):
        self.register(item, value)

    def clone(self):
        rval = Matcher()
        rval.ctors.update(self.ctors)
        return rval

    def __call__(self, ptree):
        result = self.match(ptree)
        if result is None:
            raise Exception("Could not find a rule for:", ptree)
        f, args = result
        return f(self, ptree, **args)





class TextDocument:

    def __init__(self):
        self.data = ""

    def append(self, data):
        self.data += data

    def get(self):
        return self.data


class HTMLDocument(TextDocument):

    def get(self):
        return self.data


class SectionsDocument:

    def __init__(self):
        self.sections = []

    def add(self, name, contents):
        self.sections.append((name, contents))




class Generator:

    def docmaps(self, current):
        return [(current, self, self.deps(), self.generators())]

    def deps(self):
        return {}

    def generators(self):
        results = {}
        for name in dir(self):
            if name.startswith("generate_"):
                results[name[9:]] = getattr(self, name)
        return results


class KeywordGenerator(Generator):

    def __init__(self, associations):
        self.associations = associations

    def generate_main(self, docs):
        doc = docs['main']
        for cls in doc.__class__.__mro__:
            if cls in self.associations:
                doc.append(self.associations[cls])
                return
        doc.append(self.associations.get(False, "?"))


class RawGenerator(Generator):

    def __init__(self, text):
        self.text = str(text)

    def generate_main(self, docs):
        docs['main'].append(self.text)


class TextGenerator(RawGenerator):

    re1 = re.compile(r"((?<=[^\\])|^)~")
    re2 = re.compile(r"\\("+rx_choice(all_op + [" ", "\\"])+")")

    def generate_main(self, docs):
        text = self.re1.sub("", self.text)
        text = self.re2.sub("\\1", text)
        # print(repr(self.text), repr(text))
        docs['main'].append(cgi.escape(text))


class WSGenerator(RawGenerator):

    re1 = re.compile("[^ \n]+")

    def generate_main(self, docs):
        text = self.re1.sub("", self.text)
        docs['main'].append(text)


class ProxyGenerator(Generator):

    def __init__(self, element):
        self.element = element

    def docmaps(self, current):
        results = [(current, self, self.deps(), self.generators())]
        results += self.element.docmaps(current)
        return results


class PartsGenerator(Generator):

    def docmaps(self, current):
        results = [(current, self, self.deps(), self.generators())]
        for child in self.parts():
            results += child.docmaps(current)
        return results


class MultiGenerator(PartsGenerator):

    def __init__(self, *children):
        self.children = children

    def parts(self):
        return self.children


class RedirectGenerator(Generator):

    def __init__(self, gen):
        self.gen = gen

    def docmaps(self, current):
        doc = HTMLDocument()
        mydocs = dict(current)
        mydocs['redirect'] = doc
        subdocs = dict(current)
        subdocs['main'] = doc
        results = [(mydocs, self, self.deps(), self.generators())]
        results += self.gen.docmaps(subdocs)
        return results

    def deps(self):
        return {'main': 'redirect'}


# class Doubler(RedirectGenerator):

#     def generate_main(self, docs):
#         print("what", docs['redirect'].data)
#         docs['main'].append(docs['redirect'].data)
#         docs['main'].append(docs['redirect'].data)

# def doubler_generator(engine, node, x):
#     return Doubler(engine(x))


class SectionGenerator(RedirectGenerator):

    def __init__(self, section_name, contents):
        self.section_name = section_name
        super().__init__(contents)

    def deps(self):
        return {'sections': 'redirect',
                'main': 'redirect'}

    def generate_sections(self, docs):
        docs['sections'].add(self.section_name, docs['redirect'])

    def generate_main(self, docs):
        docs['main'].append(docs['redirect'].data)



class TOCGenerator(Generator):

    def deps(self):
        return {'main': 'sections'}

    def generate_main(self, docs):
        main = docs['main']
        sections = docs['sections']
        for name, section in sections.sections:
            main.append(section.data)
            main.append("<br/>")

# class SectionGenerator(ProxyGenerator):

#     def __init__(self, section_name, contents):
#         self.section_name = section_name
#         super().__init__(contents)

#     def generate_sections(self, docs):
#         docs['sections'].add(self.section_name, self.element)



# class TOCGenerator(Generator):

#     def deps(self):
#         return {'main': 'sections'}

#     def generate_main(self, docs):
#         main = docs['main']
#         sections = docs['sections']
#         for name, section in sections.sections:
#             main.append(name)
#             main.append("<br/>")


# toc_generator = TOCGenerator()



# class WrapGenerator(MultiGenerator):

#     def __init__(self, prefix, join, suffix, children):
#         self.children = children
#         real_children = []
#         if prefix:
#             real_children.append(prefix)
#         if join and children:
#             real_children.append(children[0])
#             for child in children[1:]:
#                 real_children.append(join)
#                 real_children.append(child)
#         else:
#             real_children += children
#         if suffix:
#             real_children.append(suffix)
#         self._real_children = real_children



class WrapGenerator(PartsGenerator):

    def __init__(self, prefix, join, suffix, children):
        self.children = children
        self.prefix = prefix
        self.join = join
        self.suffix = suffix

    def parts(self):
        if self.prefix:
            yield self.prefix
        if self.join and self.children:
            yield self.children[0]
            for child in self.children[1:]:
                yield self.join
                yield child
        else:
            for child in self.children:
                yield child
        if self.suffix:
            yield self.suffix


class AutoMergeGenerator(PartsGenerator):

    def __init__(self, children):
        c = children[:1]
        for child in children[1:]:
            if hasattr(c[-1], 'merge'):
                m = c[-1].merge(child)
                if m:
                    c[-1] = m
                    continue
            c.append(child)
        self.children = c

    def parts(self):
        return self.children





class ListGenerator(PartsGenerator):

    def __init__(self, *children, ordered = False):
        self.ordered = ordered
        self.children = children

    def parts(self):
        yield RawGenerator("<ol>" if self.ordered else "<ul>")
        for child in self.children:
            yield RawGenerator("<li>")
            yield child
            yield RawGenerator("</li>")
        yield RawGenerator("</ol>" if self.ordered else "</ul>")

    def merge(self, other):
        if isinstance(other, ListGenerator) and self.ordered == other.ordered:
            return ListGenerator(*(self.children + other.children),
                                 ordered = self.ordered)
        else:
            return None


class TableHeader:
    def __init__(self, *cells):
        self.cells = cells
    def __iter__(self):
        return iter(self.cells)


class TableGenerator(PartsGenerator):

    def __init__(self, *children):
        self.children = children

    def parts(self):
        yield RawGenerator("<table>")
        for cells in self.children:
            header = isinstance(cells, TableHeader)
            yield RawGenerator("<tr>")
            for cell in cells:
                yield RawGenerator("<th>" if header else "<td>")
                yield cell
                yield RawGenerator("</th>" if header else "</td>")
            yield RawGenerator("</tr>")
        yield RawGenerator("</table>")

    def merge(self, other):
        if isinstance(other, TableGenerator):
            return TableGenerator(*(self.children + other.children))
        else:
            return None


class ParagraphGenerator(WrapGenerator):

    def __init__(self, children, can_merge = False):
        self.can_merge = can_merge
        super().__init__(RawGenerator("<p>"),
                         TextGenerator(""),
                         RawGenerator("</p>"),
                         children)

    def merge(self, other):
        if self.can_merge and isinstance(other, ParagraphGenerator):
            return ParagraphGenerator(self.children + other.children, True)
        else:
            return None














# def bracket_generator(engine, node, body):
#     return MultiGenerator(engine(node.args[0]),
#                           engine(body),
#                           engine(node.args[2]))

def dedent(code):
    lines = code.split("\n")
    lines2 = [line for line in lines if line]
    nspaces = len(lines2[0]) - len(lines2[0].lstrip())
    return "\n".join([line[nspaces:] for line in lines])

# def eval_generator(engine, node, body):
#     code = dedent(body.location.get())

#     try:
#         x = eval(code, engine.environment)
#     except SyntaxError:
#         exec(code, engine.environment)
#         x = TextGenerator("")
#     else:
#         if isinstance(x, (ast.ASTNode, ast.quaintstr)):
#             x = engine(x)
#         elif not isinstance(x, Generator):
#             x = TextGenerator(str(x))

#     return MultiGenerator(engine(node.args[0]),
#                           x,
#                           engine(node.args[2]))

# def eval2_generator(engine, node, f, x, y):
#     code = dedent(f.location.get())
#     f = eval(code, engine.environment)
#     return f(engine, node, x, y)

# def swap(engine, node, x, y):
#     return MultiGenerator(engine(y), engine(x))

# def css(engine, node, _, x):
#     return MultiGenerator(RawGenerator("<style>"),
#                           RawGenerator(x.raw()),
#                           RawGenerator("</style>"))

# def setvar_generator(engine, node, name, body):
#     name = strip(name.raw())
#     engine.environment[name] = body
#     return RawGenerator("")




# def boundaries(**assoc):
#     assoc = {{'html': HTMLDocument}[k]: v
#              for k, v in assoc.items()}

#     starts = KeywordGenerator({k: v[0] for k, v in assoc.items()})
#     ends = KeywordGenerator({k: v[1] for k, v in assoc.items()})
#     return starts, ends

# def expression_wrapper(**defs):
#     a, b = boundaries(**defs)
#     def f(engine, node, expr):
#         return WrapGenerator(MultiGenerator(RawGenerator(node.args[0].text), a),
#                              None,
#                              b, #MultiGenerator([b, RawGenerator(node.args[-1].text)]),
#                              [engine(expr)])
#     return f


# # def bold_generator(engine, node, em):
# #     return expression_wrapper(html = ["<b>", "</b>"])(engine, node, em)

#     # a, b = boundaries(html = ["<i>", "</i>"])
#     # return WrapGenerator(a, None, b, [engine(em)])


# def emphasis_generator(engine, node, v, em):
#     return MultiGenerator(engine(v),
#                           WrapGenerator(RawGenerator("<i>"),
#                                         None,
#                                         RawGenerator("</i>"),
#                                         [engine(em)]))

# def bold_generator(engine, node, v, em):
#     return MultiGenerator(engine(v),
#                           WrapGenerator(RawGenerator("<b>"),
#                                         None,
#                                         RawGenerator("</b>"),
#                                         [engine(em)]))

# # bold_generator = expression_wrapper(html = ["<b>", "</b>"])
# # emphasis_generator = expression_wrapper(html = ["<i>", "</i>"])

# def header_generator(engine, node):
#     contents, _ = node.args
#     return WrapGenerator(RawGenerator("<h1>"),
#                          None,
#                          RawGenerator("</h1>"),
#                          [SectionGenerator(contents.location.get(),
#                                            engine(contents))])

# def header2_generator(engine, node):
#     contents, _ = node.args
#     return WrapGenerator(RawGenerator("<h2>"),
#                          None,
#                          RawGenerator("</h2>"),
#                          [SectionGenerator(contents.location.get(),
#                                            engine(contents))])

def codehl(lang, code):

    if lang == 'auto':
        lexer = pygments.lexers.guess_lexer(code)

    else:
        try:
            lexer = pygments.lexers.get_lexer_by_name(lang)
        except pygments.util.ClassNotFound:
            lexer = pygments.lexers.TextLexer()

    hlcode = pygments.highlight(code, lexer,
                                pygments.formatters.HtmlFormatter(nowrap = True))

    return hlcode


strip_re_begin = re.compile("^({ws}*)".format(ws = "[ \n~]"))
strip_re_end = re.compile("({ws})*$".format(ws = "[ \n~]"))
def strip_and_ws(text):
    mb = strip_re_begin.search(text)
    me = strip_re_end.search(text)
    b = mb.regs[0][1]
    e = me.regs[0][0]
    # print(repr(text), mb.regs, me.regs)
    return text[:b], text[b:e], text[e:]

# strip_re = re.compile("^{ws}+|{ws}+$".format(ws = "[ \n~]"))
def strip(w):
    a, b, c = strip_and_ws(w)
    return b
    # print(repr(w))
    # print(repr(strip_re.sub("", w)))
    # return strip_re.sub("", w)

def extract_and_codehl(engine, lang, code, do_strip = False):

    if isinstance(code, ast.InlineOp) and code.operator == '[]':
        wsl, code, wsr = code.args
        do_strip = False
    else:
        wsl, code, wsr = "", code, ""
    wsl = engine(wsl)
    wsr = engine(wsr)

    if isinstance(lang, ast.Void):
        lang = "text"
    else:
        lang = lang.raw().strip().lower()

    if do_strip:
        _, code, wsr2 = strip_and_ws(code.raw())
        wsr = MultiGenerator(wsr, TextGenerator(wsr2))
    else:
        code = dedent(code.raw())
    return wsl, wsr, codehl(lang, code)


# def code_generator(engine, node, lang, expr):
#     wsl, wsr, code = extract_and_codehl(engine, lang, expr, True)
#     return WrapGenerator(RawGenerator('<span class="highlight"><code>'),
#                          None,
#                          RawGenerator('</code></span>'),
#                          # Note: code.strip() removes the line break pygments'
#                          # HTMLFormatter puts at the end of the generated code.
#                          # That line break produces whitespace we might not want.
#                          [WSGenerator(lang), wsl, RawGenerator(code.strip()), wsr])

# def code_block_generator(engine, node, lang, body):
#     wsl, wsr, code = extract_and_codehl(engine, lang, body, False)
#     return WrapGenerator(RawGenerator('<div class="highlight"><pre>'),
#                          None,
#                          RawGenerator('</pre></div>'),
#                          [RawGenerator(code)])

# def paragraph_generator(engine, node, par):
#     contents = par.args
#     contents = [engine(x) for x in contents]
#     contents = [x if hasattr(x, 'merge') else ParagraphGenerator([x], True)
#                 for x in contents]
#     return AutoMergeGenerator(contents)

# def blocks_generator(engine, node, pars):
#     contents = pars.args
#     contents = [engine(x) for x in contents]
#     contents = [x if hasattr(x, 'merge') else ParagraphGenerator([x])
#                 for x in contents]
#     return AutoMergeGenerator(contents)

# def get_cells(engine, row, op):
#     cells = []
#     while isinstance(row, ast.InlineOp) and row.operator == op:
#         cells.append(engine(row.args[0]))
#         row = row.args[1]
#     if not isinstance(row, ast.Void):
#         cells.append(engine(row))
#     return cells

def collapse(expr, op):
    results = []
    while isinstance(expr, ast.InlineOp) and expr.operator == op:
        results.append(expr.args[0])
        expr = expr.args[1]
    if not isinstance(expr, ast.Void):
        results.append(expr)
    return results

# def table_row_generator(engine, node, row):
#     return TableGenerator(get_cells(engine, row, '|'))

# def table_header_generator(engine, node, row):
#     return TableGenerator(TableHeader(*get_cells(engine, row, '+')))

# def ulist_generator(engine, node, bulletpoint):
#     return ListGenerator(engine(bulletpoint))

# def olist_generator(engine, node, bulletpoint):
#     return ListGenerator(engine(bulletpoint), ordered = True)


# def text_generator(engine, node):
#     if not isinstance(node, str):
#         node = node.raw()
#     return TextGenerator(node)

# def raw_generator(engine, node):
#     if not isinstance(node, str):
#         node = node.raw()
#     return RawGenerator(node)


# def indent_generator(engine, node, i):
#     contents = i.args
#     return WrapGenerator(RawGenerator("<span>"),
#                          None,
#                          RawGenerator("</span>"),
#                          list(map(engine, contents)))


# def default_op_generator(engine, node):
#     # args = []
#     # for token, op in zip(node.args, node.operators + [None]):
#     #     args.append(engine(token))
#     #     if op is not None:
#     #         args.append(engine(op))
#     # print([arg.text for arg in args])

#     args = [engine(node.args[0])]
#     for token in node.args[1:]:
#         args.append(engine(node.operator))
#         args.append(engine(token))
#     return WrapGenerator(RawGenerator("<span>"),
#                          None,
#                          RawGenerator("</span>"),
#                          args)









def prepare_documents(root, initial_documents):
    documents = set()
    deps = defaultdict(set)
    generators = defaultdict(list)

    for docmap, node, node_deps, node_generators in root.docmaps(initial_documents):
        for name, doc in docmap.items():
            documents.add(doc)
        for name, depends_on in node_deps.items():
            if isinstance(depends_on, str):
                depends_on = (depends_on,)
            deps[docmap[name]] |= {docmap[x] for x in depends_on}
        for name, gen_fn in node_generators.items():
            generators[docmap[name]].append((gen_fn, docmap))

    for doc in documents:
        deps.setdefault(doc, set())

    order = toposort(deps)
    return [(doc, generators[doc]) for doc in order]


def execute_documents(root, initial_documents):
    documents = prepare_documents(root, initial_documents)
    for doc, generators in documents:
        for generator, docmap in generators:
            generator(docmap)
    return [d for d, _ in documents]


# class DefaultGenerator(Generator):

#     def generate(self, documents):
#         for child in self.







# def eng0():

#     def sequence_of(c, cls = ast.Op):
#         c = set(c)
#         def test(x):
#             if isinstance(x, cls) and set(x.operator) == c:
#                 return {}
#             else:
#                 return None
#         return test

#     m = Engine()

#     m.register(ast.Void, text_generator)
#     m.register(ast.Nullary, text_generator)
#     m.register(str, text_generator)
#     m.register(ast.Op, default_op_generator)

#     m.register(sequence_of('=', ast.BlockOp), header_generator, "=")
#     m.register(sequence_of('-', ast.BlockOp), header2_generator, "-")

#     m.register("void v _ em", emphasis_generator)
#     m.register("void v __ em", bold_generator)
#     m.register("maybe lang ` expr", code_generator)
#     m.register("maybe lang % body", code_block_generator)

#     m.register(("I", "i"), indent_generator)
#     m.register(("P", "par"), paragraph_generator)
#     m.register(("B", "pars"), blocks_generator)

#     m.register(('[]', [ast.Void, 'body', ast.Void]), bracket_generator)
#     m.register("{body}", eval_generator)
#     m.register("maybe x <f> maybe y", eval2_generator)

#     m.register("* bulletpoint", ulist_generator)
#     m.register("# bulletpoint", olist_generator)
#     m.register("| row", table_row_generator)
#     m.register("+ row", table_header_generator)

#     m.register("name <- body", setvar_generator)

#     m.environment['engine'] = m
#     m.environment['swap'] = swap
#     # m.environment['setvar'] = setvar
#     m.environment['css'] = css
#     m.environment['table'] = TableGenerator

#     m.environment['gen'] = MultiGenerator
#     m.environment['raw'] = RawGenerator
#     m.environment['text'] = TextGenerator
#     m.environment['toc'] = toc_generator

#     return m


def evaluate(x, engine):

    # for k, v in m.ctors.items():
    #     print(k, v)

    # e.matcher.register("a - b", woop2)
    # e.matcher.register("*/a - b*", woop2)
    # e.matcher.register(lambda x: {}, woop3)

    # return m(x).generate_html()

    doc = HTMLDocument()
    documents = {'main': doc,
                 'sections': SectionsDocument()}
    documents = execute_documents(engine(x), documents)

    return doc.data

    # rval = [d for d in documents if isinstance(d, HTMLDocument)]

    # return rval[0].data








    # def clone(self, clone_matcher = False):
    #     rval = Engine()
    #     if clone_matcher:
    #         rval.matcher = self.matcher.clone()
    #     else:
    #         rval.matcher = self.matcher
    #     rval.components = dict(self.components)
    #     return rval

    # def enter(self, name, component):
    #     return self.enter_all([(name, component)])

    # def enter_all(self, mods):
    #     rval = self.clone()
    #     for name, component in mods:
    #         self[name].append(component(rval))
    #         rval[name] = component
    #     return rval



# class TextGenerator:

#     def __init__(self, text):
#         self.text = text

#     def generate_html(self):
#         return cgi.escape(self.text)


# class WrapGenerator:

#     def __init__(self, children):
#         self.children = children

#     def append(self, element):
#         self.children.append(element)

#     def generate_html(self):
#         return "<div>{0}</div>".format("".join(child.generate_html()
#                                                for child in self.children))



# class Constructor:

#     def on_raw(self, *text):
#         ee

#     def on_raw_parse(self, *ptree):
#         aa

#     def on_simplified_parse(self, *ptree):
#         aaa

#     def on_final(self, language, *result):
#         eee


# # class Emphasis(Formatter):
# #     def __init__(self, node, em):
# #         self.node = node
# #         self.em = em
# #     def 


# class EmphasisGenerator:
#     def __init__(self):
#         ee


# def emphasis(engine, node, em):
#     subengine = engine.append('main', EmphasisGenerator)
#     subengine.process(em)

# engine.register_matcher("*em*", emphasis)





def toposort(pred):
    # I haven't tested this enough to actually *know* it is correct.

    # First, copy the map element -> predecessors and build the map
    # element -> successors.
    pred = {k: set(v) for k, v in pred.items()}
    succ = defaultdict(set)
    candidates = []
    for entry, prereqs in pred.items():
        if prereqs:
            for prereq in prereqs:
                succ[prereq].add(entry)
        else:
            # Our starting pool is the elements that have no
            # predecessors.
            candidates.append(entry)

    results = []
    done = set()
    candidates_set = set(candidates)
    count = 0
    while candidates:
        count += 1
        if count > len(candidates):
            # If we get here, it means we looped through all
            # candidates without changing anything.
            raise Exception("There are cycles in the topological ordering. (0)")
        candidate = candidates.pop(0)
        candidates_set.remove(candidate)
        if candidate in done:
            continue
        pred[candidate] -= done
        if pred[candidate]:
            # There are still predecessors for this node that haven't
            # been processed yet, so we add it back at the end.
            if candidate not in candidates_set:
                candidates.append(candidate)
                candidates_set.add(candidate)
        else:
            # All predecessors are cleared, so we add this node to the
            # results and we consider its successors as candidates.
            count = 0
            results.append(candidate)
            done.add(candidate)
            candidates += [x for x in succ[candidate] - candidates_set]
            candidates_set |= succ[candidate]

    if len(results) < len(pred):
        # There is some connected group where all nodes have incoming
        # edges (must be a cycle).
        raise Exception("There are cycles in the topological ordering. (1)")

    return results


