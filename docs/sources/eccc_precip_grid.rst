ECCC precip grids (``ECCC_PRECIP_GRID``)
========================================

**Upstream:** ECCC Datamart **HRDPA / RDPA** accumulated precipitation in GRIB2; **HREPA** (High Resolution Ensemble Precipitation Analysis, CaPA-HREPA) in NetCDF on the same Datamart layout. Product overview and access notes: `MSC HREPA readme <https://eccc-msc.github.io/open-data/msc-data/nwp_hrepa/readme_hrepa_en/>`_.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for typical Datamart access.

**CLI:** ``coldcast download eccc_precip_grid [--model HRDPA|RDPA|HREPA|HREPA_PCT25|HREPA_PCT75]``

**Settings:** ``ECCC_PRECIP_GRID`` with ``default_model`` (e.g. ``RDPA``), per-model ``hour_list``, ``delay_hours``, ``num_days_back``.

**Code:** :mod:`coldcast.sources.eccc_precip_grid`

HREPA files are NetCDF, not GRIB2; use NetCDF-aware tooling downstream.
