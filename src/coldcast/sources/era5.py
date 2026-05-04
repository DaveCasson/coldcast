from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from ..bounding_box import resolve_era5_cds_sequence, round_cds_area_string
from ..download import DownloadRequest


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    return []


def download(settings: Dict[str, object], data_source: str) -> None:
    try:
        import cdsapi
    except ImportError as exc:
        raise RuntimeError("ERA5 downloads require cdsapi (install coldcast[era5]).") from exc

    if data_source == "ERA5":
        cfg = settings["ERA5"]
        seq = resolve_era5_cds_sequence(settings, cfg)
        coordinates = round_cds_area_string(seq)

        num_days_back = int(cfg["num_days_back"])
        delay_days = int(cfg["delay_days"])
        variables = cfg["variables_surface_level"]
        grid = cfg["grid"]
        hours = cfg["hours"]

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
        seq = resolve_era5_cds_sequence(settings, cfg)
        coordinates = round_cds_area_string(seq)
        num_days_back = int(cfg["num_days_back"])
        delay_days = int(cfg["delay_days"])
        variables = cfg["variables"]
        hours = cfg["hours"]

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
