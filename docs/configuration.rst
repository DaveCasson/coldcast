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
* ``bounding_box`` — optional default geographic extent:

  * **Preferred:** mapping ``lon_min``, ``lon_max``, ``lat_min``, ``lat_max`` (west/east/south/north latitude bounds).
  * **CDS-style:** sequence ``[North, West, South, East]`` (degrees), same order as CDS ``area``.

  Sources that honor it merge **per key** with a more specific block—``ERA5`` / ``ERA5_LAND`` accept ``bounding_box`` or ``bbox`` in the source block; ``DYNAMICAL_CATALOG`` model ``bbox``; ``ECCC_PRECIP_GRID`` ``fews_netcdf.clip_bbox`` when ``clip_to_bbox`` is true—so product keys **override** the global default for those keys only.
* **Shared YAML anchors** — The bundled defaults repeat identical sub-mappings (for example NOMADS ``bbox`` and shared clip regions) using YAML aliases; that is layout-only and does not change runtime behavior.

Per-source blocks
-----------------

Each data source has a YAML block named after the source key (e.g. ``NOAA_HRRR``, ``ECCC_API``). Inside that block:

* **Templates** — ``url_template`` and ``filename_template`` are Python ``str.format``-style templates. Context variables are built in code per source.
* **Models** — Multi-model sources (``ECCC_NWP``, ``ECCC_PRECIP_GRID``, ``ECMWF_NWP``, ``DYNAMICAL_CATALOG``) nest configuration under model keys; ``default_model`` selects the default when ``--model`` is omitted.
* **HREPA FEWS NetCDF** — Under ``ECCC_PRECIP_GRID`` keys ``HREPA``, ``HREPA_PCT25``, and ``HREPA_PCT75``, optional ``fews_netcdf`` enables post-processing after download (clip via ``clip_to_bbox`` / ``clip_bbox``, merged with top-level ``bounding_box``; CF metadata touch-ups, optional variable rename). ``ECMWF_NWP`` YAML may list ``clip_to_bbox`` / ``clip_bbox``, but those keys are **not** applied to ECMWF GRIB2 downloads in code—only the HREPA FEWS NetCDF path uses clipping today.
* **Dynamical catalog FEWS NetCDF** — ``DYNAMICAL_CATALOG`` opens dynamical.org xarray/Zarr forecast datasets, selects ``init_time`` from FEWS runinfo ``time0`` minus ``delay_hours``, clips using the merge of top-level ``bounding_box`` and each model’s ``bbox``, and writes one CF NetCDF. Ensemble datasets keep all members in a single file using the CF ``realization`` dimension.
* **Sequences** — ``forecast_hours`` and ``members`` may be a list or a dict with ``start`` / ``end`` / ``step`` (expanded at runtime).

Bundled CSV assets
------------------

Station lists for ``ECCC_API`` and ``SNOTEL`` ship under ``coldcast.data``. Relative paths in YAML are resolved relative to the **settings file directory** when you pass a custom ``--settings`` path, or relative to the package data directory when using defaults.

NOAA Grib Filter
----------------

``NOAA_HRRR``, ``NOAA_GFS``, and ``NOAA_GEFS`` build `NOMADS Grib Filter <https://nomads.ncep.noaa.gov/>`_ URLs using ``url_base``, ``filter_script``, native NOMADS bbox fields (``leftlon``, ``rightlon``, ``toplat``, ``bottomlat``), variables, cycles, and forecast hours defined in YAML. There is **no** conversion from top-level ``bounding_box`` to NOMADS parameters; use source ``bbox`` as in the bundled defaults.
