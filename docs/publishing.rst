Publishing on Read the Docs
===========================

This repository includes a `Read the Docs <https://readthedocs.org/>`_ config file: ``.readthedocs.yaml`` at the repo root. It:

* Uses **Ubuntu 24.04** and **Python 3.11**.
* Installs **system packages** ``libhdf5-dev`` and ``libnetcdf-dev`` so ``netCDF4`` wheels/builds succeed when importing the package for autodoc.
* Runs ``pip install .`` from the repository root, then ``pip install -r docs/requirements.txt``.
* Builds HTML with Sphinx using ``docs/conf.py``.

Steps
-----

1. Sign in at https://readthedocs.org/ (e.g. with your GitHub account).
2. Click **Import a project** and select the **coldcast** GitHub repository.
3. Under **Admin → Advanced Settings**, set **Configuration file** to ``.readthedocs.yaml`` if the UI does not pick it up automatically.
4. Save and trigger a build. The default **latest** version tracks your default branch; **stable** appears when you publish **git tags** (optional).

Troubleshooting
---------------

* If the build fails on **importing netCDF4**, confirm ``build.apt_packages`` in ``.readthedocs.yaml`` matches what your environment needs; RTD’s images change over time.
* If **autodoc** cannot import ``coldcast``, ensure ``sys.path`` in ``docs/conf.py`` includes ``src`` (already set) *or* rely on ``pip install .`` (configured) so the package is on ``PYTHONPATH``.
* Warnings: you can add ``sphinx-build -W`` in CI to treat warnings as errors once the doc set is stable.
