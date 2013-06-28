

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
chr_op1 = r"""
+ - * / ^ = % # $ @ & | ! ? _ ` < >
""".split()

chr_op2 = r"""
, ;
""".split()

chr_op = chr_op1 + chr_op2

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
    (chr_op1, mkre(rx_choice(chr_op1) + "+"), True, m_operator("?fix")),
    (chr_op2, mkre(rx_choice(chr_op2)), True, m_operator("infix")),

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


# @tokenizer_wrapper
# def split_operators(tokenizer):
#     for token in tokenizer:
#         if token.type == 'operator' and not token.line_operator:
#             loc = token.location
#             for i, c in enumerate(token.text):
#                 t = Token(**token.__dict__)
#                 t.text = c
#                 t.location = Location(loc.source, (loc.start+i, loc.start+i+1))
#                 if c in [',', ';', '<', '>']:
#                     t.fixity = 'infix'
#                 if i > 0:
#                     t.space_before = t.height_before = 0
#                     t.wsb = ""
#                 if i < len(token.text) -  1:
#                     t.space_after = t.height_after = 0
#                     t.wsa = ""
#                 yield t
#         else:
#             yield token

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
            if token.type == 'id':
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
    to_sandwich = []
    ignore_if_lineop = False

    for token in tokenizer:
        if current_indent is None:
            current_indent = len(token.wsb.split("\n")[0])

        for insert, ignore_if_lineop in to_sandwich:
            if (not ignore_if_lineop
                or ((not last or not last.line_operator)
                    and (not token or not token.line_operator))):
                yield sandwich(last, token, insert)

        to_sandwich = []

        yield token

        if token.height_after > 0:
            indent = len(token.wsa.split("\n")[-1])
            if indent > current_indent:
                indent_stack.append(current_indent)
                current_indent = indent
                to_sandwich.append([dict(type = "operator",
                                         fixity = "infix",
                                         text = "I("), False])
            else:
                while (indent < current_indent
                       and indent_stack
                       and indent <= indent_stack[-1]):
                    current_indent = indent_stack.pop()
                    to_sandwich.append([dict(type = "operator",
                                            fixity = "suffix",
                                            text = ")I"), False])
            to_sandwich.append([dict(type = "operator",
                                     fixity = "infix",
                                     text = ""), True])

        last = token


    for insert, ignore_if_lineop in to_sandwich:
        if (not ignore_if_lineop
            or (not last or last.type != "operator" or not last.line_operator)):
            yield sandwich(last, None, insert)


# @tokenizer_wrapper
# def add_indent_and_linebreaks(tokenizer):
#     current_indent = None
#     indent_stack = []
#     last = None
#     to_sandwich = None
#     ignore_if_lineop = False

#     for token in tokenizer:
#         if current_indent is None:
#             current_indent = len(token.wsb.split("\n")[0])

#         if to_sandwich:
#             if (not ignore_if_lineop
#                 or ((not last or not last.line_operator)
#                     and (not token or not token.line_operator))):
#                 yield sandwich(last, token, to_sandwich)

#         to_sandwich = None
#         ignore_if_lineop = False

#         yield token

#         if token.height_after > 0:
#             indent = len(token.wsa.split("\n")[-1])
#             if indent > current_indent:
#                 indent_stack.append(current_indent)
#                 current_indent = indent
#                 to_sandwich = dict(type = "operator",
#                                    fixity = "infix",
#                                    text = "I(")
#             elif (indent < current_indent
#                   and indent_stack
#                   and indent <= indent_stack[-1]):
#                 current_indent = indent_stack.pop()
#                 to_sandwich = dict(type = "operator",
#                                    fixity = "suffix",
#                                    text = ")I")
#             else:
#                 to_sandwich = dict(type = "operator",
#                                    fixity = "infix",
#                                    text = "")
#                 ignore_if_lineop = True

#         last = token


#     if to_sandwich:
#         if (not ignore_if_lineop
#             or (not last or last.type != "operator" or not last.line_operator)):
#             yield sandwich(last, None, to_sandwich)


