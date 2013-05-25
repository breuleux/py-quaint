

import re
from .operparse import (
    SubTokenizer, Tokenizer, subtok_rule, Token, Void, SyntaxError
    )


################
### Tokenize ###
################

# Characters that define operators
chr_op = r"""
+ - * / ^ < > = : % # $ @ & | ! ?
""".split()


def rx_choice(chars, negate = False):
    return "[" + ("^" if negate else "") + "".join(map(re.escape, chars)) + "]"

def rx_without(oper, banned):
    rx = "(" + oper + ")($|" + rx_choice(banned, True) + ")"
    return re.compile(rx)


whitespace_re = re.compile(" *(;[^\n]*)?")

def extract_indent(match):
    return len(match.split("\n")[-1])


standard_matchers = [

    # Operators

    # []
    subtok_rule("[", "\\[", ["prefix", 0]),
    subtok_rule("]", "\\]", ["suffix", 0]),
    
    # Generic
    subtok_rule("~", "~+" + rx_choice(chr_op) + "+", ["prefix", 0]),
    subtok_rule(chr_op, rx_choice(chr_op) + "+~+", ["suffix", 0]),
    subtok_rule(chr_op, rx_choice(chr_op) + "+", ["?fix", 0]),

    # {}
    subtok_rule("~", "~+\\{", ["prefix", 0]),
    subtok_rule("}", "\\}~+", ["suffix", 0]),
    subtok_rule("{", "\\{", ["?fix", 0]),
    subtok_rule("}", "\\}", ["?fix", 0]),

    # Tilde
    subtok_rule("~", "~+", ["infix", 0]),

    #line breaks
    subtok_rule("\n", "(?:\n *)+", ["infix", "INDENT", extract_indent]),

    # Rest
    subtok_rule(True, rx_choice(chr_op + list(" ~\n[]{}"), negate = True)
                + "+", ["id", "id", 0]),

    # Don't put anything here. It won't be reached.
]

subtok_normal = SubTokenizer(
    standard_matchers,
    whitespace_re)

def tokenizer_plus_indent(tokenizer):
    indent_stack = []
    current_indent = 0
    for tok in tokenizer:
        if tok.args[0] == 'INDENT':
            indent = tok.args[1]
            if indent > current_indent:
                indent_stack.append(current_indent)
                yield Token("infix", [''], (0, 0), loc = tok.loc)
                yield Token("id", [Void], (0, 0), loc = tok.loc)
                yield Token("prefix", ['('], (0, 0), loc = tok.loc)
                current_indent = indent
            elif indent < current_indent:
                first = True
                while indent_stack:
                    previous_indent = indent_stack.pop()
                    if not first:
                        yield Token("id", [Void], (0, 0), loc = tok.loc)
                    else:
                        first = False
                    yield Token("suffix", [')'], (0, 0), loc = tok.loc)
                    if indent == previous_indent:
                        break
                yield Token("id", [Void], (0, 0), loc = tok.loc)
                yield Token("infix", ['NL', 0], tok.ws, loc = tok.loc)
                if indent != previous_indent:
                    raise SyntaxError["indent_mismatch"](
                        token = tok,
                        indent = indent,
                        indent_above = current_indent,
                        indent_below = previous_indent)
                current_indent = previous_indent
            else:
                yield Token("infix", ['NL', 0], tok.ws, loc = tok.loc)
        else:
            yield tok

def tokenize(source):
    t = Tokenizer(source, dict(normal = subtok_normal))
    t = tokenizer_plus_indent(t)
    return t




