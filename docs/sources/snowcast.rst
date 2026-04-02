Snowcast SWE (``SNOWCAST``)
===========================

**Upstream:** Snow water equivalent GeoTIFFs on **hpfx.collab.science.gc.ca** (path ``~chm003/tiff/`` in defaults).

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None unless the server requires it.

**CLI:** ``coldcast download snowcast``

**Settings:** ``SNOWCAST`` — ``delay_hours``, ``filename_template``.

**Code:** :mod:`coldcast.sources.snowcast`
