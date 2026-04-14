ECCC GeoMet API (``ECCC_API``)
==============================

**Upstream:** ECCC **GeoMet OGC API - Features** collections (base URL ``https://api.weather.gc.ca/collections``). Station GeoJSON is fetched per station and collection; hydrometric vs meteorological station lists use separate CSVs (``station_csv_hydro`` / ``station_csv_meteo`` or legacy ``station_csv``).

**Transport:** ``requests`` in :func:`coldcast.sources.eccc_api.download`. Not the generic :func:`coldcast.download.download_requests` path.

**Auth:** None for public GeoMet API.

**CLI:** ``coldcast download eccc_api`` (all configured collections), or
``coldcast download eccc_api --model <collection-name>`` to run a single
collection (for example ``hydrometric-realtime``, ``swob-realtime``, or
``climate-daily`` / ``climate-hourly``). ``climate_daily`` and
``climate_hourly`` are also accepted.
With ``--model``, only that collection is built and downloaded.
Optional ``--stations-csv PATH`` uses that file instead of
``station_csv_hydro`` / ``station_csv_meteo`` (or legacy ``station_csv``) from
settings; the same path is used for both ``hydro`` and ``meteo`` station lists,
so the file must include the column each collection expects (typically ``ID`` or
``MSC_ID``, or a per-collection ``station_column`` override).

**Output:** By default, **wide** CSV suitable for Delft-FEWS import (see bundled ``default_settings.yaml`` under ``fews_csv``). Layout ``long`` and column maps are configurable.

GeoMet returns at most **10000** features per ``/items`` request. For **both** hydrometric (``STATION_NUMBER``) and meteo collections, Coldcast follows OGC ``rel=next`` links until every page is fetched (``fetch_all_pages``), up to ``max_pagination_pages``. The ``limit`` setting is the **per-request** page size (capped at 10000). With ``sort_output_datetime_descending: true`` (default in bundled settings), exported CSV rows are ordered **newest first** so recent observations appear at the top.

**Settings:** ``ECCC_API`` — ``collections``, ``fews_csv``, ``limit``, ``fetch_all_pages``, ``max_pagination_pages``, ``sort_output_datetime_descending``, ``time_range``, ``http_timeout_seconds``.

**Code:** :mod:`coldcast.sources.eccc_api`, :mod:`coldcast.sources.eccc_fews_csv`
