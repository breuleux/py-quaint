
import cgi
from . import ast
from .parser import parse
from .operparse import Source
from collections import defaultdict



def simple_match(pattern, value, results = None):

    if results is None:
        results = {}

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



class Matcher:

    def __init__(self):
        self.ctors = defaultdict(list)

    def match(self, ptree):
        if hasattr(ptree, "signature"):
            candidates = self.ctors.get(ptree.signature(), [])
        else:
            candidates = []
        candidates += self.ctors.get(True, [])
        for pattern, f in candidates:
            args = pattern(ptree)
            if args is not None:
                return (f, args)
        return None

    def register(self, pattern, function):
        if isinstance(pattern, str):
            pattern = parse(Source(pattern, url = None))
            def p(ptree):
                return simple_match(pattern, ptree)
            self.ctors[pattern.signature()].insert(0, (p, function))
        else:
            self.ctors[True].insert(0, (pattern, function))

    def clone(self):
        rval = Matcher()
        rval.ctors.update(self.ctors)
        return rval

    def __call__(self, ptree):
        f, args = self.match(ptree)
        return f(self, ptree, **args)



def bracket_generator(engine, node, body):
    return WrapGenerator(
        TextGenerator(node.operators[0].replace("[", "")),
        None,
        TextGenerator(node.operators[1].replace("]", "")),
        [engine(body)])

def eval_generator(engine, node, body):
    code = body.location.get()

    try:
        x = eval(code)
    except SyntaxError:
        exec(code)
        x = TextGenerator("")
    else:
        if not isinstance(x, Generator):
            x = TextGenerator(str(x))

    return WrapGenerator(
        TextGenerator(node.operators[0].replace("{", "")),
        None,
        TextGenerator(node.operators[1].replace("}", "")),
        [x])

def eval2_generator(engine, node, f, x = None, y = None):
    f = eval(f.location.get())
    if x is None:
        return f(engine, node, y)
    else:
        return f(engine, node, x, y)

def swap(engine, node, x, y):
    return MultiGenerator([engine(y), engine(x)])

def bold(engine, node, y):
    return WrapGenerator(RawGenerator("<b>"),
                         None,
                         RawGenerator("</b>"),
                         [engine(y)])


def emphasis_generator(engine, node, em):
    return WrapGenerator(RawGenerator("<i>"),
                         None,
                         RawGenerator("</i>"),
                         [engine(em)])

def header_generator(engine, node, contents):
    return WrapGenerator(RawGenerator("<h1>"),
                         None,
                         RawGenerator("</h1>"),
                         [SectionGenerator(contents.location.get(),
                                           engine(contents))])

def paragraph_generator(engine, node, contents):
    contents = [engine(x) for x in contents]
    contents = [x if hasattr(x, 'merge') else ParagraphGenerator([x])
                for x in contents]
    return AutoMergeGenerator(contents)

def ulist_generator(engine, node, bullet_point):
    return ListGenerator([engine(bullet_point)])

def olist_generator(engine, node, bullet_point):
    return ListGenerator([engine(bullet_point)], True)


def default_void_generator(engine, node):
    return TextGenerator("")


def default_str_generator(engine, node):
    return TextGenerator(node)


def default_op_generator(engine, node):
    args = []
    for token, op in zip(node.args, node.operators + [None]):
        args.append(engine(token))
        if op is not None:
            args.append(engine(op))
    # print([arg.text for arg in args])
    return WrapGenerator(RawGenerator("<span>"),
                          None,
                          RawGenerator("</span>"),
                          args)



class TextDocument:

    def __init__(self):
        self.data = ""

    def append(self, data):
        self.data += data


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




class RawGenerator(Generator):

    def __init__(self, text):
        self.text = text

    def generate_main(self, docs):
        docs['main'].append(self.text)


class TextGenerator(RawGenerator):

    def generate_main(self, docs):
        docs['main'].append(cgi.escape(self.text))



class MultiGenerator(Generator):

    def __init__(self, children):
        self.children = children
        self._real_children = children

    def docmaps(self, current):
        results = [(current, self, self.deps(), self.generators())]
        for child in self._real_children:
            results += child.docmaps(current)
        return results


class SectionGenerator(MultiGenerator):

    def __init__(self, section_name, contents):
        self.section_name = section_name
        super().__init__([contents])

    def generate_sections(self, docs):
        docs['sections'].add(self.section_name, self.children[0])



class TOCGenerator(Generator):

    def deps(self):
        return {'main': 'sections'}

    def generate_main(self, docs):
        main = docs['main']
        sections = docs['sections']
        for name, section in sections.sections:
            main.append(name)
            main.append("<br/>")


