from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np
import xarray as xr

from ..bounding_box import merge_clip_bbox
from ..download import DownloadRequest
from ..url_templates import render_template

logger = logging.getLogger("coldcast.eccc_precip_grid")


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


def is_hrepa_model(model: Optional[str]) -> bool:
    return bool(model) and str(model).upper().startswith("HREPA")


def get_fews_netcdf_config(model_cfg: Mapping[str, object]) -> Optional[Dict[str, object]]:
    raw = model_cfg.get("fews_netcdf")
    if not raw or not isinstance(raw, dict):
        return None
    if not raw.get("enabled"):
        return None
    return dict(raw)


def clip_rlat_rlon_slices(
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> Tuple[slice, slice]:
    """Axis-aligned index ranges covering all cells inside the geographic bounding box."""
    lon_cmp = np.asarray(lon, dtype=np.float64)
    if lon_min < 0 or lon_max < 0:
        lon_cmp = (lon_cmp + 180.0) % 360.0 - 180.0
    lat_arr = np.asarray(lat, dtype=np.float64)
    mask = (lat_arr >= lat_min) & (lat_arr <= lat_max) & (lon_cmp >= lon_min) & (lon_cmp <= lon_max)
    if not np.any(mask):
        raise ValueError(
            "clip_bbox does not intersect the grid (no cells selected). "
            f"bbox lon [{lon_min}, {lon_max}] lat [{lat_min}, {lat_max}]"
        )
    rows = np.where(np.any(mask, axis=1))[0]
    cols = np.where(np.any(mask, axis=0))[0]
    return slice(int(rows[0]), int(rows[-1]) + 1), slice(int(cols[0]), int(cols[-1]) + 1)


def _primary_hrepa_precip_var(ds: xr.Dataset) -> str:
    need = {"ensemble", "time", "rlat", "rlon"}
    for name in ds.data_vars:
        if name == "ConfidenceIndex":
            continue
        da = ds[name]
        if need.issubset(da.dims) and da.ndim == 4:
            return name
    raise ValueError(
        "Could not find an HREPA-style precipitation variable "
        "(expected dims ensemble, time, rlat, rlon)."
    )


def _apply_cf_touchups(ds: xr.Dataset) -> xr.Dataset:
    out = ds.copy()
    out.attrs["Conventions"] = "CF-1.8"
    stamp = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    prev = out.attrs.get("history", "")
    line = f"{stamp} coldcast: FEWS-oriented post-process (clip/rename optional)."
    out.attrs["history"] = line if not prev or str(prev).strip() in ("", "--") else f"{prev}\n{line}"

    precip = _primary_hrepa_precip_var(out)
    u = out[precip].attrs.get("units", "")
    if isinstance(u, str) and u.replace(" ", "") in ("kg.m-2", "kg.m**-2"):
        out[precip].attrs["units"] = "kg m-2"
    return out


def postprocess_hrepa_netcdf(
    raw_path: Path,
    output_path: Path,
    fews_cfg: Mapping[str, object],
) -> bool:
    """
    Read HREPA NetCDF from Datamart, optionally clip and adjust for FEWS import; write NetCDF.

    Returns True if a new file was written, False if output already existed.
    """
    if output_path.exists():
        logger.info("HREPA FEWS output exists, skipping: %s", output_path)
        return False

    clip_on = bool(fews_cfg.get("clip_to_bbox"))
    bbox = fews_cfg.get("clip_bbox") if clip_on else None
    if clip_on:
        if not isinstance(bbox, dict):
            raise ValueError("fews_netcdf.clip_to_bbox is true but clip_bbox is missing or not a mapping.")
        for key in ("lon_min", "lon_max", "lat_min", "lat_max"):
            if key not in bbox:
                raise ValueError(f"fews_netcdf.clip_bbox missing key {key!r}")

    with xr.open_dataset(raw_path) as ds:
        if "lat" not in ds.variables or "lon" not in ds.variables:
            raise ValueError("HREPA file must contain 2D lat and lon for clipping/metadata.")

        if clip_on:
            lat = ds["lat"].values
            lon = ds["lon"].values
            rlat_sl, rlon_sl = clip_rlat_rlon_slices(
                lat,
                lon,
                lon_min=float(bbox["lon_min"]),
                lon_max=float(bbox["lon_max"]),
                lat_min=float(bbox["lat_min"]),
                lat_max=float(bbox["lat_max"]),
            )
            out = ds.isel(rlat=rlat_sl, rlon=rlon_sl).load()
        else:
            out = ds.load()

        if not bool(fews_cfg.get("include_confidence_index", False)) and "ConfidenceIndex" in out:
            out = out.drop_vars("ConfidenceIndex")

        out = _apply_cf_touchups(out)

        rename_to = fews_cfg.get("output_variable_name")
        if rename_to:
            precip = _primary_hrepa_precip_var(out)
            if precip != rename_to:
                out = out.rename({precip: str(rename_to)})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_netcdf(output_path)
        logger.info("Wrote HREPA FEWS NetCDF %s", output_path)
        return True


def maybe_postprocess_hrepa_fews(
    settings: Dict[str, object],
    model: str,
    requests_list: List[DownloadRequest],
    output_dir: str,
) -> None:
    source = settings["ECCC_PRECIP_GRID"]
    model_cfg = source[model]
    fews_cfg = get_fews_netcdf_config(model_cfg)
    if not fews_cfg:
        return

    fews_cfg = dict(fews_cfg)
    if bool(fews_cfg.get("clip_to_bbox")):
        fews_cfg["clip_bbox"] = merge_clip_bbox(settings, fews_cfg.get("clip_bbox"))

    suffix = str(fews_cfg.get("output_suffix", "_fews.nc"))
    if not suffix.endswith(".nc"):
        suffix = f"{suffix}.nc"

    out_root = Path(output_dir)
    for req in requests_list:
        raw_path = out_root / req.filename
        if not raw_path.is_file():
            logger.warning("HREPA raw file missing, skip FEWS post-process: %s", raw_path)
            continue
        stem = Path(req.filename).stem
        out_path = out_root / f"{stem}{suffix}"
        try:
            postprocess_hrepa_netcdf(raw_path, out_path, fews_cfg)
        except Exception as exc:
            logger.warning("HREPA FEWS post-process failed for %s: %s", raw_path, exc)
