

from . import engine as mod_engine
from .engine import (
    RawGenerator as raw,
    TextGenerator as text,
    WSGenerator as gen_ws,
    MultiGenerator2 as gen,
)


def em(engine, node, v, em):
    # emphasis (italics)
    return gen(engine(v), raw("<em>"), engine(em), raw("</em>"))

def strong(engine, node, v, em):
    # strong emphasis (bold)
    return gen(engine(v), raw("<strong>"), engine(em), raw("</strong>"))

def code(engine, node, lang, code):
    # inline code snippets
    wsl, wsr, code = mod_engine.extract_and_codehl(engine, lang, code, True)
    return gen(raw('<span class="highlight"><code>'),
               gen_ws(lang),
               wsl,
               # Note: code.strip() removes the line break pygments'
               # HTMLFormatter puts at the end of the generated code.
               # That line break produces whitespace we might not want.
               raw(code.strip()),
               wsr,
               raw('</code></span>'))

def code_block(engine, node, lang, code):
    # blocks of code
    wsl, wsr, code = extract_and_codehl(engine, lang, code, False)
    return gen(raw('<div class="highlight"><pre>'),
               raw(code),
               raw('</pre></div>'))



