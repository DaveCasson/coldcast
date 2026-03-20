from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple


def _fews_column_names(fews_csv: Mapping[str, object]) -> Dict[str, str]:
    return {
        "location": str(fews_csv.get("location_column", "locationId")),
        "parameter": str(fews_csv.get("parameter_column", "parameterId")),
        "datetime": str(fews_csv.get("datetime_column", "dateTime")),
        "value": str(fews_csv.get("value_column", "value")),
        "unit": str(fews_csv.get("unit_column", "unit")),
        "quality": str(fews_csv.get("quality_column", "qualityFlag")),
    }


def _location_from_properties(props: Mapping[str, Any], station_list: str) -> str:
    if station_list == "hydro":
        v = props.get("STATION_NUMBER")
        return str(v).strip() if v is not None and str(v).strip() else ""
    for key in ("msc_id-value", "clim_id-value", "stn_id-value"):
        v = props.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _datetime_from_properties(props: Mapping[str, Any], datetime_column: str) -> Optional[str]:
    raw = props.get(datetime_column)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _scalar_value(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _format_numeric(num: float) -> str:
    if isinstance(num, float) and num.is_integer():
        return str(int(num))
    return str(num)


def geojson_features_to_fews_rows(
    features: List[Mapping[str, Any]],
    collection_cfg: Mapping[str, Any],
    *,
    fews_csv_cfg: Mapping[str, object],
    parameter_id_map: Mapping[str, str],
) -> List[Dict[str, str]]:
    """One row per (location, time, parameter) for Delft-FEWS delimited / general CSV import."""
    station_list = str(collection_cfg.get("station_list", "hydro"))
    dt_col = str(collection_cfg.get("datetime_column", "DATETIME"))
    variables = _variables_list(collection_cfg)

    names = _fews_column_names(fews_csv_cfg)
    loc_key = names["location"]
    par_key = names["parameter"]
    dt_key = names["datetime"]
    val_key = names["value"]
    unit_col = names["unit"]
    qual_col = names["quality"]

    rows: List[Dict[str, str]] = []
    for feat in features:
        props = feat.get("properties")
        if not isinstance(props, dict):
            continue
        loc = _location_from_properties(props, station_list)
        dt = _datetime_from_properties(props, dt_col)
        if not loc or not dt:
            continue
        for param in variables:
            pname = str(param)
            raw = props.get(pname)
            num = _scalar_value(raw)
            if num is None:
                continue
            fews_pid = parameter_id_map.get(pname, pname)
            uom = props.get(f"{pname}-uom")
            qa = props.get(f"{pname}-qa")
            rows.append(
                {
                    loc_key: loc,
                    par_key: str(fews_pid),
                    dt_key: dt,
                    val_key: _format_numeric(num),
                    unit_col: "" if uom is None else str(uom),
                    qual_col: "" if qa is None else str(qa),
                }
            )

    sort_keys = (names["location"], names["datetime"], names["parameter"])
    rows.sort(key=lambda r: tuple(r.get(k, "") for k in sort_keys))
    return rows


def write_fews_csv(
    path: Path,
    rows: List[MutableMapping[str, str]],
    *,
    fews_csv_cfg: Mapping[str, object],
) -> None:
    names = _fews_column_names(fews_csv_cfg)
    fieldnames = [
        names["location"],
        names["parameter"],
        names["datetime"],
        names["value"],
        names["unit"],
        names["quality"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if fews_csv_cfg.get("utf8_bom") else "utf-8"
    delimiter = str(fews_csv_cfg.get("delimiter", ","))
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_geojson_bytes(body: bytes) -> List[Mapping[str, Any]]:
    data = json.loads(body.decode("utf-8"))
    feats = data.get("features")
    if not isinstance(feats, list):
        return []
    return feats


def _variables_list(collection_cfg: Mapping[str, Any]) -> List[str]:
    station_list = str(collection_cfg.get("station_list", "hydro"))
    variables = collection_cfg.get("download_variables")
    if not variables:
        variables = (
            ["DISCHARGE", "LEVEL"]
            if station_list == "hydro"
            else ["air_temp", "pcpn_amt_pst1hr", "rnfl_amt_pst1hr"]
        )
    return [str(v) for v in variables]


def _wide_header_map(
    variables: List[str],
    value_column_names: Mapping[str, str],
) -> Tuple[List[str], Dict[str, str]]:
    """CSV column headers in variable order; maps API property name -> header."""
    headers: List[str] = []
    api_to_header: Dict[str, str] = {}
    for api in variables:
        header = str(value_column_names.get(api, api))
        headers.append(header)
        api_to_header[api] = header
    return headers, api_to_header


def geojson_features_to_fews_wide_rows(
    features: List[Mapping[str, Any]],
    collection_cfg: Mapping[str, Any],
    *,
    fews_csv_cfg: Mapping[str, object],
    value_column_names: Mapping[str, str],
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    One row per observation time; columns match FEWS table dateTimeColumn + valueColumn names.

    Returns (rows, fieldnames) where fieldnames is [datetime_header, *value_headers].
    """
    dt_prop = str(collection_cfg.get("datetime_column", "DATETIME"))
    variables = _variables_list(collection_cfg)

    dt_header = str(fews_csv_cfg.get("table_datetime_column", "DATETIME"))
    value_headers, api_to_header = _wide_header_map(variables, value_column_names)
    fieldnames = [dt_header] + value_headers

    rows: List[Dict[str, str]] = []
    for feat in features:
        props = feat.get("properties")
        if not isinstance(props, dict):
            continue
        dt = _datetime_from_properties(props, dt_prop)
        if not dt:
            continue
        row: Dict[str, str] = {dt_header: dt}
        for api in variables:
            header = api_to_header[api]
            raw = props.get(api)
            num = _scalar_value(raw)
            row[header] = "" if num is None else _format_numeric(num)
        rows.append(row)

    rows.sort(key=lambda r: r.get(dt_header, ""))
    return rows, fieldnames


def write_fews_wide_csv(
    path: Path,
    rows: List[MutableMapping[str, str]],
    fieldnames: List[str],
    *,
    fews_csv_cfg: Mapping[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if fews_csv_cfg.get("utf8_bom") else "utf-8"
    delimiter = str(fews_csv_cfg.get("delimiter", ","))
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
