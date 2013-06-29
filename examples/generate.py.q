
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

* `Raw produces unescaped text: {Raw("<b>hello</b>")}

* `Text produces escaped text: {Text("<b>hello</b>")}

* `Gen puts pieces together: {Gen(Raw("<b>"), Text("hello"), Raw("</b>"))}

Using `List and `Table you can easily generate content:

{List(Text("one"), Text("two"), Text("three"), ordered = True)}

{Table(*[[Text(i * j) for i in range(10)] for j in range(10)])}


Definitions
-----------

You can also embed definitions and statements, and any variables you
set will be available in subsequent expressions.

For instance, {x = "knock"} {x} {x} {x}. (In this particular instance,
however, it may be better to use the `[<-] operator, because it
preserves the syntax: [x <- knock] {x} {x} {x}).

As an exercise, try importing functions from a package and formatting
their documentation!


`[<>] Operators
---------------

The `[x <f> y] syntax applies the function defined by the expression
`f to the arguments `x and `y~. To give a simple example:

{
  def swap(engine, node, x, y):
      return Gen(engine(y), engine(x))
}

I can now [words <swap> swap], though white space is problematic in
this instance.

A useful operator is `wrapper(...), which lets you wrap expressions
using arbitrary tags and classes. Exponents,
<wrapper("sup")>[for instance]~. Or
[<wrapper("a", href = "http://breuleux.net")> a link].

<wrapper("pre", classes = "some_class")>
  Or a whole indented block.

Unless you define an indented block, try to keep the whole `[<>]
expression on a single line. If it still acts up, that might be
operator priority acting up, so try wrapping the argument and/or the
whole application in `[[]]~s.




