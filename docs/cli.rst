Command-line interface
======================

The entry point is the ``coldcast`` program. The main workflow is:

.. code-block:: text

   coldcast download <source> [options]

where ``<source>`` is one of the subcommands listed below (e.g. ``noaa_hrrr``, ``era5``). Names are case-insensitive; uppercase aliases (e.g. ``NOAA_HRRR``) are accepted.

The following reference is generated from the live :mod:`argparse` definition in :mod:`coldcast.cli`.

.. argparse::
   :module: coldcast.cli
   :func: build_arg_parser
   :prog: coldcast

When ``--output-dir`` is provided and the directory does not exist, Coldcast
creates it automatically.

Dry-run
-------

With ``--dry-run``, Coldcast prints the URLs (or job list) that would be used and **does not** download. Sources that use custom download paths (for example GeoMet-style APIs, regional station services, CDS jobs, or ECMWF open-data clients) still run their planners; exact behavior is documented on each source page.

See also
--------

* :doc:`configuration` for YAML structure shared across sources.
* :doc:`sources/index` for per-source notes and upstream links.
