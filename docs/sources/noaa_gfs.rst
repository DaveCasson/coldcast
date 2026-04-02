NOAA GFS (``NOAA_GFS``)
=======================

**Upstream:** NOMADS **GFS 0.25°** Grib Filter (``filter_gfs_0p25.pl``). Same pattern as HRRR: cycle, forecast hours, bbox, variables.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for public NOMADS.

**CLI:** ``coldcast download noaa_gfs``

**Settings:** ``NOAA_GFS``

**Code:** :mod:`coldcast.sources.gfs`
