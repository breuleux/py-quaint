
import re

from .common import Void, TokenizerError, SyntaxError
from .location import Location, Source



#################
### TOKENIZER ###
#################

class Token:
    def __init__(self, kind, args, ws, loc, **kw):
        self.kind = kind
        self.args = args
        self.ws = ws
        self.loc = loc
        self.all = [kind, args, ws]
        self.__dict__.update(kw)
    def __getitem__(self, i):
        return self.all[i]
    def __iter__(self):
        return iter(self.all)
    def __str__(self):
        return "Token[%s]" % ", ".join(map(str, self.all))
    def __repr__(self):
        return str(self)


class SubTokenizer:
    """
    SubTokenizer(rules) creates a tokenizer from various rules. Each
    rule is of the form:

        [chrs, regexp, spangroup, [take_wsb, take_wsa], description, action]

        chrs: a list of characters that trigger the rule (whitespace skipped); if True
            then all characters trigger the rule.
        regexp: a regular expression that will extract the token
        spangroup: the group number representing the token's "extent"; the length
            of the string corresponding to that group, plus the length of any whitespace
            skipped before it, will be returned as the number of characters to skip
            to get past the token.
        take_wsb: boolean; if True, then any whitespace characters will be skipped,
            and their number will be stored in the return Token. Otherwise whitespace
            is not skipped.
        take_wsa: same as take_wsb, but for the whitespace after the token.
        description: a list of things to include as the token's arguments; if
            a number is given, the string for the corresponding group in the regexp
            will be inserted. Anything else will be inserted verbatim.
        action: some action to take when reading the token. It can be either:
            ["push", subtokenizer_name] to instruct a Tokenizer to switch to some other
                SubTokenizer.
            ["pop"] to instruct a Tokenizer to switch back to the SubTokenizer it was
                using right before this one.
            These actions are usually needed to pop in and out of a string context.

        Example:
        >>> st = SubTokenizer([["abc", re.compile("((a)b)(c*)"), 0, [True, True], ["id", "hello", 1, 2], None]])
        >>> st.read(Source("  abccccc def"), 0)
        (Token[id, ['hello', 'a', 'ccccc'], [2, 1]], 4)

        i.e. a token of kind "id" with arguments "hello", "a" and
        "ccccc" (the latter two are the strings associated to groups 1
        and 2 in the regular expression "((a)b)(c*)"), which has 2
        whitespaces before (which we skipped because take_wsb is True)
        and 1 whitespace after. The number 4 corresponds to the length
        of group 0, i.e. the group "((a)b)" in the regular expression,
        plus the whitespace before the token, so after reading this
        token we will have to position ourselves on the first c before
        reading the next.

    Rules are tried in order. The first to match is returned. If pos is
    at the end of the string, [False, 0] is returned. If pos is *not* at
    the end of the string, and yet no match is found, an exception is
    raised, so the rules should cover all expected inputs.

    Provides the `read(source, pos)` method which, given a Source
    object and an integer position, returns a Token beginning at that
    position and the number of characters to skip to get past the
    token.
    """

    def __init__(self, rules, ws_re):
        self.ws_re = ws_re
        self.rules = rules
        self.rulemap = [[] for i in range(129)]
        for rule in rules:
            chars, *rest = rule
            if chars is True:
                for i in range(129):
                    self.rulemap[i].append(rest)
            else:
                for c in chars:
                    i = min(ord(c), 128)
                    self.rulemap[i].append(rest)

    def ws(self, text, pos):
        ws = self.ws_re.match(text, pos)
        s = ws.span()
        return s[1] - s[0]

    def read(self, source, pos):
        def compute(descr, groups):
            if isinstance(descr, int):
                return groups[descr]
            elif callable(descr):
                return descr(*groups)
            else:
                return descr

        text = source.text
        if pos >= len(text):
            return [False, 0]
        wsb = self.ws(text, pos)
        pos2 = pos + wsb
        rules = self.rulemap[min(ord(text[pos2]), 128)]
        for rxp, spangroup, (take_wsb, take_wsa), descr, action in rules:
            match = rxp.match(text, pos2 if take_wsb else pos)
            if match:
                groups = match.groups()
                span = match.regs[spangroup + 1]
                descr = [compute(x, groups) for x in descr]
                return (Token(descr[0], descr[1:],
                              (wsb if take_wsb else 0,
                               self.ws(text, span[1]) if take_wsa else 0),
                              loc = Location(source, span),
                              action = action),
                        (span[1] - pos))
        if pos + wsb >= len(text):
            return [False, 0]
        raise TokenizerError['no_token'](source = source,
                                         pos = pos,
                                         subtokenizer = self)


def subtok_rule(chrs, rxp, fields, span = 0, ws = (True, True), action = None):
    if isinstance(rxp, str):
        rxp = re.compile("(" + rxp + ")")
    return (chrs, rxp, span, ws, fields, action)



