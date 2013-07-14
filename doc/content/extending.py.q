
{meta}:
  title: Extending Quaint
  author: Olivier Breuleux


{toc}


Phases
======

Quaint processes a document in four phases:

Parsing :=
  Quaint creates a parse tree. This phase __[cannot be customized].

Generator building :=
  An _engine associates each node in the parse tree to a function that
  takes the engine and the node and returns a _generator. A generator
  is an object which can contribute to one or several documents.

Document generation :=

  * Several _documents are created (html, css, js, sections, xlinks,
    links, errors, etc.).
  * All generators are consulted for _dependencies. For instance,
    perhaps some generator needs to consult the _references document
    in order to append a citation to the _html document.
  * For each document, each generator may contribute to the document.

Assembly :=
  All documents are _assembled into the output file.

The __engine can be customized to add new operators. It is also
possible (but seldom necessary) to define custom generators and custom
document types.


Customizing the engine
======================

The engine can be personalized by associating _patterns to
_handlers. Here is a simple example that makes the `[%%] operator to
swap its operands (which it will do poorly, because it does not adjust
for whitespace).

python %
  def swap(engine, node, left, right):
      return Gen(engine(right), engine(left))

  engine['left %% right'] = swap

As explained previously, you cannot customize the _parsing of Quaint
markup. The language already identified applications of `[%%], but it
lets you tell it what to do with them. This allows you to define new
functionality swiftly and without being bothered by -- you know how it
is -- tedious, blundering attempts to define its syntax coherently.

Let's go over the arguments of the function:

  `engine :=
    The handler is given the engine so that it may apply it to its
    other arguments. In `swap, we apply it to `right and `left so that
    further rules may be triggered.

  `node :=
    The node the engine was applied to and matched the pattern.
    Normally, this will be an operator node. If so:

    * `node.args: list of the node's arguments
    * `node.operator: the operator string (here it would be `[%%])
    * `node.raw(): yields the source code that generated this node
      but without surrounding whitespace
      * Tip: `source(node) will also give you the source, but with
        whitespace.
    * `node.whitespace_left: the string of whitespace left of the
      application
    * `node.whitespace_right: the string of whitespace right of the
      application

  `left :=
    This is a part of the node extracted by the pattern.
    In `swap this is the same as `node.args[0].

  `right :=
    This is a part of the node extracted by the pattern.
    In `swap this is the same as `node.args[1].


== Generators

Unless specified otherwise, all generators generate text to the _html
document. Using the generators below, you should be able to implement
most simple functionality easily.


=== Basic generators

`Raw(x) :=
  Generates the string `x _unescaped. If `x contains HTML tags and the
  like, they will be passed along.

`Text(x) :=
  Escapes the string `x using `cgi.escape.

`Gen(x, y, ...) :=
  Generates each of its arguments.

`x when `x is not an instance of `Generator :=
  Same as `Text(str(string))

=== Other generators

`List(x, y, ..., [ordered = False]) :=
  Generate a bullet list of `x, `y, etc. `ordered is a keyword
  argument. If False, the list will be unordered (`[<ul>]),
  else it will be ordered (`[<ol>]).

`Definitions((term1, def1), ...) :=
  Generate a definition list (term1 with definition def1, etc.)
  using `[<dl>], `[<dt>], `[<dd>].

`Table(row1, row2, ...) :=
  Generate a table with the given rows. Each row is either a list or
  tuple of generators (one for each column) or an instance of
  `TableHeader (which generates table headers).

=== Cross-document generators

Normally, generators append to the _html document. `GenFor and
`GenFrom, on the other hand, allow you to stash and retrieve
information in special documents. Why? The basic idea is that there
are as many generation "phases" as there are documents, and the phases
are ordered according to what the generators declare that they need.

With these features, it is easy, for instance, to generate a table of
contents, even though the table comes _before the sections it lists:
each section generates _for the _sections document, populating it with
a hierarchy of sections and subsections (not all documents are text
documents). `toc on the other hand generates _from the sections
document (formatting it for display) and into the html document. Of
course this necessitates that the sections document be generated
first. So we do a first pass on all generators, asking for sections,
then we do a second pass, asking for html.

`GenFor(doc, x, ...) :=
  Generates `x and the arguments that follow in the document `doc.
  Semantics depend on the semantics of the document. For instance, the
  _css document requires a CSS string, whereas the _meta document
  requires a key and a value.

`GenFrom(doc, f) :=
  First, forces the document called `doc to be generated before the
  html document. Then, `f will be passed document `doc. It must return
  a string to append to the html document. For instance, a
  bibliography might generate from the _references document (which
  could be populated using `GenFor).


== Patterns

