
try:
    import builtins
except ImportError:
    import __builtin__ as builtins


class DerivableException(type):
    """
    Metaclass easing derivation. When declaring a new class, set its
    metaclass to DerivableException, and the class itself will gain
    the specialize(name) method.

    C.specialize(name) will create a subclass of C with name C/name
    and it will return it.

    C.specialize("a/b") is shorthand for
    C.specialize("a").specialize("b").
    
    C[name] is shorthand for C.specialize(name)

    Multiple calls to C.specialize with the same name will return
    cached versions.
    """

    __wrapped__ = {}

    def __new__(cls, name, bases, dct):
        # return super(DerivableException, cls).__new__(cls, name, bases, dct)
        return type.__new__(cls, name, bases + (object, ), dct)

    def __init__(cls, name, bases, dct):
        cls.__derived__ = {}
        super(DerivableException, cls).__init__(name, bases, dct)
        cls.__original__ = None

    def __subclasscheck__(cls, other):
        original = getattr(cls, '__original__', None)
        if (original and issubclass(other, original)):
            return True
        return super(DerivableException, cls).__subclasscheck__(other)

    def __instancecheck__(cls, instance):
        original = getattr(cls, '__original__', None)
        if (original and isinstance(instance, original)):
            return True
        return super(DerivableException, cls).__instancecheck__(instance)

    def specialize(cls, name):
        """
        Create a subclass of this class with name C/name, and return
        it.

        cls.specialize("a/b") is shorthand for
        cls.specialize("a").specialize("b").

        Multiple calls to C.specialize with the same name will return
        cached versions.
        """
        parts = name.split("/")
        if len(parts) == 1:
            if name in cls.__derived__:
                return cls.__derived__[name]
            else:
                new_cls = DerivableException(cls.__name__ + "/" + name,
                                             (cls,),
                                             {})
                cls.__derived__[name] = new_cls
                return new_cls
        else:
            while parts:
                cls = cls.specialize(parts.pop(0))
            return cls

    def __getitem__(cls, item):
        """
        Shorthand for cls.specialize(item)
        """
        return cls.specialize(item)

    @classmethod
    def wrap(mcls, exctype):
        """
        Make a subclass of the given exception type using
        DerivableException as the metaclass. The resulting class can
        be derived using specialize or __getitem__.

        Wrapping the same class twice returns the same result.
        """
        if exctype in mcls.__wrapped__:
            return mcls.__wrapped__[exctype]
        else:
            wrapped = DerivableException(
                exctype.__name__,
                (exctype,),
                {})
            wrapped.__original__ = exctype
            mcls.__wrapped__[exctype] = wrapped
            return wrapped


def __wrap_builtins():
    g = globals()
    for builtin in dir(builtins):
        if builtin.endswith('Error') or builtin.endswith('Exception'):
            g[builtin] = DerivableException.wrap(getattr(builtins, builtin))
            __all__.append(builtin)

def mod_builtins():
    """
    Replaces all builtins by versions wrapped using
    DerivableException.wrap.

    It is not recommended to do this, and there is pretty much no
    benefit.
    """
    g = globals()
    for builtin in dir(builtins):
        if builtin.endswith('Error') or builtin.endswith('Exception'):
            setattr(builtins, builtin, g[builtin])


__all__ = ['DerivableException']
__wrap_builtins()

class RichException(Exception):
    def __init__(self, **keywords):
        self.__dict__.update(keywords)
    def __str__(self):
        return "[%s]" % (", ".join("%s = %r" % (k, v)
                                   for k, v in self.__dict__.items()))

