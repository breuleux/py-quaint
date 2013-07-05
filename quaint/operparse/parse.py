
from .. import exc

########################
### Operator parsing ###
########################


class Operator:

    def __init__(self, left_facing, right_facing, *args, location):
        self.left_facing = left_facing
        self.right_facing = right_facing
        self.args = args
        self.location = location

    def __str__(self):
        if self.left_facing == self.right_facing:
            return '<{0.left_facing}>'.format(self)
        else:
            return '<{0.left_facing}|{0.right_facing}>'.format(self)

    def __repr__(self):
        return str(self)



def operator_parse(tokenizer, order, finalize):
    """
    Operator parsing

    tokenizer: an iterator generating a list of tokens. The tokens
      must always alternate between non-operator tokens and instances
      of Operator.

    order: a function taking two arbitrary arguments and returning an
      ordering value between the two. The ordering value must be one
      of:
      'l': the left operator has precedence
      'r': the right operator has precedence
      None: neither operator has precedence (this will raise a
        SyntaxError)
      'a': the left and right operators will be aggregated into a
        single operator

    returns: a list of lists. Each list corresponds to an expression.

    How it works:

    An Operator has two attributes: `left_facing` and `right
    facing`. The first is an object that will be used to compare
    precedence with operators on its left and the second will be used
    to compare with operators on its right. We can denote such an
    operator `<O|P>` where O faces left and P faces right. So you
    might have the following expression:

        x <O|P> y <Q|R> z <S|T> w

    operator_parse will call order(P, Q), then order(R, S), then
    (potentially) order(P, S) in order to group the expressions. The
    return value might be something like [<O|P>, x, [<S|T>, [<Q|R>, y, z], w]].

    If oper(P, Q) returns 'a' then both operators are *merged*, which
    means that the expression becomes, conceptually:

        x <O|y|R> z <S|T> w

    In reality, <O|P> and <P|Q> become a ternary operator, and y the
    middle argument. The return value may look like this:
    [[<O|P>, <Q|R>], x, y, [<S|T>, z, w]].

    * To implement a ternary operator like "x ? y : z", define
      order("?", ":") == "a". Note that the right of "?" and the left
      of ":" must have lower priority than everything else if you want
      to ensure that they meet. You can set some orderings to "None"
      to raise syntax errors, for instance between "?" and ")" when
      ")" is to the right of "?".

    * You can define quaternary, etc. operators. Just merge each part
      in sequence.

    * To implement a prefix operator, insert some dummy argument
      before it to satisfy alternation between operators and
      non-operators, and give maximum priority to the left-facing part
      (so that it takes the dummy operator for sure). This will create
      a kind of binary operator where the first argument is always a
      dummy. You can get rid of dummies in post processing.

    * Same principle, in reverse, to implement a suffix operator.

    * To implement brackets, implement "(" and ")" like a prefix and
      suffix operator respectively, then make it so that order("(",
      ")") == "a". This will create a kind of ternary operator where
      the first and third "arguments" are dummies.

    Note: this hasn't been tested very well.
    """

    def helper(left_op, between, right_op, make_left):

        while True:

            if left_op is None:
                o = 'r'
            else:
                o = order(left_op.right_facing, right_op.left_facing)

            if o == 'l':
                left_op, between, make_left = make_left(between)
                continue

            elif o == 'r':
                def new_make_left(*right, aggregate = None):
                    if aggregate is None:
                        this = finalize([right_op, between] + list(right))
                    else:
                        this = finalize([[right_op] + aggregate, between] + list(right))
                    return left_op, this, make_left
                next_id = next(tokenizer)
                try:
                    righter_op = next(tokenizer)
                    return lambda: helper(right_op, next_id, righter_op, new_make_left)
                except StopIteration:
                    return lambda: new_make_left(next_id)

            elif o == 'a':
                def new_make_left(*right, aggregate = []):
                    return make_left(between, *right,
                                     aggregate = [right_op] + aggregate)
                next_id = next(tokenizer)
                try:
                    righter_op = next(tokenizer)
                    return lambda: helper(right_op, next_id, righter_op, new_make_left)
                except StopIteration:
                    return lambda: new_make_left(next_id)

            else:
                raise exc.RichException['unknown_order'](
                    message = "Unknown order.",
                    order = o,
                    left = left_op,
                    right = right_op)

    id1 = next(tokenizer)
    try:
        op1 = next(tokenizer)
    except StopIteration:
        return finalize(id1)

    results = lambda: helper(None, id1, op1, lambda right: [None, right, None])
    while callable(results):
        results = results() #helper(None, id1, op1, lambda right: [None, right, None])

    while results[2] is not None:
        results = results[2](results[1])
    return results[1]



