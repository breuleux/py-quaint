
{meta}:
    title: Recipes
    author: Olivier Breuleux


{use_asset}: script/tabs.js
{js}:
    convert_all_tabdivs("tabbed");

See also __advanced@@recipes/advanced and __expert@@recipes/expert
recipes!

{toc}

Basic markup
------------

Notice the use of `[[]] in order to group words together.

{show_and_run}:
  _Emphasis and __[strong emphasis].
  A link to Google::http://google.com.
  Some `typewriter text.

{show_and_run}:
  _ You can emphasize whole lines.

  __
    You can also emphasize
    whole paragraphs!

Operators can be escaped with \\. The \~ character, if unescaped,
counts as whitespace, but is omitted from output.

{show_and_run}:
  No \_emphasis here.
  No~spaces~here~because~of\~.
  Two ways of em[_pha]sis in
  the middle of a syl~_la~ble.

You can define a label standing in for a link, and define the link
associated to the label later:

{show_and_run}:
  Link::?x and [link more!]::?x
  ?x :: #lists

You can parametrize links with variables if you use `[::=] instead of
`[::]

.sar-vstack ..
  {show_and_run}:
    {root = "http://breuleux.net/quaint"}
    [Link to documentation]::={root}/documentation.html


Lists
-----

.tabbed ..
  ..
    .. Bullets
    .. Numbered
    .. From number
    .. Alpha
    .. Roman
  ..
    ..
      {show_and_run}:
      
        * Bullet
        * Points
          * And sub-points as well.
            They can span multiple lines
            with proper indent.

    ..      
      {show_and_run}:
      
        # One
        # Two
        # Three
      
    ..
      {show_and_run}:
      
        8 # Eight
        . # Nine
        . # Ten
      
    ..
      {show_and_run}:
      
        A # A
        . # Bee
        . # Cee
      
    ..
      {show_and_run}:
      
        i # eye
        . # eye eye
        . # eye eye eye
        . # eye vee


Headers
-------

I won't show you these ones because the display would be screwy and the
table of contents would be ruined.

%

  Largest header (h1)
  ===================

  Almost largest (h2)  
  -------------------

  = h1
  == h2
  === h3
  ==== h4
  ===== h5
  ====== h6


Tables
------

{show_and_run}:

  + Name      + Grade +
  | John      | 95%   |
  | Catherine | 75%   |
  | Bobby     | 61%   |


Code
----

Inline:

{show_and_run}:
  `[This is plain].
  This is Python:
  python`[print("hello!")]

Blocks:

{show_and_run}:
  ruby %
    def fib(n)
        if n <= 1
            n
        else
            fib(n - 1) + fib(n - 2)
        end
    end


Quotes
------

{show_and_run}:

  >> Quoting without credit

  someone >> Quoting someone

  >>
    Quoting a
    whole paragraph
    Einstein >> Quoting someone
      more interesting


Definitions
-----------

{show_and_run}:
  Term := Definition
  Other term :=
    Other definition

