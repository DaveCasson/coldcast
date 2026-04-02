ERA5-Land (``ERA5_LAND``)
=========================

**Upstream:** Same **CDS** stack as :doc:`era5`, with ERA5-Land dataset parameters (snow cover, SWE, etc.).

**Transport:** :func:`coldcast.sources.era5.download` with ``data_source`` ``ERA5_LAND``.

**Auth:** CDS ``~/.cdsapirc``.

**CLI:** ``coldcast download era5_land``

**Settings:** ``ERA5_LAND`` — ``variables``, ``bbox``, ``hours``, ``num_days_back``, ``delay_days``.

**Code:** :mod:`coldcast.sources.era5` (shared with ERA5)
