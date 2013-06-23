

import re
from .operparse import (
    SubTokenizer, Tokenizer, Token, Void, SyntaxError,
    FixityDisambiguator, Alternator, Location, TokenizerWrapper,
    tokenizer_wrapper
    )
from .operparse.parse import Operator, operator_parse
from . import ast


################
### Tokenize ###
################

# Characters that define operators
chr_op = r"""
+ - * / ^ = < > % # $ @ & | ! ? : , ;
""".split()

all_op = chr_op + """
~ \n [ ] { }
""".split(" ") #+ [" "]

def rx_choice(chars, negate = False):
    return "[" + ("^" if negate else "") + "".join(map(re.escape, chars)) + "]"

def rx_without(oper, banned):
    rx = "(" + oper + ")($|" + rx_choice(banned, True) + ")"
    return re.compile(rx)


whitespace_re = re.compile("[ ~\n]*")

def wsb_length(match, wsb, wsa):
    return len(wsb)

def wsa_length(match, wsb, wsa):
    return len(wsa)

def extract_indent(match, wsb, wsa):
    s = match.group(0)
    return len(s.split("\n")[-1])

def mkre(rxp):
    if isinstance(rxp, str):
        rxp = re.compile("(" + rxp + ")")
    return rxp


def analyze_whitespace(wsb, wsa):
    s_wsb = wsb.split("\n")
    s_wsa = wsa.split("\n")
    return {"wsb": wsb,
            "wsa": wsa,
            "space_before": len(s_wsb[-1]),
            "space_after": len(s_wsa[0]),
            "height_before": len(s_wsb) - 1,
            "height_after": len(s_wsa) - 1}

def make_token(source, start, end, d):
    loc = Location(source, (start, end))
    token = Token(location = loc, **d)
    return token


def m_id(source, m, wsb, wsa):

    text = wsb + m.groups()[0] + wsa
    start, end = m.regs[0]
    start -= len(wsb)
    end += len(wsa)

    d = {"type": "id",
         "text": text,
         # "own_line": False,
         "line_operator": False}
    d.update(analyze_whitespace(wsb, wsa))

    return make_token(source, start, end, d), m.regs[0][1]


def m_operator(fixity):

    def f(source, m, wsb, wsa):
        text = m.groups()[0]
        start, end = m.regs[0]
        d = {"type": "operator",
             "fixity": fixity,
             "text": text}
        d.update(analyze_whitespace(wsb, wsa))

        token = make_token(source, start, end, d)
        token.line_operator = ((token.height_before > 0)
                               and (token.height_after > 0)
                               and (len(text) >= 3))
        # token.own_line = token.line_operator

        return token, m.regs[0][1]

    return f



standard_matchers = [

    # Brackets
    ("[{", mkre("[\\[\\{]"), True, m_operator("prefix")),
    ("]}", mkre("[\\]\\}]"), True, m_operator("suffix")),

    # Generic
    (chr_op, mkre(rx_choice(chr_op) + "+"), True, m_operator("?fix")),

    # Rest
    (True, mkre("(\\\\{chr}|{nochr})+".format(
                chr = rx_choice(all_op + [" "]),
                nochr = rx_choice(all_op + [" "], negate = True))),
     True, m_id),

    # (True, mkre(rx_choice(all_op, negate = True) + "*"
    #             + rx_choice(all_op + [" "], negate = True)),
    #  True, m_id),

    # Don't put anything here. It won't be reached.
]

subtok_normal = SubTokenizer(
    standard_matchers,
    whitespace_re)


@tokenizer_wrapper
def split_operators(tokenizer):
    for token in tokenizer:
        if token.type == 'operator' and not token.line_operator:
            loc = token.location
            for i, c in enumerate(token.text):
                t = Token(**token.__dict__)
                t.text = c
                t.location = Location(loc.source, (loc.start+i, loc.start+i+1))
                if c in [',', ';', '<', '>']:
                    t.fixity = 'infix'
                if i > 0:
                    t.space_before = t.height_before = 0
                    t.wsb = ""
                if i < len(token.text) -  1:
                    t.space_after = t.height_after = 0
                    t.wsa = ""
                yield t
        else:
            yield token

@tokenizer_wrapper
def adjust_locations(tokenizer):
    rightmost = 0
    for token in tokenizer:
        loc = token.location
        change = False

        if loc.start > loc.end:
            loc = Location(loc.source, (loc.start, loc.start))
            change = True
        if rightmost > loc.start:
            loc = Location(loc.source, (rightmost, loc.end))
            change = True

        if change:
            token.location = loc
            token.text = loc.get()

        rightmost = loc.end
        yield token

def sandwich(left, right, params):
    # TODO: change the locations of left and right
    # or maybe not.
    location = Location(left.location.source if left else right.location.source,
                        (left.location.end if left else right.location.start,
                         right.location.start if right else left.location.end))
    is_operator = params.get("type", None) == 'operator'
    return Token(location = location,
                 space_before = left.space_after if left else 0,
                 space_after = right.space_before if right else 0,
                 line_operator = is_operator and ((not left or left.height_after)
                                                  and (not right or right.height_before)),
                 height_before = left.height_after if left else 0,
                 height_after = right.height_before if right else 0,
                 wsb = left.wsa if left else "",
                 wsa = right.wsb if right else "",
                 **params)

