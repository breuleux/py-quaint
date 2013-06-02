
import re

from .common import Void, TokenizerError, SyntaxError
from .location import Location, Source


#################
### TOKENIZER ###
#################

class Token:
    def __init__(self, **args):
        self.location = None
        self.__dict__.update(args)
    # def __getitem__(self, i):
    #     return self.args[i]
    # def __setitem__(self, i, value):
    #     self.args[i] = value
    # def __iter__(self):
    #     return iter(self.args)
    def __str__(self):
        return "Token%s" % self.__dict__
    def __repr__(self):
        return str(self)


class SubTokenizer:
    """
    SubTokenizer(rules) creates a tokenizer from various rules. Each
    rule is of the form:

        [chrs, regexp, spangroup, skip_ws, description]

        chrs: a list of characters that trigger the rule (whitespace skipped); if True
            then all characters trigger the rule.
        regexp: a regular expression that will extract the token
        spangroup: the group number representing the token's "extent"; the length
            of the string corresponding to that group, plus the length of any whitespace
            skipped before it, will be returned as the number of characters to skip
            to get past the token.
        skip_ws: boolean; if True, then any whitespace characters will be skipped
        description: either a function or a list of integers or strings
            if function: called with the regexp's match object and returns a list
                of the token's arguments. If "!wsb" or "!wsa" are in the list, they
                will be translated as per what follows.
            if list: becomes the token's arguments, with the following translations:
                function: replaced by the result of calling the function with the
                    regexp's match object
                int: replaced by the string for the corresponding group in the
                    regexp
                str: verbatim
                "!wsb": replaced by the whitespace matched before the string (is null
                    if skip_ws is False
                "!wsa": replaced by any whitespace matched *after* the string

        Example:
        >>> st = SubTokenizer([["abc", re.compile("((a)b)(c*)"), 0, True, ["id", "hello", 1, 2, "!wsa"], None]])
        >>> st.read(Source("  abccccc def"), 0)
        (Token['id', 'hello', 'a', 'ccccc', ' '], 4)

        i.e. a token with arguments "id", "hello", "a" (matching group
        1), "ccccc" (matching group 2), " " (the whitespace right
        after it). The number 4 corresponds to the length of group 0,
        i.e. the group "((a)b)" in the regular expression, plus the
        whitespace before the token, so after reading this token we
        will have to position ourselves on the first c before reading
        the next.

    Rules are tried in order. The first to match is returned. If pos
    is at the end of the string, [None, 0] is returned. If pos is
    *not* at the end of the string, and yet no match is found, an
    exception is raised, so the rules should cover all expected
    inputs.

    Provides the `read(source, pos)` method which, given a Source
    object and an integer position, returns a Token beginning at that
    position and the number of characters to skip to get past the
    token.
    """

    def __init__(self, rules, ws_re):

        self.ws_re = ws_re
        self.ws_cache = (-1, None, 0)

        self.rules = rules
        self.rulemap = ([[] for i in range(129)],
                        [[] for i in range(129)])
        for rulemap, skip_ws in ((self.rulemap[0], False),
                                 (self.rulemap[1], True)):
            for rule in rules:
                chars, rxp, spangroup, rule_skip_ws, descr = rule
                if skip_ws == rule_skip_ws:
                    if chars is True:
                        for i in range(129):
                            rulemap[i].append(rule[1:])
                    else:
                        for c in chars:
                            i = min(ord(c), 128)
                            rulemap[i].append(rule[1:])

    def ws(self, text, pos):
        cache_pos, cache_text, length = self.ws_cache
        if pos == cache_pos and text is cache_text:
            return length
        ws = self.ws_re.match(text, pos)
        s = ws.span()
        length = s[1] - s[0]
        self.ws_cache = (pos, text, length)
        return length

    def read(self, source, pos):
        """
        source = Source object
        it is assumed that pos > 0
        """

        text = source.text
        if pos >= len(text):
            # out of bounds
            return [False, 0]

        # we compute whitespace before once for all rules
        wsb = self.ws(text, pos)
        
        # the first pos past whitespace
        pos2 = pos + wsb

        # to speed up processing, self.rulemap associates each ASCII
        # character to a list of rules that can apply there; there are
        # two possible starting points: pos and pos2, depending on
        # whether the rule skips whitespace or not
        rules = self.rulemap[0][min(ord(text[pos]), 128)]
        if pos2 < len(text):
            rules = rules + self.rulemap[1][min(ord(text[pos2]), 128)]

        for rxp, spangroup, skip_ws, descr in rules:
            match = rxp.match(text, pos2 if skip_ws else pos)
            if match:
                groups = match.groups()
                # if spangroup == -1:
                #     start, end = match.regs[]
                #     wsa = self.ws(text, end)
                #     start, end = pos, match.regs[0] + wsa
                # else:
                start, end = match.regs[spangroup + 1]
                wsa = self.ws(text, end)

                # build argument list
                if callable(descr):
                    descr = descr(match, text[pos:pos2], text[end:end + wsa])
                    translate_int = False
                else:
                    translate_int = True

                new_descr = {}
                for k, x in descr.items():
                    if translate_int and x == -1:
                        new_descr[k] = (text[pos:pos2]
                                        + groups[0]
                                        + text[end:end + wsa])
                        continue
                    elif translate_int and isinstance(x, int):
                        new_descr[k] = groups[x]
                        continue
                    elif callable(x):
                        x = x(match, text[pos:pos2], text[end:end + wsa])

                    if x == '!wsb':
                        new_descr[k] = text[pos:pos2]
                    elif x == '!wsa':
                        new_descr[k] = text[end:end + wsa]
                    else:
                        new_descr[k] = x

                return (Token(location = Location(source, (start, end)),
                              **new_descr),
                        end - pos)

        if pos + wsb >= len(text):
            return [False, 0]

        raise TokenizerError['no_token'](
            source = source,
            pos = pos,
            subtokenizer = self)