class Tokenizer:

    def __init__(self, source, subtok, initial_state = 'normal'):
        self.subtok = subtok
        self.source = source

        self.buffer = []
        self.buffer_pfx = True
        self.last = Token("start", (), (0, 0), loc = Location(source, (0, 0)))
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

    def dump_buffer(self):
        b = self.buffer
        def helper(last, i):
            if i >= len(b):
                return []
            else:
                current = b[i]
                last = last or Token("n/a", (), (0, 0), loc = Location(self.source, (0, 0)))
                t1, _, (_, wsr) = last
                t2, _, (wsl, _) = current
                pl = last.loc.end
                pr = current.loc.start
                ws = Token("infix", ("",), (wsl, wsr), loc = Location(self.source, (pl, pr)))
                void = Token("id", (Void,), (wsl, wsr), loc = Location(self.source, (pl, pr)))
                t = t1 + "/" + t2
                if t in ["id/id"]:
                    return [ws] + helper(None, i)
                elif t in ["prefix/infix",
                           "infix/infix",
                           "infix/suffix",
                           "start/prefix",
                           "start/infix",
                           "start/suffix",
                           "infix/prefix",
                           "suffix/infix",
                           "prefix/prefix",
                           "prefix/suffix",
                           "suffix/suffix"]:
                    return [void] + helper(None, i)
                elif t in ["id/prefix"]:
                    return [ws, void] + helper(None, i)
                elif t in ["suffix/id"]:
                    return [void, ws] + helper(None, i)
                elif t in ["suffix/prefix"]:
                    return [void, ws, void] + helper(None, i)
                else:
                    return [current] + helper(current, i + 1)

        results = helper(self.last, 0)

        actions = [getattr(tok, "action", None) for tok in results]
        if [a for a in actions[:-1] if a]:
            raise SyntaxError['lookahead_action'](tokens = results,
                                                  actions = actions)
            # raise Exception("Actions associated to operators should not require lookahead")
        if actions and actions[-1]:
            action = actions[-1]
            command, *args = action
            if command == 'pop':
                self.pop_state()
            elif command == 'push':
                self.push_state(args[0])
            else:
                raise SyntaxError["unknown_action"](token = results[-1],
                                                    action = action)
                # raise Exception("Unknown command: " + str(action))

        self.buffer = []
        if results:
            self.last = results[-1]
        return results

    def process_buffer(self, pfx, sfx, start):
        n = len(self.buffer) - start
        if n == 0:
            return
        elif pfx and sfx:
            if n > 1:
                raise SyntaxError["ambiguous_nullary"](operators = self.buffer[start:])
                # raise Exception("Cannot have more than one operator in this situation.")
            elif n == 1:
                tok = self.buffer[0]
                self.buffer[0] = Token("id", ["id"] + tok.args, tok.ws, loc = tok.loc)
        elif pfx:
            for i in range(start, len(self.buffer)):
                tok = self.buffer[i]
                self.buffer[i] = Token("prefix", tok.args, tok.ws, loc = tok.loc)
        elif sfx:
            for i in range(start, len(self.buffer)):
                tok = self.buffer[i]
                self.buffer[i] = Token("suffix", tok.args, tok.ws, loc = tok.loc)
        else:
            tok = self.buffer[start]
            wsl, wsr = tok.ws
            if (wsl == wsr == 0) or (wsl > 0 and wsr > 0):
                self.buffer[start] = Token("infix", tok.args, tok.ws, loc = tok.loc)
                self.process_buffer(True, sfx, start + 1)
            elif wsl > 0:
                self.buffer[start] = Token("prefix", tok.args, tok.ws, loc = tok.loc)
                self.process_buffer(True, sfx, start + 1)
            elif wsr > 0:
                self.buffer[start] = Token("suffix", tok.args, tok.ws, loc = tok.loc)
                self.process_buffer(False, sfx, start + 1)

    def next_batch(self):
        tok, skip = self.st.read(self.source, self.mark)
        if skip:
            self.mark += skip

        assoc = {"id": (False, False),
                 "infix": (True, True),
                 "prefix": (False, True),
                 "suffix": (True, False)}

        if tok:
            if tok.kind in assoc:
                sfx, newpfx = assoc[tok.kind]
                self.process_buffer(self.buffer_pfx, sfx, 0)
                self.buffer.append(tok)
                self.buffer_pfx = newpfx
                return self.dump_buffer()

            elif tok.kind == "?fix":
                self.buffer.append(tok)
                return self.next_batch()

        elif self.buffer:
            self.process_buffer(self.buffer_pfx, True, 0)
            return self.dump_buffer()
        elif self.last and self.last.kind != "id":
            self.last = None
            return [Token("id", (Void,), (0, 0),
                          loc = Location(self.source, (self.mark, self.mark)))]
        else:
            return False

    def __iter__(self):
        while True:
            batch = self.next_batch()
            if batch is False:
                return
            for tok in batch:
                yield tok

