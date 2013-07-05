
Generating markup
=================

It is very easy to generate markup. With the `.py.q extension, you can
embed Python code directly in a Quaint file.

Curly brackets `{...} can enclose either a Python expression or Python
definitions and statements.


Expressions
-----------

An expression can return any Python object. If the object is not a
string, it will be converted to one. For instance, 1 + 2 + 3 =
{1 + 2 + 3}. Here's a list: {[1, 1 + 1, "  xyz ".strip()]}.

Alternatively, it is possible to return Quaint _generators, which can
be built using primitives like `Raw, `Text, `Gen and more elaborate
constructors like `List or `Table~.

* `Raw produces unescaped text
  {show_and_run}:
    {Raw("<b>hello</b>")}

* `Text produces escaped text:
  {show_and_run}:
    {Text("<b>hello</b>")}

* `Gen puts pieces together:
  {show_and_run}:
    {Gen(Raw("<b>"), "hello", Raw("</b>"))}

Using `List and `Table you can easily generate content:

{show_and_run}:
  {List("one", "two", "three", ordered = True)}

{show_and_run}:
  {Table(*[[i * j for i in range(10)] for j in range(10)])}


Definitions
-----------

You can also embed definitions and statements, and any variables you
set will be available in subsequent expressions.

For instance, {x = "knock"} {x} {x} {x}. (In this particular instance,
however, it may be better to use the `[<-] operator, because it
preserves the syntax: [x <- knock] {x} {x} {x}).

As an exercise, try importing functions from a package and formatting
their documentation!


Operators
---------

The `[{f}: x] syntax applies the function defined by the expression `f
to the argument `x. To give a simple example:

{show_and_run}:
  {
    def sup(engine, node, x):
        return Gen(Raw("<sup>"), engine(x), Raw("</sup>"))
  }

I can now write {sup}:superscript.

A useful operator is `wrapper(...), which lets you wrap expressions
using arbitrary tags and classes. Exponents, {wrapper("sup")}:[for
instance]. Or {wrapper("a", href = "http://breuleux.net")}:[a link].

{wrapper("pre", classes = "some_class")}:
  Or a whole indented block.

The syntax only triggers if the left hand side of `[:] is a curly
bracket expression. What follows:

%
  word {sup}: arg1 arg2
  word [{sup}: arg1 arg2]
  word {sup}:arg notarg
  word {sup}:[arg1 arg2]

Produces what follows (notice whitespace patterns):

{wrapper("pre")}:
  word {sup}: arg1 arg2
  word [{sup}: arg1 arg2]
  word {sup}:arg notarg
  word {sup}:[arg1 arg2]


