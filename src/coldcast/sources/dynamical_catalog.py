from __future__ import annotations

import datetime as dt
import json
import logging
import numbers
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import xarray as xr

from ..bounding_box import geographic_lon_lat_bounds, resolve_merged_geographic_bbox
from ..download import DownloadRequest
from ..url_templates import render_template

logger = logging.getLogger("coldcast.dynamical_catalog")


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    """Dynamical catalog datasets are opened through xarray, not URL requests."""
    return []


def _normalize_lon(values: np.ndarray) -> np.ndarray:
    return (np.asarray(values, dtype=np.float64) + 180.0) % 360.0 - 180.0


def _lon_mask(lon: np.ndarray, *, lon_min: float, lon_max: float) -> np.ndarray:
    lon_cmp = np.asarray(lon, dtype=np.float64)
    if lon_min < 0 or lon_max < 0:
        lon_cmp = _normalize_lon(lon_cmp)
    if lon_min <= lon_max:
        return (lon_cmp >= lon_min) & (lon_cmp <= lon_max)
    return (lon_cmp >= lon_min) | (lon_cmp <= lon_max)


def _find_lat_lon_names(ds: xr.Dataset) -> Tuple[str, str]:
    lat_name = next((name for name in ("latitude", "lat") if name in ds.variables), None)
    lon_name = next((name for name in ("longitude", "lon") if name in ds.variables), None)
    if lat_name is None or lon_name is None:
        raise ValueError("Dataset must contain latitude/longitude or lat/lon coordinates for bbox clipping.")
    return lat_name, lon_name


def _contiguous_slice(indices: np.ndarray) -> slice:
    return slice(int(indices[0]), int(indices[-1]) + 1)


def clip_to_bbox(ds: xr.Dataset, bbox: Mapping[str, object]) -> xr.Dataset:
    """Clip either 1D lat/lon grids or projected grids with 2D lat/lon coordinates."""
    lon_min, lon_max, lat_min, lat_max = geographic_lon_lat_bounds(bbox)
    lat_name, lon_name = _find_lat_lon_names(ds)
    lat = ds[lat_name]
    lon = ds[lon_name]

    if lat.ndim == 1 and lon.ndim == 1:
        lat_mask = (np.asarray(lat.values, dtype=np.float64) >= lat_min) & (
            np.asarray(lat.values, dtype=np.float64) <= lat_max
        )
        lon_mask = _lon_mask(lon.values, lon_min=lon_min, lon_max=lon_max)
        if not np.any(lat_mask) or not np.any(lon_mask):
            raise ValueError(
                "DYNAMICAL_CATALOG bbox does not intersect the grid "
                f"(lon [{lon_min}, {lon_max}], lat [{lat_min}, {lat_max}])."
            )
        lat_indices = np.where(lat_mask)[0]
        lon_indices = np.where(lon_mask)[0]
        return ds.isel({lat.dims[0]: _contiguous_slice(lat_indices), lon.dims[0]: _contiguous_slice(lon_indices)})

    if lat.ndim == 2 and lon.ndim == 2 and lat.dims == lon.dims:
        lat_values = np.asarray(lat.values, dtype=np.float64)
        mask = (
            (lat_values >= lat_min)
            & (lat_values <= lat_max)
            & _lon_mask(lon.values, lon_min=lon_min, lon_max=lon_max)
        )
        if not np.any(mask):
            raise ValueError(
                "DYNAMICAL_CATALOG bbox does not intersect the projected grid "
                f"(lon [{lon_min}, {lon_max}], lat [{lat_min}, {lat_max}])."
            )
        rows = np.where(np.any(mask, axis=1))[0]
        cols = np.where(np.any(mask, axis=0))[0]
        return ds.isel({lat.dims[0]: _contiguous_slice(rows), lat.dims[1]: _contiguous_slice(cols)})

    raise ValueError("Unsupported latitude/longitude layout; expected both 1D or matching 2D coordinates.")


