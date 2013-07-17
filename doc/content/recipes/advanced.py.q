
{meta}:
    title: Advanced recipes
    author: Olivier Breuleux


The following will be useful to you if you want to really take
advantage of Quaint. Most code listed here embeds Python and should
therefore be placed in files with the `.py.q extension.

Also see __basic@@recipes/ and __expert@@recipes/expert recipes!

{toc}

Comments
--------

Use `[;;] for comments. Note that `[;;] works like a normal operator
(see the @@syntax), and comments out its right hand side.

.sar-60 ..
  {show_and_run}:
    It is public ;; and this is private
    that my favorite fruit is the ;;apple
    ;;banana cherry.
    ;;
      This entire paragraph
      is too scandalous to be shown.


Embedding HTML
--------------

You can embed raw HTML with `[{html}:] (and CSS with `[{css}:])

.sar-60 ..
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

.sar-60 ..
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
  [#anchor ..]Define anchors
  and [link to them]::anchor.


Including files
---------------

There is a simple command to include files relative to the current
file.

{show_and_run}:
  {include}: subdoc.q

Link@@recipes/subdoc to the included file.


Wrappers
--------

The `wrapper utility lets you construct generators that automatically
wrap their arguments in the tags of your choice. They also take care
of whitespace for you.

* The argument to wrap _must be called `expr.
* If there is an argument named `other, it will be printed but not wrapped.

.sar-80 ..
  {show_and_run}:
    {engine["maybe other ^ expr"] = wrapper("sup")}
    3^2 + 4^2 = 5^2

For the above, remember that `maybe means that the left hand side
might be empty.

.sar-80 ..
  {show_and_run}:
    {engine["&* expr"]=wrapper("span",classes="reddish")}
    {css}: .reddish {color: #835}
    This is &*reddish and &*[__ bold reddish].

If your use case is more complex, you can always just write it
yourself. Here's an implementation of the above to get you started:

.sar-80 ..
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

.sar-60 ..
  {show_and_run}:
    {
      @link_type('wiki')
      def wiki_link(engine, node, text, link):
        return {'href':'//wikipedia.org/wiki/%s'
                       % link.raw()}
    }
    Most people eat ::wiki:pasta with
    [toothed utensils]::wiki:Fork.

The `text and `link arguments will be set to each other if one is
missing (by default, `text will be the body of the tag, so you don't
need to worry about it). Of course, if the syntax is not terse enough
for you, you can make it terser:

.sar-60 ..
  {show_and_run}:
    {engine['maybe text // link'] = wiki_link}
    Most people eat //pasta with
    [toothed utensils]//fork.

Note that you can make it produce pretty much any kind of tag. For
instance:

.sar-60 ..
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


YAML data
---------

You can define data structures using //YAML, which is sometimes
practical. The YAML document must define a dictionary, so that each
key/value pair in it will set an environment variable.

{show_and_run}:
  {yaml}:
    food:
      - potatoes
      - bananas
      - cakes
      - maple syrup
    people:
      - {name: Peter, age: 26}
      - {name: Hilda, age: 61}
      - {name: Homer, age: 4}

  {List(*food)}

  {
    Table(TableHeader("Name", "Age"),
          *[[p['name'], p['age']]
            for p in people])
  }

You can also load the data from a file or a URL. Here we load from
//JSON format (YAML, JSON and CSV//Comma-separated_values) are available.

The data can be a url or an absolute path, otherwise it is relative to
the source.

.sar-vstack ..
  {show_and_run}:
    data <= gross.json

    {
      Table(TableHeader("Rank", "Title", "Gross", "Year"),
            *[[i + 1, entry["Title"], entry["Gross"], entry["Year"]]
              for i, entry in enumerate(data[:10])])
    }



Quick templates
---------------

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
    Gen(*[engine(x, var = f)
          for f in food])
  }

