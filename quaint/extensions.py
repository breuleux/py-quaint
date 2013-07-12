
from os.path import join as pj
from .engine import Once
from .lib import link_type, plain_or_code, Gen, GenFor
from .builders import HTMLMetaNode


def use_theme(engine, path = 'theme/'):

    @link_type('media')
    def media_link(engine, node, text, link):
        return {'tag': 'img',
                'src': pj(path, 'media', plain_or_code(engine, link)),
                'alt': text.raw(),
                'body': ''}

    def add_css(engine, node):
        return Gen(GenFor('xlinks', 'stylesheet', pj(path, 'style/main.css')),
                   engine(node))

    engine[Once(HTMLMetaNode)] = add_css


def extend_environment(engine, env):
    engine.environment.update(env)

