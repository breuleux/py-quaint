
html ..

  head ..
    meta [http-equiv = Content-type] [content = [text/html; charset=UTF-8]] ..
    {insert_document}: xlinks
    title ..
      {meta}: title
    {insert_document}: css

  body ..
    div #main ..
      {insert_document}: main
    {insert_document}: errors
    {insert_document}: js
