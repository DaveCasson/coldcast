from __future__ import annotations

import json
import logging
import math
import numbers
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

import pandas as pd
import requests

from ..download import DownloadRequest
from ..url_templates import render_template
from .eccc_fews_csv import (
    geojson_features_to_fews_rows,
    geojson_features_to_fews_wide_rows,
    write_fews_csv,
    write_fews_wide_csv,
)

logger = logging.getLogger("coldcast.eccc_api")

_STATION_LIST_KINDS = frozenset({"hydro", "meteo"})

# MSC GeoMet OGC API — Features caps each /items response (see collection `numberReturned`).
GEOMET_OAPI_ITEMS_MAX_LIMIT = 10000


def _normalize_collection_name(value: object) -> str:
    return str(value).strip().lower().replace("_", "-")


def _csv_cell_to_station_id_str(val: object) -> str | None:
    """Normalize a mapping CSV cell to a station/id string (no ``.0`` from float-backed integers)."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    if isinstance(val, bool):
        return None
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            f = float(s)
            if math.isfinite(f) and f.is_integer():
                return str(int(f))
        except ValueError:
            pass
        return s
    if isinstance(val, numbers.Integral):
        return str(int(val))
    if isinstance(val, float):
        if not math.isfinite(val):
            return None
        if val.is_integer():
            return str(int(val))
        s = str(val).strip()
        return s or None
    s = str(val).strip()
    if not s:
        return None
    try:
        f = float(s)
        if math.isfinite(f) and f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


def _read_station_ids(csv_path: Path, column: str) -> List[str]:
    df = pd.read_csv(csv_path)
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not found in {csv_path}; columns: {list(df.columns)}")
    out: List[str] = []
    for val in df[column]:
        sid = _csv_cell_to_station_id_str(val)
        if sid:
            out.append(sid)
    return out


def _hydro_meteo_paths(source: Dict[str, object]) -> Tuple[str, str | None]:
    hydro = source.get("station_csv_hydro") or source.get("station_csv")
    if not hydro:
        raise KeyError(
            "ECCC_API requires station_csv_hydro (or legacy station_csv) for hydrological stations."
        )
    meteo = source.get("station_csv_meteo")
    return str(hydro), str(meteo) if meteo else None


def build_requests(
    settings: Dict[str, object],
    model: str | None = None,
    stations_csv: str | None = None,
) -> List[DownloadRequest]:
    source = settings["ECCC_API"]
    default_url_template = source["url_template"]
    default_filename_template = source["filename_template"]

    hydro_path_s, meteo_path_s = _hydro_meteo_paths(source)
    hydro_path = Path(hydro_path_s)
    meteo_path = Path(meteo_path_s) if meteo_path_s else None

    stations_override: Path | None = None
    if stations_csv and str(stations_csv).strip():
        stations_override = Path(stations_csv).expanduser().resolve()

    id_cache: Dict[Tuple[str, str], List[str]] = {}

    def station_ids(path: Path, column: str) -> List[str]:
        key = (str(path.resolve()), column)
        if key not in id_cache:
            id_cache[key] = _read_station_ids(path, column)
        return id_cache[key]

    try:
        raw_limit = int(source.get("limit", GEOMET_OAPI_ITEMS_MAX_LIMIT))
    except (TypeError, ValueError):
        raw_limit = GEOMET_OAPI_ITEMS_MAX_LIMIT
    page_limit = min(max(raw_limit, 1), GEOMET_OAPI_ITEMS_MAX_LIMIT)
    time_range = source.get("time_range", "")

    collections = source["collections"]
    selected_collection_name: str | None = None
    if model:
        model_key = _normalize_collection_name(model)
        if model_key:
            for collection_name, collection_cfg in collections.items():
                if _normalize_collection_name(collection_name) == model_key:
                    selected_collection_name = collection_name
                    break
                if isinstance(collection_cfg, dict) and _normalize_collection_name(
                    collection_cfg.get("collection", "")
                ) == model_key:
                    selected_collection_name = collection_name
                    break
        if selected_collection_name is None:
            available = ", ".join(str(k) for k in collections.keys())
            raise KeyError(
                f"Unknown ECCC_API collection '{model}'. Use one of: {available}"
            )

    requests: List[DownloadRequest] = []
    for collection_name, collection_cfg in collections.items():
        if selected_collection_name is not None and collection_name != selected_collection_name:
            continue
        if not isinstance(collection_cfg, dict):
            continue
        kind = collection_cfg.get("station_list")
        if kind not in _STATION_LIST_KINDS:
            raise ValueError(
                f"ECCC_API collection must set station_list to 'hydro' or 'meteo', got {kind!r}."
            )

        if kind == "hydro":
            path = stations_override if stations_override is not None else hydro_path
            default_col = "ID"
        else:
            if stations_override is not None:
                path = stations_override
            elif meteo_path is None:
                raise ValueError(
                    "ECCC_API.station_csv_meteo is required when a collection uses station_list: meteo."
                )
            else:
                path = meteo_path
            default_col = "MSC_ID"

        column = str(collection_cfg.get("station_column", default_col))
        try:
            stations = station_ids(path, column)
        except KeyError:
            if column != default_col:
                logger.warning(
                    "Column %r not found in %s for ECCC_API collection %s; falling back to %r",
                    column,
                    path,
                    collection_name,
                    default_col,
                )
                stations = station_ids(path, default_col)
            else:
                raise

        url_template = collection_cfg.get("url_template", default_url_template)
        filename_template = collection_cfg.get("filename_template", default_filename_template)

        for station in stations:
            context = {
                "url_base": source["url_base"],
                "collection": collection_cfg["collection"],
                "station": station,
                "limit": page_limit,
            }
            if time_range:
                context["time_range"] = time_range
            else:
                context["time_range"] = None
            filename = render_template(filename_template, context)
            context["filename"] = filename
            url = render_template(url_template, context)
            if not time_range:
                url = url.replace("&datetime=None", "").replace("&datetime=", "")
            requests.append(
                DownloadRequest(url=url, filename=filename, eccc_collection_key=collection_name)
            )

    return requests


def _output_csv_path(output_dir: Path, req: DownloadRequest) -> Path:
    name = Path(req.filename).name
    return output_dir / Path(name).with_suffix(".csv")


def _ogc_items_next_href(payload: Mapping[str, object]) -> str | None:
    links = payload.get("links")
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") == "next":
            href = link.get("href")
            if href:
                s = str(href).strip()
                return s or None
    return None


def _fetch_geojson_features_paginated(
    first_url: str,
    timeout: int,
    *,
    fetch_all_pages: bool,
    max_pages: int,
) -> List[Mapping[str, object]]:
    """Follow OGC `rel=next` links until exhausted or ``max_pages`` is reached."""
    all_feats: List[Mapping[str, object]] = []
    url: str | None = first_url
    pages = 0
    while url:
        pages += 1
        if pages > max_pages:
            logger.warning(
                "ECCC_API pagination stopped at max_pagination_pages=%s (incomplete data). last_url=%s",
                max_pages,
                url,
            )
            break
        try:
            response = requests.get(url, timeout=timeout)
        except requests.RequestException as exc:
            logger.warning("Download failed for %s: %s", url, exc)
            break
        if response.status_code < 200 or response.status_code >= 300:
            logger.warning("Failed to download %s (status %s)", url, response.status_code)
            break
        try:
            payload = json.loads(response.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid JSON for %s: %s", url, exc)
            break
        chunk = payload.get("features")
        if isinstance(chunk, list):
            all_feats.extend(chunk)
            logger.info(
                "ECCC_API page %s: +%s features (total %s)",
                pages,
                len(chunk),
                len(all_feats),
            )
        if not fetch_all_pages:
            break
        url = _ogc_items_next_href(payload)
    return all_feats


def _download_one_eccc(
    req: DownloadRequest,
    output_dir: Path,
    source: Dict[str, object],
    fews_csv_cfg: Dict[str, object],
    parameter_id_map: Dict[str, str],
    value_column_names: Dict[str, str],
    timeout: int,
) -> bool:
    if not req.eccc_collection_key:
        logger.error("ECCC_API request missing eccc_collection_key for %s", req.url)
        return False
    collections = source["collections"]
    raw_cfg = collections.get(req.eccc_collection_key)
    if not isinstance(raw_cfg, dict):
        logger.error("Unknown ECCC_API collection %r", req.eccc_collection_key)
        return False
    collection_cfg = raw_cfg

    out_path = _output_csv_path(output_dir, req)
    if out_path.exists():
        logger.info("File %s already exists. Skipping.", out_path)
        return False

    # Pagination, page-size clamp, and CSV datetime order apply to every collection
    # (hydrometric and meteo); there is no separate hydro code path.
    fetch_all = bool(source.get("fetch_all_pages", True))
    try:
        max_pages = int(source.get("max_pagination_pages", 5000))
    except (TypeError, ValueError):
        max_pages = 5000
    max_pages = max(max_pages, 1)

    sort_dt_desc = bool(source.get("sort_output_datetime_descending", False))

    features = _fetch_geojson_features_paginated(
        req.url,
        timeout,
        fetch_all_pages=fetch_all,
        max_pages=max_pages,
    )

    if not features:
        logger.warning(
            "ECCC_API no data for station (empty GeoJSON features); skipping CSV. "
            "collection=%s file=%s url=%s",
            req.eccc_collection_key,
            out_path.name,
            req.url,
        )
        return False

    layout = str(fews_csv_cfg.get("layout", "wide")).lower()
    if layout == "long":
        rows = geojson_features_to_fews_rows(
            features,
            collection_cfg,
            fews_csv_cfg=fews_csv_cfg,
            parameter_id_map=parameter_id_map,
            sort_datetime_descending=sort_dt_desc,
        )
        if not rows:
            logger.warning(
                "ECCC_API no CSV rows produced (no usable observations in %s features); skipping CSV. "
                "collection=%s file=%s url=%s",
                len(features),
                req.eccc_collection_key,
                out_path.name,
                req.url,
            )
            return False
        write_fews_csv(out_path, rows, fews_csv_cfg=fews_csv_cfg)
        logger.info("Wrote FEWS CSV (long) %s (%s rows)", out_path, len(rows))
    else:
        wide_rows, fieldnames = geojson_features_to_fews_wide_rows(
            features,
            collection_cfg,
            fews_csv_cfg=fews_csv_cfg,
            value_column_names=value_column_names,
            sort_datetime_descending=sort_dt_desc,
        )
        if not wide_rows:
            logger.warning(
                "ECCC_API no CSV rows produced (no valid times/values in %s features); skipping CSV. "
                "collection=%s file=%s url=%s",
                len(features),
                req.eccc_collection_key,
                out_path.name,
                req.url,
            )
            return False
        write_fews_wide_csv(out_path, wide_rows, fieldnames, fews_csv_cfg=fews_csv_cfg)
        logger.info("Wrote FEWS CSV (wide) %s (%s rows)", out_path, len(wide_rows))
    return True


def download(
    settings: Dict[str, object],
    data_source: str,
    model: str | None = None,
    stations_csv: str | None = None,
) -> None:
    """Download GeoJSON from MSC GeoMet and write Delft-FEWS-friendly CSV files."""
    _ = data_source
    source = settings["ECCC_API"]
    output_dir = Path(settings["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    max_threads = int(settings.get("max_num_threads", 4))
    timeout = int(source.get("http_timeout_seconds", 120))

    fews_raw = source.get("fews_csv")
    fews_csv_cfg: Dict[str, object] = dict(fews_raw) if isinstance(fews_raw, dict) else {}

    pmap_raw = fews_csv_cfg.get("parameter_id_map")
    parameter_id_map: Dict[str, str] = {}
    if isinstance(pmap_raw, dict):
        parameter_id_map = {str(k): str(v) for k, v in pmap_raw.items()}

    vcn_raw = fews_csv_cfg.get("value_column_names")
    value_column_names: Dict[str, str] = {}
    if isinstance(vcn_raw, dict):
        value_column_names = {str(k): str(v) for k, v in vcn_raw.items()}

    requests_list = build_requests(settings, model=model, stations_csv=stations_csv)
    if not requests_list:
        logger.info("No ECCC_API download requests to process.")
        return

    semaphore = threading.BoundedSemaphore(max_threads)

    def wrapped(req: DownloadRequest) -> bool:
        with semaphore:
            return _download_one_eccc(
                req,
                output_dir,
                source,
                fews_csv_cfg,
                parameter_id_map,
                value_column_names,
                timeout,
            )

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(wrapped, req) for req in requests_list]
        for future in as_completed(futures):
            future.result()
