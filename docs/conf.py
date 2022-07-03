#!/usr/bin/env python
#
# pybaselines documentation build configuration file, created by
# sphinx-quickstart on Fri March 5 14:29:21 2021.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
#
import os
import sys


sys.path.insert(0, os.path.abspath('..'))

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    #'sphinx.ext.autodoc',
    #'sphinx.ext.autosummary',
    'autoapi.extension',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.todo',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosectionlabel',
    'matplotlib.sphinxext.plot_directive',
    'sphinx_gallery.gen_gallery'
]

#autosummary_generate = True # enables autosummary extension

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'pybaselines'
copyright = "2021-2022, Donald Erb"
author = "Donald Erb"

# The version info for the project you're documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = '0.8.0'
# The full version, including alpha/beta/rc tags.
release = version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# smartquotes converts quotes and dashes to typographically correct entities
# but I think it's been messing up my html documentation.
smartquotes = False

# used for generator .po and/or .pot files, for translating to other languages
gettext_compact = False

# used for version tracking in the generated .po and/or .pot files
gettext_uuid = True

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# outside documentation references for the intersphinx extension
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/reference/', None),
    'pentapy': ('https://geostat-framework.readthedocs.io/projects/pentapy/en/stable/', None)
}

# cache remote doc inventories for 14 days
intersphinx_cache_limit = 14

napoleon_include_private_with_doc = True

# ensure each label from the autosection extension is unique
autosectionlabel_prefix_document = True

# -- Settings for autoapi extension ----------------------------

# autoapi gets the docstrings for all public modules in the package
autoapi_type = 'python'
autoapi_dirs = ['../pybaselines']
autoapi_template_dir = '_templates/autoapi'
autoapi_root = 'api'
autoapi_options = [
    'members',
    'inherited-members',
    #'undoc-members', # show objects that do not have doc strings
    #'private_members', # show private objects (_variable)
    #'show-inheritance',
    'show-module-summary',
    #'special-members', # show things like __str__
    #'imported-members', # document things imported within each module
]
autoapi_member_order = 'groupwise' # groups into classes, functions, etc.
autoapi_python_class_content = 'class' # include class docstring from class and/or __init__
#autoapi_keep_files = True # keep the files after generation
#autoapi_add_toctree_entry = False # need to manually add to toctree if False
#autoapi_generate_api_docs = False # will not generate new docs when False

# ignore an import warning from sphinx-autoapi due to double import of utils
suppress_warnings = ['autoapi.python_import_resolution']


# -- Settings for sphinx-gallery extension ----------------------------

from sphinx_gallery.sorting import ExplicitOrder, FileNameSortKey


# specifies the order of the example galleries
gallery_section_order = [
    '../examples/general',
    '../examples/whittaker',
    '../examples/morphological',
    '../examples/spline',
    '../examples/classification',
]

sphinx_gallery_conf = {
    # location of example files
    'examples_dirs': ['../examples'],
    # location of output folder
    'gallery_dirs': ['examples'],
    # must set to None or else autoapi errors
    'backreferences_dir': None,
    # remove button on front page for downloading all examples
    'download_all_examples': False,
    # order sections explicitly
    'subsection_order': ExplicitOrder(gallery_section_order),
    # order subsection examples by filename
    'within_subsection_order': FileNameSortKey,
    # removes configuration comments from rst output
    'remove_config_comments': True,
    # disables trying to link variables to intersphinx
    'inspect_global_variables': False,
    # prevents getting repr of last item in cell; good for ignoring matplotlib objects
    'capture_repr': (),
    # ignore the example_helpers.py files that contain setup code for the examples
    'ignore_pattern': r'example_helpers\.py',
}


# -- Options for HTML output -------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
try:
    import sphinx_rtd_theme
except ImportError:
    html_theme = 'nature'
else:
    html_theme = 'sphinx_rtd_theme'
    del sphinx_rtd_theme

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    'navigation_depth': 8,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = [
    #'_static'
]


# -- Options for HTMLHelp output ---------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'pybaselinesdoc'


# -- Options for LaTeX output ------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'pybaselines.tex',
     'pybaselines Documentation',
     'Donald Erb', 'manual'),
]

#latex_logo = os.path.abspath('./images/logo.png')

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = True

# If true, show page references after internal links.
latex_show_pagerefs = True

# 'footnote' puts the URL addresses at the footnote.
# 'inline' displays URLS inline in parentheses
latex_show_urls = 'inline'

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
latex_domain_indices = True


# -- Options for manual page output ------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'pybaselines',
     'pybaselines Documentation',
     [author], 1)
]


# -- Options for Texinfo output ----------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'pybaselines',
     'pybaselines Documentation',
     author,
     'pybaselines',
     'A library of baseline correction algorithms.',
     'Miscellaneous'),
]
