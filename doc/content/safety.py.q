
{meta}:
  title: Safe engines
  author: Olivier Breuleux


A Quaint file typically allows embedding and executing arbitrary
Python code, as well as generating pages that contain arbitrary HTML,
CSS and JavaScript. If you were to use Quaint to, say, format comments
in a comment system, that would be unacceptable, so I'm going to
explain how to make your own safe engine from scratch.


Creating a safe engine
======================

The engine is what determines what functionality to apply for certain
operators and it is an optional argument to `full_html and `site.

First create a "barebones" engine:

python %
  from quaint import builders
  engine = builders.bare_engine()

A bare engine contains default logic that will reproduce the input
pretty much verbatim -- it will wrap paragraphs with `[<div>] tags and
it will ignore square brackets, but that's about it. All text will be
escaped properly, so it is perfectly safe.

It is then up to you to add functionality.


== Safe

python %
    from quaint import lib
    engine['_ expr'] = lib.em # = wrapper('em')
    engine['__ expr'] = lib.strong # = wrapper('strong')
    engine['maybe other ^ expr'] = wrapper('sup')

`wrapper(tag, **attributes) is safe to use, as long as `tag and the
attribute names are sanitized, and as long as the tag is safe (the
`script or `style tags shouldn't be available to untrusted content!)

python %
    from quaint import ast, builders
    engine.register(builders.test_sequence_of('=', ast.BlockOp), lib.header1, '=')

Use `builders.test_sequence_of(characters, cls) to test for
arbitrarily long sequences of characters. The last argument tells the
engine that the pattern certainly starts with `[=], so it can optimize
things a bit. `header1 through `header6 are safe.

python %
    engine['maybe lang ` shed1 code'] = lib.code
    engine['maybe lang % code'] = lib.code_block
    engine['text :: maybe shed1 link'] = lib.link
    engine['text :: type : maybe shed1 link'] = lib.special_link
    engine['text ::= maybe shed1 link'] = lib.elink
    engine['* item'] = lib.ulist
    engine['maybe start # item'] = lib.olist
    engine['term := definition'] = lib.dlist
    engine['+ row'] = lib.table_header
    engine['| row'] = lib.table_row
    engine['maybe source >> quote'] = lib.quote
    engine['maybe left ;; right'] = lib.ignore
    engine['cond ?? yes'] = lib.ifthenelse
    engine['cond ?? yes !! no'] = lib.ifthenelse

These are all safe too.

python %
    engine['{body}'] = lib.safe_eval
    engine['{f}: x'] = lib.safe_feval

`safe_eval(engine, node, body) will simply output
`engine.environment[body], so it is safe if everything in the
environment is non-confidential and is safe to print or generate. The
return string will be properly escaped, but be careful if there are
instances of `Generator.

Likewise, `safe_feval(engine, node, body) calls
`engine.environment[f](engine, node, x), which makes it as safe as the
least safe function in the environment.

All the functions in the environment of `bare_engine() are safe.

python %
    engine.extend_environment(
        meta = lib.meta,
        yaml = lib.yaml,
        json = lib.json)

These are functions you can safely make available. Quaint uses
`yaml.safe_load to load YAML, so there can't be any surprises.


== __Not safe

;;
  Safe now

  python %
      engine['text :: maybe link'] = lib.link
      engine['text :: type : maybe link'] = lib.special_link
  
  The current implementation of `link allows for arbitrary Python code
  execution because it checks if the right hand side is `{}, and if so,
  it evaluates it and takes the return value as the value of the link
  (it will do so even if `{} is not bound to anything in the engine!). I
  will fix that in time so that it can't do anything the engine won't
  allow, but right now you'll have to implement something safe yourself.

python %
    engine['maybe tag .. maybe body'] = lib.domnode

This does not sanitize tags, nor does it sanitize
attributes. Furthermore, some tags are dangerous. I will add the
sanitization eventually, and provide some customization (e.g. a tag
whitelist or blacklist). If you do it before me, please tell me about
it.

python %
    engine['{body}'] = lib.eval
    engine['{f}: x'] = lib.feval

No real need to explain why these two are not safe, but do remember
that Python is a very difficult language to sandbox. Even if
`engine.environment only gives access to apparently safe
functionality, there are so many holes to cover that you can't make
sure that untrusted code will stay in the box.

