
import exc
from bisect import bisect_right
from functools import reduce

__all__ = ['Source', 'Location', 'merge_locations']


class Source(object):

    def __init__(self, text, url = None):
        self.text = text
        self.url = url
        self.lines = [0]
        for i, c in enumerate(text):
            if c == "\n":
                self.lines.append(i + 1)

    def linecol(self, pos):
        if 0 <= pos <= len(self.text):
            line = bisect_right(self.lines, pos) - 1
            return (line + 1, pos - self.lines[line] + 1)
        else:
            raise exc.IndexError['sourcepos'](dict(pos = pos,
                                                   source = self,
                                                   length = len(self.text)))

    def substring(self, start, end):
        return self.text[start:end]

    def __descr__(self, recurse):
        if self.url is None:
            return [self.text]
        else:
            return [{"file"}, self.url, self.text]


class Location(object):
    """
    Location object - meant to represent some code excerpt. It
    contains a pointer to the source and a (start, end) tuple
    representing the extent of the excerpt in the source.

    Methods are provided to get line/columns for the excerpt, raw or
    formatted.
    """
    def __init__(self, source, span, tokens = []):
        self.source = source
        self.span = span
        self.start = span[0]
        self.end = span[1]
        self.tokens = tokens
        self._linecol = None

    def get(self):
        return self.source.substring(self.start, self.end)

    def linecol(self):

        def helper(source, start, end, promote_zerolength = False):
            end -= 1 # end position is now inclusive
            l1, c1 = source.linecol(start)
            if start > end:
                return ((l1, c1), (l1, c1) if promote_zerolength else None)
            l2, c2 = source.linecol(end)
            return ((l1, c1), (l2, c2))

        if self._linecol is not None:
            return self._linecol

        self._linecol = helper(self.source, self.start, self.end)
        return self._linecol

    def ref(self):
        """
        Returns a string representing the location of the excerpt. If
        the excerpt is only one character, it will format the location
        as "line:column". If it is on a single line, the format will
        be "line:colstart-colend". Else,
        "linestart:colstart-lineend:colend". In the special case where
        the excerpt is a token not in the source text (e.g. one that
        was inserted by the parser), "<" will be appended to the end.
        """
        ((l1, c1), lc2) = self.linecol()
        if lc2 is not None:
            l2, c2 = lc2
        if lc2 is None or l1 == l2 and c1 == c2:
            return ("%s:%s" % (l1, c1)) + ("<" if lc2 is None else "")
        elif l1 == l2:
            return "%s:%s-%s" % (l1, c1, c2)
        else:
            return "%s:%s-%s:%s" % (l1, c1, l2, c2)

    def change_start(self, n):
        return Location(self.source, (self.start + n, self.end))

    def change_end(self, n):
        return Location(self.source, (self.start, self.end + n))

    def at_start(self):
        return Location(self.source, (self.start, self.start))

    def at_end(self):
        return Location(self.source, (self.end, self.end))

    def __add__(self, loc):
        return merge_locations([self, loc])

    def __radd__(self, loc):
        return merge_locations([loc, self])

    def __gt__(self, loc):
        return loc.start < self.start

    def __lt__(self, loc):
        return loc.start > self.start

    def __ge__(self, loc):
        return loc.start <= self.start

    def __le__(self, loc):
        return loc.start >= self.start

    def __str__(self):
        return self.ref()

    def __repr__(self):
        return self.ref()

    def __descr__(self, recurse):
        return [{"location"},
                recurse(self.source),
                (self.start, self.end, {"hl2"})]


class Locations:

    __hls__ = ["hl1", "hl2", "hl3", "hlE"]

    def __init__(self, locations):
        self.locations = locations

    def get_hl(self, i):
        return self.__hls__[i % len(self.__hls__)]

    def __descr__(self, recurse):
        locations = [(l.start, l.end, {self.get_hl(i)})
                     for i, l in enumerate(self.locations)]
        if self.locations:
            return [{"location"},
                    recurse(self.locations[0].source)] + locations
        return []
        

def merge_locations(locations):
    """
    Handy function to merge *contiguous* locations. (note: assuming
    that you gave a, b, c in the right order, merge_locations(a, b, c)
    does the same thing as merge_locations(a, c). However, a future
    version of the function might differentiate them, so *don't do
    it*)

    TODO: it'd be nice to have a class for discontinuous locations, so
    that you could highlight two tokens on the same line that are not
    next to each other. Do it if a good use case arise.
    """
    locations = [loc for loc in locations if loc]
    if not locations:
        return Location("", (0, 0), [])
    return Location(source = locations[0].source,
                    span = (min(l.start for l in locations),
                            max(l.end for l in locations)))

