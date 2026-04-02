from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from xml.etree.ElementTree import parse
import numpy as np


def _get_namespace(settings: Dict[str, Any]) -> str:
    return settings.get("fews_name_space", "http://www.wldelft.nl/fews/PI")


def _find_text(root, namespace: str, tag: str) -> Optional[str]:
    node = root.find(f".//{{{namespace}}}{tag}")
    return node.text if node is not None else None


def _find_datetime(root, namespace: str, tag: str) -> Optional[datetime]:
    node = root.find(f".//{{{namespace}}}{tag}")
    if node is None:
        return None
    date = node.attrib.get("date")
    time = node.attrib.get("time", "")
    if time and "." in time:
        time = time.split(".")[0]
    return datetime.strptime(f"{date}{time}", "%Y-%m-%d%H:%M:%S")


def apply_run_info(settings: Dict[str, Any]) -> Dict[str, Any]:
    run_info_file = settings.get("run_info_file")
    if not run_info_file:
        return settings

    run_info_path = Path(run_info_file)
    if not run_info_path.exists() or not run_info_path.is_file():
        settings["xml_log"] = False
        return settings

    namespace = _get_namespace(settings)
    tree = parse(run_info_path.open("r", encoding="utf-8"))
    root = tree.getroot()

    settings["start_time"] = _find_datetime(root, namespace, "startDateTime")
    settings["end_time"] = _find_datetime(root, namespace, "endDateTime")
    settings["work_dir"] = _find_text(root, namespace, "workDir")

    destination_dir = _find_text(root, namespace, "destinationDir")
    if destination_dir:
        settings["output_dir"] = str(Path(destination_dir).expanduser().resolve())

    return settings


def _select_runinfo_time_variable(ds: Any) -> Any:
    """Prefer Delft-FEWS runinfo ``time0``, then CF ``time``, then first datetime64 variable."""
    if "time0" in ds.variables:
        return ds["time0"]
    for candidate in ("time", "TIME", "Time"):
        if candidate in ds.variables:
            return ds[candidate]
    for name in ds.variables:
        data = ds[name]
        if np.issubdtype(data.dtype, np.datetime64):
            return data
    return None


def _scalar_time_to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, np.datetime64):
        ts = np.datetime_as_string(value, unit="s")
        return datetime.fromisoformat(str(ts))

    import pandas as pd

    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("Invalid or missing time value in runinfo netCDF.")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def _first_instant_from_time_var(da: Any) -> datetime:
    import xarray as xr

    arr = np.asarray(da.values)
    if arr.size == 0:
        raise ValueError("Empty time variable in runinfo netCDF.")

    scalar = arr.flat[0]
    if isinstance(scalar, (float, np.floating, int, np.integer)) and da.attrs.get("units"):
        decoded = xr.decode_cf(xr.Dataset({"t": da}))["t"]
        arr = np.asarray(decoded.values)
        if arr.size == 0:
            raise ValueError("Decoded time variable empty in runinfo netCDF.")
        scalar = arr.flat[0]

    return _scalar_time_to_datetime(scalar)


def read_netcdf_reference_time(netcdf_path: Path) -> datetime:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("Run info netCDF requires xarray (install coldcast[ecmwf]).") from exc

    ds = xr.open_dataset(netcdf_path, decode_times=True)
    try:
        time_var = _select_runinfo_time_variable(ds)
        if time_var is None:
            raise ValueError("No valid time variable found in runinfo netCDF.")
        return _first_instant_from_time_var(time_var)
    finally:
        ds.close()
