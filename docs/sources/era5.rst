ERA5 (``ERA5``)
===============

**Upstream:** **Copernicus Climate Data Store (CDS)** via `cdsapi <https://cds.climate.copernicus.eu/>`_. Retrieval uses the CDS API (not presigned HTTP URLs from :func:`coldcast.download.download_requests`).

**Transport:** :func:`coldcast.sources.era5.download` calls ``cdsapi.Client().retrieve()`` into ``output_dir``.

**Auth:** ``~/.cdsapirc`` with CDS URL and API key.

**CLI:** ``coldcast download era5 [--run-info-netcdf …]``

**Settings:** ``ERA5`` — ``num_days_back``, ``delay_days``, ``variables_surface_level``, ``grid``, ``hours``; global or block ``bounding_box``.

**Code:** :mod:`coldcast.sources.era5`
