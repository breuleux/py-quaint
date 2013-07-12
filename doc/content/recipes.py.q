
{meta}:
    title: Recipes
    author: Olivier Breuleux


Here's a sizable number of recipes that you can use to perform common
tasks or automate them. Just copy/paste the code in a Quaint file with
extension `py.q.

{toc}

Comments
--------

Use `[;;] for comments. Note that `[;;] works like a normal operator
(see the ::q:syntax), and comments out its right hand side.

{show_and_run}:
  It is public ;; and this is private
  that my favorite fruit is the ;;apple ;;banana cherry.
  ;;
    This entire paragraph
    is too scandalous to be shown.


Embedding HTML
--------------

You can embed raw HTML with `[{html}:] (and CSS with `[{css}:])

{show_and_run}:
  {css}:
    .blue, .red, .green {margin: 10px;}
    .blue {border: 4px solid blue}
    .red {border: 4px solid red}
    .green {border: 4px solid green}
  {html}:
    <div class="blue" id="box1">
      <div class="red">
        Here's some <em>text!</em>
      </div>
      <div class="green">
        La la la
      </div>
    </div>

Of course, that's a bit tedious and you can't embed Quaint expressions
in it, so there's a better way:

{show_and_run}:
  .blue #box2 ..
    .red ..
      Here's some _text!
    .green ..
      La la la

By default the syntax creates `div elements, but you can override
that, e.g. `x[sup..2] -> x[sup..2].

* Be careful about white space: `[.red..xyz] will not work as intended
  because `[.] and `[..] are right associative, so you need to write
  `[.red .. xyz] or `[[.red]..xyz].

{show_and_run}:
  [#anchor ..]Define anchors and [link to them]::anchor.


Including files
---------------

There is a simple command to include files relative to the current
file.

{show_and_run}:
  {include}: subdoc.q

Link::q:subdoc to the included file.

__Tip: the `[__file__] environment variable contains the path of the
Quaint source file. Use `[engine.open(file)] to open a file in the
same directory.


Wrappers
--------

The `wrapper utility lets you construct generators that automatically
wrap their arguments in the tags of your choice. They also take care
of whitespace for you.

* The argument to wrap _must be called `expr.
* If there is an argument named `other, it will be printed but not wrapped.

{show_and_run}:
  {engine["maybe other ^ expr"] = wrapper("sup")}
  3^2 + 4^2 = 5^2

For the above, remember that `maybe means that the left hand side
might be empty.

{show_and_run}:
  {engine["&* expr"] = wrapper("span", classes = "reddish")}
  {css}: .reddish {color: #835}
  This is &*reddish and &*[__ bold reddish].

If your use case is more complex, you can always just write it
yourself. Here's an implementation of the above to get you started:

{show_and_run}:
  {
    @wrap_whitespace
    def reddish(engine, node, expr):
        return Gen(Markup('<span class="reddish">'),
                   engine(expr),
                   Markup('</span>'))
    engine["&** expr"] = reddish
  }
  {css}: .reddish {color: #835}
  This is also &**reddish and &**[__ bold reddish].


Link types
----------

To define your own kind of link, e.g. links to Wikipedia, you can hook
into the link syntax:

{show_and_run}:
  {
    @link_type('wiki')
    def wiki_link(engine, node, text, link):
      return {'href': 'http://wikipedia.org/wiki/%s' % link.raw()}
  }
  Most people eat ::wiki:pasta with [toothed utensils]::wiki:Fork.

The `text and `link arguments will be set to each other if one is
missing (by default, `text will be the body of the tag, so you don't
need to worry about it). Of course, if the syntax is not terse enough
for you, you can make it terser:

{show_and_run}:
  {engine['maybe text // link'] = wiki_link}
  Most people eat //pasta with [toothed utensils]//fork.

Note that you can make it produce pretty much any kind of tag. For
instance:

{show_and_run}:
  {
    @link_type('bold')
    def bold_link(engine, node, text, link):
      return {'tag': 'b', 'body': link.raw()}
  }
  We have a new way to do ::bold:emphasis.

By convention, this feature should only be used for links, images or
embedded media (youtube etc.) -- not for bold tags -- but it's not my
place to judge. Do remember to set `body to an empty string if you
don't want `text to show up in the tags.


Storing document parts
----------------------

`[var <- code] will put the parse tree of `code in the variable
`var. The engine will be automatically applied if you return the parse
tree in a `{} expression.

{show_and_run}:
  x <- _knock!
  {x} {x} {x}

You can embed Python code in the stored expression. Since it is not
executed immediately, you can use the engine to execute it multiple
times, with different values for the environment variables:

{show_and_run}:
  x <- I love {var}!
  {
    Gen(*[engine(x, var = thing)
          for thing in "potatoes bananas cakes".split()])
  }


Post-processing
---------------

In Quaint, the generation of a document or of multiple documents is
_staged. For instance, sections will register themselves before the
table of contents is generated, meta-information will be processed
before anything that needs it, and so on.

Here's how to list all of your document's meta-information:

{show_and_run}:
  {genfrom("meta")}:
    row <- | {key.capitalize()} | {value} |
    {
      AutoMerge([engine(row, key=key, value=value)
                 for key, value in sorted(meta.data.items())])
    }

`AutoMerge is needed to put the rows together (otherwise you will
create a different table for each row).

Note that this will work _even for meta-information that I define
_afterwards (I dare say that's the whole point of staging). Here I
define the "extra" key, but you see that it is listed above
regardless!

{show_and_run}:
  {meta}:
    extra: Extra, extra!

Better yet, if you do site generation, there will be a document called
`globalinfo containing the information of _all documents. Let's list
their titles:

{show_and_run}:
  {genfrom("globalinfo")}:
    row <- | {path} | {title}::{link} |
    {
      AutoMerge([engine(row,
                        path = path,
                        link = (siteroot
                                + path.replace('.py', '')
                                      .replace('.q', '.html')),
                        title = docs['meta'].get('title', "untitled"))
                 for path, docs in sorted(globalinfo.data.items())])
    }

Mind that the markup in a `[{genfrom(...)}:] block can only generate
to the _html document. You can't declare sections or meta-information
in there. If it fails, it won't do so gracefully either.

