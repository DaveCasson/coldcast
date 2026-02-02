from __future__ import annotations

import datetime as dt
from typing import Dict, List

from ..download import DownloadRequest
from ..url_templates import render_template


def _get_reference_time(basis_unit_minutes: int, base_time: dt.datetime | None = None) -> dt.datetime:
    now = base_time or dt.datetime.utcnow()
    minutes_past_hour = now.minute
    nearest_basis = round(minutes_past_hour / basis_unit_minutes) * basis_unit_minutes
    if nearest_basis >= 60:
        adjusted_time = now.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=1)
    else:
        adjusted_time = now.replace(minute=nearest_basis, second=0, microsecond=0)
    return adjusted_time


def _create_timestamps(
    timestep_minutes: int,
    delay_minutes: int,
    search_period_hours: int,
    base_time: dt.datetime | None = None,
) -> List[dt.datetime]:
    end_time = _get_reference_time(timestep_minutes, base_time) - dt.timedelta(minutes=delay_minutes)
    start_time = _get_reference_time(timestep_minutes, base_time) - dt.timedelta(hours=search_period_hours)
    timestamps = []
    current_time = start_time
    while current_time <= end_time:
        timestamps.append(current_time)
        current_time += dt.timedelta(minutes=timestep_minutes)
    return timestamps


def build_requests(settings: Dict[str, object], model: str | None = None) -> List[DownloadRequest]:
    source = settings["ECCC_RADAR"]
    url_template = source["url_template"]
    filename_template = source["filename_template"]

    username = source.get("username")
    password = source.get("password")
    auth = (username, password) if username and password else None

    timestamps = _create_timestamps(
        int(source["timestep_minutes"]),
        int(source["delay_minutes"]),
        int(source["search_period_hours"]),
        settings.get("reference_time"),
    )

    requests: List[DownloadRequest] = []
    for timestamp in timestamps:
        day_str = timestamp.strftime("%Y%m%d")
        timestamp_str = f"{timestamp.strftime('%Y%m%d')}T{timestamp.strftime('%H%M')}"
        context = {
            "day_str": day_str,
            "timestamp": timestamp_str,
            "data_type": source["data_type"],
            "url_base": source["url_base"],
        }
        filename = render_template(filename_template, context)
        context["filename"] = filename
        url = render_template(url_template, context)
        requests.append(DownloadRequest(url=url, filename=filename, auth=auth))

    return requests
