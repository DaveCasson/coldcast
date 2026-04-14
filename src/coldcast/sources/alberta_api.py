from __future__ import annotations

import csv
import io
import json
import logging
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

import pandas as pd
import requests

from ..download import DownloadRequest
from .eccc_fews_csv import write_fews_csv, write_fews_wide_csv

logger = logging.getLogger("coldcast.alberta_api")


@dataclass(frozen=True)
class MappingEntry:
    station: str
    parameter: str
    ts_id: str


@dataclass(frozen=True)
class TimeValue:
    date_time: str
    value: float


def _read_mapping_csv(csv_path: Path) -> List[MappingEntry]:
    df = pd.read_csv(csv_path)
    required = ("Station", "Parameter", "TsID")
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise KeyError(f"Missing mapping CSV columns {missing} in {csv_path}")

    rows: List[MappingEntry] = []
    for _, row in df.iterrows():
        station = str(row["Station"]).strip() if not pd.isna(row["Station"]) else ""
        parameter = str(row["Parameter"]).strip() if not pd.isna(row["Parameter"]) else ""
        ts_id = str(row["TsID"]).strip() if not pd.isna(row["TsID"]) else ""
        if station and parameter and ts_id:
            rows.append(MappingEntry(station=station, parameter=parameter, ts_id=ts_id))
    return rows


def _build_remote_filename(entry: MappingEntry, suffix: str) -> str:
    return f"{entry.station}_{entry.parameter}_{suffix}.csv"


def _build_url(
    source: Mapping[str, object],
    entry: MappingEntry,
    from_date: str,
    to_date: str,
) -> str:
    filename_suffix = str(source.get("remote_filename_suffix", "C.Corrected-Sensor"))
    params = {
        "tsId": entry.ts_id,
        "from": from_date,
        "to": to_date,
        "filename": _build_remote_filename(entry, filename_suffix),
        "zip": str(bool(source.get("zip", False))).lower(),
        "json": str(bool(source.get("json", True))).lower(),
    }
    return f"{source['url_base']}?{urlencode(params)}"


def _mapping_csv_path(source: Mapping[str, object], stations_csv: str | None) -> Path:
    if stations_csv and str(stations_csv).strip():
        return Path(stations_csv).expanduser().resolve()
    return Path(str(source["mapping_csv"]))


def _resolve_to_date(raw_to_date: object) -> str:
    value = str(raw_to_date).strip()
    if value.lower() in {"latest", "today", ""}:
        return date.today().isoformat()
    return value


def _years_before_calendar(today: date, years: int) -> date:
    """Same month/day as *today*, *years* earlier (Feb 29 -> Feb 28 if needed)."""
    y = today.year - years
    try:
        return today.replace(year=y)
    except ValueError:
        return today.replace(month=2, day=28, year=y)


def _resolve_from_date(source: Mapping[str, object]) -> str:
    """
    If ``from_date`` is ``auto`` (or empty), use *default_years_back* calendar years
    before today. Otherwise use the configured ISO date string.
    """
    raw = source.get("from_date", "auto")
    value = str(raw).strip() if raw is not None else ""
    if value.lower() in {"auto", "", "rolling", "default"}:
        years = int(source.get("default_years_back", 2))
        return _years_before_calendar(date.today(), years).isoformat()
    return value


def build_requests(
    settings: Dict[str, object],
    model: str | None = None,
    stations_csv: str | None = None,
) -> List[DownloadRequest]:
    _ = model
    source = settings["ALBERTA_API"]
    mapping_csv = _mapping_csv_path(source, stations_csv)
    entries = _read_mapping_csv(mapping_csv)
    from_date = _resolve_from_date(source)
    to_date = _resolve_to_date(source.get("to_date", "latest"))
    suffix = str(source.get("remote_filename_suffix", "C.Corrected-Sensor"))

    requests_list: List[DownloadRequest] = []
    for entry in entries:
        url = _build_url(source, entry, from_date, to_date)
        filename = _build_remote_filename(entry, suffix)
        requests_list.append(DownloadRequest(url=url, filename=filename))
    return requests_list


def _raw_response_path(output_dir: Path, entry: MappingEntry, body: bytes) -> Path:
    """Filename for the undecoded HTTP body (zip from Alberta WISKI when zip=true)."""
    if body[:2] == b"PK":
        return output_dir / f"{entry.station}_{entry.parameter}.zip"
    return output_dir / f"{entry.station}_{entry.parameter}.download"


def _save_raw_response_if_enabled(
    output_dir: Path,
    entry: MappingEntry,
    body: bytes,
    *,
    source: Mapping[str, object],
) -> None:
    if not bool(source.get("save_raw_response", True)):
        return
    path = _raw_response_path(output_dir, entry, body)
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    logger.info("Wrote raw HTTP response %s (%s bytes)", path, len(body))


