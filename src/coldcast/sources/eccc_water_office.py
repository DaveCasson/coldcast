from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Union
from urllib.parse import urlencode

from ..download import DownloadRequest
from ..url_templates import render_template
from .eccc_api import _read_station_ids


def _http_verify(source: Dict[str, object]) -> Union[bool, str]:
    bundle = str(source.get("http_ca_bundle", "") or "").strip()
    if bundle:
        return str(Path(bundle).expanduser().resolve())
    if source.get("http_verify_ssl") is False:
        return False
    return True


def _time_range(source: Dict[str, object]) -> tuple[str, str]:
    start_s = str(source.get("start_date", "") or "").strip()
    end_s = str(source.get("end_date", "") or "").strip()
    if start_s or end_s:
        if not start_s or not end_s:
            raise ValueError(
                "ECCC_WATER_OFFICE: set both start_date and end_date, or omit both to use days_back."
            )
        return start_s, end_s
    try:
        days_back = int(source.get("days_back", 7))
    except (TypeError, ValueError):
        days_back = 7
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)
    return (
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    )


def build_requests(
    settings: Dict[str, object],
    model: str | None = None,
    stations_csv: str | None = None,
) -> List[DownloadRequest]:
    _ = model
    source = settings["ECCC_WATER_OFFICE"]
    if stations_csv and str(stations_csv).strip():
        station_path = Path(stations_csv).expanduser().resolve()
    else:
        station_path = Path(str(source["station_csv"]))
    column = str(source.get("station_column", "ID"))
    stations = _read_station_ids(station_path, column)
    raw_params = source.get("parameters") or ["6"]
    parameters = [str(p) for p in raw_params]
    if not parameters:
        raise ValueError("ECCC_WATER_OFFICE.parameters must be a non-empty list")
    start_date, end_date = _time_range(source)
    url_base = str(source["url_base"]).rstrip("/")
    filename_template = str(source.get("filename_template", "{station}_water_office.csv"))
    verify = _http_verify(source)

    requests: List[DownloadRequest] = []
    for station in stations:
        query: List[tuple[str, str]] = [("stations[]", station)]
        for p in parameters:
            query.append(("parameters[]", p))
        query.append(("start_date", start_date))
        query.append(("end_date", end_date))
        url = f"{url_base}?{urlencode(query)}"
        context = {"station": station, "station_id": station}
        filename = render_template(filename_template, context)
        requests.append(DownloadRequest(url=url, filename=filename, verify=verify))
    return requests
