NOAA HRRR (``NOAA_HRRR``)
=========================

**Upstream:** `NCEP NOMADS <https://nomads.ncep.noaa.gov/>`_ HRRR-Alaska **Grib Filter** (Perl CGI). URLs are built from ``url_base``, ``filter_script``, domain, cycle, forecast hours, bbox, and variable/level pairs in YAML.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for public NOMADS endpoints.

**CLI:** ``coldcast download noaa_hrrr [--dry-run]``

**Settings:** Block ``NOAA_HRRR`` in ``default_settings.yaml`` (``delay_hours``, ``cycle_interval_hours``, ``bbox``, ``variables``, ``forecast_hours``, templates).

**Code:** :mod:`coldcast.sources.hrrr`
