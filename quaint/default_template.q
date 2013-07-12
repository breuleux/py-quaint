
html ..

  head ..
    meta [http-equiv = Content-type] [content = [text/html; charset=UTF-8]] ..
    {insert_document}: xlinks
    title ..
      {meta}: title
    {insert_document}: css

  body ..
    {insert_document}: js
    div #main ..
      {insert_document}: main
    {insert_document}: errors
