NOAA GEFS (``NOAA_GEFS``)
=========================

**Upstream:** NOMADS **GEFS** Grib Filter (``filter_gefs_atmos_0p25s.pl``). Member indices expand to ``gepXX`` in filenames/URLs per YAML ``members`` and ``forecast_hours``.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for public NOMADS.

**CLI:** ``coldcast download noaa_gefs``

**Settings:** ``NOAA_GEFS``

**Code:** :mod:`coldcast.sources.gefs`
