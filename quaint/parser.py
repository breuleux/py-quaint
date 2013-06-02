

import re
from .operparse import (
    SubTokenizer, Tokenizer, Token, Void, SyntaxError,
    FixityDisambiguator, Alternator, Location, TokenizerWrapper,
    tokenizer_wrapper, sandwich
    )
from .operparse.parse import Operator, operator_parse


################
### Tokenize ###
################

# Characters that define operators
chr_op = r"""
+ - * / ^ = % # $ @ & | < > ! ? : , ;
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

def subtok_rule(chrs, rxp, fields, span = 0, ws = True):
    if isinstance(rxp, str):
        rxp = re.compile("(" + rxp + ")")
    return (chrs, rxp, span, ws, fields)


def m_fill_in(**others):
    def f(m, wsb, wsa):
        groups = m.groups()
        s_wsb = wsb.split("\n")
        s_wsa = wsa.split("\n")
        own_line = (len(s_wsb) > 1) and (len(s_wsa) > 1)
        spangroup = others.pop("text", 0)
        text = groups[spangroup]
        d = {"text": text,
             "wsb": wsb,
             "wsa": wsa,
             "space_before": len(s_wsb[-1]),
             "space_after": len(s_wsa[0]),
             "own_line": own_line,
             "height_before": len(s_wsb) - 1,
             "height_after": len(s_wsa) - 1}
        d.update(others)
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
    return m_fill_in(type = "id")


standard_matchers = [

    # Brackets
    subtok_rule("[{", "[\\[\\{]", m_prefix()),
    subtok_rule("]}", "[\\]\\}]", m_suffix()),

    # Generic
    subtok_rule(chr_op, rx_choice(chr_op) + "+", m_unknownfix()),

    # Rest
    subtok_rule(True, rx_choice(all_op, negate = True)
                + "+", m_id()),

    # Don't put anything here. It won't be reached.
]

subtok_normal = SubTokenizer(
    standard_matchers,
    whitespace_re)


@tokenizer_wrapper
def split_operators(tokenizer):
    for token in tokenizer:
        if token.type == 'operator' and not token.own_line: # token.text != "INDENT":
            loc = token.location
            for i, c in enumerate(token.text):
                t = Token(**token.__dict__)
                t.text = c
                t.location = Location(loc.source, (loc.start+i, loc.start+i+1))
                if c == ',':
                    t.fixity = 'infix'
                if i > 0:
                    t.space_before = t.height_before = 0
                if i < len(token.text) -  1:
                    t.space_after = t.height_after = 0
                yield t
        else:
            yield token

@tokenizer_wrapper
def adjust_locations(tokenizer):
    for token in tokenizer:
        if token.type in ('id', 'nullary'):
            loc = token.location
            token.location = Location(loc.source, (loc.start - len(token.wsb),
                                                   loc.end + len(token.wsa)))
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
    t = adjust_locations(t)
    t = Alternator(t,
                   dict(type = "void"),
                   dict(type = "operator",
                        fixity = "infix",
                        text = ""))
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
                if token.own_line:
                    if token.text:
                        priority = (token.space_before * 1e-9)
                    else:
                        priority = (token.space_after * 1e-9
                                    + (1e-10 if token.height_before <= 1 else 0))
                    p = (10 + priority, 'l', True)
                    print(p)
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
            s = quaintstr(x.text)
        elif t == 'void':
            s = ast.void()
        elif t == 'nullary':
            s = ast.nullary(x.text)
        else:
            raise Exception
        s.location = x.location
        return s

    elif isinstance(x, ASTNode):
        return x

    ops, *args = x
    if not isinstance(ops, (list, tuple)):
        ops = [ops]

    if ops[0].args[0]:
        new_tokens = list(make_operators_2(ops, args))
        return operator_parse(iter(new_tokens), order, finalize_1)

    else:
        op_text = [op.args[1].text for op in ops]
        args = list(map(finalize_1, args))

        if op_text == ['[', ']']:
            r = ast.bracket('[]', args[1])

        elif op_text == ['{', '}']:
            r = ast.bracket('{}', args[1])

        elif op_text == ['<', '>']:
            r = ast.bracket('<>', *args)

        elif op_text == ['I(', ')I']:
            # if args[0]

            r = ast.block('I', *args[:-1])

        elif ops[0].args[1].own_line:
            if ops[0].args[1].text:
                r = ast.block(op_text[0], *args)
            elif ops[0].args[1].height_before > 1:
                r = ast.block("B", *args)
            else:
                r = ast.block("P", *args)

        elif all(x == op_text[0] for x in op_text[1:]):
            r = ast.bracket(op_text[0], *args)

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
        # if toki.text == tokj.text:
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
                l, r = pw if token.space_before else ps, p0
            elif f == 'infix':
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

class quaintstr(str):
    def __init__(self, s, location = None):
        super().__init__(s)
        self.location = location

class ASTNode:
    def __init__(self, name, *args, location = None):
        self.name = name
        self.args = list(args)
        if not location:
            for arg in args:
                if hasattr(arg, 'location'):
                    if location is None:
                        location = arg.location
                    else:
                        location += arg.location
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
    # if op.left_facing == -1:
        return op.args[0].text
    # if op.left_facing is None:
    #     return op.right_facing.text
    # else:
    #     return op.left_facing.text


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
        if parse_tree.type == 'id':
            s = quaintstr(parse_tree.text)
        elif parse_tree.type == 'void':
            s = ast.void()
        elif parse_tree.type == 'nullary':
            s = ast.nullary(parse_tree.text)
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
        ops = set(op)
        r = ast.oper(op[0] if len(ops) == 1 else ops, *args)

    loc += sum(x.location for x in args)
    r.location = loc
    return r
