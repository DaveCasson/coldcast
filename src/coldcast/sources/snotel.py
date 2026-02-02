from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..download import DownloadRequest
from ..url_templates import render_template


def build_requests(settings: Dict[str, object], model: str | None = None) -> List[DownloadRequest]:
    source = settings["SNOTEL"]
    url_template = source["url_template"]
    filename_template = source["filename_template"]

    station_csv = Path(source["station_csv"])
    stations = pd.read_csv(station_csv)

    url_param = source.get(
        "url_param",
        "POR_BEGIN,POR_END/WTEQ::value,PREC::value,PRCP::value,SNWD::value,"
        "TAVG::value,WSPDV::value,TMAX::value,TMIN::value,SRADV::value",
    )

    requests: List[DownloadRequest] = []
    for _, row in stations.iterrows():
        station_name = str(row["SITE_NAME"]).replace(" ", "_")
        station_id = f"{row['SITE_ID']}:{row['STATE']}:SNTL%7Cid=%22%22%7Cname/"
        context = {
            "url_base": source["url_base"],
            "url_site": station_id,
            "url_param": url_param,
            "station_name": station_name,
        }
        filename = render_template(filename_template, context)
        context["filename"] = filename
        url = render_template(url_template, context)
        requests.append(DownloadRequest(url=url, filename=filename))

    return requests
