
{html}:[<!DOCTYPE html>]
html ..

  head ..
    meta [http-equiv = Content-type] [content = text/html; charset=UTF-8] ..
    {insert_document}: xlinks
    title ..
      {meta}: title
    {insert_document}: css

  body ..
    {
      engine["maybe text @@ shed1 link"] = site_link
    }
    #nav ..
      logo <- {Raw("<img src='%sassets/media/quaint.png' alt='Quaint'/>" % siteroot)}
      .navlink #name .. Quaint @@ index
      #logo .. {logo} @@ index
      .navlink #doc .. Doc @@ documentation
      .navlink #recipes .. Recipes @@ recipes/
      .navlink #source .. Source::https://github.com/breuleux/quaint

    h1 .title ..
      {meta}: title

    #main ..
      {insert_document}: main

    #foot ..
      .footlink ..
        {ghurl = "https://raw.github.com/breuleux/quaint/master/"}
        {ghdocurl = "https://raw.github.com/breuleux/quaint/master/doc/content/"}
        {
          GenFrom('meta', lambda d: ('<a href="%s%s">Source for this file</a>'
                                     % (ghdocurl, d['realpath'])))
        }

    {insert_document}: js
    {insert_document}: errors
