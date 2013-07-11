
html ..

  head ..
    meta [http-equiv = Content-type] [content = [text/html; charset=UTF-8]] ..
    {insert_document}: xlinks
    title ..
      {meta}: title
    {insert_document}: css

  body ..

    #nav ..
      logo <- {Raw("<img src='%s/theme/media/logo.png' height=80px />" % siteroot)}
      #logo .. {logo}::{siteroot + "index.html"}
      .navlink #doc .. Doc::{siteroot + "documentation.html"}
      .navlink #source .. Source::https://github.com/breuleux/quaint

    h1 .title ..
      {meta}: title

    .body ..
      #main ..
        .buffer ..
        {insert_document}: main

    #foot ..
      .footlink ..
        {ghdocurl = "https://raw.github.com/breuleux/quaint/master/doc/content/"}
        {
          GenFrom('meta', lambda d: ('<a href="%s%s">Source for this file</a>'
                                     % (ghdocurl, d['path'])))
        }

    {insert_document}: js
    {insert_document}: errors