def is_wide(tok):

    if tok.line_operator:
        wsl = tok.height_before - 1
        wsr = tok.height_after - 1
    else:
        wsl = tok.space_before if not tok.height_before else 0
        wsr = tok.space_after if not tok.height_after else 0

    if tok.fixity == 'infix':
        return bool(wsl or wsr)
    elif tok.fixity == 'prefix':
        return bool(wsr)
    elif tok.fixity == 'suffix':
        return bool(wsl)


def inherent_fixity(tok):

    if tok.line_operator:
        wsl = tok.height_before - 1
        wsr = tok.height_after - 1
    else:
        wsl = tok.space_before if not tok.height_before else None
        wsr = tok.space_after if not tok.height_after else None

    if tok.text == '<' and wsl is not None:
        return "infix"
    elif tok.text == '>' and wsr is not None:
        return "infix"

    if ((wsl is not None and wsr is not None)
        and ((wsl == wsr == 0) or (wsl > 0 and wsr > 0))):
        return "infix"
    elif wsl is None or (wsr is not None and wsl > 0):
        return "prefix"
    elif wsr is None or wsr > 0:
        return "suffix"
    else:
        raise Exception("Cannot determine fixity", tok)


def tokenize(source):
    t = Tokenizer(source, dict(normal = subtok_normal))
    t = add_indent_and_linebreaks(t)
    t = FixityDisambiguator(t, inherent_fixity,
                            {"id": (False, False),
                             "infix": (True, True),
                             "prefix": (False, True),
                             "suffix": (True, False)})
    # t = split_operators(t)
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


quaint_priority_table = [
    (0, "Indent block delimiter."),
    (1, "Brackets (e.g. [] {})"),
    (10, "Wide line operator (e.g. 'a\n\n====\n\nb')"),
    (20, "Wide line breaks (e.g. 'a\n\nb')"),
    (30, "Narrow line operator (e.g. 'a\n====\nb')"),
    (40, "Narrow line breaks (e.g. 'a\nb')"),
    (50, "Left of opening indent block."),
    (99, "Right of < and left of >"),
    (100, "Wide inline operator (e.g. 'a + b')"),
    (200, "Wide juxtaposition (words, e.g. 'a b')"),
    (300, "Narrow inline operator (e.g. 'a+b')"),
    (400, "Narrow juxtaposition (e.g. ab)"),
    (1000, "Consumes dummies on the left of prefix operators or right of suffix operators.")
]


def make_operators(tokenizer):

    p_immediate = (1000, 'l', None)

    left_priorities = {
        'I(': (50, 'l', None),
        ')I': (0, 'l', ['[']),
        ']': (1, 'l', ['[']),
        '}': (1, 'l', ['{']),
        '>': (99, 'l', ['<']),
        }
    
    right_priorities = {
        'I(': (0, 'l', [')I']),
        '[': (1, 'l', [']']),
        '{': (1, 'l', ['}']),
        '<': (99, 'l', ['>']),
        }

    for token in tokenizer:

        loc = token.location

        if token.type != 'operator':
            yield token

        else:
            lp = left_priorities.get(token.text, None)
            rp = right_priorities.get(token.text, None)

            if token.line_operator:
                multiplier = 10
                widths = (token.height_before > 1, token.height_after > 1)
            else:
                multiplier = 100
                widths = (token.space_before > 0, token.space_after > 0)

            if token.text:
                priority = multiplier
            else:
                # juxtaposition or line break have higher priority
                priority = 2 * multiplier

            if token.fixity == 'prefix':
                wide = widths[1]
                lp = p_immediate
            elif token.fixity == 'suffix':
                wide = widths[0]
                rp = p_immediate
            else:
                wide = widths[0] or widths[1]

            if not wide:
                # "narrow" operator application has higher priority
                # e.g. 'a+b' binds tighter than 'a + b'
                priority += 2 * multiplier

            if not token.text:
                aggr = [token.text]
            else:
                aggr = None

            if lp is None:
                lp = (priority, 'r', aggr)
            if rp is None:
                rp = (priority, 'r', aggr)

            l = (token.text,) + lp
            r = (token.text,) + rp

            yield Operator(l, r, token, location = loc)







# def make_operators_1(tokenizer):

#     p_immediate = (1000, 'l', None)

