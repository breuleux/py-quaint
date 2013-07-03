

Syntax
======

Quaint's syntax is a simple operator based syntax. Each token is
either a _word or an _operator. Any sequence of one or more of the
following characters is a distinct operator:

{from quaint.parser import chr_op}
{Raw(" ".join(chr_op))}

For instance, `[+] is an operator, `[++] is an operator, `[/_%%] is an
operator, and so on. You can _escape an operator character or a
bracket with \\ (e.g. `[\%]).

{
  red = wrapper(style = "color: red; font-weight: bold")
  blue = wrapper(style = "color: blue; font-weight: bold")
}

Almost all operators behave the same. Consider the `[/] operator, for
instance. The `[/] operator take two arguments (left hand side and
right hand side). In the following example, in [<red> red], I
highlight the [<red> left hand side], and in [<blue> blue], I
highlight the [<blue> right hand side]. Sometimes, one of them will be
_void:

{
  # Did you think I was highlighting by hand? :)
  @wrap_whitespace
  def hl(engine, node, lhs, rhs):
      return Gen(Raw('<span class="lhs">'), source(lhs), Raw('</span>'),
                 Raw('<span class="oper">'), node.operator, Raw('</span>'),
                 Raw('<span class="rhs">'), source(rhs), Raw('</span>'))
  engine['maybe lhs / maybe rhs'] = hl

  def pre(engine, node, expr):
      return Gen(Raw('<div class="pre">'), node.operator, engine(expr), Raw('</div>'))
  engine['## expr'] = pre
}

<css>
  .lhs {color: red; font-weight: bold; white-space: pre}
  .rhs {color: blue; font-weight: bold; white-space: pre}
  .oper {color: black; font-weight: bold}
  .pre {white-space: pre; font-family: monospace}


Operators bind tighter if there is no whitespace around them (__note:
the (non-printing) `[~] character counts as whitespace).

  * cow potato car / spring grape
  * cow potato car/spring grape

Operators are __prefix when they are at the beginning of a line, right
after \[, or when the _[whitespace] is wider on the _left. Again,
tightness matters.

  * / cow potato car spring grape
  * /cow potato car spring grape
  * cow potato car /spring grape
  * cow potato /[car spring] grape
  * cow potato \[[/ car spring]\] grape

Operators are __suffix when they are at the beginning of a line, right
before \], or when the _[whitespace] is wider on the _right. Tightness
matters.

  * cow potato car spring grape /
  * cow potato car spring grape/
  * cow potato car/ spring grape
  * cow [potato car]/ spring grape
  * cow \[[potato car /]\] spring grape

Operators are __[right associative]. Observe how `[/] interacts with
the `[$$] operator (the `[$$] operator _[does nothing], but even so,
it is still part of the parse tree!).

  * cow $$ potato car / spring $$ grape
  * cow potato /car$$ spring grape
  * cow potato $$car/ spring grape

__[Indented blocks] are given to the operator if they encompass the
_whole line before the indented block. Look at this file's source to
understand the layout better.

Left hand side /
  right
  hand
  side

Left hand side / right
  hand
  side

/ All the lines
  of this paragraph
  are lumped together.

/
  The operator can also be on its own line.

## / However, the second and third lines in this paragraph are
     associated to `[##] even if they line up with `[/]. That's
     because it is `[##] and not `[/] that spans the whole first line!

A few __exceptions are made in order to satisfy typographical
expectations and reduce boilerplate.

* `[,] and `[:] cannot be suffix operators. `[a, b] and `[a: b] are
  therefore infix applications.

* When it is a suffix operator, `[.] has lower priority than
  normal. Notice that the dot is not blue after this /word. That's
  why. This is not true if `[.] is in /infix.position.

Besides these few exceptions, __[all operators behave like \/].


Paragraph operators
-------------------

A _[paragraph operator] is an operator which

* is the only token on its line, and
* is at least three characters long

These operators, instead of applying to words on their left or right,
apply to the whole paragraphs that lie above or below them. If you
imagine that a paragraph is a word and that blank lines are spaces,
they obey the same rules as normal operators. Let's highlight the
`[///] operator to see how that works:

{
  @wrap_whitespace
  def hl2(engine, node, lhs, rhs):
      return Gen(Raw('<span class="lhs">'), source(lhs).replace("  ", ""), Raw('</span>'),
                 Raw('<span class="oper">'), node.operator, Raw('</span>'),
                 Raw('<span class="rhs">'), source(rhs).replace("  ", ""), Raw('</span>'))

  engine['maybe lhs /// maybe rhs'] = hl2
}

<css>
  blockquote {font-family: monospace}

>>
  paragraph 1

  paragraph 2
  ///
  paragraph 3

  paragraph 4

>>
  paragraph 1

  paragraph 2

  ///

  paragraph 3

  paragraph 4

>>
  paragraph 1

  paragraph 2
  ///

  paragraph 3

  paragraph 4

>>
  paragraph 1

  paragraph 2

  ///
  paragraph 3

  paragraph 4


Brackets
--------

Brackets (`[[]], `{}, `() and `[<>]) work as you'd expect with a few
caveats.

* `() and `[<>] are not matched across lines. For instance, if `[(]
  and `[)] are found on different lines, they will be printed without
  problem, but they won't be matched to form a unit.

* An opening bracket will only match a closing bracket that's on a
  line with the same indent level. _[This can trip you].

  These brackets __[will not match]:
  %
    * We are _[best
      friends] forever!

  Neither will these (the curly ones):
  python %
    {def f(x):
         return x}

  While the first case is unfortunate, this rule stems from the idea
  that indented blocks are often used to contain source code from
  other languages, so it is best that they are self-contained units
  and unbalanced brackets are stopped cold at their boundaries.

  You can rewrite the previous two examples like this:
  %
    *
      We are _[best
      friends] forever!
  python %
    {def f(x):
         return x
    }

