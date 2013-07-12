
import os
import sys
import re
import traceback
import cgi
import weakref
from . import ast
from .parser import parse, all_op, rx_choice, whitespace_re
from .operparse import Source
from collections import defaultdict

try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None


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

        if ast.is_square_bracket(ptree):
            ptree = ptree.args[1]
            #return create_pattern(ptree.args[1], properties)

        if ptree.operator:

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


def default_error_handler(engine, ptree, exc):
    raise

def inline_error_handler(engine, ptree, exc):
    def find(doc):
        for i, (a, b, c, d) in enumerate(doc.data):
            if d is tb:
                return '<a class="err_link" href="#__ERR_{i}">E{i}</a>'.format(i = i + 1)
        return ""
    etype, e, tb = exc
    text = source_nows(ptree)
    return Gen(GenFor('errors', ptree, etype, e, tb),
               Raw(ptree.whitespace_left),
               Markup('<span class="error">'),
               Text(text),
               Markup('</span>'),
               Markup('<sup>'),
               GenFrom('errors', find),
               Markup('</sup>'),
               Raw(ptree.whitespace_right))


class MetaNode:

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, engine):
        return self.process(engine, *self.args, **self.kwargs)


def make_rule(pattern):

    first_character = True

    if isinstance(pattern, str):
        pattern = create_pattern(parse(pattern), [])

    if isinstance(pattern, tuple) or isinstance(pattern, type):
        def p(ptree):
            return match_pattern(pattern, ptree)
        if isinstance(pattern, tuple):
            head = pattern[0]
            if isinstance(head, tuple):
                head = head[0]
            if isinstance(head, tuple):
                # it needs to be done twice for operators that are
                # tuples e.g. ('(', ')')
                head = head[0]
            if isinstance(head, str):
                first_character = head and head[0]
        elif isinstance(pattern, type):
            first_character = pattern
    else:
        p = pattern

    if not hasattr(p, 'first_character'):
        p.first_character = first_character

    return p




class Once:

    def __init__(self, predicate):
        self.predicate = make_rule(predicate)
        self.first_character = self.predicate.first_character
        self.seen = weakref.WeakSet()

    def __call__(self, node):
        if node in self.seen:
            return None
        self.seen.add(node)
        result = self.predicate(node)
        if isinstance(result, dict):
            return result
        else:
            return None


def firstchar(ptree):
    if isinstance(ptree, ast.Op):
        oper = ptree.operator
        if isinstance(oper, (list, tuple)):
            oper = oper[0]
        return oper and oper[0]
    return None


class Engine:

    def __init__(self, error_handler = None):
        self.ctors = defaultdict(list)
        self.environment = {}
        if error_handler is None:
            error_handler = default_error_handler
        self.error_handler = error_handler

    def match(self, ptree):

        candidates = self.ctors.get(firstchar(ptree), [])

        for c in ptree.__class__.__mro__:
            candidates += self.ctors.get(c, [])

        candidates += self.ctors.get(True, [])
        for pattern, f in candidates:
            args = pattern(ptree)
            if args is not None:
                return (f, args)
        return None

    def register(self, pattern, function, first_character = True):

        # if isinstance(pattern, str):
        #     pattern = create_pattern(parse(pattern), [])

        # if isinstance(pattern, tuple) or isinstance(pattern, type):
        #     def p(ptree):
        #         return match_pattern(pattern, ptree)
        #     if isinstance(pattern, tuple):
        #         head = pattern[0]
        #         if isinstance(head, tuple):
        #             head = head[0]
        #         if isinstance(head, tuple):
        #             # it needs to be done twice for operators that are
        #             # tuples e.g. ('(', ')')
        #             head = head[0]
        #         if isinstance(head, str):
        #             first_character = head and head[0]
        #     elif isinstance(pattern, type):
        #         first_character = pattern
        # else:
        #     p = pattern

        p = make_rule(pattern)
        if p.first_character is True:
            p.first_character = first_character
        self.ctors[p.first_character].insert(0, (p, function))

    def extend_environment(self, **ext):
        self.environment.update(ext)

    def __setitem__(self, item, value):
        self.register(item, value)

    def clone(self):
        rval = Engine(self.error_handler)
        rval.ctors.update(self.ctors)
        rval.environment.update(self.environment)
        return rval

    def execute(self, ptree):
        result = self.match(ptree)
        if result is None:
            raise Exception("Could not find a rule for:", ptree)
        f, args = result
        try:
            return f(self, ptree, **args)
        except Exception:
            return self.error_handler(self, ptree, sys.exc_info())

    def __call__(self, ptree, **env):
        if env:
            engine = self.clone()
            engine.environment.update(env)
            return engine.execute(ptree)
        else:
            return self.execute(ptree)

    def curdir(self):
        f = self.environment['__file__']
        if f is None:
            return os.curdir()
        else:
            return os.path.dirname(f)

    def open(self, filename, *args, **kwargs):
        return open(os.path.join(self.curdir(), filename), *args, **kwargs)