def _as_utc_naive(value: object) -> dt.datetime:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("Invalid datetime value.")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def select_forecast_run(
    ds: xr.Dataset,
    *,
    reference_time: dt.datetime,
    delay_hours: float,
    method: str = "pad",
    max_run_age_hours: Optional[float] = None,
) -> Tuple[xr.Dataset, dt.datetime]:
    """Select the latest available forecast run at or before reference_time - delay."""
    if "init_time" not in ds.coords and "init_time" not in ds.variables:
        raise ValueError("Dynamical catalog forecast datasets must contain an init_time coordinate.")

    reference_time = _as_utc_naive(reference_time)
    cutoff = reference_time - dt.timedelta(hours=delay_hours)
    selector = {"init_time": np.datetime64(cutoff.replace(tzinfo=None))}
    selection_method = None if method.lower() in ("", "exact", "none") else method
    selected = ds["init_time"].sel(selector, method=selection_method)
    selected_value = np.asarray(selected.values).reshape(-1)[0]
    selected_time = _as_utc_naive(selected_value)

    if max_run_age_hours is not None:
        age = cutoff - selected_time
        if age > dt.timedelta(hours=float(max_run_age_hours)):
            raise ValueError(
                "Selected dynamical catalog run is older than max_run_age_hours "
                f"({selected_time.isoformat()} vs cutoff {cutoff.isoformat()})."
            )

    out = ds.sel(init_time=selected_value)
    out = out.assign_coords(forecast_reference_time=np.datetime64(selected_time))
    out["forecast_reference_time"].attrs.update(
        {
            "standard_name": "forecast_reference_time",
            "long_name": "forecast reference time",
        }
    )
    if "init_time" in out.coords or "init_time" in out.data_vars:
        out = out.drop_vars("init_time")
    return out, selected_time


def _drop_vars_if_present(ds: xr.Dataset, names: Sequence[str]) -> xr.Dataset:
    present = [name for name in names if name in ds.variables]
    return ds.drop_vars(present) if present else ds


def promote_valid_time(ds: xr.Dataset) -> xr.Dataset:
    """Use valid forecast time as the primary CF/FEWS time axis."""
    if "valid_time" in ds.variables:
        valid_time = ds["valid_time"]
        if "lead_time" in valid_time.dims:
            ds = ds.assign_coords(time=("lead_time", np.asarray(valid_time.values)))
            ds["time"].attrs.update({"standard_name": "time", "axis": "T"})
            ds = ds.swap_dims({"lead_time": "time"})
            ds = _drop_vars_if_present(ds, ["valid_time"])
            return ds

    if "lead_time" in ds.dims and "forecast_reference_time" in ds.coords:
        lead = ds["lead_time"].values
        ref = np.asarray(ds["forecast_reference_time"].values)
        ds = ds.assign_coords(time=("lead_time", ref + lead))
        ds["time"].attrs.update({"standard_name": "time", "axis": "T"})
        ds = ds.swap_dims({"lead_time": "time"})
    elif "time" in ds.coords:
        ds["time"].attrs.setdefault("standard_name", "time")
        ds["time"].attrs.setdefault("axis", "T")
    return ds


def select_variables(ds: xr.Dataset, variables: Sequence[object]) -> xr.Dataset:
    if not variables:
        return ds

    rename_map: Dict[str, str] = {}
    selected: List[str] = []
    attr_updates: Dict[str, Mapping[str, object]] = {}
    for entry in variables:
        if isinstance(entry, str):
            source_name = entry
            output_name = entry
            attrs: Mapping[str, object] = {}
        elif isinstance(entry, Mapping):
            source_name = str(entry.get("source") or entry.get("name") or "")
            output_name = str(entry.get("name") or source_name)
            attrs = {
                key: entry[key]
                for key in ("standard_name", "long_name", "units")
                if key in entry and entry[key] is not None
            }
        else:
            raise ValueError(f"Invalid DYNAMICAL_CATALOG variable entry: {entry!r}")

        if not source_name:
            raise ValueError("DYNAMICAL_CATALOG variable entries require source or name.")
        if source_name not in ds.data_vars:
            raise KeyError(f"Dynamical catalog variable {source_name!r} not found in dataset.")

        selected.append(source_name)
        if output_name != source_name:
            rename_map[source_name] = output_name
        if attrs:
            attr_updates[output_name] = attrs

    out = ds[selected]
    if rename_map:
        out = out.rename(rename_map)
    for name, attrs in attr_updates.items():
        out[name].attrs.update({str(key): value for key, value in attrs.items()})
    return out


def _lead_time_hours(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values)
    if np.issubdtype(values.dtype, np.timedelta64):
        return values / np.timedelta64(1, "h")
    return values.astype(np.float64)


