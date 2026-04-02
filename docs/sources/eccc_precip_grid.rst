ECCC precip grids (``ECCC_PRECIP_GRID``)
========================================

**Upstream:** ECCC Datamart **HRDPA / RDPA** (and related) accumulated precipitation GRIB2 products.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for typical Datamart access.

**CLI:** ``coldcast download eccc_precip_grid [--model HRDPA|RDPA]``

**Settings:** ``ECCC_PRECIP_GRID`` with ``default_model`` (e.g. ``RDPA``), ``hour_list``, ``delay_hours``, ``num_days_back``.

**Code:** :mod:`coldcast.sources.eccc_precip_grid`