@tokenizer_wrapper
def add_indent_and_linebreaks(tokenizer):
    current_indent = None
    indent_stack = []
    last = None
    to_sandwich = None
    ignore_if_lineop = False

    for token in tokenizer:
        if current_indent is None:
            current_indent = len(token.wsb.split("\n")[0])

        if to_sandwich:
            if (not ignore_if_lineop
                or ((not last or not last.line_operator)
                    and (not token or not token.line_operator))):
                yield sandwich(last, token, to_sandwich)

        to_sandwich = None
        ignore_if_lineop = False

        yield token

        if token.height_after > 0:
            indent = len(token.wsa.split("\n")[-1])
            if indent > current_indent:
                indent_stack.append(current_indent)
                current_indent = indent
                to_sandwich = dict(type = "operator",
                                   fixity = "infix",
                                   text = "I(")
            elif (indent < current_indent
                  and indent_stack
                  and indent <= indent_stack[-1]):
                current_indent = indent_stack.pop()
                to_sandwich = dict(type = "operator",
                                   fixity = "suffix",
                                   text = ")I")
            else:
                to_sandwich = dict(type = "operator",
                                   fixity = "infix",
                                   text = "")
                ignore_if_lineop = True

        last = token


    if to_sandwich:
        if (not ignore_if_lineop
            or (not last or last.type != "operator" or not last.line_operator)):
            yield sandwich(last, None, to_sandwich)



def inherent_fixity(tok):

    if tok.line_operator:
        wsl = tok.height_before - 1
        wsr = tok.height_after - 1
    else:
        wsl = tok.space_before if not tok.height_before else None
        wsr = tok.space_after if not tok.height_after else None

    if ((wsl is not None and wsr is not None)
        and ((wsl == wsr == 0) or (wsl > 0 and wsr > 0))):
        return "infix"
    elif wsl is None or wsl > 0:
        return "prefix"
    elif wsr is None or wsr > 0:
        return "suffix"
    else:
        raise Exception("Cannot determine fixity", tok)



def tokenize(source):
    t = Tokenizer(source, dict(normal = subtok_normal))
    t = add_indent_and_linebreaks(t)
    t = FixityDisambiguator(t, inherent_fixity, {})
    t = split_operators(t)
    t = Alternator(t,
                   Token(location = Location(t.source, (0, 0)),
                         fixity = "infix",
                         wsb = "",
                         wsa = "",
                         space_before = 0,
                         space_after = 0,
                         height_before = 0,
                         height_after = 0),
                   lambda l, r: sandwich(l, r, dict(type = "void")),
                   lambda l, r: sandwich(l, r, dict(type = "operator",
                                                    fixity = "infix",
                                                    text = "")))
    t = adjust_locations(t)
    return t 





def make_operators_1(tokenizer):

    p_immediate = (1000, 'l', None)

    priorities = {
        'I(': ((15, 'l', None), (0, 'l', [')I'])),
        ')I': ((0, 'l', ['[']), p_immediate),
        '[': (p_immediate, (0, 'l', [']'])),
        ']': ((0, 'l', ['[']), p_immediate),
        '{': (p_immediate, (0, 'l', ['}'])),
        '}': ((0, 'l', ['{']), p_immediate)
        }

    for token in tokenizer:
        if not isinstance(token, Token):
            yield token
            continue
        loc = token.location
        if token.type == 'operator':

            if token.text in priorities:
                l, r = priorities[token.text]
                second_pass = False
            else:
                if token.line_operator:
                    if token.text:
                        priority = (token.space_before * 1e-9
                                    + (1e-10 if token.height_before <= 1 else 0))
                    else:
                        priority = (token.space_after * 1e-9
                                    + (1e-10 if token.height_before <= 1 else 0))
                    p = (10 + priority, 'l', True)
                else:
                    p = (100, 'l', True)
                l, r = p, p
                second_pass = True

            l = (token.text,) + l
            r = (token.text,) + r

            yield Operator(l, r, second_pass, token, location = loc)
        else:
            yield token