def _lead_time_bounds(cfg: Mapping[str, object]) -> Tuple[Optional[float], Optional[float]]:
    spec = cfg.get("lead_time_hours")
    if spec is None:
        max_lead = cfg.get("max_lead_time_hours")
        return None, float(max_lead) if max_lead is not None else None

    if isinstance(spec, Mapping):
        start = spec.get("start", spec.get("min"))
        end = spec.get("end", spec.get("max"))
        return (
            float(start) if start is not None else None,
            float(end) if end is not None else None,
        )

    return None, float(spec)


def select_lead_times(ds: xr.Dataset, cfg: Mapping[str, object]) -> xr.Dataset:
    """Subset lead_time hours before remote chunks are materialized."""
    start_hour, end_hour = _lead_time_bounds(cfg)
    if start_hour is None and end_hour is None:
        return ds
    if "lead_time" not in ds.variables:
        raise ValueError("DYNAMICAL_CATALOG lead_time_hours requires a lead_time coordinate.")

    lead = ds["lead_time"]
    if lead.ndim != 1:
        raise ValueError("DYNAMICAL_CATALOG lead_time_hours requires a 1D lead_time coordinate.")

    hours = _lead_time_hours(lead.values)
    mask = np.ones(hours.shape, dtype=bool)
    if start_hour is not None:
        mask &= hours >= start_hour
    if end_hour is not None:
        mask &= hours <= end_hour
    if not np.any(mask):
        raise ValueError(
            "DYNAMICAL_CATALOG lead_time_hours does not intersect available lead_time values."
        )

    indices = np.where(mask)[0]
    return ds.isel({lead.dims[0]: _contiguous_slice(indices)})


def normalize_ensemble(ds: xr.Dataset, ensemble_dimension: Optional[str] = None) -> xr.Dataset:
    candidates = [ensemble_dimension] if ensemble_dimension else ["ensemble_member", "member", "number"]
    source_dim = next((name for name in candidates if name and (name in ds.dims or name in ds.coords)), None)
    if source_dim and source_dim != "realization":
        ds = ds.rename({source_dim: "realization"})
    if "realization" in ds.coords:
        ds["realization"].attrs.update(
            {
                "standard_name": "realization",
                "long_name": "ensemble member",
            }
        )
    return ds


def apply_cf_metadata(ds: xr.Dataset) -> xr.Dataset:
    out = ds.copy()
    out.attrs["Conventions"] = "CF-1.8"
    out.attrs.setdefault("title", "Coldcast dynamical catalog forecast")
    stamp = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    line = f"{stamp} coldcast: dynamical catalog FEWS NetCDF export."
    previous = str(out.attrs.get("history", "")).strip()
    out.attrs["history"] = line if not previous or previous == "--" else f"{previous}\n{line}"

    coord_attrs = {
        "latitude": {"standard_name": "latitude", "units": "degrees_north", "axis": "Y"},
        "lat": {"standard_name": "latitude", "units": "degrees_north", "axis": "Y"},
        "longitude": {"standard_name": "longitude", "units": "degrees_east", "axis": "X"},
        "lon": {"standard_name": "longitude", "units": "degrees_east", "axis": "X"},
        "time": {"standard_name": "time", "axis": "T"},
        "realization": {"standard_name": "realization", "long_name": "ensemble member"},
        "spatial_ref": {"long_name": "coordinate reference system"},
    }
    for name, attrs in coord_attrs.items():
        if name in out.variables:
            for key, value in attrs.items():
                out[name].attrs.setdefault(key, value)
    out = _sanitize_coordinates_attrs(out)
    return sanitize_netcdf_attrs(out)


def _sanitize_coordinates_attrs(ds: xr.Dataset) -> xr.Dataset:
    out = ds.copy()
    variables = set(out.variables)
    for name in out.variables:
        coordinates = " ".join(
            value
            for value in (
                out[name].attrs.get("coordinates"),
                out[name].encoding.get("coordinates"),
            )
            if isinstance(value, str)
        )
        sanitized = _sanitize_coordinates_value(coordinates, variables=variables, dims=set(out[name].dims))
        if sanitized is None:
            out[name].attrs.pop("coordinates", None)
        else:
            out[name].attrs["coordinates"] = sanitized
        out[name].encoding.pop("coordinates", None)
    return out


