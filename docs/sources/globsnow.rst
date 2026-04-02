GlobSnow (``GLOBSNOW``)
=======================

**Upstream:** **GlobSnow** near-real-time SWE files (HTTP ``globsnow.info`` path layout with year and dated ``GlobSnow_SWE_L3A_*.nc.gz``).

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for the public archive as configured.

**CLI:** ``coldcast download globsnow``

**Settings:** ``GLOBSNOW`` — ``num_days_back``, ``delay_hours``.

**Code:** :mod:`coldcast.sources.globsnow`
