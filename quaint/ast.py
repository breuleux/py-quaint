

class AST:

    def __init__(self):
        self.whitespace_left = ""
        self.whitespace_right = ""


class quaintstr(str, AST):

    def __new__(cls, s, location = None):
        ob = super(quaintstr, cls).__new__(cls, s)
        return ob

    def __init__(self, s, location = None):
        super().__init__()
        self.location = location

    def raw(self):
        if not self.location:
            return self
        else:
            return self.location.get()


class ASTNode(AST):

    def __init__(self, *args, location = None):
        super().__init__()
        self.args = list(args)
        if not location:
            for arg in args:
                if hasattr(arg, 'location'):
                    if location is None:
                        location = arg.location
                    else:
                        location += arg.location
        self.location = location

    def signature(self):
        return (self.__class__,)

    def raw(self):
        if not self.location:
            return ""
        else:
            return self.location.get()

    def __getitem__(self, i):
        return self.args[i]

    def __setitem__(self, i, value):
        self.args[i] = value

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '#{0.__class__.__name__}{0.args!r}'.format(self)

    def __descr__(self, descr):
        name = self.__class__.__name__
        return [(({"@quaint.ast", "@quaint.ast." + name, "object"},)
                 + tuple(descr(x) for x in self.args))]


class Op(ASTNode):

    def __init__(self, operator, *args, location = None, wide = None):
        super().__init__(*args, location = location)
        self.wide = wide
        self.operator = operator

    def signature(self):
        return (self.__class__,
                self.operator,
                tuple(not isinstance(arg, Void)
                      for arg in self.args))

    def __str__(self):
        return '#{0.__class__.__name__}:{0.operator}{0.args!r}'.format(self)

    def __descr__(self, descr):
        name = self.__class__.__name__
        return [(({"@quaint.ast", "@quaint.ast." + name, "object"}, descr(self.operator))
                 + tuple(descr(x) for x in self.args))]

    @classmethod
    def is_operator(cls, op, name):
        return (isinstance(op, cls) and op.operator == name)


class InlineOp(Op):
    pass

class BlockOp(Op):
    pass


class Void(ASTNode):
    def __init__(self, location = None):
        self.text = location.get() if location else ""
        super().__init__(location = location)
    def __nonzero__(self):
        return False


class Nullary(ASTNode):
    def __init__(self, text, location = None):
        self.text = text
        super().__init__(location = location)
