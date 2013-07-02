
Loading and formatting data
===========================

Quaint offers support for data in JSON or YAML formats. You can either
load a file into a variable using the `[<=] operator or include the
data directly in the file.


Reading files
-------------

In order to load data in YAML format from the file `data.yaml and put
it in the variable `data, either of these statements will work:

%
  data <= yaml:data.yaml
  data <= :data.yaml
  {data = pyyaml.safe_load(open("data.yaml").read())}

The first two methods translate to other formats, such as JSON, in a
straightforward manner. The third method depends on the library used
to parse the data, but it's good to keep in mind that you shouldn't
feel limited by the syntactical options Quaint offers as a
convenience. You can use straight Python if need be.

Once the data is loaded, you can format it:

python %
  {
    Table(TableHeader("Rank", "Title", "Gross", "Year"),
          *[[i + 1, entry["Title"], entry["Gross"], entry["Year"]]
            for i, entry in enumerate(data)])
  }

In action:

data <= :data.yaml
{
  Table(TableHeader("Rank", "Title", "Gross", "Year"),
        *[[i + 1, entry["Title"], entry["Gross"], entry["Year"]]
          for i, entry in enumerate(data)])
}


Embedding data
--------------

In some situations it can be practical to put the data directly in the
document.

The `[<yaml>] and `[<json>] directives let you embed YAML/JSON data as
an indented block below the directive. The caveat is this: each
top-level key/value pair sets the variable named by the key to the
value. For instance, the following:

%
  <json>
    {
      "grades": [
        {"Name": "Jason", "Grade": 94},
        {"Name": "Catherine", "Grade": 71},
        {"Name": "Robert", "Grade": 48}
      ],
      "something": 1234
    }

Will set the variable `grades to the list the key of the same name
maps to, and the variable `something to the number 1234. Again, these
variables can be used to build tables and whatnot:

python %
  {
    Table(*[[entry["Name"], entry["Grade"]]
            for entry in grades])
  }

Result:

<json>
  {
    "grades": [
      {"Name": "Jason", "Grade": 94},
      {"Name": "Catherine", "Grade": 71},
      {"Name": "Robert", "Grade": 48}
    ]
  }

{
  Table(*[[entry["Name"], entry["Grade"]]
          for entry in grades])
}
