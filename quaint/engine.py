
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
                         TextGenerator("\n"),
                         RawGenerator("</p>"),
                         children)

    def merge(self, other):
        if self.can_merge and isinstance(other, ParagraphGenerator):
            return ParagraphGenerator(self.children + other.children, True)
        else:
            return None


def dedent(code):
    lines = code.split("\n")
    lines2 = [line for line in lines if line]
    nspaces = len(lines2[0]) - len(lines2[0].lstrip())
    return "\n".join([line[nspaces:] for line in lines])


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


def evaluate(x, engine):
    doc = HTMLDocument()
    documents = {'main': doc,
                 'sections': SectionsDocument()}
    documents = execute_documents(engine(x), documents)
    return doc.data

