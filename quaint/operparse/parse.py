
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
        results = results()

    while results[2] is not None:
        results = results[2](results[1])
    return results[1]
