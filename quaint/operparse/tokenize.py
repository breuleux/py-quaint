
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
    def __str__(self):
        return "Token%s" % self.__dict__
    def __repr__(self):
        return str(self)


class RegexpMatcher:

    def __init__(self, regexp):
        self.regexp = regexp

    def __call__(self, text, pos, wsb, wsa):
        eee



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
                chars, rxp, rule_skip_ws, descr = rule
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

        for rxp, skip_ws, descr in rules:
            match = rxp.match(text, pos2 if skip_ws else pos)
            if match:
                start, end = match.regs[0]
                wsa = self.ws(text, end)
                token, endpos = descr(source, match, text[pos:pos2], text[end:end + wsa])
                return token, endpos - pos

        if pos + wsb >= len(text):
            return False, 0

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

    def __init__(self, tokenizer, inherent_fixity, surround_map):
        self.buffer = []
        self.buffer_pfx = True
        self.inherent_fixity = inherent_fixity
        self.surround_map = surround_map
        super().__init__(tokenizer)

    def process_buffer(self, pfx, sfx, start):
        n = len(self.buffer) - start
        if n == 0:
            return
        elif pfx and sfx:
            for i in range(start, len(self.buffer)):
                self.buffer[i].fixity = None
                self.buffer[i].type = "nullary"
        elif pfx:
            for i in range(start, len(self.buffer)):
                self.buffer[i].fixity = "prefix"
        elif sfx:
            for i in range(start, len(self.buffer)):
                self.buffer[i].fixity = "suffix"
        else:
            tok = self.buffer[start]
            fixity = self.inherent_fixity(tok)
            self.buffer[start].fixity = fixity
            self.process_buffer(fixity in ('infix', 'prefix'),
                                sfx, start + 1)


    def __iter__(self):

        for tok in iter(self.tokenizer):
            fixity = getattr(tok, 'fixity', None)

            if fixity == "?fix":
                self.buffer.append(tok)

            else:
                sfx, newpfx = self.surround_map.get(fixity, (False, False))
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


class Alternator(TokenizerWrapper):

    def __init__(self, tokenizer, token0, sandwich_void, sandwich_juxt):
        self.token0 = token0
        self.sandwich_void = sandwich_void
        self.sandwich_juxt = sandwich_juxt
        super().__init__(tokenizer)

    def __iter__(self):

        last = self.token0

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
                yield self.sandwich_void(ws, current)
            elif t in ["suffix/id"]:
                yield void
                yield self.sandwich_juxt(void, current)
            elif t in ["suffix/prefix"]:
                yield void
                ws = self.sandwich_juxt(void, current)
                yield ws
                yield self.sandwich_void(ws, current)
                
            yield current
            last = current

        if last and last.type == 'operator':
            yield self.sandwich_void(last, None)


