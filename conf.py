# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

# -- Project information -----------------------------------------------------

project = 'Usando Micropython de verdad: bienvenidos a la robótica'
copyright = '2026, Nekmo'
author = 'Nekmo'
master_doc = 'index'
release = 'MIT'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx_revealjs',
    'sphinxcontrib.video',
    'stackchan_ext',
]

templates_path = ['_templates']
language = 'es'
smartquotes = False
exclude_patterns = [
    '_build', 'Thumbs.db', '.DS_Store', 'README.rst', 'demos', 'tools',
    '.github', '.idea', 'robot', '_extra',
]

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
html_favicon = 'images/favicon.svg'
html_static_path = ['_static']
# coi-sw.js must be served from the site root (service worker scope)
html_extra_path = ['_extra']

# -- Options for Reveal.js output --------------------------------------------

revealjs_static_path = ['_static']
revealjs_style_theme = 'black'
revealjs_script_conf = {
    'controls': True,
    'progress': True,
    'history': True,
    'hash': True,
    'center': True,
    'width': 1280,
    'height': 800,
    'margin': 0.06,
    'transition': 'slide',
    'backgroundTransition': 'fade',
}
revealjs_script_plugins = [
    {'name': 'RevealNotes', 'src': 'revealjs/plugin/notes/notes.js'},
    {'name': 'RevealHighlight', 'src': 'revealjs/plugin/highlight/highlight.js'},
]
revealjs_css_files = [
    'vendor/fonts/fonts.css',
    'theme.css',
]
revealjs_js_files = [
    'js/isolation.js',
    'js/scenes.js',
    'js/camera.js',
    'js/robot-link.js',
    'js/demo.js',
    'js/model-version.js',
    'js/stackchan3d.js',
]
revealjs_use_section_ids = True

# -- Options for extensions --------------------------------------------------

if 'GTAGJS_IDS' in os.environ:
    gtagjs_ids = os.environ['GTAGJS_IDS'].split(',')