#     priorities = {
#         'I(': ((15, 'l', None), (0, 'l', [')I'])),
#         ')I': ((0, 'l', ['[']), p_immediate),
#         '[': (p_immediate, (0, 'l', [']'])),
#         ']': ((0, 'l', ['[']), p_immediate),
#         '{': (p_immediate, (0, 'l', ['}'])),
#         '}': ((0, 'l', ['{']), p_immediate)
#         }

#     for token in tokenizer:
#         if not isinstance(token, Token):
#             yield token
#             continue
#         loc = token.location
#         if token.type == 'operator':

#             if token.text in priorities:
#                 l, r = priorities[token.text]
#                 second_pass = False
#             else:
#                 if token.line_operator:
#                     if token.text:
#                         priority = (token.space_before * 1e-9
#                                     + (1e-10 if token.height_before <= 1 else 0))
#                     else:
#                         priority = (token.space_after * 1e-9
#                                     + (1e-10 if token.height_before <= 1 else 0))
#                     p = (10 + priority, 'l', True)
#                 else:
#                     p = (100, 'l', True)
#                 l, r = p, p
#                 second_pass = True

#             l = (token.text,) + l
#             r = (token.text,) + r

#             yield Operator(l, r, second_pass, token, location = loc)
#         else:
#             yield token


def finalize_1(x):

    if isinstance(x, Token):
        t = x.type
        if t == 'id':
            s = ast.quaintstr(x.text)
        elif t == 'void':
            s = ast.Void(x.location)
        elif t == 'nullary':
            s = ast.Nullary(x.text, x.location)
        else:
            raise Exception
        s.location = x.location
        return s

    elif isinstance(x, ast.ASTNode):
        return x

    ops, *args = x
    if not isinstance(ops, (list, tuple)):
        ops = [ops]

    # if ops[0].args[0]:
    #     new_tokens = list(make_operators_2(ops, args))
    #     return operator_parse(iter(new_tokens), order, finalize_1)

    # else:
    if True:

        op_text = [op.args[0].text for op in ops]
        wide = any(is_wide(op.args[0]) for op in ops)

        # op_text_and_ws = [op.args[0].location.get() for op in ops]
        args = list(map(finalize_1, args))

        if op_text == ['[', ']']:
            r = ast.InlineOp('[]', *args, wide = wide)

        elif op_text == ['{', '}']:
            r = ast.InlineOp('{}', *args, wide = wide)

        elif op_text == ['<', '>']:
            r = ast.InlineOp('<>', *args, wide = wide)

        elif op_text == ['I(', ')I']:
            # TODO: fix op_text_and_ws here
            # print(ast.InlineOp.is_operator(args[0], '*'))
            if isinstance(args[1], ast.BlockOp) and args[1].operator == 'P':
                args = args[:1] + args[1].args + args[-1:]

            if isinstance(args[0], ast.InlineOp) and args[0].operator:
                r = ast.InlineOp(args[0].operator,
                                 *(args[0][:-1]
                                   + [ast.BlockOp('I', args[0][-1], *args[1:-1],
                                                  wide = True)]),
                                 wide = args[0].wide)
            elif isinstance(args[0], ast.Nullary):
                r = ast.InlineOp(args[0].text,
                                 ast.Void(),
                                 ast.BlockOp('I', *args[1:-1],
                                             wide = True),
                                 wide = True)
            else:
                r = ast.BlockOp('I', *args[:-1], wide = wide)

        elif ops[0].args[0].line_operator:
            if ops[0].args[0].text:
                r = ast.BlockOp(op_text[0], *args, wide = wide)
            elif ops[0].args[0].height_before > 1:
                r = ast.BlockOp("B", *args, wide = wide)
            else:
                r = ast.BlockOp("P", *args, wide = wide)

        elif all(x == op_text[0] for x in op_text[1:]):
            r = ast.InlineOp(op_text[0], *args, wide = wide)

        else:
            raise Exception

        return r





def match_for(c):
    if c == '{': return ['}']
    elif c == '<': return ['>']
    else: return [c]



# def make_operators_2(operators, tokens):

#     brackets = []
#     new_operators = []
#     new_tokens = []

