

import re
from .operparse import (
    SubTokenizer, Tokenizer, Token, Void, SyntaxError,
    FixityDisambiguator, Alternator, Location, TokenizerWrapper,
    tokenizer_wrapper, sandwich
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
""".split(" ") + [" "]

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

def subtok_rule(chrs, rxp, fields, span = 0, skip = 0, ws = True):
    if isinstance(rxp, str):
        rxp = re.compile("(" + rxp + ")")
    return (chrs, rxp, span, skip, ws, fields)


def m_fill_in(**others):
    def f(m, wsb, wsa):
        args = dict(others)
        groups = m.groups()
        s_wsb = wsb.split("\n")
        s_wsa = wsa.split("\n")
        own_line = (len(s_wsb) > 1) and (len(s_wsa) > 1)
        spangroup = args.pop("text", 0)
        if spangroup == -1:
            text = wsb + groups[0] + wsa
        else:
            text = groups[spangroup]
        line_operator = own_line and len(text) >= 3
        d = {"text": text,
             "wsb": wsb,
             "wsa": wsa,
             "space_before": len(s_wsb[-1]),
             "space_after": len(s_wsa[0]),
             "own_line": own_line,
             "line_operator": line_operator,
             "height_before": len(s_wsb) - 1,
             "height_after": len(s_wsa) - 1}
        d.update(args)
        return d
    return f

def m_operator(fixity, **others):
    return m_fill_in(type = 'operator',
                     fixity = fixity,
                     **others)

def m_prefix(**others):
    return m_operator("prefix", **others)

def m_suffix(**others):
    return m_operator("suffix", **others)

def m_infix(**others):
    return m_operator("infix", **others)

def m_unknownfix(**others):
    return m_operator("?fix", **others)

def m_id(**others):
    return m_fill_in(text = -1, type = "id")


standard_matchers = [

    # Brackets
    subtok_rule("[{", "[\\[\\{]", m_prefix()),
    subtok_rule("]}", "[\\]\\}]", m_suffix()),

    # Generic
    subtok_rule(chr_op, rx_choice(chr_op) + "+", m_unknownfix()),

    # Rest
    subtok_rule(True, rx_choice(all_op, negate = True)
                + "+", m_id(), span = -1, skip = 0),

    # Don't put anything here. It won't be reached.
]

subtok_normal = SubTokenizer(
    standard_matchers,
    whitespace_re)


@tokenizer_wrapper
def split_operators(tokenizer):
    for token in tokenizer:
        # if token.type == 'operator' and (not token.own_line
        #                                  or re.match("^"+rx_choice(chr_op)+"{1,2}$", token.text)):
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

        # if token.type in ('operator',) and token.text.strip():
        #     # token.location = Location(loc.source, (loc.start - token.space_before,
        #     #                                        loc.end + token.space_after))
        #     loc = Location(loc.source, (loc.start - len(token.wsb),
        #                                 loc.end + len(token.wsa)))
        #     token.location = loc

        # print(rightmost, loc.start, loc.end, repr(getattr(token, 'text', '??')))

        if loc.start > loc.end:
            loc = Location(loc.source, (loc.start, loc.start))
        if rightmost > loc.start:
            loc = Location(loc.source, (rightmost, loc.end))

        token.location = loc

        rightmost = loc.end
        yield token

@tokenizer_wrapper
def add_indent_and_linebreaks(tokenizer):
    current_indent = None
    indent_stack = []
    last = None
    to_sandwich = None
    ignore_if_own_line = False

    for token in tokenizer:
        if current_indent is None:
            current_indent = len(token.wsb.split("\n")[0])

        if to_sandwich:
            if (not ignore_if_own_line
                or ((not last or last.type != "operator" or not last.own_line)
                    and (not token or token.type != "operator" or not token.own_line))):
                yield sandwich(last, token, to_sandwich)

        to_sandwich = None
        ignore_if_own_line = False

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
                ignore_if_own_line = True

        last = token


    if to_sandwich:
        if (not ignore_if_own_line
            or (not last or last.type != "operator" or not last.own_line)):
            yield sandwich(last, None, to_sandwich)


def tokenize(source):
    t = Tokenizer(source, dict(normal = subtok_normal))
    t = add_indent_and_linebreaks(t)
    t = FixityDisambiguator(t)
    t = split_operators(t)
    t = Alternator(t,
                   dict(type = "void"),
                   dict(type = "operator",
                        fixity = "infix",
                        text = ""))
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
                if token.own_line and not token.text in chr_op:
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
            s = ast.Void()
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
            r = ast.InlineOp('[]', args[1], operators = op_text_and_ws)

        elif op_text == ['{', '}']:
            r = ast.InlineOp('{}', args[1], operators = op_text_and_ws)

        elif op_text == ['<', '>']:
            r = ast.InlineOp('<>', *args, operators = op_text_and_ws)

        elif op_text == ['I(', ')I']:
            # TODO: fix op_text_and_ws here
            # print(ast.InlineOp.is_operator(args[0], '*'))
            if isinstance(args[0], ast.InlineOp) and args[0].operator:
                r = ast.InlineOp(args[0].operator,
                                 *(args[0][:-1]
                                   + [ast.BlockOp('I', args[0][-1], *args[1:-1],
                                                  operators = [""]*len(args))]),
                                 operators = args[0].operators)
            else:
                r = ast.BlockOp('I', *args[:-1], operators = op_text_and_ws)

        elif ops[0].args[1].own_line:
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