def _sanitize_coordinates_value(
    coordinates: object,
    *,
    variables: set[str],
    dims: set[str],
) -> Optional[str]:
    if not isinstance(coordinates, str):
        return None
    names: List[str] = []
    for coord_name in coordinates.split():
        if coord_name == "valid_time" and "time" in variables:
            coord_name = "time"
        if coord_name in variables and coord_name not in dims and coord_name not in names:
            names.append(coord_name)
    return " ".join(names) if names else None


def _netcdf_safe_attr_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (str, bytes, numbers.Number, np.ndarray)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp, np.datetime64, np.timedelta64)):
        return str(value)
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, (list, tuple)):
        if all(isinstance(item, (str, bytes, numbers.Number, np.generic)) for item in value):
            return value
        return json.dumps(value, default=str)
    return str(value)


def _sanitize_attrs(attrs: Mapping[object, object]) -> Dict[str, object]:
    safe: Dict[str, object] = {}
    for key, value in attrs.items():
        safe_value = _netcdf_safe_attr_value(value)
        if safe_value is not None:
            safe[str(key)] = safe_value
    return safe


def sanitize_netcdf_attrs(ds: xr.Dataset) -> xr.Dataset:
    """Convert rich catalog metadata attrs into NetCDF-serializable values."""
    out = ds.copy()
    out.attrs = _sanitize_attrs(out.attrs)
    for name in out.variables:
        out[name].attrs = _sanitize_attrs(out[name].attrs)
    return out


def prepare_fews_dataset(
    ds: xr.Dataset,
    cfg: Mapping[str, object],
    *,
    reference_time: dt.datetime,
    settings: Optional[Mapping[str, object]] = None,
) -> Tuple[xr.Dataset, dt.datetime]:
    selected, run_time = select_forecast_run(
        ds,
        reference_time=reference_time,
        delay_hours=float(cfg.get("delay_hours", 0)),
        method=str(cfg.get("forecast_selection", "pad")),
        max_run_age_hours=(
            float(cfg["max_run_age_hours"]) if cfg.get("max_run_age_hours") is not None else None
        ),
    )
    selected = select_lead_times(selected, cfg)
    out = select_variables(selected, cfg.get("variables", []))
    out = promote_valid_time(out)
    merged = resolve_merged_geographic_bbox(settings or {}, cfg.get("bbox"))
    if merged:
        out = clip_to_bbox(out, merged)
    out = normalize_ensemble(out, ensemble_dimension=cfg.get("ensemble_dimension"))
    return apply_cf_metadata(out), run_time


def _output_path(output_dir: object, cfg: Mapping[str, object], *, model: str, run_time: dt.datetime) -> Path:
    dataset_id = str(cfg["dataset_id"])
    template = str(
        cfg.get("output_filename_template")
        or "dynamical_{model}_{run_time:%Y%m%d%H%M}.nc"
    )
    filename = render_template(
        template,
        {
            "model": model,
            "dataset_id": dataset_id.replace("/", "_"),
            "run_time": run_time,
        },
    )
    if not filename.endswith(".nc"):
        filename = f"{filename}.nc"
    return Path(str(output_dir)).expanduser() / filename


def _can_encode_int32(values: np.ndarray) -> bool:
    if values.size == 0:
        return True
    info = np.iinfo(np.int32)
    return bool(np.nanmin(values) >= info.min and np.nanmax(values) <= info.max)


