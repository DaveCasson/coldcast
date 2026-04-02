Installation
============

Requirements
------------

Coldcast targets **Python 3.9+**. Dependencies are declared in the project ``pyproject.toml`` (pandas, PyYAML, requests, cdsapi, ecmwf-opendata, netCDF4, xarray, …).

Install from a clone (editable)
-------------------------------

From the repository root:

.. code-block:: bash

   python -m pip install -e .

This installs the ``coldcast`` package from ``src/`` and registers the ``coldcast`` console script.

Using Poetry
------------

.. code-block:: bash

   poetry install

Run the CLI via:

.. code-block:: bash

   poetry run coldcast download --help

Optional: documentation build dependencies
------------------------------------------

.. code-block:: bash

   poetry install --with docs
   sphinx-build -b html docs docs/_build/html

Then open ``docs/_build/html/index.html`` in a browser.

External credentials
--------------------

**Copernicus CDS (ERA5 / ERA5-LAND)**  
Downloads use `cdsapi <https://cds.climate.copernicus.eu/>`_. Configure a ``~/.cdsapirc`` with your API URL and key as described in the CDS documentation.

**ECMWF open data (ECMWF_NWP)**  
Retrieval uses the `ecmwf-opendata <https://github.com/ecmwf/ecmwf-opendata>`_ client. Public open-data endpoints generally do not need a personal token; follow ECMWF’s current guidance if that changes.

**ECCC radar (optional HTTP auth)**  
If your ``ECCC_RADAR`` settings include ``username`` / ``password``, those are passed as HTTP basic auth to the configured URLs.

**NOAA SNODAS**  
URLs are built from the collaborator product layout documented by NOAA; no Coldcast-specific API key is required.
