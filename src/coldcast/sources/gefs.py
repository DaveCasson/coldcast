from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional
from urllib.parse import urlencode

from ..download import DownloadRequest
from ..time_utils import get_reference_time
from ..url_templates import render_template
from ..utils import expand_sequence


def _latest_cycle(reference_time: dt.datetime, interval_hours: int) -> tuple[str, str]:
    hour = interval_hours * int(reference_time.hour / interval_hours)
    cycle_time = reference_time.replace(hour=hour, minute=0, second=0, microsecond=0)
    return cycle_time.strftime("%Y%m%d"), f"{hour:02d}"


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    source = settings["NOAA_GEFS"]

    delay_hours = int(source.get("delay_hours", 6))
    cycle_interval_hours = int(source.get("cycle_interval_hours", 6))
    reference_time = get_reference_time(delay_hours * 3600, base_time=settings.get("reference_time"))
    date_str, cycle_hour = _latest_cycle(reference_time, cycle_interval_hours)

    base_url = source["url_base"]
    filter_script = source["filter_script"]
    file_template = source["file_template"]
    dir_template = source["dir_template"]
    members = source.get("members", ["pgrb2a"])

    params_common = {
        "subregion": "",
        "leftlon": source["bbox"]["leftlon"],
        "rightlon": source["bbox"]["rightlon"],
        "toplat": source["bbox"]["toplat"],
        "bottomlat": source["bbox"]["bottomlat"],
    }

    var_params = {}
    for entry in source["variables"]:
        var_params[f"var_{entry['var']}"] = "on"
        var_params[f"lev_{entry['level']}"] = "on"

    requests: List[DownloadRequest] = []
    for forecast_hour in expand_sequence(source["forecast_hours"]):
        for member in expand_sequence(members):
            context = {
            "date": date_str,
            "cycle_hour": cycle_hour,
            "forecast_hour": int(forecast_hour),
                "member": member,
        }
        filename = render_template(file_template, context)
        dir_value = render_template(dir_template, context)
        params = {
            "file": filename,
            **var_params,
            **params_common,
            "dir": dir_value,
        }
        query = urlencode(params, doseq=True, safe="/")
        url = f"{base_url}{filter_script}?{query}"
        requests.append(DownloadRequest(url=url, filename=filename))

    return requests
