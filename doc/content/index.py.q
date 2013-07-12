
{meta}:
  title: Quaint
  author: Olivier Breuleux


{toc}


What is Quaint?
===============

Quaint is a markup language loosely inspired from Markdown but focused
on _consistency and _extensibility. It is simple and intuitive enough
to be used by non-techies, but powerful enough for hackers to tailor
to their own individual needs.

* __Terse: Quaint does not get in your way. There is no boilerplate,
  no spurious markup. If you do something _[a lot], you can make it as
  short as you want. (Link to Wikipedia a lot? Four lines of Python
  will let you write /Batman to link to Batman's Wikipedia article).

* __Complete: all essential functionality (links, bullet points, etc.)
  is already built-in, plus a few _very useful extras (code
  highlighting using Pygments, tables).

* __[Embedded code]: you can embed Python code in a Quaint file (use
  the extension `.py.q). For instance, you can procedurally generate
  lists or tables, write and test new extensions in a single file,
  etc. That can come in handy to generate documentation!

* __Consistent: all markup operators follow the same rules with
  respect to priority, grouping, nesting, and so on. There is no mess
  of regular expressions, no unnecessary idiosyncracies. Custom
  operators and extensions are all used like the usual ones, so you
  only ever need to learn what they _do.

* __[Easy to extend]: create a function with the proper signature,
  associate it to any valid operator you like, and you're done. If
  what you want to do is trivial (e.g. add a superscript operator),
  its implementation will be trivial (a single line of code).

Quaint's file extension is `.q. As you might already have guessed, all
of this documentation is written in Quaint. At the bottom of each
page, there should be a link pointing to its source code.


Installing
==========

You can install the `quaint package through `pip or `easy-install.

bash %
  pip install quaint

This will install a command called `quaint, which you can try
immediately on an example (which we will fetch from the repository):

bash %
  wget https://raw.github.com/breuleux/quaint/master/doc/content/examples/features.q
  quaint html features.q -o features.html
  <your-favorite-browser> features.html


Using
=====

This is a primer on getting productive use out of Quaint in five
minutes, which glosses over advanced features and details.


To generate individual documents
--------------------------------

bash %
  quaint mydoc.q -o output.html -x "extension1, extension2(arg1, arg2)"

* A useful extension is `use_theme, which will make the output use the
  stylesheet contained in `theme/style/main.css relative to the
  current working directory and will enable the syntax
  `[::media:image.png] to link to the images you put in `theme/media.

  * `[-x use_theme(borkborkbork)] will fetch the theme in
    `borkborkbork/ instead of `theme/.

* Rename the file `mydoc.py.q if you want to embed Python code in it.


To generate a "site"
--------------------

As a convenience, Quaint also offers a command to recursively convert
all files in a directory, so you can make static sites of sorts with
multiple pages:

bash %
  quaint site content_dir -o output_dir

Each Quaint file will be associated to an HTML file and the document
structure will be preserved.

* If Quaint finds a file called `[@template.q] or `[@template.py.q],
  it will use it as a template to generate all the documents in the
  directory (and subdirectories, unless they contain their own
  template files). Example::{ghdocurl + "@template.py.q"}.


Programmatically
----------------

The following command:

bash %
  quaint html file.q -o out.html -x extension

Is equivalent to the following Python code:

python %
  from quaint import full_html
  html = full_html(open("file.q").read(), ['extension'])
  print(html, file = open("out.html", "w"))


Learn more
==========

* Look at examples::q:recipes/index. That's the best way to learn.

* Documentation::q:documentation (a bit more in-depth, but still a
  work in progress).

* Read [lib.py]::{ghurl + "quaint/lib.py"}. It's kinda messy and
  undocumented right now, but a lot of the functionality is defined
  there, and most code is straightforward, so it's a good starting
  point. As a rule of thumb, when you see functionality where the
  syntax is like `[{xyz}: abc] the definition of `xyz is probably
  in `lib.py.
