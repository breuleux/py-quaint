
from os.path import join as pj
from .engine import Once
from .lib import link_type, Gen, GenFor
from .builders import HTMLMetaNode
from .ast import source_nows
from .util import format_anchor


def use_assets(engine, path = 'assets/'):

    @link_type('media')
    def media_link(engine, node, text, link):
        return {'tag': 'img',
                'src': pj(path, 'media', link.raw()), #plain_or_code(engine, link)),
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

def siteroot(engine, root = '/'):

    @link_type('site')
    def site_link(engine, node, text, link):
        #link = plain_or_code(engine, link)
        return {'href': format_site_link(link.raw())}

    def format_site_link(link, raw = False):
        if not raw:
            link = format_anchor(link)
            if not link.endswith('/'):
                link += '.html'
        return root + link

    engine.extend_environment(
        siteroot = root,
        site_link = site_link,
        format_site_link = format_site_link
        )




