NOAA SNODAS (``SNODAS``)
========================

**Upstream:** NOAA **NOHRSC** collaborator **GRIB2** products (``nohrsc.noaa.gov/products/collaborators/``). Filenames combine parameter tokens, date, and suffixes from YAML lists.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for the collaborator product URLs in default configuration.

**CLI:** ``coldcast download snodas``

**Settings:** ``SNODAS`` — ``parameters``, ``file_suffixes``, ``num_days_back``.

**Code:** :mod:`coldcast.sources.snodas`
