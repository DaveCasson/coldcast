ECMWF open data (``ECMWF_NWP``)
===============================

**Upstream:** **ECMWF open data** (IFS, AIFS deterministic and ensemble) via the `ecmwf-opendata <https://github.com/ecmwf/ecmwf-opendata>`_ Python client. Coldcast uses the **00 UTC** cycle only after applying delay and reference time (see README / model settings).

**Transport:** :func:`coldcast.sources.ecmwf_nwp.download` uses ``ecmwf.opendata.Client`` with threading; not the generic HTTP downloader.

**Auth:** Follow ECMWF’s current open-data policy; defaults typically use public endpoints.

**CLI:** ``coldcast download ecmwf_nwp [--model IFS_DET|IFS_ENS|…]``

**Settings:** ``ECMWF_NWP`` — ``default_model`` and per-model keys: ``ecmwf_model``, ``stream``, ensemble options, ``lead_time``, ``delay``, ``parameters``, optional ``clip_bbox``.

**Code:** :mod:`coldcast.sources.ecmwf_nwp`
