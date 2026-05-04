ECCC precip grids (``ECCC_PRECIP_GRID``)
========================================

**Upstream:** ECCC Datamart **HRDPA / RDPA** accumulated precipitation in GRIB2; **HREPA** (High Resolution Ensemble Precipitation Analysis, CaPA-HREPA) in NetCDF on the same Datamart layout (no GRIB conversion—Datamart delivers ``.nc``). Product overview: `MSC HREPA readme <https://eccc-msc.github.io/open-data/msc-data/nwp_hrepa/readme_hrepa_en/>`_.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for typical Datamart access.

**CLI:** ``coldcast download eccc_precip_grid [--model HRDPA|RDPA|HREPA|HREPA_PCT25|HREPA_PCT75]``

**Settings:** ``ECCC_PRECIP_GRID`` with ``default_model`` (e.g. ``RDPA``), per-model ``hour_list``, ``delay_hours``, ``num_days_back``.

**HREPA FEWS NetCDF (optional):** On **HREPA** model keys only, you may set ``fews_netcdf.enabled: true``. After each successful download, Coldcast writes an additional NetCDF next to the raw file (suffix from ``output_suffix``, default ``_fews`` → ``*_fews.nc``): optional geographic clip (``clip_to_bbox`` / ``clip_bbox``, merged **per key** with top-level ``bounding_box``; same lon/lat keys as ECMWF YAML examples), ``Conventions`` set to CF-1.8, optional ``output_variable_name`` to rename the main precip variable (e.g. for FEWS), and optional omission of ``ConfidenceIndex`` (``include_confidence_index: false``). Raw Datamart files are unchanged.

**Code:** :mod:`coldcast.sources.eccc_precip_grid`

HRDPA/RDPA remain GRIB2; HREPA is NetCDF end-to-end.
