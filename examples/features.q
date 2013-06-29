
Section
=======

_Emphasis, __[strong emphasis], emphasis on syl[_la]ble,
`verbatim. You will need [square brackets] around the argument if it
is more than one word.  Operator characters like \[, \] or \_ can be
escaped with \\.

The character \~ behaves like a space, but it is omitted from the
out~put, so you can highlight _syl~lables with it as well.


Subsection
----------

* A bullet point
  can span multiple lines.
  * And here's a subitem.

# Numbered list.

# Here's a table:

    + Name      + Grade +
    | John      | 95%   |
    | Catherine | 75%   |
    | Bobby     | 61%   |

# Here's some Ruby code:
    ruby %
      def fib(n)
          if n <= 1
              n
          else
              fib(n - 1) + fib(n - 2)
          end
      end


_ You can put emphasis on a whole line if there's whitespace after the
operator.

__
  Pretty much any operator can take an indented block. So this whole
  paragraph is in bold.