#     def match(bi, i, j):
#         oi = new_operators[i]
#         oj = new_operators[j]
#         toki = oi.args[1]
#         tokj = oj.args[1]
#         if tokj.text in match_for(toki.text):
#             if tokj.fixity == 'infix':
#                 brackets[bi:] = [j]
#             else:
#                 brackets[bi:] = []
#             oi.right_facing = (toki.text, 0, 'l', [tokj.text])
#             oj.left_facing = (tokj.text, 0, 'l', [toki.text])
#             return True
#         else:
#             return False

#     for i, (op, node) in enumerate(zip(operators, tokens)):

#         token = op.args[1]
#         w = token.space_before or token.space_after
#         f = token.fixity
#         if token.text:
#             p0 = (token.text, 1000, 'l', None)
#             ps = (token.text, 300, 'r', match_for(token.text))
#             pw = (token.text, 100, 'r', match_for(token.text))

#             if f == 'prefix':
#                 l, r = p0, pw if token.space_after else ps
#                 brackets.append(i)
#             elif f == 'suffix':
#                 if i == 0:
#                     # suffix operators become infix when they
#                     # are the first operator, e.g.:
#                     # 1# first bullet point
#                     l, r = pw if token.space_before else ps, pw
#                 else:
#                     l, r = pw if token.space_before else ps, p0
#             elif f == 'infix':
#                 if token.text == '<':
#                     brackets.append(i)
#                 p = pw if token.space_before or token.space_after else ps
#                 l, r = p, p
#         else:
#             l = ('', 200 if w else 400, 'a', [''])
#             r = l
#         new_operators.append(Operator(l, r, False, token, location = token.location))
#         if f in ('infix', 'suffix'):
#             for bi in range(len(brackets) - 1, -1, -1):
#                 if match(bi, brackets[bi], i):
#                     break

#     yield tokens[0]
#     for op, token in zip(new_operators, tokens[1:]):
#         yield op
#         yield token



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
    # t = list(make_operators_1(t))
    t = list(make_operators(t))
    p = operator_parse(iter(t), order, finalize_1)
    p = fix_whitespace(p, True, True)[0]
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



strip_re_begin = re.compile("^({ws}*)".format(ws = "[ \n~]"))
strip_re_end = re.compile("({ws}*)$".format(ws = "[ \n~]"))
def strip_and_ws(text):
    mb = strip_re_begin.search(text)
    me = strip_re_end.search(text)
    b = mb.regs[0][1]
    e = me.regs[0][0]
    # print(repr(text), mb.regs, me.regs)
    return text[:b], text[b:e], text[e:]


def fix_whitespace(ptree, owns_left, owns_right):

    if isinstance(ptree, ast.quaintstr):
        left, text, right = strip_and_ws(ptree)
        loc = ptree.location.change_start(len(left)).change_end(-len(right))
        ptree = ast.quaintstr(text)
        ptree.location = loc

    elif isinstance(ptree, ast.Nullary):
        left, text, right = strip_and_ws(ptree.text)
        ptree.text = text

    elif isinstance(ptree, ast.Void):
        left, right = ptree.text, ptree.text
        ptree.text = ""

    elif isinstance(ptree, ast.Op):
        args = ptree.args
        if len(args) == 0:
            raise Exception("Ops should have at least one argument")
        elif len(args) == 1:
            arg, left, right = fix_whitespace(args[0], False, False)
            ptree.args = [arg]
        else:
            arg0, left, _ = fix_whitespace(args[0], False, True)
            new_args = [arg0]
            for arg in args[1:-1]:
                argi, _, _ = fix_whitespace(arg, True, True)
                new_args.append(argi)
            argn, _, right = fix_whitespace(args[-1], True, False)
            new_args.append(argn)
            ptree.args = new_args

    else:
        raise Exception("Unknown node", ptree)

    if owns_left and owns_right:
        ptree.whitespace_left = left
        ptree.whitespace_right = right
        return (ptree, None, None)
    elif owns_left:
        ptree.whitespace_left = left
        ptree.whitespace_right = ""
        return (ptree, None, right)
    elif owns_right:
        ptree.whitespace_left = ""
        ptree.whitespace_right = right
        return (ptree, left, None)
    else:
        return (ptree, left, right)




