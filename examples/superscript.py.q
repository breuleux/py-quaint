
Implementing superscript
========================

In a `[.py.q] document, the following code will implement the `[^]
operator so that it wraps its right hand side in `[<sup>] tags:

supcode <-
  {
    @wrap_whitespace
    def sup(engine, node, left, right):
      return Gen(engine(left), Raw("<sup>"), engine(right), Raw("</sup>"))
    engine['maybe left ^ right'] = sup
  }

{code_block(engine, None, "python", supcode)}

Clarifying the code:

* python`[@wrap_whitespace] ensures that the whitespace around the
  expression, if there is any, is kept. You can do it yourself too --
  the whitespace is available in `node.whitespace_left and
  `node.whitespace_right.

* `Gen generates each of its arguments.

* `Raw generates the given text without html escaping it (if you want
  to escape, use `Text).

* `engine(x) will call the engine recursively on the argument, so for
  instance if `x is a caret expression it will be wrapped too.

* Note that we only wrap the `right argument to `[^].

* python`[engine['maybe left ^ right'] = sup] extends the engine so
  that an expression like `x^y results in a call to
  python`[sup(engine, x^y, left = x, right = y)].
  
* In the pattern, `[maybe left] means that the argument `left might be
  empty. Otherwise the pattern will require a non-empty argument.

* The update to the engine will only kick in for the expressions that
  come after it.

Let's try it:


Before
------

3^2 + 4^2 = 5[^2]. ^[I can superscript whole sentences, too!]
Exponent t^o^w^e^r^s work splendidly. Write \\\^ to escape \^:
\^^\^^\^^\^^\^^\^


After
-----

{engine(supcode)}

3^2 + 4^2 = 5[^2]. ^[I can superscript whole sentences, too!]
Exponent t^o^w^e^r^s work splendidly. Write \\\^ to escape \^:
\^^\^^\^^\^^\^^\^


An even simpler way
-------------------

You can use the `wrapper function to create the above function
automatically. For instance, to define subscripts as `a_b (this will
not disable emphasis since emphasis requires `[_] in prefix position):

{show_as_and_run("python")}:
  {
    engine['lhs _ expr'] = wrapper('sub')
  }

A_ij = [sum_k](B_ik C_kj)

By convention the arguments must be named `lhs (optional argument) and
`expr (mandatory). `expr (here, the right hand side) is the one that
will be wrapped.

