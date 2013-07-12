from setuptools import setup

setup(
    name = 'quaint',
    version = '0.1',
    packages = ['quaint', 'quaint.operparse'],   
    package_data = {'quaint': ['default_engine.q']},
    scripts = ['bin/quaint'],

    # Metadata
    author = 'Olivier Breuleux',
    author_email = 'olivier@breuleux.net',
    url = 'https://github.com/breuleux/quaint',
    download_url = 'https://github.com/downloads/breuleux/quaint/quaint.tar.gz',
    license = 'BSD',

    description = 'Extensible Markup language',
    long_description = (
        'Markup language inspired from Markdown but geared towards'
        ' extensibility. Terse and human-readable. Possible to embed'
        ' Python code and generate markup programmatically.'),

    keywords = 'markup language',
    classifiers = [
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.1',
          'Programming Language :: Python :: 3.2',
          'Topic :: Text Processing :: Markup',
          'Topic :: Text Processing :: Markup :: HTML',
    ],

    requires = ['pyyaml', 'pygments']
)
