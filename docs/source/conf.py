"""Configuration file for the Sphinx documentation builder.

This file does only contain a selection of the most common options. For a full list see
the documentation: http://www.sphinx-doc.org/en/master/config

-- Path setup --------------------------------------------------------------

If extensions (or modules to document with autodoc) are in another directory, add these
directories to ``sys.path`` here. If the directory is relative to the documentation
root, use ``os.path.abspath`` to make it absolute, like shown here.

"""

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------

project = "ssslm"
copyright = f"{date.today().year}, Charles Tapley Hoyt"
author = "Charles Tapley Hoyt"

# The full version, including alpha/beta/rc tags.
release = "0.0.2"

# The short X.Y version.
parsed_version = re.match(
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<release>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
    release,
)
version = parsed_version.expand(r"\g<major>.\g<minor>.\g<patch>")

if parsed_version.group("release"):
    tags.add("prerelease")  # noqa:F821


# See https://about.readthedocs.com/blog/2024/07/addons-by-default/
# Define the canonical URL if you are using a custom domain on Read the Docs
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

# See https://about.readthedocs.com/blog/2024/07/addons-by-default/
# Tell Jinja2 templates the build is running on Read the Docs
if os.environ.get("READTHEDOCS", "") == "True":
    if "html_context" not in globals():
        html_context = {}
    html_context["READTHEDOCS"] = True


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = False

# A list of prefixes that are ignored when creating the module index. (new in Sphinx 0.6)
modindex_common_prefix = ["ssslm."]

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx_automodapi.automodapi",
    "sphinx_automodapi.smart_resolver",
    # 'texext',
]


extensions.append("sphinx_click.ext")


# generate autosummary pages
autosummary_generate = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = {
    ".rst": "restructuredtext",
}

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#
if os.path.exists("logo.png"):
    html_logo = "logo.png"

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "ssslm_doc"

# -- Options for LaTeX output ------------------------------------------------

# latex_elements = {
#     The paper size ('letterpaper' or 'a4paper').
#
#     'papersize': 'letterpaper',
#
#     The font size ('10pt', '11pt' or '12pt').
#
#     'pointsize': '10pt',
#
#     Additional stuff for the LaTeX preamble.
#
#     'preamble': '',
#
#     Latex figure (float) alignment
#
#     'figure_align': 'htbp',
# }

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
# latex_documents = [
#     (
#         master_doc,
#         'ssslm.tex',
#         'Simple Standard for Sharing Literal Mappings Documentation',
#         author,
#         'manual',
#     ),
# ]

# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (
        master_doc,
        "ssslm",
        "Simple Standard for Sharing Literal Mappings Documentation",
        [author],
        1,
    ),
]

# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "ssslm",
        "Simple Standard for Sharing Literal Mappings Documentation",
        author,
        "Charles Tapley Hoyt",
        "A simple standard for sharing literal mappings",
        "Miscellaneous",
    ),
]

# -- Options for Epub output -------------------------------------------------

# Bibliographic Dublin Core info.
# epub_title = project

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ''

# A unique identification for the text.
#
# epub_uid = ''

# A list of files that should not be packed into the epub file.
# epub_exclude_files = ['search.html']

# -- Extension configuration -------------------------------------------------

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
# Note: don't add trailing slashes, since sphinx adds "/objects.inv" to the end
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "curies": ("https://curies.readthedocs.io/en/latest", None),
    "gilda": ("https://gilda.readthedocs.io/en/latest", None),
    "nltk": ("https://nltk.readthedocs.io/en/latest", None),
}

autoclass_content = "both"

# Don't sort alphabetically, explained at:
# https://stackoverflow.com/questions/37209921/python-how-not-to-sort-sphinx-output-in-alphabetical-order
autodoc_member_order = "bysource"

todo_include_todos = True
todo_emit_warnings = True

# Output SVG inheritance diagrams
graphviz_output_format = "svg"
