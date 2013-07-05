
import sys
import re
import traceback
import cgi
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
    return MultiGenerator(GeneratorFor('errors', ptree, etype, e, tb),
                          RawGenerator(ptree.whitespace_left),
                          RawGenerator('<span class="error">'),
                          TextGenerator(text),
                          RawGenerator('</span>'),
                          RawGenerator('<sup>'),
                          GeneratorFrom('errors', find),
                          RawGenerator('</sup>'),
                          RawGenerator(ptree.whitespace_right))


class MetaNode:

    def __init__(self, *args):
        self.args = args

    def __call__(self, engine):
        return self.process(engine, *self.args)


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

        # if isinstance(ptree, ast.Op):
        #     candidates = self.ctors.get(ptree.operator and ptree.operator[0], [])
        # else:
        #     candidates = []

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
                    # yes, it needs to be done twice
                    head = head[0]
                if isinstance(head, str):
                    first_character = head and head[0]
            elif isinstance(pattern, type):
                first_character = pattern
        else:
            p = pattern

        self.ctors[first_character].insert(0, (p, function))

    def extend_environment(self, **ext):
        self.environment.update(ext)

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
        try:
            return f(self, ptree, **args)
        except Exception:
            return self.error_handler(self, ptree, sys.exc_info())





class TextDocument:

    def __init__(self):
        self.data = ""

    def add(self, data):
        self.data += data

    def get(self):
        return self.data

    def clone(self):
        rval = self.__class__()
        rval.data = self.data
        return rval


class HTMLDocument(TextDocument):
    pass


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


class GeneratorFor(Generator):

    def __init__(self, docname, *args):
        self.docname = docname
        self.args = args

    def generate(self, docs):
        docs[self.docname].add(*self.args)

    def generators(self):
        return {self.docname: self.generate}



class GeneratorFrom(Generator):

    def __init__(self, docname, f):
        self.docname = docname
        self.f = f

    def generate_main(self, docs):
        docs['main'].add(self.f(docs[self.docname]))

    def deps(self):
        return {'main': self.docname}


def fork_doc(docs, docname, gen):
    if docname in docs:
        return docs[docname].clone()
    else:
        return gen()

class HTMLDocumentGenerator(Generator):

    def __init__(self, gen):
        self.gen = gen

    def docmaps(self, current):

        new_documents = dict(
            main = fork_doc(current, 'main', HTMLDocument),
            css = fork_doc(current, 'css', TextDocument),
            js = fork_doc(current, 'js', TextDocument),
            links = fork_doc(current, 'links', RepoDocument),
            xlinks = fork_doc(current, 'xlinks', SetDocument),
            meta = fork_doc(current, 'meta', RepoDocument),
            sections = SectionsDocument(),
            errors = ListDocument())

        new = dict(current, **new_documents)
        current = dict(current, **{'_sub_' + k: v
                                   for k, v in new_documents.items()})

        return ([(current, self, self.deps(), self.generators())]
                + self.gen.docmaps(new))

    def deps(self):
        return {'main': {'_sub_' + x
                         for x in 'main css js links xlinks meta sections error'.split()}}

    def generate_main(self, docs):
        unmangled_docs = {k[5:]: v
                          for k, v in docs.items() if k.startswith('_sub_')}
        return generate_html_file(unmangled_docs)



class KeywordGenerator(Generator):

    def __init__(self, associations):
        self.associations = associations

    def generate_main(self, docs):
        doc = docs['main']
        for cls in doc.__class__.__mro__:
            if cls in self.associations:
                doc.add(self.associations[cls])
                return
        doc.add(self.associations.get(False, "?"))


class RawGenerator(Generator):

    def __init__(self, text):
        self.text = str(text)

    def generate_main(self, docs):
        docs['main'].add(self.text)


class TextGenerator(RawGenerator):

    re1 = re.compile(r"((?<=[^\\])|^)~")
    re2 = re.compile(r"\\("+rx_choice(all_op + [" ", "\\"])+")")

    def generate_main(self, docs):
        text = self.re1.sub("", self.text)
        text = self.re2.sub("\\1", text)
        # print(repr(self.text), repr(text))
        docs['main'].add(cgi.escape(text))


class WSGenerator(RawGenerator):

    re1 = re.compile("[^ \n]+")

    def generate_main(self, docs):
        text = self.re1.sub("", self.text)
        docs['main'].add(text)


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
                child = TextGenerator(child)
            results += child.docmaps(current)
        return results


class MultiGenerator(PartsGenerator):

    def __init__(self, *children):
        self.children = children
# [child if isinstance(child, Generator) else child
#                          for child in children]

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


class SectionGenerator(RedirectGenerator):

    def __init__(self, section_name, contents, level):
        self.section_name = section_name
        self.level = level
        super().__init__(contents)

    def deps(self):
        return {'sections': 'redirect',
                'main': 'redirect'}

    def generate_sections(self, docs):
        docs['sections'].add(self.section_name, docs['redirect'], self.level)

    def generate_main(self, docs):
        docs['main'].add(docs['redirect'].data)


class TOCGenerator(Generator):

    def deps(self):
        return {'main': 'sections'}

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

    def generate_main(self, docs):
        main = docs['main']
        sections = docs['sections']
        main.add("".join(self.format_section(sections, [], False)))


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


class DefinitionsGenerator(PartsGenerator):

    def __init__(self, *children):
        self.children = children

    def parts(self):
        yield RawGenerator("<dl>")
        for t, d in self.children:
            yield RawGenerator("<dt>")
            yield t
            yield RawGenerator("</dt>")
            yield RawGenerator("<dd>")
            yield d
            yield RawGenerator("</dd>")
        yield RawGenerator("</dl>")

    def merge(self, other):
        if isinstance(other, DefinitionsGenerator):
            return DefinitionsGenerator(*(self.children + other.children))
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
                         TextGenerator("\n"),
                         RawGenerator("</p>"),
                         children)

    def merge(self, other):
        if self.can_merge and isinstance(other, ParagraphGenerator):
            return ParagraphGenerator(self.children + other.children, True)
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
    return s.lower().replace(' ', '-').replace('\n', '-').replace('~', '')

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
        <style>
          {style}
        </style>
      </head>
      <body>
        <div class="main">
          {contents}
        </div>
        <script>
          {script}
        </script>
        {errtext}
      </body>
    </html>
    """)

    xlinks = []
    for type, link in documents['xlinks'].data:
        xlinks.append('<link rel={type} href="{link}">'.format(
                type = type, link = link))

    errors = documents['errors'].data
    if errors:
        errtext = ""
        for i, (culprit, etype, error, tb) in enumerate(errors):
            errsource = source(culprit)
            tb = traceback.format_tb(tb)
            errtext += """
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
              """.format(errsource = cgi.escape(errsource),
                         loc = cgi.escape(str(culprit.location)),
                         error = cgi.escape(str(error)),
                         etype = cgi.escape(etype.__name__),
                         tb = cgi.escape("".join(tb)),
                         i = i + 1)
        errtext = '<div class="err_reports">%s</div>' % errtext
    else:
        errtext = ""

    return template.format(style = documents['css'].data,
                           title = documents['meta'].get('title', 'Untitled'),
                           xlinks = "\n".join(xlinks),
                           script = documents['js'].data,
                           contents = documents['main'].data,
                           errtext = errtext)


def evaluate(x, engine, documents):
    execute_documents(engine(x), documents)

