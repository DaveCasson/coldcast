ECCC radar composite (``ECCC_RADAR``)
=====================================

**Upstream:** MSC radar composite GeoTIFF on **hpfx.collab.science.gc.ca** (path pattern with date and timestamp).

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`. Optional ``username`` / ``password`` in YAML become HTTP basic auth.

**Auth:** Optional basic auth per settings.

**CLI:** ``coldcast download eccc_radar``

**Settings:** ``ECCC_RADAR`` — ``delay_minutes``, ``timestep_minutes``, ``search_period_hours``, ``data_type``, templates.

**Code:** :mod:`coldcast.sources.eccc_radar`
