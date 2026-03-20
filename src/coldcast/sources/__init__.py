from __future__ import annotations

from typing import Callable, Dict, Optional, List

from . import (
    gfs,
    gefs,
    hrrr,
    eccc_api,
    eccc_nwp,
    eccc_precip_grid,
    eccc_radar,
    globsnow,
    snowcast,
    snodas,
    snotel,
)
from .era5 import build_requests as era5_requests
from .era5 import download as era5_download
from .ecmwf_nwp import build_requests as ecmwf_requests
from .ecmwf_nwp import download as ecmwf_download
from ..download import DownloadRequest


BuildFn = Callable[..., List[DownloadRequest]]


SOURCES: Dict[str, BuildFn] = {
    "NOAA_HRRR": hrrr.build_requests,
    "NOAA_GFS": gfs.build_requests,
    "NOAA_GEFS": gefs.build_requests,
    "ECCC_API": eccc_api.build_requests,
    "ECCC_NWP": eccc_nwp.build_requests,
    "ECCC_PRECIP_GRID": eccc_precip_grid.build_requests,
    "ECCC_RADAR": eccc_radar.build_requests,
    "SNOTEL": snotel.build_requests,
    "SNOWCAST": snowcast.build_requests,
    "GLOBSNOW": globsnow.build_requests,
    "SNODAS": snodas.build_requests,
    "ERA5": era5_requests,
    "ERA5_LAND": era5_requests,
    "ECMWF_NWP": ecmwf_requests,
}


DOWNLOAD_SOURCES = {
    "ERA5": era5_download,
    "ERA5_LAND": era5_download,
    "ECMWF_NWP": ecmwf_download,
    "ECCC_API": eccc_api.download,
}
