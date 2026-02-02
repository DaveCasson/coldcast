from __future__ import annotations

import datetime as dt
from typing import Dict, List

from ..download import DownloadRequest
from ..url_templates import render_template


def build_requests(settings: Dict[str, object], model: str | None = None) -> List[DownloadRequest]:
    source = settings["SNODAS"]
    url_template = source["url_template"]
    filename_template = source["filename_template"]

    num_days_back = int(source["num_days_back"])
    parameters = source["parameters"]
    file_suffixes = source["file_suffixes"]

    base_time = settings.get("reference_time") or dt.datetime.utcnow()
    ref_date = base_time - dt.timedelta(days=num_days_back)
    requests: List[DownloadRequest] = []

    for day in range(0, num_days_back):
        ref_date = ref_date + dt.timedelta(days=1)
        date_str = ref_date.date().strftime("%Y%m%d")
        for parameter, suffix in zip(parameters, file_suffixes):
            context = {
                "url_base": source["url_base"],
                "parameter": parameter,
                "date_str": date_str,
                "file_suffix": suffix,
            }
            filename = render_template(filename_template, context)
            context["filename"] = filename
            url = render_template(url_template, context)
            requests.append(DownloadRequest(url=url, filename=filename))

    return requests
