
import cgi
import traceback
from .util import dedent
from .ast import source, source_nows
from collections import defaultdict


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
            if type == 'text/javascript':
                xlinks.append('<script type="{type}" src="{link}"></script>'.format(
                        type = type, link = link))
            else:
                xlinks.append('<link rel="{type}" href="{link}">'.format(
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



document_types = dict(
    html = HTMLDocument,
    css = CSSDocument,
    js = JSDocument,
    links = RepoDocument,
    xlinks = XLinksDocument,
    sections = SectionsDocument,
    meta = RepoDocument,
    errors = ErrorsDocument,
    files = RepoDocument,
    globalinfo = RepoDocument,
    )

def make_documents(*names, **others):
    docs = {}
    for name in names:
        docs[name] = document_types[name]()
    docs.update(others)
    return docs

def complete_documents(docs, *names, **others):
    docs = dict(docs)
    for name in names:
        if name not in docs:
            docs[name] = document_types[name]()
    for k, v in others.items():
        if k not in docs:
            docs[k] = v()
    return docs



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


