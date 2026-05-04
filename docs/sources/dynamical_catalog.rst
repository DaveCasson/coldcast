Dynamical catalog (``DYNAMICAL_CATALOG``)
==========================================

**Upstream:** `dynamical.org catalog <https://dynamical.org/catalog/>`_ forecast datasets opened through `dynamical-catalog <https://github.com/dynamical-org/dynamical-catalog>`_.
Bundled examples include NOAA GEFS/HRRR and `ECMWF IFS ENS (15-day, 0.25°) <https://dynamical.org/catalog/ecmwf-ifs-ens-forecast-15-day-0-25-degree>`_ (51 members, 00 UTC cycles, ``init_time`` from 2024-04-01 onward).

**Transport:** xarray/Zarr/Icechunk via ``dynamical_catalog.open(...)``; Coldcast writes a derived NetCDF product rather than downloading individual upstream files.

**Auth:** None for anonymous catalog access. Set ``identifier`` on a model config, or top-level ``dynamical_catalog_identifier``, to pass an identifying user-agent to the catalog.

**CLI:** ``coldcast download dynamical_catalog [--model GEFS|gefs|HRRR|IFS|ECMWF_IFS_ENS] --run-info-netcdf runinfo.nc`` — ``IFS`` selects the ECMWF IFS ENS block (alias for ``ECMWF_IFS_ENS``); ``GEFS`` matches the NOAA GEFS 35-day block (case-insensitive).

**Runtime requirement:** ``dynamical-catalog`` currently requires Python 3.12 or newer. Coldcast imports it lazily, so other sources continue to run on older supported Python versions; this source requires a Python 3.12+ environment with ``dynamical-catalog`` installed.

**Settings:** ``DYNAMICAL_CATALOG`` with ``default_model`` and per-model blocks:

* ``dataset_id`` — dynamical catalog dataset ID, for example ``noaa-gefs-forecast-35-day`` or ``ecmwf-ifs-ens-forecast-15-day-0-25-degree``.
* ``delay_hours`` — subtracted from FEWS runinfo ``time0`` before choosing a forecast run.
* ``forecast_selection`` — xarray selection method for ``init_time``; default ``pad`` selects the latest run at or before the delayed reference time.
* ``max_run_age_hours`` — optional guard against selecting an unexpectedly old run.
* ``lead_time_hours`` — optional lead-time limit in hours, either a scalar maximum or a mapping with ``start`` and ``end``.
* ``bbox`` — ``lon_min``, ``lon_max``, ``lat_min``, ``lat_max``; merged **per key** with top-level ``bounding_box``, so omit keys to inherit globals.
* ``variables`` — source variables and FEWS/CF output names plus optional ``standard_name``, ``long_name``, and ``units``.
* ``output_filename_template`` — Python format template with ``model``, ``dataset_id``, and ``run_time``.
* ``xr_open_kwargs`` — passed to ``dynamical_catalog.open``.
* ``compression`` — ``false`` to disable NetCDF compression, or a mapping such as ``zlib: true`` and ``complevel: 1``.

Forecast selection uses the existing FEWS runinfo NetCDF support: ``time0`` is read into ``settings["reference_time"]``, then Coldcast selects ``init_time <= time0 - delay_hours``. The selected initialization time is written as the scalar CF coordinate ``forecast_reference_time``.

For regular latitude/longitude datasets, Coldcast clips by 1D ``latitude`` and ``longitude`` coordinate indexes. For projected datasets such as HRRR, Coldcast clips the minimal contiguous grid window that intersects the requested bbox using matching 2D latitude/longitude coordinates.

Ensemble datasets are written as a single CF NetCDF. ``ensemble_member`` is renamed to ``realization`` and annotated with ``standard_name = "realization"`` so Delft-FEWS can ingest all members from one file. Deterministic datasets omit that dimension.

For ``ecmwf-ifs-ens-forecast-15-day-0-25-degree``, the dynamical.org catalog notes that ``precipitation_surface`` is NaN-filled before 2024-11-13 UTC; other variables span the full archive from 2024-04-01.

**Code:** :mod:`coldcast.sources.dynamical_catalog`
