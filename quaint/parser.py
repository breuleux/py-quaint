

import re
from .operparse import (
    SubTokenizer, Tokenizer, Token, Void, SyntaxError,
    FixityDisambiguator, Alternator, Source, Location,
    TokenizerWrapper, tokenizer_wrapper
    )
from .operparse.parse import Operator, operator_parse
from . import ast


################
### Tokenize ###
################

# Characters that define operators
chr_op1 = r"""
+ - * / ^ = % # $ @ & | ! ? _ ` < > ; :
""".split()

chr_op2 = r"""
, .
""".split()

chr_op = chr_op1 + chr_op2

all_op = chr_op + """
~ \n [ ] { } ( )
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

        return token, m.regs[0][1]

    return f



standard_matchers = [

    # Brackets
    ("[{(", mkre("[\\[\\{\\(]"), True, m_operator("prefix")),
    ("]})", mkre("[\\]\\}\\)]"), True, m_operator("suffix")),

    # Generic
    (chr_op1, mkre(rx_choice(chr_op1) + "+"), True, m_operator("?fix")),
    (',', mkre(rx_choice([','])), True, m_operator("infix")),
    ('.', mkre(rx_choice(['.']) + "+"), True, m_operator("?fix")),

    # Rest
    (True, mkre(r"(\\\\|\\{chr}|{nochr})+".format(
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

def sandwich(left, right, params, zerolength = False):
    # TODO: change the locations of left and right
    # or maybe not.
    source = left.location.source if left else right.location.source
    start = left.location.end if left else right.location.start
    if zerolength:
        end = start
    else:
        end = right.location.start if right else left.location.end
    location = Location(source, (start, end))
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
                yield sandwich(last, token, insert, True)

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

    # if tok.text == '<' and wsl is not None:
    #     return "infix"

    # if tok.text == '<':
    #     return "prefix"
    # elif tok.text == '>' and wsr is not None:
    #     return "infix"
    # elif (tok.text == ':'
    #       and wsl == 0 and wsr is not None):
    #     return "infix"

    # if '<' in tok.text and '>' not in tok.text:
    #     return "prefix"
    # elif '>' in tok.text:
    #     return "suffix"

    if (tok.text == ':'
          and wsl == 0 and wsr is not None):
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
        ')': (91, 'l', ['(']),
        ',': (100, 'l', None),
        # '>': (90, 'l', ['<']),
        }
    
    right_priorities = {
        'I(': (0, 'l', [')I']),
        '[': (1, 'l', [']']),
        '{': (1, 'l', ['}']),
        '(': (91, 'l', [')']),
        ',': (100, 'l', None),
        # '<': (90, 'l', ['>']),
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
                # if '<' in token.text:
                #     priority = 90
                #     wide = True
            elif token.fixity == 'suffix':
                wide = widths[0]
                rp = p_immediate
                # if '>' in token.text:
                #     priority = 90
                #     wide = True
                if token.text == '.' and not wide:
                    priority = 99
            else:
                wide = widths[0] or widths[1]

            if not wide:
                # "narrow" operator application has higher priority
                # e.g. 'a+b' binds tighter than 'a + b'
                priority += 2 * multiplier

            if not token.text:
                aggr = [token.text]
            # elif '<' in token.text:
            #     aggr = lambda other: ('>' in other)
            else:
                aggr = None

            if lp is None:
                lp = (priority, 'r', aggr)
            if rp is None:
                rp = (priority, 'r', aggr)

            l = (token.text,) + lp
            r = (token.text,) + rp

            yield Operator(l, r, token, location = loc)


def finalize(x):

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

    # else:
    if True:

        op_text = [op.args[0].text for op in ops]
        wide = any(is_wide(op.args[0]) for op in ops)

        # op_text_and_ws = [op.args[0].location.get() for op in ops]
        args = list(map(finalize, args))

        # if op_text == ['[', ']']:
        #     r = ast.InlineOp(tuple(op_text), *args, wide = wide)

        # elif op_text == ['{', '}']:
        #     r = ast.InlineOp(tuple(op_text), *args, wide = wide)

        # elif op_text == ['(', ')']:
        #     r = ast.InlineOp(tuple(op_text), *args, wide = wide)

        # # elif op_text == ['<', '>']:
        # #     r = ast.InlineOp('<>', *args, wide = wide)

        # elif (len(op_text) == 2
        #       and '<' in op_text[0]
        #       and '>' in op_text[1]):
        #     r = ast.InlineOp(tuple(op_text), *args, wide = wide)

        if op_text == ['I(', ')I']:
            # TODO: fix op_text_and_ws here
            # print(ast.InlineOp.is_operator(args[0], '*'))
            if isinstance(args[1], ast.BlockOp) and args[1].operator == 'P':
                args = args[:1] + args[1].args + args[-1:]

            if isinstance(args[0], ast.InlineOp) and args[0].operator:
                ind = [ast.BlockOp('I', args[0][-1], *args[1:-1],
                                   wide = True)]
                r = ast.InlineOp(args[0].operator,
                                 *(args[0][:-1] + ind),
                                 wide = args[0].wide)

            elif isinstance(args[0], ast.Nullary):
                ind = ast.BlockOp('I', *args[1:-1],
                                  wide = True)
                r = ast.InlineOp(args[0].text,
                                 ast.Void(),
                                 ind,
                                 wide = True)

            else:
                r = ind = ast.BlockOp('I', *args[:-1], wide = wide)

        elif len(op_text) == 2 and op_text[0] != op_text[1]:
            r = ast.InlineOp(tuple(op_text), *args, wide = wide)

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



def order(left, right):

    t1, p1, a1, m1 = left
    t2, p2, a2, m2 = right

    if p1 > p2:
        return 'l'
    elif p1 < p2:
        return 'r'
    elif m1 and (m1 is True
                 or (callable(m1) and m1(t2))
                 or isinstance(m1, (list, tuple, str)) and t2 in m1):
        return 'a'
    else:
        return a1



def parse(source):
    if not isinstance(source, Source):
        source = Source(source, url = None)
    t = tokenize(source)
    # t = list(make_operators_1(t))
    t = list(make_operators(t))
    p = operator_parse(iter(t), order, finalize)
    p = fix_whitespace(p, True, True)[0]
    return p



strip_re_begin = re.compile("^({ws}*)".format(ws = "[ \n~]"))
strip_re_end = re.compile("({ws}*)$".format(ws = "[ \n~]"))
def strip_and_ws(text):
    mb = strip_re_begin.search(text)
    me = strip_re_end.search(text)
    b = mb.regs[0][1]
    e = me.regs[0][0]
    # print(repr(text), mb.regs, me.regs)
    return text[:b], text[b:e], text[e:]


# def fix_whitespace(ptree, owns_left, owns_right):

#     if isinstance(ptree, ast.quaintstr):
#         left, text, right = strip_and_ws(ptree)
#         loc = ptree.location.change_start(len(left)).change_end(-len(right))
#         ptree = ast.quaintstr(text)
#         ptree.location = loc

#     elif isinstance(ptree, ast.Nullary):
#         left, text, right = strip_and_ws(ptree.text)
#         ptree.text = text

#     elif isinstance(ptree, ast.Void):
#         left, right = ptree.text, ptree.text
#         ptree.text = ""

#     elif isinstance(ptree, ast.Op):
#         args = ptree.args
#         if len(args) == 0:
#             raise Exception("Ops should have at least one argument")
#         elif len(args) == 1:
#             arg, left, right = fix_whitespace(args[0], False, False)
#             ptree.args = [arg]
#         else:
#             arg0, left, _ = fix_whitespace(args[0], False, True)
#             new_args = [arg0]
#             for arg in args[1:-1]:
#                 argi, _, _ = fix_whitespace(arg, True, True)
#                 new_args.append(argi)
#             argn, _, right = fix_whitespace(args[-1], True, False)
#             new_args.append(argn)
#             ptree.args = new_args

#     else:
#         raise Exception("Unknown node", ptree)

#     if owns_left and owns_right:
#         ptree.whitespace_left = left
#         ptree.whitespace_right = right
#         return (ptree, None, None)
#     elif owns_left:
#         ptree.whitespace_left = left
#         ptree.whitespace_right = ""
#         return (ptree, None, right)
#     elif owns_right:
#         ptree.whitespace_left = ""
#         ptree.whitespace_right = right
#         return (ptree, left, None)
#     else:
#         return (ptree, left, right)






def fix_whitespace(ptree, owns_left, owns_right):

    loc = ptree.location

    if isinstance(ptree, ast.quaintstr):
        left, text, right = strip_and_ws(ptree)
        ptree = ast.quaintstr(text)
        # loc = loc.change_start(len(left)).change_end(-len(right))
        # ptree.location = loc

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
        rval = (ptree, None, None)
    elif owns_left:
        ptree.whitespace_left = left
        ptree.whitespace_right = ""
        rval = (ptree, None, right)
    elif owns_right:
        ptree.whitespace_left = ""
        ptree.whitespace_right = right
        rval = (ptree, left, None)
    else:
        rval = (ptree, left, right)

    if isinstance(ptree, ast.Void) and owns_left and owns_right:
        ptree.whitespace_right = ""

    if loc:
        loc = loc.change_end(-len(right))
        loc = loc.change_start(len(left))
        ptree.location = loc

    return rval





