# Coldcast

<p align="left">
  <img src="assets/logo-arctic.svg" alt="Arctic" width="72" height="72" />
  <img src="assets/logo-alpine.svg" alt="Alpine" width="72" height="72" />
  <img src="assets/logo-boreal.svg" alt="Boreal" width="72" height="72" />
</p>

Coldcast is a configurable data downloader for hydrometric, radar, snow, and
reanalysis products. It provides a single `coldcast` CLI and YAML-driven
URL/filename templates so each source can be customized without code changes.

## Quick start

Install (editable for local development):

```bash
python -m pip install -e .
```

Run a dry-run to see URLs without downloading:

```bash
coldcast download noaa_hrrr --dry-run
```

Use a custom settings file:

```bash
coldcast download eccc_precip_grid --model RDPA --settings ./settings.yaml
```

## Product coverage

| Source | Description | CLI | 
| --- | --- | --- |
| `ECCC_NWP`, `ECCC_PRECIP_GRID`, `ECCC_RADAR`, `SNOWCAST`, `GLOBSNOW`, `SNODAS`, `ECCC_API`, `SNOTEL` | Environment Canada grib/radar/csv downloads. | `coldcast download eccc_nwp --model RDPS` |
| `NOAA_HRRR`, `NOAA_GFS`, `NOAA_GEFS` | NOMADS Grib Filter subsetting with bbox/variables/members. | `coldcast download noaa_hrrr --dry-run` |
| `ERA5`, `ERA5_LAND` | CDS netCDF retrievals via `cdsapi`. | `coldcast download era5 --run-info-netcdf ./runinfo.nc` |
| `ECMWF_NWP` | ECMWF open-data deterministic/ensemble downloads (IFS/AIFS). | `coldcast download ecmwf_nwp --model IFS_ENS` |

## CLI usage

```text
coldcast download <source> [options]
```

Common options:

- `--settings`: YAML config (defaults to `src/coldcast/data/default_settings.yaml`).
- `--output-dir`: download destination.
- `--max-threads`: concurrency limit for HTTP downloads.
- `--model`: model key for multi-model sources (ECCC_NWP, ECMWF_NWP).
- `--dry-run`: print URLs/jobs without downloading.
- `--run-info-file`: FEWS XML run info.
- `--run-info-netcdf`: netCDF time override.

## Examples

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

### `ECCC_API` (GeoMet hydrometric + SWOB)

Hydrological and meteorological station lists are separate:

- `station_csv_hydro` — bundled as `ECCC_API_Stations_Hydro.csv`; `ID` is the hydrometric station number (`STATION_NUMBER` in URLs).
- `station_csv_meteo` — bundled as `ECCC_API_Stations_Meteo.csv`; default column `MSC_ID` for `swob-realtime` (`msc_id-value` in URLs). Override with `station_column` on a collection if needed.

Each entry under `ECCC_API.collections` must set `station_list: hydro` or `station_list: meteo`. Collections may override `url_template` / `filename_template` (e.g. SWOB uses `properties=` to limit JSON fields).

**Delft-FEWS CSV output:** `coldcast download eccc_api` (without `--dry-run`) downloads GeoJSON from GeoMet, then writes **wide** CSV by default: one column `DATETIME` (name from `fews_csv.table_datetime_column`) plus one column per variable in `download_variables`, matching FEWS `dateTimeColumn` / `valueColumn` **name** attributes, e.g.

```xml
<table>
  <dateTimeColumn name="DATETIME" pattern="yyyy-MM-dd'T'HH:mm:ss'Z'"/>
  <valueColumn name="DISCHARGE" unit="m3/s" parameterId="QR.obs"/>
  <valueColumn name="LEVEL" unit="m" parameterId="HG.obs"/>
</table>
```

Rename CSV headers vs API fields with `fews_csv.value_column_names` (map API key → column name). Use `fews_csv.layout: long` for the previous long format (`locationId`, `parameterId`, `dateTime`, `value`, …) and `fews_csv.parameter_id_map` there. Set `fews_csv.utf8_bom: true` if your import expects a BOM. Output filenames use the `.csv` extension from `filename_template`.

If GeoMet returns no features, or no rows can be built (e.g. missing timestamps), a **warning is logged** and **no CSV file** is created for that station/collection.

```bash
coldcast download eccc_api --dry-run
coldcast download eccc_api --output-dir ./work
```

Legacy configs may keep `station_csv` instead of `station_csv_hydro` for hydrological stations only.

## Run-info overrides

FEWS XML or netCDF run info overrides the reference time, output path, and logs:

```bash
coldcast download eccc_precip_grid --run-info-file ../runinfo.xml
coldcast download era5 --run-info-netcdf ./runinfo.nc
```

The netCDF reader uses xarray to locate the first datetime variable in the file.

## Testing

- `pytest tests/test_urls.py` verifies URL building; `pytest tests/test_eccc_api.py` covers hydro vs meteo `ECCC_API` routing. Network checks are opt-in:
  `COLDCAST_RUN_NETWORK_TESTS=1 pytest -m network`.
- `pytest tests/test_api_clients.py -m api_client` mocks `cdsapi` and ECMWF clients.
