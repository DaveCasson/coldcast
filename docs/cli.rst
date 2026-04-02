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

Dry-run
-------

With ``--dry-run``, Coldcast prints the URLs (or job list) that would be used and **does not** download. Sources that use custom download paths (e.g. ``ECCC_API``, ``ERA5``, ``ECMWF_NWP``) still run their builders; behavior is source-specific.
