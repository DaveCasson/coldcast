ECCC GeoMet API (``ECCC_API``)
==============================

**Upstream:** ECCC **GeoMet OGC API - Features** collections (base URL ``https://api.weather.gc.ca/collections``). Station GeoJSON is fetched per station and collection; hydrometric vs meteorological station lists use separate CSVs (``station_csv_hydro`` / ``station_csv_meteo`` or legacy ``station_csv``).

**Transport:** ``requests`` in :func:`coldcast.sources.eccc_api.download`. Not the generic :func:`coldcast.download.download_requests` path.

**Auth:** None for public GeoMet API.

**CLI:** ``coldcast download eccc_api``

**Output:** By default, **wide** CSV suitable for Delft-FEWS import (see bundled ``default_settings.yaml`` under ``fews_csv``). Layout ``long`` and column maps are configurable.

**Settings:** ``ECCC_API`` — ``collections``, ``fews_csv``, ``limit``, ``time_range``, ``http_timeout_seconds``.

**Code:** :mod:`coldcast.sources.eccc_api`, :mod:`coldcast.sources.eccc_fews_csv`
