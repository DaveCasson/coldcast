ECCC NWP (``ECCC_NWP``)
=======================

**Upstream:** Environment and Climate Change Canada **Datamart** (``dd.weather.gc.ca``) GRIB2 for HRDPS, RDPS, GDPS, REPS, GEPS, etc. URLs combine model-specific paths, cycles, lead times, and parameters.

**Transport:** HTTP GET via :func:`coldcast.download.download_requests`.

**Auth:** None for anonymous Datamart HTTP access (subject to ECCC terms of use).

**CLI:** ``coldcast download eccc_nwp [--model HRDPS|RDPS|…]``

**Settings:** ``ECCC_NWP`` with ``default_model`` and per-model sub-keys.

**Code:** :mod:`coldcast.sources.eccc_nwp`
