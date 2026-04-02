USDA SNOTEL (``SNOTEL``)
========================

**Upstream:** USDA **WCC reportGenerator** CSV endpoint (``wcc.sc.egov.usda.gov``). Station list and URL fragments come from a bundled or custom CSV (``station_csv``, columns such as ``SITE_ID``, ``SITE_NAME``, ``STATE``).

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for the public report generator URLs used in defaults (subject to USDA terms).

**CLI:** ``coldcast download snotel``

**Settings:** ``SNOTEL`` — ``url_base``, ``url_template``, ``filename_template``, ``url_param``, ``station_csv``.

**Code:** :mod:`coldcast.sources.snotel`
