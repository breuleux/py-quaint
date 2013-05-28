

import re
from .operparse import (
    SubTokenizer, Tokenizer, Token, Void, SyntaxError,
    FixityDisambiguator, Alternator, Location
    )
from .operparse.parse import Operator, operator_parse


################
### Tokenize ###
################

# Characters that define operators
chr_op = r"""
+ - * / ^ = % # $ @ & |
""".split()

all_op = chr_op + r"""
< > ! ? : , ; ~ \n [ ] { }
""".split()

def rx_choice(chars, negate = False):
    return "[" + ("^" if negate else "") + "".join(map(re.escape, chars)) + "]"

def rx_without(oper, banned):
    rx = "(" + oper + ")($|" + rx_choice(banned, True) + ")"
    return re.compile(rx)


whitespace_re = re.compile("[ ~]*")

def extract_indent(match):
    s = match.group(0)
    return len(s.split("\n")[-1])

def subtok_rule(chrs, rxp, fields, span = 0, ws = True):
    if isinstance(rxp, str):
        rxp = re.compile("(" + rxp + ")")
    if isinstance(fields, list):
        return (chrs, rxp, span, ws, [fields[0], "!wsb", "!wsa"] + fields[1:])
    else:
        return (chrs, rxp, span, ws, fields)


standard_matchers = [

    # Operators

    # Brackets
    subtok_rule("[{", "[\\[\\{]", ["prefix", 0]),
    subtok_rule("]}", "[\\]\\}]", ["suffix", 0]),

    # Predefined operators
    subtok_rule(",", ",+", ["infix", 0]),
    subtok_rule(";", ";+", ["infix", 0]),
    subtok_rule(":", ":+", ["infix", 0]),
    subtok_rule("!?", "[!?]+", ["?fix", 0]),
    
    # Generic
    subtok_rule(chr_op, rx_choice(chr_op) + "+", ["?fix", 0]),

    # subtok_rule(["~"] + chr_op,
    #             "(~*)(" + rx_choice(chr_op) + "+)(~*)", generic_operator),

    # subtok_rule("~", "~+" + rx_choice(chr_op) + "+", ["phase2", "prefix", 0]),
    # subtok_rule(chr_op, rx_choice(chr_op) + "+~+", ["phase2", "suffix", 0]),
    # subtok_rule(chr_op, rx_choice(chr_op) + "+", ["phase2", "?fix", 0]),

    # # {}
    # subtok_rule("~", "~+\\{", ["prefix", 0]),
    # subtok_rule("}", "\\}~+", ["suffix", 0]),
    # subtok_rule("{", "\\{", ["?fix", 0]),
    # subtok_rule("}", "\\}", ["?fix", 0]),

    # # Tilde
    # subtok_rule("~", "~+", ["infix", 0]),

    #line breaks
    subtok_rule("\n", "(?:\n *){2,}", ["infix", "INDENT", "wide", extract_indent]),
    subtok_rule("\n", "(?:\n *)", ["infix", "INDENT", "short", extract_indent]),

    # Rest
    subtok_rule(True, rx_choice(all_op, negate = True)
                + "+", ["id", -1]),

    # Don't put anything here. It won't be reached.
]




# standard_matchers = [

#     # Operators

#     # []
#     subtok_rule("[", "\\[", ["prefix", 0]),
#     subtok_rule("]", "\\]", ["suffix", 0]),
    
#     # Generic
#     subtok_rule("~", "~+" + rx_choice(chr_op) + "+", ["prefix", 0]),
#     subtok_rule(chr_op, rx_choice(chr_op) + "+~+", ["suffix", 0]),
#     subtok_rule(chr_op, rx_choice(chr_op) + "+", ["?fix", 0]),

#     # {}
#     subtok_rule("~", "~+\\{", ["prefix", 0]),
#     subtok_rule("}", "\\}~+", ["suffix", 0]),
#     subtok_rule("{", "\\{", ["?fix", 0]),
#     subtok_rule("}", "\\}", ["?fix", 0]),

#     # Tilde
#     subtok_rule("~", "~+", ["infix", 0]),

#     #line breaks
#     subtok_rule("\n", "(?:\n *)+", ["infix", "INDENT", extract_indent]),

#     # Rest
#     subtok_rule(True, rx_choice(chr_op + list(" ~\n[]{}"), negate = True)
#                 + "+", ["id", 0]),

#     # Don't put anything here. It won't be reached.
# ]

subtok_normal = SubTokenizer(
    standard_matchers,
    whitespace_re)


class AdjustLocations:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.source = tokenizer.source

    def __iter__(self):
        for token in self.tokenizer:
            if token[0] in ('id', 'nullary'):
                loc = token.location
                token.location = Location(loc.source, (loc.start - len(token[1]),
                                                       loc.end + len(token[2])))
            yield token


class AdjustIndentChanges:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.source = tokenizer.source

    def __iter__(self):
        last_indent = 0
        for token in self.tokenizer:
            if token[0] == 'infix' and token[3] == 'INDENT':
                indent = token[5]
                if indent > last_indent:
                    token[4] = 'wide'
                last_indent = indent
            yield token



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