The pattern language is parsed like Quaint, which creates a kind of
mini parse tree. A leaf that's a word (alphanumeric, and _[no
underscores! Underscores are operators!]) will be interpreted as a
variable matching a subtree. Patterns can also be _specified using the
words `wide, `narrow, `line, `inline, `void and `maybe.

You can use square brackets in a pattern for grouping, but patterns
_[do not penetrate] square brackets. If a node contains `[]s, the
pattern may fail.

Here are a few examples of patterns and what they apply and don't
apply to:

{yaml}:
  pattern_examples:

    - - "/ x"
      - ["/x", "/ x"]
      - ["x/y", "x / y", "x/"]
      - ""

    - - "x / y"
      - ["x/y", "x / y"]
      - ["/ y", "x/"]
      - ""

    - - "x / y + z"
      - ["x/y+z", "x / y + z", "x / y+z"]
      - ["x / y", "x/y + z", "x / y - z"]
      - ""
    
    - - "maybe x / y"
      - ["x/y", "x / y", "/y"]
      - ["x/"]
      - "`x may be absent, but `y must be present"
    
    - - "wide [x / y]"
      - ["x / y"]
      - ["x/y", "[x / y]"]
      - "`[]s are necessary so that `wide applies to the whole expression and not just to `x."
    
    - - "narrow [x / y]"
      - ["x/y"]
      - ["x / y", "[x / y]"]
      - ""

    - - "[[x / y]]"
      - ["[x / y]"]
      - ["x / y"]
      - ""
    
    - - "void x / y"
      - ["/y"]
      - ["x/y"]
      - ""
    
    - - "x / wide y"
      - ["x / y + z", "x / y / z"]
      - ["x / y+z"]
      - The `wide instruction applies to `y

{css}:
  .pattx {padding-left: 5px; padding-right: 5px; border: 1px solid #888}

{
  def w(x):
    return '<code class="pattx">%s</code>' % cgi.escape(x)
}

{
  Table(TableHeader("Pattern", "Applies to", "Does not apply to"),
        *[(Raw(w(repr(p))),
           Raw(" ".join([w(x) for x in app])),
           Raw(" ".join([w(x) for x in noapp])))
          for p, app, noapp, comment in pattern_examples])
}

The pattern can also be

* A type. There's a match if `instanceof(node, type) is True.

* A function taking a node and returning either None (no match), or a
  dictionary mapping variable names to parts of the node (the
  dictionary can be empty).


Where to write extensions
=========================

You have two major choices here:

* __Embed your extensions in a Quaint file. The extension should be
  `[.py.q] to indicate the file may execute arbitrary code.

* Write your extensions in a __[separate file] and tell Quaint to
  include it.

With the first option, simply enclose your Python code in [`{}]s. The
source file that produced this page (link at the bottom) contains a
few examples.

If you make a separate file or module, it should define a function
called `quaint_extend(engine). Here's example code:


python %
  from quaint.lib import Raw, Gen, wrap_whitespace

  def swap(engine, node, left, right):
      return Gen(engine(right), engine(left))

  @wrap_whitespace
  def sup(engine, node, left, right):
      return Gen(engine(left), Raw("<sup>"), engine(right), Raw("</sup>"))

  def quaint_extend(engine):
      engine['left %% right'] = swap
      engine['maybe left ^ right'] = sup
      engine.extend_environment(x = "banana")

Its meaning should be straightforward, save for a few things...

* python`[@wrap_whitespace] is a handy decorator that will take care
  of whitespace for you. It is recommended to use it for any operator
  that's meant to be used inline.

* python`engine.extend_environment(x = "banana") modifies the
  environment available to embedded code. It is equivalent to
  embedding python`{x = "banana"}. If this extension is loaded, `{x}
  will therefore generate "banana". Useful values and functions can be
  made available to embedded code that way.

__Loading your extension:

* On the __[command line], use the `-x option with the `quaint
  command.  If your extension is visible as a module, you can give the
  module path.

  bash %
    quaint html -x your_extension doc.q

  Separate the extension names with commas if you want to load more
  than one:

  bash %
    quaint html -x your_extension,other_extension doc.q

* In a __script:

  python %
    from quaint import full_html
    import your_extension
    html = full_html(open(file).read(),
                     extensions = [your_extension.quaint_extend])

* Quaint will only look for a function named `quaint_extend if it is
  given a _module. If you have a module `m containing an extension
  named `ext, you can use the flag like `[-x m.ext] to tell Quaint
  what function to use.

* If your extension takes additional arguments after `engine, they can
  be specified on the command line like `[-x
  'extension(arg1,arg2,...)'], or in a script by providing a tuple
  e.g. `[extensions = [(extension, [arg1, arg2, ...])]].