def _zip_member_payloads_ordered(body: bytes) -> List[bytes]:
    """Read each non-directory zip member; JSON-like names first (Alberta WISKI often ships one JSON file)."""
    with zipfile.ZipFile(io.BytesIO(body), "r") as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        if not members:
            raise ValueError("Zip payload had no files")

        def sort_key(name: str) -> Tuple[int, str]:
            lower = name.lower()
            if lower.endswith(".json"):
                return (0, name)
            if lower.endswith(".txt"):
                return (1, name)
            if lower.endswith(".csv"):
                return (2, name)
            return (3, name)

        members.sort(key=sort_key)
        return [zf.read(m) for m in members]


def _coerce_timestamp_to_iso_utc(ts: object) -> Optional[str]:
    """Map numeric epoch (seconds or ms) or string timestamps to ISO-UTC for FEWS CSV."""
    if ts is None or isinstance(ts, bool):
        return None
    if isinstance(ts, str):
        s = ts.strip()
        return s or None
    if isinstance(ts, (int, float)):
        num = float(ts)
        # Epoch milliseconds are often below 1e12 before ~Sep 2001; treat large numeric
        # values as ms (seconds stay well below 1e10 through ~2286 CE).
        if num > 1e10:
            num /= 1000.0
        try:
            dt = datetime.fromtimestamp(num, tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OSError, ValueError, OverflowError):
            return None
    return None


_JSON_TIME_KEYS = (
    "t",
    "T",
    "time",
    "Time",
    "timestamp",
    "Timestamp",
    "dateTime",
    "DateTime",
    "x",
    "date",
    "Date",
    "LocalDateTime",
    "localDateTime",
    "observationTime",
    "ObservationTime",
    "PointDate",
    "pointDate",
    "ReadingDate",
    "readingDate",
)
_JSON_VALUE_KEYS = (
    "v",
    "V",
    "value",
    "Value",
    "y",
    "Y",
    "Measurement",
    "measurement",
    "Val",
    "val",
)

_JSON_LIST_KEYS = (
    "Points",
    "points",
    "Data",
    "data",
    "values",
    "Values",
    "items",
    "Items",
    "records",
    "Records",
    "observations",
    "Observations",
    "Rows",
    "rows",
    "Series",
    "series",
    "TimeSeries",
    "timeSeries",
    "TimeSeriesPoints",
    "timeSeriesPoints",
    "Results",
    "results",
)

_MAX_JSON_DEPTH = 12