class TextDocument:

    def __init__(self):
        self.data = ""

    def add(self, data):
        self.data += data

    def clone(self):
        rval = self.__class__()
        rval.data = self.data
        return rval


class SetDocument:

    def __init__(self):
        self.data = set()

    def add(self, *entry):
        self.data.add(entry)

    def clone(self):
        rval = self.__class__()
        rval.data = set(self.data)
        return rval


class ListDocument:

    def __init__(self):
        self.data = []

    def add(self, *entry):
        self.data.append(entry)

    def clone(self):
        rval = self.__class__()
        rval.data = list(self.data)
        return rval


class RepoDocument:

    def __init__(self):
        self.data = {}

    def get(self, key, default):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def add(self, key, value):
        self[key] = value

    def clone(self):
        rval = self.__class__()
        rval.data = dict(self.data)
        return rval


class HTMLDocument(TextDocument):
    def format_html(self):
        return self.data

class CSSDocument(TextDocument):
    def format_html(self):
        return "<style>%s</style>" % self.data

class JSDocument(TextDocument):
    def format_html(self):
        return "<script>%s</script>" % self.data

class XLinksDocument(SetDocument):
    def format_html(self):
        xlinks = []
        for type, link in self.data:
            xlinks.append('<link rel={type} href="{link}">'.format(
                    type = type, link = link))
        return "\n".join(xlinks)

class ErrorsDocument(ListDocument):
    def format_html(self):
        errors = self.data
        if errors:
            errtext = ""
            for i, (culprit, etype, error, tb) in enumerate(errors):
                errsource = source(culprit)
                tb = traceback.format_tb(tb)
                errtext += dedent("""
                  <div class="err_report" id="__ERR_{i}">
                    <div class="err_source">
                      <span class="err_num">E{i}</span>
                      <div>{errsource}</div>
                      <div>{loc}</div>
                    </div>
                    <div class="err_exception">
                      <div class="err_type">{etype}</div>
                      <div class="err_contents">{error}</div>
                    </div>
                    <div class="err_traceback">{tb}</div>
                  </div>
                  """).format(errsource = cgi.escape(errsource),
                              loc = cgi.escape(str(culprit.location)),
                              error = cgi.escape(str(error)),
                              etype = cgi.escape(etype.__name__),
                              tb = cgi.escape("".join(tb)),
                              i = i + 1)
            errtext = '<div class="err_reports">%s</div>' % errtext
        else:
            errtext = ""
        return errtext


class SectionsDocument:

    def __init__(self, name = None, contents = None):
        self.name = name
        self.contents = contents
        self.subsections = []

    def add(self, name, contents, level):
        if level == 1:
            self.subsections.append(SectionsDocument(name, contents))
        else:
            if not self.subsections:
                section = SectionsDocument()
                self.subsections.append(section)
            else:
                section = self.subsections[-1]
            section.add(name, contents, level - 1)




# class SectionsDocument:

#     def __init__(self):
#         self.sections = []

#     def add(self, name, contents):
#         self.sections.append((name, contents))





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


class TransGen(Generator):

    def __init__(self, target, sources, fn):
        self.target = target
        self.sources = [sources] if isinstance(sources, str) else sources
        self.fn = fn

    def deps(self):
        if self.sources:
            return {self.target: set(self.sources)}
        else:
            return {}

    def generate(self, docs):
        args = [docs.get(src, None) for src in self.sources]
        contrib = self.fn(*args)
        docs[self.target].add(contrib)

    def generators(self):
        return {self.target: self.generate}


class GenFor(TransGen):

    def __init__(self, docname, *args):
        super().__init__(docname, [], args)

    def generate(self, docs):
        docs[self.target].add(*self.fn)


class GenFrom(TransGen):

    def __init__(self, sources, fn):
        super().__init__('html', sources, fn)






# class GenFor(Generator):

#     def __init__(self, docname, *args):
#         self.docname = docname
#         self.args = args

