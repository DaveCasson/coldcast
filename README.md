# Coldcast

Coldcast is a configurable data downloader for hydrometric, radar, snow, and
global reanalysis products. It wraps the legacy scripts into a pip-installable
package, offers a single `coldcast` CLI, and centralizes URL/filename templates
so every source can be tuned via YAML.

![Workflow](https://em-content.zobj.net/thumbs/120/apple/325/compass_1f9ed.png)

## Product coverage

| Source | Description | CLI |
| --- | --- | --- |
| `ECCC_NWP`, `ECCC_PRECIP_GRID`, `ECCC_RADAR`, `SNOWCAST`, `GLOBSNOW`, `SNODAS`, `ECCC_API`, `SNOTEL` | Environment Canada grib/radar/csv downloads. | `coldcast download eccc_nwp --model RDPS` |
| `NOAA_HRRR`, `NOAA_GFS`, `NOAA_GEFS` | NOMADS Grib Filter subsetting with bbox/variables/members. | `coldcast download noaa_hrrr --dry-run` |
| `ERA5`, `ERA5_LAND` | CDS netCDF retrievals via `cdsapi`. | `coldcast download era5 --run-info-netcdf ./runinfo.nc` |
| `ECMWF_NWP` | ECMWF open-data deterministic/ensemble downloads (IFS/AIFS). | `coldcast download ecmwf_nwp --model IFS_ENS` |

## Installation

```bash
python -m pip install -e .
```

All ERA5/ECMWF dependencies (`cdsapi`, `ecmwf-opendata`, `netCDF4`, `xarray`) are bundled into the main install so the CLI is ready for the full product suite out of the box.

## CLI overview

```
coldcast download <source> [options]
```

Options:

- `--settings`: YAML config (defaults to `src/coldcast/data/default_settings.yaml`).
- `--output-dir`: download destination.
- `--max-threads`: concurency limit for HTTP downloads.
- `--model`: model key for multi-model sources (ECCC_NWP, ECMWF_NWP).
- `--dry-run`: print URLs/jobs without downloading.
- `--run-info-file`: FEWS XML run info.
- `--run-info-netcdf`: netCDF time override (requires `xarray`/`netCDF4` via `coldcast[ecmwf]`).

### Example commands

```bash
coldcast download noaa_hrrr --dry-run
coldcast download noaa_gfs --dry-run
coldcast download noaa_gefs --dry-run
coldcast download eccc_precip_grid --model RDPA --output-dir ./work
coldcast download snotel --dry-run
coldcast download era5 --run-info-netcdf ./runinfo.nc
coldcast download ecmwf_nwp --model AIFS_ENS --max-threads 4
```

## Configuration

Copy `src/coldcast/data/default_settings.yaml` and adjust:

- Templates (`url_template`, `filename_template`) are Python format strings.
- Range definitions (`forecast_hours`, `members`) accept `start/end/step`.
- NOAA blocks define bbox + variable/level pairs; GEFS members expand to `gepXX`.
- ECMWF & ERA5 sections mirror the legacy defaults for compatibility.

## Run-info overrides

FEWS XML or netCDF run info overrides the reference time, output path, and logs:

```bash
coldcast download eccc_precip_grid --run-info-file ../runinfo.xml
coldcast download era5 --run-info-netcdf ./runinfo.nc
```

The netCDF reader uses xarray to locate the first datetime variable in the file.

## Testing

- `pytest tests/test_urls.py` verifies URL building; network checks are opt-in:
  `COLDCAST_RUN_NETWORK_TESTS=1 pytest -m network`.
- `pytest tests/test_api_clients.py -m api_client` mocks `cdsapi` and ECMWF clients.

## Packaging

```bash
python -m build
twine upload dist/*
```

Ensure `pyproject.toml` defines `coldcast = "coldcast.cli:main"` and documents extras.
# Coldcast

Coldcast is a configurable data downloader for hydrometric, radar, and snow data sources.
It wraps the legacy scripts into a pip-installable package, adds a unified CLI, and
centralizes URL/filename templates in YAML for easy customization.

## Use cases

- Operational runs that download the latest ECCC NWP or precipitation grids.
- Daily station pulls from SNOTEL or ECCC hydrometric APIs.
- Automated snow products (SNODAS, GlobSnow, SnowCast) into scheduled pipelines.
- NOAA HRRR/GFS/GEFS subset downloads via NOMADS GRIB filter (with custom variables/levels).
- Reproducible backfills using a fixed reference time from a run info netCDF.

## Install

```bash
python -m pip install -e .
```

Optional extras:

```bash
python -m pip install -e ".[era5]"
python -m pip install -e ".[ecmwf]"
```

## CLI usage

Examples:

```bash
coldcast download noaa_hrrr --dry-run
coldcast download noaa_gfs --dry-run
coldcast download noaa_gefs --dry-run
coldcast download eccc_nwp --model HRDPS
coldcast download eccc_precip_grid --model RDPA --output-dir ./work
coldcast download snotel --dry-run
```

Common arguments:

- `--settings`: YAML settings file path
- `--run-info-file`: optional FEWS run info XML
- `--run-info-netcdf`: optional run info netCDF (sets reference time)
- `--output-dir`: override output directory
- `--max-threads`: override max download threads
- `--model`: model name (for model-based sources)
- `--dry-run`: print URLs only

## Reference time override (run info netCDF)

Many sources use `now` as the reference time. If you provide a run info netCDF,
its time value becomes the reference time for URL generation:

```bash
coldcast download eccc_precip_grid --model HRDPA --run-info-netcdf /path/to/runinfo.nc
```

This requires `netCDF4`:

```bash
python -m pip install netCDF4
```

## Configuration

The default configuration lives in `src/coldcast/data/default_settings.yaml`.
You can copy and modify it, or provide a custom file via `--settings`.

Templates live in YAML. Example:

```yaml
ECCC_NWP:
  url_template: "{url_base}{day_str}{url_detail}{hour_str}/{lead_time_str}/{filename}"
  HRDPS:
    filename_template: "{day_str}T{hour_str}Z_MSC_HRDPS_{parameter}_RLatLon0.0225_PT{lead_time_str}H.grib2"
```

## NOAA HRRR (GRIB filter)

HRRR queries are built using the NOMADS GRIB filter migration guidance:
https://nomads.ncep.noaa.gov/info.php?page=opendap_grib_migration

HRRR settings live under `NOAA_HRRR` in `default_settings.yaml`. You can change:
- `domain` and `product` (e.g., `alaska`/`wrfsfcf`)
- `domain_suffix` when you need e.g. `.ak` for Alaska filenames
- `forecast_hours` (accepts `start`, `end`, `step` or explicit list)
- `bbox`
- `variables` (var/level pairs)

GFS and GEFS settings are similarly defined under `NOAA_GFS` and `NOAA_GEFS` (defaulting to 0.25°). GEFS `members` also support `start`/`end`/`step` ranges to request the entire ensemble compactly.

## Tests

URL construction tests:

```bash
pytest tests/test_urls.py
```

Network URL checks are marked and skipped by default:

```bash
COLDCAST_RUN_NETWORK_TESTS=1 pytest -m network
```
