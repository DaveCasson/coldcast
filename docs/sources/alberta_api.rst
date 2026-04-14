Alberta WISKI API (``ALBERTA_API``)
===================================

**Upstream:** Alberta rivers WISKI download endpoint (default base URL ``https://rivers.alberta.ca/WiskiLiveDataService/Download``).

**Transport:** ``requests`` in :func:`coldcast.sources.alberta_api.download`.

**Auth:** None for public endpoint.

**CLI:** ``coldcast download alberta_api``.
Optional ``--stations-csv PATH`` overrides ``ALBERTA_API.mapping_csv`` for the run.

**Mapping CSV columns:** ``Station``, ``Parameter``, ``TsID``.

**Request pattern:**

.. code-block:: text

   https://rivers.alberta.ca/WiskiLiveDataService/Download
     ?tsId=<TsID>&from=<from_date>&to=<to_date>
     &filename=<Station>_<Parameter>_C.Corrected-Sensor.csv
     &zip=true&json=true

``to_date: latest`` is resolved to today's date (``YYYY-MM-DD``) at runtime.

``from_date: auto`` (default) resolves to the same month and day as today, ``default_years_back`` calendar years earlier (default ``2``). Set an explicit ``YYYY-MM-DD`` for a fixed window.

**Raw download:** On each successful HTTP GET, the response body is written to ``output_dir`` before parsing: ``<Station>_<Parameter>.zip`` when the body is a ZIP (typical for ``zip=true``), otherwise ``<Station>_<Parameter>.download``. Disable with ``save_raw_response: false``. This is independent of the FEWS CSV; you can inspect the ZIP when parsing fails.

**Output:** FEWS-compatible CSV. ``fews_csv.layout`` supports:

- ``wide``: ``DATETIME`` + one value column (name from ``fews_csv.value_column_names`` or parameter name).
- ``long``: ``locationId``, ``parameterId``, ``dateTime``, ``value``, ``unit``, ``qualityFlag`` (column names configurable).

For ``PR`` records, source values are rates (per hour). Each output value is the amount in the interval since the previous timestep: ``rate × Δt`` (hours), not a running total from the start of the download.

For ``PC`` records, values are treated as a cumulative counter. Successive differences (counter reset: increment = current reading) are aggregated by summing into each UTC clock hour, producing one row per hour (e.g. four 15-minute samples in an hour contribute four increments to that hour).

JSON inside the ZIP is parsed flexibly: nested objects are searched for arrays under keys such as ``Points`` / ``points``, ``Data``, ``values``, etc.; each row can be a mapping with time/value fields (``timestamp``, ``dateTime``, ``x``, ``value``, …) or a WISKI-style pair ``[epoch_ms, value]``. Zip archives with several files try each member (``.json`` first) until records are found.

**Settings:** ``ALBERTA_API`` — ``url_base``, ``from_date``, ``default_years_back``, ``to_date``, ``mapping_csv``, ``remote_filename_suffix``, ``zip``, ``json``, ``save_raw_response``, ``http_timeout_seconds``, ``fews_csv``.

**Code:** :mod:`coldcast.sources.alberta_api`