def make_operators(tokenizer):

    for token in tokenizer:
        if not isinstance(token, Token):
            yield token
            continue
        kind = token[0]
        loc = token.location
        if kind.endswith('fix'):
            oper = ((kind, 'wide' if token[1] or token[2] else 'short')
                    + tuple(token.args[3:]))
            if kind == 'prefix':
                l, r = None, oper
            elif kind == 'suffix':
                l, r = oper, None
            elif kind == 'infix':
                l, r = oper, oper
            yield Operator(l, r, location = loc)
        else:
            yield token


def tokenize(source):
    t = Tokenizer(source, dict(normal = subtok_normal))
    t = FixityDisambiguator(t)
    t = AdjustLocations(t)
    t = AdjustIndentChanges(t)
    # t = tokenizer_plus_indent(t)
    t = Alternator(t, Token(None, "void"), Token(None, "infix", ""))
    return t




def bracket_match(op1, op2):
    if not op1 or not op2:
        return False
    a, b = op1[2], op2[2]
    return (a, b) in (('(', ')'),
                      ('[', ']'),
                      ('{', '}'))


def is_multiline_operator(op):
    try:
        return (op[3] == 'INDENT' or op[3] in '[{}]')
    except IndexError:
        return False


def get_priority(op):
    if op is None:
        return (1000, 'l')
    if op[2] in list('[{}]'):
        # Brackets
        return (0, 'l')
    elif op[2] == "INDENT":
        # Line breaks
        return (10
                + op[4] * 1e-9
                + (1e-10 if op[3] == 'short' else 0),
                'a')
    elif not op[2]:
        # Juxtaposition (words)
        return (30, 'a?l')
    else:
        return (20, 'a?r')


def order(left, right):
    if bracket_match(left, right):
        return 'a'
    p1, a1 = get_priority(left)
    p2, a2 = get_priority(right)
    if p1 > p2:
        return 'l'
    elif p1 < p2:
        return 'r'
    elif a1.startswith('a?'):
        if left == right:
            return 'a'
        else:
            return a1.split("?")[-1]
    else:
        return a1


def parse(source):
    t = tokenize(source)
    # t = pack_tokens(t, is_multiline_operator)
    t = list(make_operators(t))
    # for x in t:
    #     print(x)
    p = operator_parse(iter(t), order)
    # print(p)
    return make_ast(p)

class quaintstr(str):
    def __init__(self, s, location = None):
        super().__init__(s)
        self.location = location

class ASTNode:
    def __init__(self, name, *args, location = None):
        self.name = name
        self.args = list(args)
        self.location = location
    def __getitem__(self, i):
        return self.args[i]
    def __setitem__(self, i, value):
        self.args[i] = value
    def __str__(self):
        return '#{0.name}{0.args!r}'.format(self)
    def __repr__(self):
        return str(self)
    def __descr__(self, descr):
        name = self.name
        return [(({"@ASTNode", "+"+name, "object"},)
                 + tuple(descr(x) for x in self.args))]


class ASTBuilder:
    def __getattr__(self, name):
        def build(*args, location = None):
            return ASTNode(name, *args, location = location)
        return build

ast = ASTBuilder()



def op_to_str(op):
    if op.left_facing is None:
        return op.right_facing[2]
    else:
        return op.left_facing[2]


def is_prefix(x):
    return (isinstance(x, ASTNode)
            and x.name == 'oper'
            and isinstance(x[1], ASTNode)
            and x[1].name == 'void')


def reprocess(arg):
    if isinstance(arg, (ASTNode, quaintstr)):
        return arg
    else:
        pass



def begin(*args):
    if len(args) == 1:
        return args[0]
    else:
        return ast.begin(*args)



def make_ast(parse_tree):

    if isinstance(parse_tree, Token):
        if parse_tree[0] == 'id':
            s = quaintstr(parse_tree[3])
        elif parse_tree[0] == 'void':
            s = ast.void()
        elif parse_tree[0] == 'nullary':
            s = ast.nullary(parse_tree[3])
        else:
            raise Exception
        s.location = parse_tree.location
        return s

    _op, *args = parse_tree

    if isinstance(_op, list):
        loc = sum(x.location for x in _op)
        op = [op_to_str(x) for x in _op]
    else:
        loc = _op.location
        op = [op_to_str(_op)]
        _op = [_op]

    args = [make_ast(x) for x in args]

    if op == ['[', ']']:
        args = list(map(reprocess, args))
        r = reprocess(args[1])

    elif op == ['{', '}']:
        args = list(map(reprocess, args))
        r = ast.curly(args[1])

    # elif all(x == '' for x in op):
    #     r = ast.juxt(*args)

    elif all(x == 'INDENT' for x in op):
        if len(args) > 1:
            first, second, *rest = args
            if first.location.linecol()[0][1] < second.location.linecol()[0][1]:
                if is_prefix(first):
                    r = ast.oper(first[0], first[1],
                                 begin(first[2], second, *rest))
                elif (isinstance(first, ASTNode)
                      and first.name == 'nullary'):
                    r = ast.oper(first[0], ast.void(),
                                 begin(second, *rest))
                else:
                    r = ast.oper(first, ast.void(),
                                 begin(second, *rest))
            else:
                r = begin(*args)
        else:
            r = args[0]

    else:
        # tokens = []
        # for op, arg in zip([None] + _op, args):
        #     if op is not None:
        #         tokens.append(op)
        #     if isinstance(arg, list):
        #         tokens += arg
        #     else:
        #         tokens.append(arg)
        # return tokens
        r = ast.oper(op[0], *args)

    loc += sum(x.location for x in args)
    r.location = loc
    return r
