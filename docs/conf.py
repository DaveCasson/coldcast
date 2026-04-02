# Sphinx configuration for Coldcast.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import sys
from pathlib import Path

# Repo root (parent of docs/)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

project = "Coldcast"
copyright = "Coldcast contributors"
author = "Dave Casson"

try:
    import coldcast

    release = coldcast.__version__
except ImportError:
    release = "0.0.1"

version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
    "sphinxarg.ext",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

nitpicky = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "requests": ("https://requests.readthedocs.io/en/stable/", None),
}

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