# def operator(x):
#     return Operator(x, x, location = None)

# def open():
#     return Operator("take", "(", location = None)

# def close():
#     return Operator(")", "take", location = None)

# def convert(s):
#     toks = []
#     for c in s:
#         if c.isalpha():
#             toks.append(c)
#         else:
#             left = c if c not in "([{" else 'take'
#             right = c if c not in "}])" else 'take'
#             toks.append(Operator(left, right, location = None))
#     return toks

# #toks = convert("a+b^c+d")
# toks = convert("a~b~Z(c)Z~d+e~f")

# # toks = ['z', open(), 'a',
# #         operator("+"), 'b', close(), 'o',
# #         operator("*"), 'c',
# #         operator('**'), 'd']

# # toks = ['a',
# #         operator("+"), 'b',
# #         operator("**"), 'c',
# #         operator('*'), 'd']

# # toks = ['a',
# #         operator("+"), 'b',
# #         operator("*"), 'c']

# prio = ['take', '^', '*', '+', '=', ',', '(', ')', '~']

# def order(a, b):
#     print(a, b, 1 if prio.index(a) > prio.index(b) else -1)
#     if a == "(" and b == ")":
#         return 'a'
#         # return Operator('take', 'take', location = None)
#     if a == "~" and b == "~":
#         return 'a'
#     if prio.index(a) > prio.index(b):
#         return 'r'
#     else:
#         return 'l'

# print(operator_parse(iter(toks), order))
# 1/0





# class OperatorParse:

#     def __init__(self, source, tokenizer, order):
#         self.source = source
#         self.tokenizer = tokenizer
#         self.order = order

#         self.partials = []
#         self.current_token = None

#         self.leftn = -1
#         self.rightn = -1
#         self.done = False

#         self.result = None

#     def assimilate_to_left(self, token, left, rightn):
#         left.arg[1] = token
#         left.n[1] = rightn
#         self.finalize(left)

#     def assimilate_to_right(self, token, right, leftn):
#         right.arg[0] = token
#         right.n[0] = leftn
#         self.finalize(right)

#     def assimilate_to_both(self, token, left, right, leftn, rightn, args):
#         self.partials[leftn] = Forward(rightn)
#         new_partial = Partial(Operator(left.op.left_facing,
#                                        right.op.right_facing,
#                                        *args)
#                               [left.n[0], right.n[1]],
#                               [left.arg[0], right.arg[1], token],
#                               token.location + left.location + right.location)
#         self.partials[rightn] = new_partial
#         self.finalize(new_partial)

#     def assimilate_current(self):
#         token = self.current_token
#         self.current_token = None
#         self.assimilate(token, self.leftn, self.rightn)

#     def assimilate(self, token, leftn, rightn):
#         # print("assim", token, leftn, rightn)
#         if rightn < 0 and not self.done:
#             if self.current_token:
#                 raise exc.Exception['impossible/curtok'](
#                     "There shouldn't be a current token.")
#             else:
#                 self.leftn = leftn
#                 self.rightn = -1
#                 self.current_token = token
#         else:
#             self.force_assimilate(token, leftn, rightn)

#     def force_assimilate(self, token, leftn, rightn):
#         left = self.partials[leftn] if leftn >= 0 else None
#         right = self.partials[rightn] if rightn >= 0 else None

#         if isinstance(left, Forward):
#             return self.force_assimilate(token, left.n, rightn)
#         if isinstance(right, Forward):
#             return self.force_assimilate(token, leftn, right.n)