def _record_from_mapping(item: Mapping[str, Any]) -> Optional[TimeValue]:
    dt_raw: Any = None
    val_raw: Any = None
    for key in _JSON_TIME_KEYS:
        if key in item and item[key] is not None:
            dt_raw = item[key]
            break
    for key in _JSON_VALUE_KEYS:
        if key in item and item[key] is not None:
            val_raw = item[key]
            break
    if dt_raw is None:
        return None
    if isinstance(dt_raw, str):
        dt = dt_raw.strip() or None
    else:
        dt = _coerce_timestamp_to_iso_utc(dt_raw)
    if not dt:
        return None
    try:
        fv = float(val_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return TimeValue(date_time=dt, value=fv)


def _records_from_json_pairs(node: Sequence[object]) -> List[TimeValue]:
    """[[t, v], ...] or [[t, v, ...], ...] as used by WISKI / Highcharts-style series."""
    out: List[TimeValue] = []
    for pair in node:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        if isinstance(pair[0], str):
            dt = str(pair[0]).strip() or None
        else:
            dt = _coerce_timestamp_to_iso_utc(pair[0])
        if not dt:
            continue
        try:
            fv = float(pair[1])
        except (TypeError, ValueError):
            continue
        out.append(TimeValue(date_time=dt, value=fv))
    return out


def _records_from_json_node(node: object, depth: int = 0) -> List[TimeValue]:
    if depth > _MAX_JSON_DEPTH:
        return []

    if isinstance(node, list):
        if not node:
            return []
        first = node[0]
        if isinstance(first, (list, tuple)) and len(first) >= 2:
            pairs = _records_from_json_pairs(node)
            if pairs:
                return pairs
        dict_rows: List[TimeValue] = []
        for item in node:
            if isinstance(item, dict):
                rec = _record_from_mapping(item)
                if rec:
                    dict_rows.append(rec)
        if dict_rows:
            return dict_rows
        for item in node:
            got = _records_from_json_node(item, depth + 1)
            if got:
                return got
        return []

    if isinstance(node, dict):
        for key in _JSON_LIST_KEYS:
            if key in node:
                got = _records_from_json_node(node[key], depth + 1)
                if got:
                    return got
        for val in node.values():
            got = _records_from_json_node(val, depth + 1)
            if got:
                return got
    return []


def _records_from_json_data(data: object) -> List[TimeValue]:
    return _records_from_json_node(data, 0)


def _parse_records_from_json(raw: str) -> List[TimeValue]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return _records_from_json_data(data)


def _parse_records_from_csv(raw: str) -> List[TimeValue]:
    reader = csv.DictReader(io.StringIO(raw))
    out: List[TimeValue] = []
    for row in reader:
        dt = ""
        val = None
        for key in ("DateTime", "DATETIME", "dateTime", "date_time", "Timestamp", "timestamp"):
            candidate = row.get(key)
            if candidate:
                dt = str(candidate).strip()
                break
        for key in ("Value", "value", "VALUE", "y"):
            candidate = row.get(key)
            if candidate not in (None, ""):
                val = candidate
                break
        if not dt:
            continue
        try:
            fv = float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        out.append(TimeValue(date_time=dt, value=fv))
    return out


def _parse_time_values(body: bytes) -> List[TimeValue]:
    if body[:2] == b"PK":
        payloads = _zip_member_payloads_ordered(body)
    else:
        payloads = [body]

    for payload in payloads:
        try:
            raw = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        records = _parse_records_from_json(raw)
        if records:
            records.sort(key=lambda r: r.date_time)
            return records
        records = _parse_records_from_csv(raw)
        if records:
            records.sort(key=lambda r: r.date_time)
            return records
    return []


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _parse_ts_utc(s: str) -> Optional[pd.Timestamp]:
    ts = pd.to_datetime(s, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def _format_ts_utc(ts: pd.Timestamp) -> str:
    """UTC wall time as ``YYYY-MM-DDTHH:MM:SS`` (no trailing ``Z``; matches FEWS table patterns)."""
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def _pr_rate_to_interval_amounts(rows: List[TimeValue]) -> List[TimeValue]:
    """
    PR is a rate (per hour). Each output value is the amount in the interval since the
    previous sample: rate * delta_hours (not a running total from the start of the series).
    First valid row uses a 1 h interval when no prior sample exists.
    """
    valid: List[Tuple[TimeValue, pd.Timestamp]] = []
    for row in rows:
        ts = _parse_ts_utc(row.date_time)
        if ts is not None:
            valid.append((row, ts))
    out: List[TimeValue] = []
    for j, (row, ts) in enumerate(valid):
        if j == 0:
            dt_h = 1.0
        else:
            prev_ts = valid[j - 1][1]
            dt_h = max((ts - prev_ts).total_seconds() / 3600.0, 1e-9)
        amount = row.value * dt_h
        out.append(TimeValue(date_time=row.date_time, value=amount))
    return out


def _pc_cumulative_to_hourly_totals(rows: List[TimeValue]) -> List[TimeValue]:
    """
    PC is treated as a cumulative counter (e.g. tipping bucket). Increments are successive
    differences (counter reset: increment = current reading). Increments are summed into
    each UTC clock hour for one hourly value per hour.
    """
    parsed: List[Tuple[pd.Timestamp, float]] = []
    for r in rows:
        ts = _parse_ts_utc(r.date_time)
        if ts is None:
            continue
        parsed.append((ts, r.value))
    if not parsed:
        return []

    increments: List[Tuple[pd.Timestamp, float]] = []
    for i, (ts, v) in enumerate(parsed):
        if i == 0:
            inc = 0.0
        else:
            prev_v = parsed[i - 1][1]
            d = v - prev_v
            inc = d if d >= 0 else v
        increments.append((ts, inc))

    df = pd.DataFrame(increments, columns=["ts", "inc"])
    df["hour"] = df["ts"].dt.tz_convert("UTC").dt.floor("h")
    grouped = df.groupby("hour", as_index=False)["inc"].sum().sort_values("hour")
    out: List[TimeValue] = []
    for _, g in grouped.iterrows():
        out.append(TimeValue(date_time=_format_ts_utc(g["hour"]), value=float(g["inc"])))
    return out


def _transform_parameter_series(parameter: str, values: Iterable[TimeValue]) -> List[TimeValue]:
    rows = list(values)
    if not rows:
        return rows
    p = parameter.strip().upper()
    if p == "PR":
        return _pr_rate_to_interval_amounts(rows)
    if p == "PC":
        return _pc_cumulative_to_hourly_totals(rows)
    return rows


def _write_wide_csv(
    output_path: Path,
    entry: MappingEntry,
    rows: Sequence[TimeValue],
    fews_csv_cfg: Mapping[str, object],
) -> None:
    dt_header = str(fews_csv_cfg.get("table_datetime_column", "DATETIME"))
    value_column_names = fews_csv_cfg.get("value_column_names", {})
    mapped = value_column_names if isinstance(value_column_names, dict) else {}
    value_header = str(mapped.get(entry.parameter, entry.parameter))
    fieldnames = [dt_header, value_header]
    out_rows = [{dt_header: r.date_time, value_header: _format_number(r.value)} for r in rows]
    write_fews_wide_csv(output_path, out_rows, fieldnames, fews_csv_cfg=fews_csv_cfg)


def _write_long_csv(
    output_path: Path,
    entry: MappingEntry,
    rows: Sequence[TimeValue],
    fews_csv_cfg: Mapping[str, object],
) -> None:
    pmap_raw = fews_csv_cfg.get("parameter_id_map", {})
    pmap = pmap_raw if isinstance(pmap_raw, dict) else {}
    parameter_id = str(pmap.get(entry.parameter, entry.parameter))

    location_col = str(fews_csv_cfg.get("location_column", "locationId"))
    parameter_col = str(fews_csv_cfg.get("parameter_column", "parameterId"))
    datetime_col = str(fews_csv_cfg.get("datetime_column", "dateTime"))
    value_col = str(fews_csv_cfg.get("value_column", "value"))
    unit_col = str(fews_csv_cfg.get("unit_column", "unit"))
    quality_col = str(fews_csv_cfg.get("quality_column", "qualityFlag"))
    unit_value = str(fews_csv_cfg.get("default_unit", ""))
    quality_value = str(fews_csv_cfg.get("default_quality_flag", ""))

    out_rows = [
        {
            location_col: entry.station,
            parameter_col: parameter_id,
            datetime_col: r.date_time,
            value_col: _format_number(r.value),
            unit_col: unit_value,
            quality_col: quality_value,
        }
        for r in rows
    ]
    write_fews_csv(output_path, out_rows, fews_csv_cfg=fews_csv_cfg)


def _download_one(
    entry: MappingEntry,
    source: Mapping[str, object],
    output_dir: Path,
    timeout_seconds: int,
    fews_csv_cfg: Mapping[str, object],
) -> bool:
    from_date = _resolve_from_date(source)
    to_date = _resolve_to_date(source.get("to_date", "latest"))
    url = _build_url(source, entry, from_date, to_date)
    out_name = f"{entry.station}_{entry.parameter}.csv"
    output_path = output_dir / out_name

    if output_path.exists():
        logger.info("File %s already exists. Skipping.", output_path)
        return False

    try:
        response = requests.get(url, timeout=timeout_seconds)
        if response.status_code < 200 or response.status_code >= 300:
            logger.warning("Failed to download %s (status %s)", url, response.status_code)
            return False
    except requests.RequestException as exc:
        logger.warning("Download failed for %s: %s", url, exc)
        return False

    _save_raw_response_if_enabled(output_dir, entry, response.content, source=source)

    try:
        rows = _parse_time_values(response.content)
    except (UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
        logger.warning("Unable to parse payload for %s: %s", url, exc)
        return False

    if not rows:
        logger.warning(
            "No usable records for station=%s parameter=%s url=%s",
            entry.station,
            entry.parameter,
            url,
        )
        return False

    converted = _transform_parameter_series(entry.parameter, rows)
    layout = str(fews_csv_cfg.get("layout", "wide")).lower()
    if layout == "long":
        _write_long_csv(output_path, entry, converted, fews_csv_cfg)
    else:
        _write_wide_csv(output_path, entry, converted, fews_csv_cfg)
    logger.info("Wrote FEWS CSV %s (%s rows)", output_path, len(converted))
    return True


def download(
    settings: Dict[str, object],
    data_source: str,
    model: str | None = None,
    stations_csv: str | None = None,
) -> None:
    _ = data_source
    _ = model
    source = settings["ALBERTA_API"]
    output_dir = Path(settings["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout_seconds = int(source.get("http_timeout_seconds", 120))
    max_threads = int(settings.get("max_num_threads", 4))
    fews_raw = source.get("fews_csv")
    fews_csv_cfg: Dict[str, object] = dict(fews_raw) if isinstance(fews_raw, dict) else {}

    mapping_csv = _mapping_csv_path(source, stations_csv)
    entries = _read_mapping_csv(mapping_csv)
    if not entries:
        logger.info("No ALBERTA_API mapping rows found.")
        return

    semaphore = threading.BoundedSemaphore(max_threads)

    def wrapped(entry: MappingEntry) -> bool:
        with semaphore:
            return _download_one(entry, source, output_dir, timeout_seconds, fews_csv_cfg)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(wrapped, entry) for entry in entries]
        for future in as_completed(futures):
            future.result()
