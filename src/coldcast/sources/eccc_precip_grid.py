from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from ..download import DownloadRequest
from ..url_templates import render_template


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    source = settings["ECCC_PRECIP_GRID"]
    if model is None:
        model = source.get("default_model", "RDPA")
    model_cfg = source[model]

    url_template = source["url_template"]
    filename_template = model_cfg["filename_template"]

    num_days_back = int(model_cfg["num_days_back"])
    delay_seconds = int(model_cfg["delay_hours"]) * 3600
    hour_list = model_cfg["hour_list"]

    base_time = settings.get("reference_time") or dt.datetime.utcnow()
    end_date = base_time - dt.timedelta(seconds=delay_seconds)
    start_date = end_date - dt.timedelta(days=num_days_back)
    requests: List[DownloadRequest] = []

    current_date = start_date
    while current_date.date() <= end_date.date():
        day_str = current_date.date().strftime("%Y%m%d")
        if current_date.date() == end_date.date():
            cutoff_hour = end_date.hour
            allowed_hours = [h for h in hour_list if int(h) <= cutoff_hour]
        else:
            allowed_hours = hour_list
        for hour_str in allowed_hours:
            context = {
                "day_str": day_str,
                "hour_str": hour_str,
                "model": model,
                "url_base": model_cfg["url_base"],
                "url_detail": model_cfg["url_detail"],
            }
            filename = render_template(filename_template, context)
            context["filename"] = filename
            url = render_template(url_template, context)
            requests.append(DownloadRequest(url=url, filename=filename))
        current_date = current_date + dt.timedelta(days=1)

    return requests
