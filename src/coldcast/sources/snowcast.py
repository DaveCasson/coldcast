from __future__ import annotations

import datetime as dt
from typing import Dict, List

from ..download import DownloadRequest
from ..url_templates import render_template


def build_requests(settings: Dict[str, object], model: str | None = None) -> List[DownloadRequest]:
    source = settings["SNOWCAST"]
    url_template = source["url_template"]
    filename_template = source["filename_template"]

    delay_hours = int(source["delay_hours"])
    base_time = settings.get("reference_time") or dt.datetime.utcnow()
    ref_date = base_time - dt.timedelta(hours=delay_hours)
    date_str = ref_date.date().strftime("%Y%m%d")

    context = {"url_base": source["url_base"], "date_str": date_str}
    filename = render_template(filename_template, context)
    context["filename"] = filename
    url = render_template(url_template, context)

    return [DownloadRequest(url=url, filename=filename)]