#     def generate(self, docs):
#         docs[self.docname].add(*self.args)

#     def generators(self):
#         return {self.docname: self.generate}



# class GenFrom(Generator):

#     def __init__(self, docname, f):
#         self.docname = docname
#         self.f = f

#     def generate_html(self, docs):
#         docs['html'].add(self.f(docs[self.docname]))

#     def deps(self):
#         return {'html': self.docname}


def fork_doc(docs, docname, gen):
    if docname in docs:
        return docs[docname].clone()
    else:
        return gen()

    



# class ProxyMetaNode(MetaNode):
#     def process(self, engine, proxy, **nodes):
#         engine = engine.clone()
#         engine.environment.update(nodes)
#         return engine(proxy)


# class FullHTMLMetaNode(MetaNode):
#     def process(self, engine, node):
#         return FullHTMLGenerator(engine(node))

# class FullHTMLGenerator(Generator):

#     def __init__(self, gen):
#         self.gen = gen

#     def docmaps(self, current):
#         for (doc, type) in [('html', HTMLDocument),
#                             ('_sub_html', HTMLDocument),
#                             ('css', CSSDocument),
#                             ('js', JSDocument),
#                             ('links', RepoDocument),
#                             ('xlinks', XLinksDocument),
#                             ('meta', RepoDocument),
#                             ('sections', SectionsDocument),
#                             ('errors', ErrorsDocument)]:
#             if doc not in current:
#                 current[doc] = type()

#         subd = dict(current, html = current['_sub_html'])
#         return ([(current, self, self.deps(), self.generators())]
#                 + self.gen.docmaps(subd))

#     def deps(self):
#         subdocs = set('_sub_html css js links xlinks meta sections errors'.split())
#         return {'html': subdocs}

#     def generate_html(self, docs):
#         unmangled_docs = dict(docs, html = docs['_sub_html'])
#         docs['html'].add(generate_html_file(unmangled_docs))



class KeywordGenerator(Generator):

    def __init__(self, associations):
        self.associations = associations

    def generate_html(self, docs):
        doc = docs['html']
        for cls in doc.__class__.__mro__:
            if cls in self.associations:
                doc.add(self.associations[cls])
                return
        doc.add(self.associations.get(False, "?"))


class Raw(Generator):

    def __init__(self, text):
        self.text = str(text)

    def generate_html(self, docs):
        docs['html'].add(self.text)

    def generate_text(self, docs):
        docs['text'].add(self.text)

    def __str__(self):
        return 'Raw(%s)' % self.text

    def __repr__(self):
        return str(self)


class Markup(Generator):

    def __init__(self, text):
        self.text = str(text)

    def generate_html(self, docs):
        docs['html'].add(self.text)

    def __str__(self):
        return 'Markup(%s)' % self.text

    def __repr__(self):
        return str(self)


class Text(Generator):

    re1 = re.compile(r"((?<=[^\\])|^)~")
    re2 = re.compile(r"\\("+rx_choice(all_op + [" ", "\\"])+")")

    def __init__(self, text):
        text = str(text)
        self.source = text
        text = self.re1.sub("", text)
        text = self.re2.sub("\\1", text)
        self.text = text

    def generate_text(self, docs):
        docs['text'].add(self.text)

    def generate_html(self, docs):
        docs['html'].add(cgi.escape(self.text))

    def __str__(self):
        return 'Text(%s)' % self.text

    def __repr__(self):
        return str(self)


class ProxyGenerator(Generator):

    def __init__(self, element):
        if not isinstance(element, Generator):
            element = Text(element)
        self.element = element

    def docmaps(self, current):
        results = [(current, self, self.deps(), self.generators())]
        results += self.element.docmaps(current)
        return results


class PartsGenerator(Generator):

    def docmaps(self, current):
        results = [(current, self, self.deps(), self.generators())]
        for child in self.parts():
            if not isinstance(child, Generator):
                child = Text(child)
            results += child.docmaps(current)
        return results


class Gen(PartsGenerator):

    def __init__(self, *children):
        self.children = children
# [child if isinstance(child, Generator) else child
#                          for child in children]

    def parts(self):
        return self.children

    def __str__(self):
        return "Gen(%s)" % ', '.join(map(str, self.children))

    def __repr__(self):
        return str(self)


