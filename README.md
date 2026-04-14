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
coldcast download eccc_precip_grid --model HREPA --dry-run
```

## Product coverage

| Source | Description | CLI | 
| --- | --- | --- |
| `ECCC_NWP`, `ECCC_PRECIP_GRID`, `ECCC_RADAR`, `SNOWCAST`, `GLOBSNOW`, `SNODAS`, `ECCC_API`, `ALBERTA_API`, `SNOTEL` | Environment Canada / Alberta grib/radar/csv downloads. | `coldcast download eccc_nwp --model RDPS` |
| `NOAA_HRRR`, `NOAA_GFS`, `NOAA_GEFS` | NOMADS Grib Filter subsetting with bbox/variables/members. | `coldcast download noaa_hrrr --dry-run` |
| `ERA5`, `ERA5_LAND` | CDS netCDF retrievals via `cdsapi`. | `coldcast download era5 --run-info-netcdf ./runinfo.nc` |
| `ECMWF_NWP` | ECMWF open-data deterministic/ensemble downloads (IFS/AIFS). | `coldcast download ecmwf_nwp --model IFS_ENS --run-info-netcdf ./runinfo.nc` |

## CLI usage

```text
coldcast download <source> [options]
```

Common options:

- `--settings`: YAML config (defaults to `src/coldcast/data/default_settings.yaml`).
- `--output-dir`: download destination. If the directory does not exist, Coldcast creates it automatically.
- `--max-threads`: concurrency limit for HTTP downloads.
- `--model`: model key for multi-model sources (ECCC_NWP, ECMWF_NWP).
- `--dry-run`: print URLs/jobs without downloading.
- `--run-info-file`: FEWS XML run info.
- `--run-info-netcdf`: FEWS runinfo netCDF; uses variable `time0` as reference time when present (see Run-info overrides).

## Examples

```bash
coldcast download noaa_hrrr --dry-run
coldcast download noaa_gfs --dry-run
coldcast download noaa_gefs --dry-run
coldcast download eccc_precip_grid --model RDPA --output-dir ./work
coldcast download eccc_precip_grid --model HREPA --output-dir ./work
coldcast download eccc_api --model swob-realtime --stations-csv ./my_stations.csv --output-dir ./work
coldcast download alberta_api --stations-csv ./ALBERTA_API_Stations.csv --output-dir ./work
coldcast download snotel --dry-run
coldcast download era5 --run-info-netcdf ./runinfo.nc
coldcast download ecmwf_nwp --model AIFS_ENS --max-threads 4 --run-info-netcdf ./runinfo.nc
```

## Configuration

Copy `src/coldcast/data/default_settings.yaml` and adjust:

- Templates (`url_template`, `filename_template`) are Python format strings.
- Range definitions (`forecast_hours`, `members`) accept `start/end/step`.
- NOAA blocks define bbox + variable/level pairs; GEFS members expand to `gepXX`.
- ECMWF & ERA5 sections mirror the legacy defaults for compatibility.
- **ECMWF_NWP** always requests the **00 UTC** model cycle (06/12/18 UTC are not used); the date is the calendar day of that 00z instant after applying delay and any reference_time / latest() wall-clock.

### `ECCC_API` (GeoMet hydrometric + SWOB)

Hydrological and meteorological station lists are separate:

- `station_csv_hydro` — bundled as `ECCC_API_Stations_Hydro.csv`; `ID` is the hydrometric station number (`STATION_NUMBER` in URLs).
- `station_csv_meteo` — bundled as `ECCC_API_Stations_Meteo.csv`; default column `MSC_ID` for `swob-realtime` (`msc_id-value` in URLs). Override with `station_column` on a collection if needed.

Each entry under `ECCC_API.collections` must set `station_list: hydro` or `station_list: meteo`. Collections may override `url_template` / `filename_template` (e.g. SWOB uses `properties=` to limit JSON fields).

GeoMet caps each `/items` response at 10000 features. The bundled `ECCC_API` settings use `limit: 10000`, `fetch_all_pages: true`, and `sort_output_datetime_descending: true` for **all** collections—hydrometric (`hydrometric-realtime`, `hydrometric-daily-mean`, …) and meteo—so long station histories are merged across pages and CSV rows list newest times first.

On the CLI, `--model <collection>` runs only that collection (collection key or GeoMet `collection` id, case-insensitive). `--stations-csv PATH` uses that file instead of the configured station CSVs for the run; hydrometric and meteo collections both read station IDs from this path when they are included, so the file must contain the column each collection uses (`ID`, `MSC_ID`, or `station_column`).

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
coldcast download eccc_api --model hydrometric-realtime --stations-csv ./stations.csv --dry-run
coldcast download eccc_api --model climate-daily --stations-csv ./HindcastMeteoStations.csv --dry-run
```

Legacy configs may keep `station_csv` instead of `station_csv_hydro` for hydrological stations only.

### `ALBERTA_API` (WISKI station download)

`ALBERTA_API` downloads station time series from Alberta WISKI `Download` endpoint, using a mapping CSV with columns:

- `Station` (e.g. `05BJ805`)
- `Parameter` (e.g. `TA`, `PR`)
- `TsID` (e.g. `160424042`)

Behavior:

- Requests are built like:
  `https://rivers.alberta.ca/WiskiLiveDataService/Download?tsId=<TsID>&from=<from_date>&to=<to_date>&filename=<Station>_<Parameter>_C.Corrected-Sensor.csv&zip=true&json=true`
- `to_date: latest` resolves to today.
- Default `from_date: auto` with `default_years_back: 2` uses the same calendar month/day as today, two years earlier, through today. Override with a fixed `from_date: "YYYY-MM-DD"` if needed.
- Each successful HTTP response is saved to the output directory as `<Station>_<Parameter>.zip` when the body is a ZIP (set `save_raw_response: false` to disable). FEWS CSV is written separately as `<Station>_<Parameter>.csv` when parsing succeeds.
- `fews_csv.layout` supports `wide` (default) and `long`.
- `PR` values are rates (per hour). Each row is the amount since the previous sample: `rate × Δt` (hours), not a cumulative total from the start of the series.
- `PC` values are treated as a cumulative counter (e.g. tipping bucket). Differences between successive readings are summed into each UTC clock hour so the CSV has one row per hour.

```bash
coldcast download alberta_api --dry-run
coldcast download alberta_api --stations-csv ./ALBERTA_API_Stations.csv --output-dir ./work
```

## Run-info overrides

FEWS XML or netCDF run info overrides the reference time, output path, and logs:

```bash
coldcast download eccc_precip_grid --run-info-file ../runinfo.xml
coldcast download era5 --run-info-netcdf ./runinfo.nc
```

For Delft-FEWS `runinfo.nc`, the reader uses the **`time0`** variable (CF time units). If `time0` is absent, it falls back to a variable named `time` / `TIME` / `Time`, then the first `datetime64` variable.

## Testing

- `pytest tests/test_urls.py` verifies URL building; `pytest tests/test_eccc_api.py` covers hydro vs meteo `ECCC_API` routing; `pytest tests/test_run_info_netcdf.py` covers FEWS `runinfo.nc` / `time0` parsing. Network checks are opt-in:
  `COLDCAST_RUN_NETWORK_TESTS=1 pytest -m network`.
- `pytest tests/test_api_clients.py -m api_client` mocks `cdsapi` and ECMWF clients.
