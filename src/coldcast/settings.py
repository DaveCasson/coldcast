from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import importlib.resources as resources

import yaml

from .run_info import apply_run_info, read_netcdf_reference_time


DEFAULT_SETTINGS_FILE = "default_settings.yaml"


@dataclass
class SettingsBundle:
    settings: Dict[str, Any]
    settings_path: Path


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _resolve_relative_paths(
    settings: Dict[str, Any],
    *,
    data_base_dir: Path,
    output_base_dir: Path,
) -> Dict[str, Any]:
    def resolve_path(value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.strip() == "":
            return ""
        candidate = Path(value)
        if candidate.is_absolute():
            return str(candidate)
        return str((data_base_dir / candidate).resolve())

    if "output_dir" in settings:
        output_dir = Path(settings["output_dir"])
        if not output_dir.is_absolute():
            settings["output_dir"] = str((output_base_dir / output_dir).resolve())

    for key in ("log_file", "log_xml_file", "run_info_file", "run_info_netcdf"):
        if key in settings:
            settings[key] = resolve_path(settings[key])

    for data_source in ("ECCC_API", "SNOTEL"):
        if data_source in settings and isinstance(settings[data_source], dict):
            src = settings[data_source]
            for station_key in (
                "station_csv",
                "station_csv_hydro",
                "station_csv_meteo",
            ):
                if station_key in src:
                    src[station_key] = resolve_path(src[station_key])

    return settings


def load_settings(
    path: Optional[str] = None,
    *,
    output_dir: Optional[str] = None,
    max_num_threads: Optional[int] = None,
    run_info_file: Optional[str] = None,
    run_info_netcdf: Optional[str] = None,
) -> SettingsBundle:
    base_dir: Optional[Path] = None
    if path:
        settings_path = Path(path).expanduser().resolve()
        settings = _load_yaml(settings_path)
    else:
        data_dir = resources.files("coldcast.data")
        with data_dir.joinpath(DEFAULT_SETTINGS_FILE).open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle) or {}
        settings_path = Path(data_dir)
        base_dir = Path(data_dir)

    data_base_dir = base_dir or settings_path.parent
    output_base_dir = Path.cwd()
    settings = _resolve_relative_paths(settings, data_base_dir=data_base_dir, output_base_dir=output_base_dir)

    if output_dir is not None:
        settings["output_dir"] = str(Path(output_dir).expanduser().resolve())
    if max_num_threads is not None:
        settings["max_num_threads"] = int(max_num_threads)
    if run_info_file is not None:
        settings["run_info_file"] = str(Path(run_info_file).expanduser().resolve())
    if run_info_netcdf is not None:
        settings["run_info_netcdf"] = str(Path(run_info_netcdf).expanduser().resolve())

    if settings.get("run_info_file"):
        settings = apply_run_info(settings)
    if settings.get("run_info_netcdf"):
        reference_time = read_netcdf_reference_time(Path(settings["run_info_netcdf"]))
        settings["reference_time"] = reference_time

    return SettingsBundle(settings=settings, settings_path=settings_path)


def get_source_config(settings: Dict[str, Any], data_source: str, model: Optional[str] = None) -> Dict[str, Any]:
    source = settings.get(data_source)
    if source is None:
        raise KeyError(f"Unknown data source: {data_source}")
    if model is None:
        return source
    if model not in source:
        raise KeyError(f"Unknown model '{model}' for {data_source}")
    return source[model]
