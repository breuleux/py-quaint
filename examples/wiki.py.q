
Custom links
============

You can define custom types for the `[text :: type : link] operator,
which is (among other things) used to embed images. For instance,
the following code:

{show_as_and_run("python")}:
  {
    @link_type('wiki')
    def wiki_link(engine, node, text, link):
      return {'href': 'http://wikipedia.org/wiki/%s' % link.raw()}
  }

Allows you to easily link to wikipedia articles:

* `[::wiki:Fox] or `[Fox::wiki:] produce ::wiki:Fox.

* `[[Toothed utensil]::wiki:Fork] produces [Toothed utensil]::wiki:Fork.

You can also define some other operator as a shortcut; the argument
names _must be `text and `link (regardless of the names given in the
definition of `wiki_link):

{show_as_and_run("python")}:
  {
    engine['maybe text / link'] = wiki_link
  }

* `[/Bangkok] produces /Bangkok.

* `[[Dihydrogen monoxide]/Water] produces [Dihydrogen monoxide]/Water.