def finalize_1(x):

    if isinstance(x, Token):
        t = x.type
        if t == 'id':
            s = ast.quaintstr(x.text)
        elif t == 'void':
            s = ast.Void(x.location)
        elif t == 'nullary':
            s = ast.Nullary(x.text)
        else:
            raise Exception
        s.location = x.location
        return s

    elif isinstance(x, ast.ASTNode):
        return x

    ops, *args = x
    if not isinstance(ops, (list, tuple)):
        ops = [ops]

    if ops[0].args[0]:
        new_tokens = list(make_operators_2(ops, args))
        return operator_parse(iter(new_tokens), order, finalize_1)

    else:
        op_text = [op.args[1].text for op in ops]
        op_text_and_ws = [op.args[1].location.get() for op in ops]
        args = list(map(finalize_1, args))

        if op_text == ['[', ']']:
            r = ast.InlineOp('[]', *args, operators = op_text_and_ws)

        elif op_text == ['{', '}']:
            r = ast.InlineOp('{}', *args, operators = op_text_and_ws)

        elif op_text == ['<', '>']:
            r = ast.InlineOp('<>', *args, operators = op_text_and_ws)

        elif op_text == ['I(', ')I']:
            # TODO: fix op_text_and_ws here
            # print(ast.InlineOp.is_operator(args[0], '*'))
            if isinstance(args[1], ast.BlockOp) and args[1].operator == 'P':
                args = args[:1] + args[1].args + args[-1:]

            if isinstance(args[0], ast.InlineOp) and args[0].operator:
                r = ast.InlineOp(args[0].operator,
                                 *(args[0][:-1]
                                   + [ast.BlockOp('I', args[0][-1], *args[1:-1],
                                                  operators = [""]*len(args))]),
                                 operators = args[0].operators)
            else:
                r = ast.BlockOp('I', *args[:-1], operators = op_text_and_ws)

        elif ops[0].args[1].line_operator:
            if ops[0].args[1].text:
                r = ast.BlockOp(op_text[0], *args, operators = op_text_and_ws)
            elif ops[0].args[1].height_before > 1:
                r = ast.BlockOp("B", *args, operators = op_text_and_ws)
            else:
                r = ast.BlockOp("P", *args, operators = op_text_and_ws)

        elif all(x == op_text[0] for x in op_text[1:]):
            r = ast.InlineOp(op_text[0], *args, operators = op_text_and_ws)

        else:
            raise Exception

        return r



def match_for(c):
    if c == '{': return ['}']
    elif c == '<': return ['>']
    else: return [c]



def make_operators_2(operators, tokens):

    brackets = []
    new_operators = []
    new_tokens = []

    def match(bi, i, j):
        oi = new_operators[i]
        oj = new_operators[j]
        toki = oi.args[1]
        tokj = oj.args[1]
        if tokj.text in match_for(toki.text):
            if tokj.fixity == 'infix':
                brackets[bi:] = [j]
            else:
                brackets[bi:] = []
            oi.right_facing = (toki.text, 0, 'l', [tokj.text])
            oj.left_facing = (tokj.text, 0, 'l', [toki.text])
            return True
        else:
            return False

    for i, (op, node) in enumerate(zip(operators, tokens)):

        token = op.args[1]
        w = token.space_before or token.space_after
        f = token.fixity
        if token.text:
            p0 = (token.text, 1000, 'l', None)
            ps = (token.text, 300, 'r', match_for(token.text))
            pw = (token.text, 100, 'r', match_for(token.text))

            if f == 'prefix':
                l, r = p0, pw if token.space_after else ps
                brackets.append(i)
            elif f == 'suffix':
                if i == 0:
                    # suffix operators become infix when they
                    # are the first operator, e.g.:
                    # 1# first bullet point
                    l, r = pw if token.space_before else ps, pw
                else:
                    l, r = pw if token.space_before else ps, p0
            elif f == 'infix':
                if token.text == '<':
                    brackets.append(i)
                p = pw if token.space_before or token.space_after else ps
                l, r = p, p
        else:
            l = ('', 200 if w else 400, 'a', [''])
            r = l
        new_operators.append(Operator(l, r, False, token, location = token.location))
        if f in ('infix', 'suffix'):
            for bi in range(len(brackets) - 1, -1, -1):
                if match(bi, brackets[bi], i):
                    break

    yield tokens[0]
    for op, token in zip(new_operators, tokens[1:]):
        yield op
        yield token



def order(left, right):

    t1, p1, a1, m1 = left
    t2, p2, a2, m2 = right

    if p1 > p2:
        return 'l'
    elif p1 < p2:
        return 'r'
    elif m1 and (m1 is True or t2 in m1):
        return 'a'
    else:
        return a1



def parse(source):
    t = tokenize(source)
    t = list(make_operators_1(t))
    p = operator_parse(iter(t), order, finalize_1)
    return p

# class quaintstr(str):
#     def __init__(self, s, location = None):
#         super().__init__(s)
#         self.location = location

# class ASTNode:
#     def __init__(self, name, *args, location = None):
#         self.name = name
#         self.args = list(args)
#         if not location:
#             for arg in args:
#                 if hasattr(arg, 'location'):
#                     if location is None:
#                         location = arg.location
#                     else:
#                         location += arg.location
#         self.location = location
#     def __getitem__(self, i):
#         return self.args[i]
#     def __setitem__(self, i, value):
#         self.args[i] = value
#     def __str__(self):
#         return '#{0.name}{0.args!r}'.format(self)
#     def __repr__(self):
#         return str(self)
#     def __descr__(self, descr):
#         name = self.name
#         return [(({"@ASTNode", "+"+name, "object"},)
#                  + tuple(descr(x) for x in self.args))]


# class ASTBuilder:
#     def __getattr__(self, name):
#         def build(*args, location = None):
#             return ASTNode(name, *args, location = location)
#         return build

# ast = ASTBuilder()

