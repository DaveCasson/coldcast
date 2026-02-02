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


def read_netcdf_reference_time(netcdf_path: Path) -> datetime:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("Run info netCDF requires xarray (install coldcast[ecmwf]).") from exc

    ds = xr.open_dataset(netcdf_path, decode_times=True)
    time_var = None
    for candidate in ("time", "TIME", "Time"):
        if candidate in ds.variables:
            time_var = ds[candidate]
            break

    if time_var is None:
        for var in ds.variables:
            data = ds[var]
            if np.issubdtype(data.dtype, np.datetime64):
                time_var = data
                break

    if time_var is None or len(time_var.values) == 0:
        ds.close()
        raise ValueError("No valid time variable found in runinfo netCDF.")

    value = time_var.values[0]
    ds.close()

    if isinstance(value, np.datetime64):
        ts = np.datetime_as_string(value, unit="s")
        return datetime.fromisoformat(ts)

    return value if isinstance(value, datetime) else datetime.fromtimestamp(value)