#         if not left and not right:
#             self.result = token
#         elif not left:
#             self.assimilate_to_right(token, right, leftn)
#         elif not right:
#             self.assimilate_to_left(token, left, rightn)
#         else:
#             # order = self.matrix[self.groups[left.op[2]], self.groups[right.op[0]]]
#             lop, rop = left.op[2], right.op[0]
#             order = self.order(lop, rop)
#             if order == -1:
#                 self.assimilate_to_left(token, left, rightn)
#             elif order == 0:
#                 raise SyntaxError['priority'](left = lop,
#                                               right = rop,
#                                               locations = [left.loc, right.loc],
#                                               order = self.order,
#                                               parser = self)
#                 # raise Exception("priority error", left.op[2], right.op[0])
#             elif order == 1:
#                 self.assimilate_to_right(token, right, leftn)
#             elif isinstance(order, OpMerge):
#                 self.assimilate_to_both(token, left, right, leftn, rightn, order.merge(left, right))
#             else:
#                 raise exc.Exception['order_specification'](
#                     "Unknown order specification",
#                     dict(order = order,
#                          left = lop,
#                          right = rop,
#                          parser = self))
#                 # raise Exception("unknown", order)

#     def finalize(self, partial):
#         l, r = partial.arg[0], partial.arg[1]
#         if l and r:
#             self.assimilate(NodeToken(tag(partial.op[1], "location", partial.loc),
#                                       partial.arg,
#                                       partial.loc + l.loc + r.loc),
#                             partial.n[0],
#                             partial.n[1])

#     def process(self, token):
#         if isinstance(token, Operator):
#             partial = Partial(op = token,
#                               n = [None, None],
#                               arg = [None, None],
#                               location = token.location)            
#             self.partials.append(partial)
#             self.rightn = len(self.partials) - 1
#             self.assimilate_current()
#         else:
#             self.assimilate(token, len(self.partials) - 1, -1)

#     def parse(self):
#         for tok in self.tokenizer:
#             self.process(tok)
#         self.rightn = -1
#         self.done = True
#         self.assimilate_current()
#         return self.result
























# class Operator(struct):

#     __prefix__ = "#!"
#     __name__ = "Operator"

#     def __init__(self, fixity, width, name, **others):
#         super().__init__(fixity = fixity,
#                          width = width,
#                          name = name,
#                          **others)

#     def __hash__(self):
#         return hash(self.fixity) ^ hash(self.width) ^ hash(self.name)

#     def __eq__(self, other):
#         return (isinstance(other, Operator)
#                 and self.fixity == other.fixity
#                 and self.width == other.width
#                 and self.name == other.name)

#     def other_width(self):
#         width = "short" if self.width == "wide" else "wide"
#         return Operator(self.fixity, width, self.name)



# class Bracket(struct):

#     __prefix__ = "#!"
#     __name__ = "Bracket"

#     def __init__(self, type, **others):
#         super().__init__(type = type,
#                          **others)

#     def __hash__(self):
#         return hash(self.type)

#     def __eq__(self, other):
#         return (isinstance(other, Bracket)
#                 and self.type == other.type)



class Partial:
    def __init__(self, op, n, arg, loc):
        self.op = op
        self.n = n
        self.arg = arg
        self.loc = loc
    def __str__(self):
        return "Partial[%s, %s, %s]" % (self.op, self.n, self.arg)
    def __repr__(self):
        return str(self)

class NodeToken:
    def __init__(self, op, args, loc):
        self.op = op
        self.args = args
        self.loc = loc
    def __str__(self):
        return "NodeToken[%s, %s]" % (self.op, self.args)
    def __repr__(self):
        return str(self)

class Forward:
    def __init__(self, n):
        self.n = n
    def __str__(self):
        return "Forward[%s]" % self.n
    def __repr__(self):
        return str(self)

class OpMerge:
    def merge(self, left, right):
        return [left.op[1], right.op[1]]

class BracketMerge(OpMerge):
    def __init__(self, mappings):
        self.mappings = mappings

    def merge(self, left, right):
        try:
            return self.mappings[left.op[1].name + right.op[1].name]
        except KeyError as e:
            raise SyntaxError["bracket_mismatch"](
                open = left.op[1],
                close = right.op[1],
                nodes = [left, right]
                )