def _netcdf_encoding(ds: xr.Dataset, cfg: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    compression = cfg.get("compression", True)
    encoding: Dict[str, Dict[str, object]] = {}
    if isinstance(compression, Mapping):
        defaults = dict(compression)
    elif compression:
        defaults = {"zlib": True, "complevel": 4}
    else:
        defaults = {}

    if defaults:
        encoding.update(
            {
                name: dict(defaults)
                for name in ds.data_vars
                if ds[name].ndim > 0 and name != "spatial_ref"
            }
        )

    for name in ds.variables:
        dtype = ds[name].dtype
        var_encoding = encoding.setdefault(name, {})
        if np.issubdtype(dtype, np.datetime64):
            var_encoding.setdefault("dtype", "float64")
            var_encoding.setdefault("units", "hours since 1970-01-01 00:00:00")
            var_encoding.setdefault("calendar", "proleptic_gregorian")
        elif np.issubdtype(dtype, np.timedelta64):
            var_encoding.setdefault("dtype", "float64")
            var_encoding.setdefault("units", "hours")
        elif dtype == np.dtype("int64"):
            values = np.asarray(ds[name].values)
            if not _can_encode_int32(values):
                raise ValueError(f"Cannot encode {name!r} as int32 without overflow.")
            var_encoding.setdefault("dtype", "int32")

        if not var_encoding:
            encoding.pop(name, None)

    return encoding


# CLI shorthand and case-insensitive lookups for ``coldcast download dynamical_catalog --model``.
_NON_MODEL_BLOCKS = frozenset({"default_model"})
_DYNAMICAL_MODEL_ALIASES = {"IFS": "ECMWF_IFS_ENS"}


def resolve_dynamical_catalog_model_key(source: Mapping[str, object], model: str) -> str:
    """
    Map ``--model`` to a configured block under ``DYNAMICAL_CATALOG``.

    * ``IFS`` → ``ECMWF_IFS_ENS`` (dynamical.org ECMWF IFS ENS).
    * Model keys are matched case-insensitively (e.g. ``gefs`` → ``GEFS``).
    """
    raw = str(model).strip()
    if not raw:
        raise ValueError("DYNAMICAL_CATALOG model name must be non-empty.")
    upper = raw.upper()
    if upper in _DYNAMICAL_MODEL_ALIASES:
        canonical = _DYNAMICAL_MODEL_ALIASES[upper]
        target = source.get(canonical)
        if isinstance(target, Mapping):
            return canonical
        raise KeyError(
            f"Unknown DYNAMICAL_CATALOG model {raw!r}: expected a '{canonical}' block in settings."
        )
    if raw not in _NON_MODEL_BLOCKS and raw in source and isinstance(source[raw], Mapping):
        return raw
    for key in source:
        if key in _NON_MODEL_BLOCKS:
            continue
        if not isinstance(source[key], Mapping):
            continue
        if str(key).upper() == upper:
            return str(key)
    raise KeyError(f"Unknown DYNAMICAL_CATALOG model {raw!r}.")


def _model_config(settings: Mapping[str, object], data_source: str, model: Optional[str]) -> Tuple[str, Mapping[str, object]]:
    source = settings[data_source]
    if not isinstance(source, Mapping):
        raise ValueError(f"{data_source} settings must be a mapping.")
    if model is not None:
        selected_model = resolve_dynamical_catalog_model_key(source, model)
    else:
        default_key = source.get("default_model")
        if not default_key:
            raise ValueError(f"{data_source} requires default_model or --model.")
        selected_model = resolve_dynamical_catalog_model_key(source, str(default_key))
    if selected_model not in source or not isinstance(source[selected_model], Mapping):
        raise KeyError(f"Unknown {data_source} model {selected_model!r}.")
    return selected_model, source[selected_model]


def download(settings: Dict[str, object], data_source: str = "DYNAMICAL_CATALOG", model: Optional[str] = None) -> None:
    try:
        import dynamical_catalog as catalog
    except ImportError as exc:
        raise RuntimeError(
            "DYNAMICAL_CATALOG requires dynamical-catalog. Install it in a Python >=3.12 environment."
        ) from exc

    selected_model, cfg = _model_config(settings, data_source, model)
    identifier = cfg.get("identifier") or settings.get("dynamical_catalog_identifier")
    if identifier:
        catalog.identify(str(identifier))

    reference_time = settings.get("reference_time") or dt.datetime.utcnow()
    dataset_id = str(cfg["dataset_id"])
    open_kwargs = cfg.get("xr_open_kwargs", {})
    if not isinstance(open_kwargs, Mapping):
        raise ValueError("DYNAMICAL_CATALOG xr_open_kwargs must be a mapping.")
    open_kwargs = dict(open_kwargs)
    open_kwargs.setdefault("chunks", None)

    logger.info("Opening dynamical catalog dataset %s", dataset_id)
    ds = catalog.open(dataset_id, **open_kwargs)
    try:
        out, run_time = prepare_fews_dataset(
            ds, cfg, reference_time=reference_time, settings=settings
        )
        path = _output_path(settings["output_dir"], cfg, model=selected_model, run_time=run_time)
        if path.exists():
            logger.info("Dynamical catalog output exists, skipping: %s", path)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_netcdf(path, encoding=_netcdf_encoding(out, cfg))
        logger.info("Wrote dynamical catalog FEWS NetCDF %s", path)
    finally:
        ds.close()
