
{meta}:
    title: Expert recipes
    author: Olivier Breuleux


{toc}

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