class RedirectGenerator(Generator):

    def __init__(self, tempname, gen, *others):
        self.tempname = tempname
        self.gen = gen
        self.others = others

    def docmaps(self, current):
        doc = HTMLDocument()
        mydocs = dict(current)
        mydocs[self.tempname] = doc
        subdocs = dict(current)
        subdocs['html'] = doc
        results = [(mydocs, self, self.deps(), self.generators())]
        results += self.gen.docmaps(subdocs)
        for other in self.others:
            results += other.docmaps(mydocs)
        return results

    def deps(self):
        return {'html': self.tempname}


class Section(RedirectGenerator):

    def __init__(self, section_name, contents, level):
        self.section_name = section_name
        self.level = level
        super().__init__('redirect', contents)

    def deps(self):
        return {'sections': self.tempname,
                'html': self.tempname}

    def generate_sections(self, docs):
        docs['sections'].add(self.section_name, docs[self.tempname], self.level)

    def generate_html(self, docs):
        docs['html'].add(docs[self.tempname].format_html())



class TemplateMetaNode(MetaNode):
    def process(self, engine, template, main):
        engine.environment['__file__'] = main.location.source.url
        template = engine(template)
        main = engine(main)
        return Template(template, main)


class Template(RedirectGenerator):
    def __init__(self, template, main):
        super().__init__('main', main, template)




class TOCGenerator(Generator):

    def deps(self):
        return {'html': 'sections'}

    def format_section(self, s, results, bah):
        if s.name is not None:
            results += ['<li><a href="#',
                        s.name,
                        '">',
                        s.contents.data,
                        "</a></li>"]
        if s.subsections:
            results.append("<ul>")
            for subs in s.subsections:
                self.format_section(subs, results, True)
            results.append("</ul>")
        return results

    def generate_html(self, docs):
        html = docs['html']
        sections = docs['sections']
        html.add("".join(self.format_section(sections, [], False)))


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


class AutoMerge(PartsGenerator):

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


class List(PartsGenerator):

    def __init__(self, *children, ordered = False):
        if ordered is False:
            o, type, start = False, None, None
        elif isinstance(ordered, tuple):
            o, type, start = ordered
        elif ordered is True:
            o, type, start = True, None, None
        elif ' ' in ordered:
            o = True
            type, start = ordered.split()
            start = int(start)
            type = dict(num = "1",
                        alpha = "a", Alpha = "A",
                        roman = "i", Roman = "I").get(type, type)
        elif re.match("-?[0-9]+", ordered):
            o, type, start = True, "1", int(ordered)
        elif ordered == 'i':
            o, type, start = True, "i", 1
        elif ordered == 'I':
            o, type, start = True, "I", 1
        elif ordered.isalpha():
            o = True
            if ordered == ordered.lower():
                type = "a"
            else:
                type = "A"
            displace = ord(type)
            start = 0
            for c in ordered:
                start *= 26
                start += ord(c) - displace + 1

        self.ordered = (o, type, start)
        self.children = children

    def parts(self):
        o, type, start = self.ordered
        if o:
            if type is None: type = "1"
            if start is None: start = 1
            otag = '<ol type="{type}" start="{start}">'.format(type=type, start=start)
            ctag = '</ol>'
        else:
            otag = "<ul>"
            ctag = "</ul>"

        yield Markup(otag)
        for child in self.children:
            yield Markup("<li>")
            yield child
            yield Markup("</li>")
        yield Markup(ctag)

    def merge(self, other):
        if isinstance(other, List):
            o1, type1, start1 = self.ordered
            o2, type2, start2 = other.ordered
            if (o1 != o2 or
                not (type1 is None or type2 is None or type1 == type2) or
                not (start1 is None or start2 is None or
                     start1 + len(self.children) == start2)):
                return None
            if start1 is None and start2 is not None:
                start1 = start2 - len(self.children)
            return List(*(self.children + other.children),
                         ordered = (o1, type1 or type2, start1))
        else:
            return None


class Definitions(PartsGenerator):

    def __init__(self, *children):
        self.children = children

    def parts(self):
        yield Markup("<dl>")
        for t, d in self.children:
            yield Markup("<dt>")
            yield t
            yield Markup("</dt>")
            yield Markup("<dd>")
            yield d
            yield Markup("</dd>")
        yield Markup("</dl>")

    def merge(self, other):
        if isinstance(other, Definitions):
            return Definitions(*(self.children + other.children))
        else:
            return None





class TableHeader:
    def __init__(self, *cells):
        self.cells = cells
    def __iter__(self):
        return iter(self.cells)


