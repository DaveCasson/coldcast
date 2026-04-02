Configuration
=============

Settings are loaded from a **YAML** file. If you omit ``--settings``, Coldcast loads the bundled defaults from the package:

``src/coldcast/data/default_settings.yaml`` (installed as ``coldcast.data``).

Global keys
-----------

Typical top-level keys include:

* ``output_dir`` — download destination.
* ``max_num_threads`` — concurrency for HTTP downloads.
* ``log_file``, ``log_xml_file``, ``xml_log`` — logging.
* ``run_info_file``, ``run_info_netcdf`` — FEWS run info overrides (see :doc:`run_info`).
* ``fews_name_space`` — XML namespace for FEWS run info XML.
* ``bounding_box`` — used by some sources (e.g. ERA5) when not overridden in the source block.

Per-source blocks
-----------------

Each data source has a YAML block named after the source key (e.g. ``NOAA_HRRR``, ``ECCC_API``). Inside that block:

* **Templates** — ``url_template`` and ``filename_template`` are Python ``str.format``-style templates. Context variables are built in code per source.
* **Models** — Multi-model sources (``ECCC_NWP``, ``ECCC_PRECIP_GRID``, ``ECMWF_NWP``) nest configuration under model keys; ``default_model`` selects the default when ``--model`` is omitted.
* **Sequences** — ``forecast_hours`` and ``members`` may be a list or a dict with ``start`` / ``end`` / ``step`` (expanded at runtime).

Bundled CSV assets
------------------

Station lists for ``ECCC_API`` and ``SNOTEL`` ship under ``coldcast.data``. Relative paths in YAML are resolved relative to the **settings file directory** when you pass a custom ``--settings`` path, or relative to the package data directory when using defaults.

NOAA Grib Filter
----------------

``NOAA_HRRR``, ``NOAA_GFS``, and ``NOAA_GEFS`` build `NOMADS Grib Filter <https://nomads.ncep.noaa.gov/>`_ URLs using ``url_base``, ``filter_script``, bbox, variables, cycles, and forecast hours defined in YAML.
