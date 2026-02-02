from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from ..download import DownloadRequest
from ..time_utils import get_reference_time, lead_time_strings
from ..url_templates import render_template


def _build_context(
    day_str: str,
    hour_str: str,
    lead_time_str: str,
    parameter: str,
    model: str,
    model_cfg: Dict[str, object],
) -> Dict[str, object]:
    return {
        "day_str": day_str,
        "hour_str": hour_str,
        "lead_time_str": lead_time_str,
        "parameter": parameter,
        "model": model,
        "url_base": model_cfg["url_base"],
        "url_detail": model_cfg["url_detail"],
    }


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    source = settings["ECCC_NWP"]
    if model is None:
        model = source.get("default_model", "HRDPS")
    model_cfg = source[model]

    delay_hours = int(model_cfg["delay"])
    lead_time = int(model_cfg["lead_time"])
    interval = int(model_cfg["interval"])
    timestep = int(model_cfg["timestep"])

    parameters = model_cfg["parameter"]
    first_lead_times = model_cfg["first_lead_time"]

    ref_date = get_reference_time(delay_hours * 3600, base_time=settings.get("reference_time"))
    day_str = ref_date.date().strftime("%Y%m%d")
    hour_str = f"{interval * int(ref_date.time().hour / interval):02d}"

    requests: List[DownloadRequest] = []
    url_template = source["url_template"]
    filename_template = model_cfg["filename_template"]

    for parameter, first_lead in zip(parameters, first_lead_times):
        lead_times = lead_time_strings(int(first_lead), lead_time, timestep)
        for lead_time_str in lead_times:
            context = _build_context(day_str, hour_str, lead_time_str, parameter, model, model_cfg)
            filename = render_template(filename_template, context)
            context["filename"] = filename
            url = render_template(url_template, context)
            requests.append(DownloadRequest(url=url, filename=filename))

    return requests
