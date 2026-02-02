from __future__ import annotations

import datetime as dt
import math
from typing import Dict, List, Optional

from ..download import DownloadRequest


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    return []


def _round_coords(coords):
    lon = [coords[1], coords[3]]
    lat = [coords[2], coords[0]]

    rounded_lon = [math.floor(lon[0] * 4) / 4, math.ceil(lon[1] * 4) / 4]
    rounded_lat = [math.floor(lat[0] * 4) / 4, math.ceil(lat[1] * 4) / 4]

    if lat[0] > rounded_lat[0] + 0.125:
        rounded_lat[0] += 0.25
    if lon[0] > rounded_lon[0] + 0.125:
        rounded_lon[0] += 0.25
    if lat[1] < rounded_lat[1] - 0.125:
        rounded_lat[1] -= 0.25
    if lon[1] < rounded_lon[1] - 0.125:
        rounded_lon[1] -= 0.25

    return "{}/{}/{}/{}".format(rounded_lat[1], rounded_lon[0], rounded_lat[0], rounded_lon[1])


def download(settings: Dict[str, object], data_source: str) -> None:
    try:
        import cdsapi
    except ImportError as exc:
        raise RuntimeError("ERA5 downloads require cdsapi (install coldcast[era5]).") from exc

    if data_source == "ERA5":
        cfg = settings["ERA5"]
        bounding_box = settings.get("bounding_box", cfg.get("bbox"))
        if not bounding_box:
            raise ValueError("bounding_box is required for ERA5 downloads.")

        num_days_back = int(cfg["num_days_back"])
        delay_days = int(cfg["delay_days"])
        variables = cfg["variables_surface_level"]
        grid = cfg["grid"]
        hours = cfg["hours"]

        coordinates = _round_coords(bounding_box)
        ref_date = settings.get("reference_time") or dt.datetime.utcnow()
        end_date = ref_date - dt.timedelta(days=delay_days)
        start_date = end_date - dt.timedelta(days=num_days_back)
        total_download_days = num_days_back - delay_days

        for day_counter in range(total_download_days):
            date = start_date + dt.timedelta(days=day_counter)
            client = cdsapi.Client()

            surface_filename = f"surface_level_variables_{date.strftime('%Y%m%d')}.nc"
            surface_output = str(settings["output_dir"]) + "/" + surface_filename

            client.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": "reanalysis",
                    "variable": variables,
                    "year": date.year,
                    "month": date.month,
                    "day": date.day,
                    "time": hours,
                    "area": coordinates,
                    "grid": grid,
                    "format": "netcdf",
                },
                surface_output,
            )

    elif data_source == "ERA5_LAND":
        cfg = settings["ERA5_LAND"]
        bounding_box = cfg["bbox"]
        num_days_back = int(cfg["num_days_back"])
        delay_days = int(cfg["delay_days"])
        variables = cfg["variables"]
        hours = cfg["hours"]

        coordinates = _round_coords(bounding_box)
        ref_date = settings.get("reference_time") or dt.datetime.utcnow()
        end_date = ref_date - dt.timedelta(days=delay_days)
        start_date = end_date - dt.timedelta(days=num_days_back)
        total_download_days = num_days_back - delay_days

        for day_counter in range(total_download_days):
            date = start_date + dt.timedelta(days=day_counter)
            client = cdsapi.Client()

            filename = f"era5_land_{date.strftime('%Y%m%d')}.nc"
            output_file = str(settings["output_dir"]) + "/" + filename

            client.retrieve(
                "reanalysis-era5-land",
                {
                    "variable": variables,
                    "year": date.year,
                    "month": date.month,
                    "day": date.day,
                    "time": hours,
                    "area": coordinates,
                    "format": "netcdf",
                },
                output_file,
            )
    else:
        raise ValueError(f"Unknown ERA5 data source: {data_source}")
