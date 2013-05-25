
from .. import exc


##############
### Errors ###
##############

class SyntaxError(exc.RichException, exc.SyntaxError):
    pass

class TokenizerError(SyntaxError):
    pass


############
### Void ###
############

class Void:
    """
    Singleton representing an empty argument for prefix or postfix
    operators.
    """
    def __str__(self):
        return "Void"
    def __sub__(self, other):
        return -other
    def __add__(self, other):
        return +other
    def __repr__(self):
        return "Void"
    def __descr__(self, descr):
        return ({"@Void"}, '∅')

Void = Void()