class Table(PartsGenerator):

    def __init__(self, *children):
        self.children = children

    def parts(self):
        yield Markup("<table>")
        for cells in self.children:
            header = isinstance(cells, TableHeader)
            yield Markup("<tr>")
            for cell in cells:
                yield Markup("<th>" if header else "<td>")
                yield cell
                yield Markup("</th>" if header else "</td>")
            yield Markup("</tr>")
        yield Markup("</table>")

    def merge(self, other):
        if isinstance(other, Table):
            return Table(*(self.children + other.children))
        else:
            return None


class Paragraph(WrapGenerator):

    def __init__(self, children, can_merge = False):
        self.can_merge = can_merge
        super().__init__(Markup("<p>"),
                         Text("\n"),
                         Markup("</p>"),
                         children)

    def merge(self, other):
        if self.can_merge and isinstance(other, Paragraph):
            return Paragraph(self.children + other.children, True)
        else:
            return None


def whitespace_before(node):
    if isinstance(node, str) and not hasattr(node, 'whitespace_before'):
        return ""
    else:
        return node.whitespace_before

def whitespace_after(node):
    if isinstance(node, str) and not hasattr(node, 'whitespace_after'):
        return ""
    else:
        return node.whitespace_after

def source_nows(node):
    if isinstance(node, str) and not hasattr(node, 'raw'):
        return node
    else:
        return node.raw()

def source(node):
    if isinstance(node, str) and not hasattr(node, 'raw'):
        return node
    else:
        return (node.whitespace_left
                + node.raw()
                + node.whitespace_right)

def format_anchor(s):
    return s.lower().replace(' ', '-').replace('\n', '-').replace('~', '').replace('_', '-')

def dedent(code):
    lines = code.split("\n")
    lines2 = [line for line in lines if line]
    nspaces = len(lines2[0]) - len(lines2[0].lstrip())
    return "\n".join([line[nspaces:] for line in lines])


def codehl(lang, code):
    if not pygments:
        return cgi.escape(code)
    if lang == 'auto':
        lexer = pygments.lexers.guess_lexer(code)
    else:
        try:
            lexer = pygments.lexers.get_lexer_by_name(lang)
        except pygments.util.ClassNotFound:
            lexer = pygments.lexers.TextLexer()
    fmt = pygments.formatters.HtmlFormatter(nowrap = True)
    hlcode = pygments.highlight(code, lexer, fmt)
    return hlcode


def collapse(expr, op):
    results = []
    while isinstance(expr, ast.InlineOp) and expr.operator == op:
        results.append(expr.args[0])
        expr = expr.args[1]
    if not isinstance(expr, ast.Void):
        results.append(expr)
    return results


def prepare_documents(root, initial_documents):
    documents = set()
    deps = defaultdict(set)
    generators = defaultdict(list)

    for docmap, node, node_deps, node_generators in root.docmaps(initial_documents):
        for name, doc in docmap.items():
            documents.add(doc)
        for name, depends_on in node_deps.items():
            if name not in docmap:
                continue
            if isinstance(depends_on, str):
                depends_on = (depends_on,)
            deps[docmap[name]] |= {docmap[x] for x in depends_on if x in docmap}
        for name, gen_fn in node_generators.items():
            if name in docmap:
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


def generate_html_file(documents):

    template = dedent("""
    <html>
      <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        {xlinks}
        <title>
          {title}
        </title>
        {style}
      </head>
      <body>
        <div class="main">
          {contents}
        </div>
        {script}
        {errtext}
      </body>
    </html>
    """)

    # xlinks = []
    # for type, link in documents['xlinks'].data:
    #     xlinks.append('<link rel={type} href="{link}">'.format(
    #             type = type, link = link))


    return template.format(style = documents['css'].format_html(),
                           title = documents['meta'].get('title', 'Untitled'),
                           xlinks = documents['xlinks'].format_html(),
                           script = documents['js'].format_html(),
                           contents = documents['html'].format_html(),
                           errtext = documents['errors'].format_html())



def format_html(engine, node = None):
    html = HTMLDocument()
    docs = {'html': html}
    if node is None:
        execute_documents(engine, docs)
    else:
        evaluate(node, engine, docs)
    return html.format_html()

def format_text(engine, node):
    text = TextDocument()
    docs = {'text': text}
    if node is None:
        execute_documents(engine, docs)
    else:
        evaluate(node, engine, docs)
    return text.data


def evaluate(x, engine, documents):
    execute_documents(engine(x), documents)

