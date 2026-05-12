Coldcast
========

Coldcast is a configurable downloader for hydrometric, radar, snow, NWP, reanalysis, and
related station or gridded products. It exposes a single ``coldcast`` CLI: you define URL and
filename patterns (and other options) in YAML so new upstream layouts rarely need code changes.

**Hosted docs:** https://coldcast.readthedocs.io/en/latest/

**In this documentation**

* **User guide** — install the tool, run the CLI, edit settings, wire in FEWS run info, and
  browse per-source pages.
* **Python API** — import Coldcast modules for tests, automation, or custom tooling (the CLI
  remains the primary interface).

If you are new here, start with :doc:`installation`, then :doc:`cli` and :doc:`configuration`.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   cli
   configuration
   run_info
   sources/index
   publishing

.. toctree::
   :maxdepth: 2
   :caption: Python API

   reference/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
