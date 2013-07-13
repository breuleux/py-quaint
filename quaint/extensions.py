
from os.path import join as pj
from .engine import Once
from .lib import link_type, plain_or_code, Gen, GenFor
from .builders import HTMLMetaNode
from .ast import source_nows


def use_assets(engine, path = 'assets/'):

    @link_type('media')
    def media_link(engine, node, text, link):
        return {'tag': 'img',
                'src': pj(path, 'media', plain_or_code(engine, link)),
                'alt': text.raw(),
                'body': ''}

    def add_css(engine, node):
        return Gen(GenFor('xlinks', 'stylesheet', pj(path, 'style/main.css')),
                   engine(node))

    def use_asset(engine, node, asset):
        asset = source_nows(asset)
        if asset.endswith('.css'):
            return GenFor('xlinks', 'stylesheet', pj(path, asset))
        elif asset.endswith('.js'):
            return GenFor('xlinks', 'text/javascript', pj(path, asset))
        else:
            raise Exception("Don't know how to interpret asset", asset)

    engine.environment['assets_path'] = path
    engine.environment['use_asset'] = use_asset
    engine[Once(HTMLMetaNode)] = add_css


def extend_environment(engine, env):
    engine.environment.update(env)