class Tokenizer:

    def __init__(self, source, subtok, initial_state = 'normal'):
        self.subtok = subtok
        self.source = source
        self.mark = 0
        self.stack = []
        self.st = None
        self.push_state(initial_state)

    def install_state(self, state):
        self.st = self.subtok[state]

    def push_state(self, state):
        self.stack.append(state)
        self.install_state(state)

    def pop_state(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.install_state(self.stack[-1])
        
    def __iter__(self):
        while True:
            tok, skip = self.st.read(self.source, self.mark)
            if skip:
                self.mark += skip
            if tok:
                action = yield tok
                if action:
                    command, *args = action
                    if command == 'pop':
                        self.pop_state()
                    elif command == 'push':
                        self.push_state(args[0])
                    else:
                        raise TokenizerError["unknown_action"](
                            token = results[-1],
                            action = action)
            else:
                return


class TokenizerWrapper:

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.source = self.tokenizer.source


class GenericTokenizerWrapper(TokenizerWrapper):

    def __init__(self, tokenizer, f):
        super().__init__(tokenizer)
        self.f = f

    def __iter__(self):
        for x in self.f(self.tokenizer):
            yield x

def tokenizer_wrapper(f):
    return lambda tokenizer: GenericTokenizerWrapper(tokenizer, f)



class FixityDisambiguator(TokenizerWrapper):

    def __init__(self, tokenizer):
        self.buffer = []
        self.buffer_pfx = True
        super().__init__(tokenizer)

    def process_buffer(self, pfx, sfx, start):
        n = len(self.buffer) - start
        if n == 0:
            return
        elif pfx and sfx:
            if n > 1:
                raise SyntaxError["ambiguous_nullary"](operators = self.buffer[start:])
            elif n == 1:
                self.buffer[0].fixity = None
                self.buffer[0].type = "nullary"
                # tok = self.buffer[0]
                # self.buffer[0] = Token(tok.location, "nullary", *tok[1:])
        elif pfx:
            for i in range(start, len(self.buffer)):
                self.buffer[i].fixity = "prefix"
                # tok = self.buffer[i]
                # self.buffer[i] = Token(tok.location, "prefix", *tok[1:])
        elif sfx:
            for i in range(start, len(self.buffer)):
                self.buffer[i].fixity = "suffix"
                # tok = self.buffer[i]
                # self.buffer[i] = Token(tok.location, "suffix", *tok[1:])
        else:
            tok = self.buffer[start]
            # wsl, wsr = tok[1:3]
            # wsl = len(wsl)
            # wsr = len(wsr)
            if tok.own_line:
                wsl = tok.height_before - 1
                wsr = tok.height_after - 1
            else:
                wsl = tok.space_before if not tok.height_before else None
                wsr = tok.space_after if not tok.height_after else None
                
            if ((wsl is not None and wsr is not None)
                and ((wsl == wsr == 0) or (wsl > 0 and wsr > 0))):
                self.buffer[start].fixity = "infix"
                # self.buffer[start] = Token(tok.location, "infix", *tok[1:])
                self.process_buffer(True, sfx, start + 1)
            elif wsl is None or wsl > 0:
                self.buffer[start].fixity = "prefix"
                # self.buffer[start] = Token(tok.location, "prefix", *tok[1:])
                self.process_buffer(True, sfx, start + 1)
            elif wsr is None or wsr > 0:
                self.buffer[start].fixity = "suffix"
                # self.buffer[start] = Token(tok.location, "suffix", *tok[1:])
                self.process_buffer(False, sfx, start + 1)


    def __iter__(self):
        assoc = {"infix": (True, True),
                 "prefix": (False, True),
                 "suffix": (True, False)}

        for tok in iter(self.tokenizer):
            fixity = getattr(tok, 'fixity', None)

            if fixity == "?fix":
                self.buffer.append(tok)

            else:
                sfx, newpfx = assoc.get(fixity, (False, False))
                self.process_buffer(self.buffer_pfx, sfx, 0)
                self.buffer.append(tok)
                self.buffer_pfx = newpfx
                for tok in self.buffer:
                    yield tok
                self.buffer = []

        if self.buffer:
            self.process_buffer(self.buffer_pfx, True, 0)
            for tok in self.buffer:
                yield tok


def sandwich(left, right, params):
    location = Location(left.location.source if left else right.location.source,
                        (left.location.end if left else right.location.start,
                         right.location.start if right else left.location.end))
    return Token(location = location,
                 space_before = left.space_after if left else 0,
                 space_after = right.space_before if right else 0,
                 own_line = ((not left or left.height_after)
                             and (not right or right.height_before)),
                 height_before = left.height_after if left else 0,
                 height_after = right.height_before if right else 0,
                 **params)

class Alternator(TokenizerWrapper):

    def __init__(self, tokenizer, void_params, juxt_params):
        self.void_params = void_params
        self.juxt_params = juxt_params
        super().__init__(tokenizer)

    def sandwich_void(self, left, right):
        return sandwich(left, right, self.void_params)

    def sandwich_juxt(self, left, right):
        return sandwich(left, right, self.juxt_params)

    # def sandwich_void(self, left, right):
    #     location = Location(left.location.source,
    #                         (left.location.end,
    #                          right.location.start if right else left.location.end))
    #     return Token(location = location,
    #                  space_before = left.space_after,
    #                  space_after = right.space_before if right else 0,
    #                  **self.void_params)

    # def sandwich_juxt(self, left, right):
    #     location = Location(left.location.source,
    #                         (left.location.end, right.location.start))
    #     return Token(location = location,
    #                  space_before = left.space_after,
    #                  space_after = right.space_before,
    #                  **self.juxt_params)

    def __iter__(self):

        # The beginning of the stream acts like an infix operator
        last = Token(location = Location(self.tokenizer.source, (0, 0)),
                     fixity = "infix",
                     space_before = 0,
                     space_after = 0,
                     height_before = 0,
                     height_after = 0)

        for current in self.tokenizer:

            void = self.sandwich_void(last, current)
            ws = self.sandwich_juxt(last, current)

            t1 = getattr(last, "fixity", None) or "id"
            t2 = getattr(current, "fixity", None) or "id"
            t = t1 + "/" + t2

            if t in ["id/id"]:
                yield ws
            elif t in ["prefix/infix",
                       "infix/infix",
                       "infix/suffix",
                       "infix/prefix",
                       "suffix/infix",
                       "prefix/prefix",
                       "prefix/suffix",
                       "suffix/suffix"]:
                yield void
            elif t in ["id/prefix"]:
                yield ws
                yield void
            elif t in ["suffix/id"]:
                yield void
                yield ws
            elif t in ["suffix/prefix"]:
                yield void
                yield ws
                yield void

            yield current
            last = current

        if last and last.type == 'operator':
            yield self.sandwich_void(last, None)


