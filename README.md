# Coldcast

<p align="left">
  <img src="assets/logo-arctic.svg" alt="Arctic" width="72" height="72" />
  <img src="assets/logo-alpine.svg" alt="Alpine" width="72" height="72" />
  <img src="assets/logo-boreal.svg" alt="Boreal" width="72" height="72" />
</p>

Coldcast is a **YAML-configurable CLI** for downloading weather, hydrology, snow, radar, and reanalysis data from public services. One command—`coldcast`—covers many upstream APIs and file layouts; you adjust templates and settings instead of editing code for each source.

**Full documentation:** [coldcast.readthedocs.io](https://coldcast.readthedocs.io/en/latest/)

## What you get

- **Single entry point:** `coldcast download <source> [options]` (sources are documented [here](https://coldcast.readthedocs.io/en/latest/sources/index.html)).
- **Settings-driven:** copy and edit the bundled defaults (see [Configuration](https://coldcast.readthedocs.io/en/latest/configuration.html)); URL and filename patterns use standard Python format strings.
- **Operational hooks:** optional Delft-FEWS run-info overrides (XML or NetCDF) for reference time, paths, and logging—see [Run-info overrides](https://coldcast.readthedocs.io/en/latest/run_info.html).
- **Dry runs:** inspect planned URLs or jobs with `--dry-run` before transferring data.

## Quick start

Install (editable, from the repo root):

```bash
python -m pip install -e .
```

Check the CLI and list download subcommands:

```bash
coldcast --help
coldcast download --help
```

Preview a run without downloading (replace `<source>` with any subcommand name, e.g. from `coldcast download --help`):

```bash
coldcast download <source> --dry-run
```

Use a custom settings file:

```bash
coldcast download <source> --settings ./settings.yaml
```

Credential and optional-dependency notes (CDS, ECMWF open data, basic auth, etc.) are in the **[Installation](https://coldcast.readthedocs.io/en/latest/installation.html)** guide.

## Source coverage (overview)

Sources are grouped in the docs by **provider and data type**. Examples of categories covered—not an exhaustive list of subcommands:

| Category | Examples in the docs |
| --- | --- |
| National / regional hydromet and station APIs | GeoMet-style collections, regional station services |
| NWP and precipitation grids | Deterministic and ensemble model output, gridded precipitation |
| Radar and remote sensing | Composite radar; snow and cryosphere products |
| Global reanalysis and open NWP | NetCDF from CDS-style APIs; open-data GRIB from major centres |
| Station and specialized CSV pipelines | Configurable station lists, FEWS-oriented CSV layouts |

For the canonical list of CLI names, options, and YAML blocks, use **[Data sources](https://coldcast.readthedocs.io/en/latest/sources/index.html)** and the auto-generated **[CLI reference](https://coldcast.readthedocs.io/en/latest/cli.html)**.

## Configuration (summary)

- Default settings ship with the package; copy `src/coldcast/data/default_settings.yaml` as a starting point for your deployment.
- Per-source YAML blocks define templates, model keys, forecast hours, bounding boxes (where applicable), and other source-specific fields.

Details: **[Configuration](https://coldcast.readthedocs.io/en/latest/configuration.html)**.

## Run-info overrides (summary)

FEWS XML (`--run-info-file`) or FEWS-style NetCDF (`--run-info-netcdf`) can supply reference time, working/output directories, and logging paths.

Details: **[Run-info overrides](https://coldcast.readthedocs.io/en/latest/run_info.html)**.

## Testing

- URL and routing tests: `pytest tests/test_urls.py`, `tests/test_eccc_api.py`, `tests/test_run_info_netcdf.py`.
- Network tests (opt-in): `COLDCAST_RUN_NETWORK_TESTS=1 pytest -m network`.
- API client tests (mocked): `pytest tests/test_api_clients.py -m api_client`.

## Building the docs locally

```bash
python -m pip install -r docs/requirements.txt
python -m pip install -e .
sphinx-build -b html docs docs/_build/html
```

Hosted builds use **Read the Docs** (`.readthedocs.yaml`); maintainer notes: **[Publishing on Read the Docs](https://coldcast.readthedocs.io/en/latest/publishing.html)**.
