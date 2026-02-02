from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..download import DownloadRequest
from ..url_templates import render_template


def build_requests(settings: Dict[str, object], model: str | None = None) -> List[DownloadRequest]:
    source = settings["ECCC_API"]
    url_template = source["url_template"]
    filename_template = source["filename_template"]

    station_csv = Path(source["station_csv"])
    stations = pd.read_csv(station_csv)

    limit = source.get("limit", 100000)
    time_range = source.get("time_range", "")

    requests: List[DownloadRequest] = []
    for collection_name, collection_cfg in source["collections"].items():
        for _, row in stations.iterrows():
            station = str(row["ID"])
            context = {
                "url_base": source["url_base"],
                "collection": collection_cfg["collection"],
                "station": station,
                "limit": limit,
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
            requests.append(DownloadRequest(url=url, filename=filename))

    return requests