class WrapGenerator(MultiGenerator):

    def __init__(self, prefix, join, suffix, children):
        self.children = children
        real_children = []
        if prefix:
            real_children.append(prefix)
        if join and children:
            real_children.append(children[0])
            for child in children[1:]:
                real_children.append(join)
                real_children.append(child)
        else:
            real_children += children
        if suffix:
            real_children.append(suffix)
        self._real_children = real_children


class AutoMergeGenerator(MultiGenerator):

    def __init__(self, children, wrap = None):
        if wrap is not None:
            children = list(map(wrap, children))
        self.children = children[:1]
        for child in children[1:]:
            if hasattr(self.children[-1], 'merge'):
                m = self.children[-1].merge(child)
                if m:
                    self.children[-1] = m
                    continue
            self.children.append(child)
        self._real_children = self.children


class ListGenerator(WrapGenerator):

    def __init__(self, children, ordered = False):
        self.original_children = children
        self.ordered = ordered

        super().__init__(RawGenerator("<ol>" if ordered else "<ul>"),
                         None,
                         RawGenerator("</ol>" if ordered else "</ul>"),
                         [WrapGenerator(RawGenerator("<li>"),
                                        None,
                                        RawGenerator("</li>"),
                                        [child])
                          for child in children])

    def merge(self, other):
        if isinstance(other, ListGenerator) and self.ordered == other.ordered:
            return ListGenerator(self.original_children
                                 + other.original_children,
                                 self.ordered)
        else:
            return None


class ParagraphGenerator(WrapGenerator):

    def __init__(self, children):
        super().__init__(RawGenerator("<p>"),
                         TextGenerator("\n"),
                         RawGenerator("</p>"),
                         children)

    def merge(self, other):
        if isinstance(other, ParagraphGenerator):
            return ParagraphGenerator(self.children + other.children)
        else:
            return None




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











def evaluate(x):

    def woop(x):
        # print(x, isinstance(x, ast.BlockOp), set(x.operator))
        if isinstance(x, ast.BlockOp) and set(x.operator) == {'='}:
            return {'contents': x.args[0]}
        else:
            return None

    def woop_par(x):
        if isinstance(x, ast.BlockOp) and x.operator == 'P':
            return {'contents': x.args}
        else:
            return None
                 
                          
    # def woop(engine, ptree, **args):
    #     return TextGenerator("aha!")

    # def woop2(engine, ptree, **args):
    #     print(2, args)
    #     return 12345

    # def woop3(engine, ptree, **args):
    #     print(3, ptree)
    #     return 123456

    m = Matcher()
    m.register(lambda x: ({} if isinstance(x, ast.Void) else None),
               default_void_generator)
    m.register(lambda x: ({} if isinstance(x, str) else None),
               default_str_generator)
    m.register(lambda x: ({} if isinstance(x, ast.Op) else None),
               default_op_generator)
    m.register(woop, header_generator)
    # m.register(woop_par, paragraphs_generator)

    m.register("*em*", emphasis_generator)
    m.register("* bullet_point", ulist_generator)
    m.register("# bullet_point", olist_generator)
    m.register("[body]", bracket_generator)
    m.register("{body}", eval_generator)
    m.register("x<f>y", eval2_generator)
    m.register("<f>y", eval2_generator)
    m.register("x<f>", eval2_generator)

    m.register(woop_par, paragraph_generator)

    # e.matcher.register("a - b", woop2)
    # e.matcher.register("*/a - b*", woop2)
    # e.matcher.register(lambda x: {}, woop3)

    # return m(x).generate_html()

    documents = {'main': TextDocument(),
                 'sections': SectionsDocument()}
    documents = execute_documents(m(x), documents)

    rval = [d for d in documents if isinstance(d, TextDocument)]

    return rval[0].data








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
    count = 0
    while candidates:
        count += 1
        if count > len(candidates):
            # If we get here, it means we looped through all
            # candidates without changing anything.
            raise Exception("There are cycles in the topological ordering. (0)")
        candidate = candidates.pop(0)
        if candidate in done:
            continue
        pred[candidate] -= done
        if pred[candidate]:
            # There are still predecessors for this node that haven't
            # been processed yet, so we add it back at the end.
            candidates.append(candidate)
        else:
            # All predecessors are cleared, so we add this node to the
            # results and we consider its successors as candidates.
            count = 0
            results.append(candidate)
            done.add(candidate)
            candidates += list(succ[candidate])

    if len(results) < len(pred):
        # There is some connected group where all nodes have incoming
        # edges (must be a cycle).
        raise Exception("There are cycles in the topological ordering. (1)")

    return results

