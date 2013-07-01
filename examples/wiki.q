
Custom links
============

You can define custom types for the `[text @ type ! link] operator,
which is (among other things) used to embed images. For instance,
the following code:

python %
  {
    @link_type('wiki')
    def wiki_link(engine, node, text, link):
      return {'href': 'http://wikipedia.org/wiki/%s' % link.raw()}
  }

{
  @link_type('wiki')
  def wiki_link(engine, node, text, link):
    return {'href': 'http://wikipedia.org/wiki/%s' % link.raw()}
}

Allows you to easily link to wikipedia articles:

* `[Fox@wiki!] produces Fox@wiki!.

* `[[Toothed utensil]@wiki!Fork] produces [Toothed utensil]@wiki!Fork.

You can also define some other operator as a shortcut; the argument
names _must be `text and `link (regardless of the names given in the
definition of `wiki_link):

python %
  {
    engine['maybe text / link'] = wiki_link
  }

{
  engine['maybe text / link'] = wiki_link
}

* `[/Bangkok] produces /Bangkok.

* `[[Dihydrogen monoxide]/Water] produces [Dihydrogen monoxide]/Water.

