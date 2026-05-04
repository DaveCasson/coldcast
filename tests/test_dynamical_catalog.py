from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from coldcast.sources import dynamical_catalog


def _valid_time(init_times: np.ndarray, lead_time: np.ndarray) -> np.ndarray:
    return init_times[:, None] + lead_time[None, :]


def _regular_ensemble_dataset() -> xr.Dataset:
    init_times = np.array(["2026-04-29T00:00:00", "2026-04-29T06:00:00"], dtype="datetime64[ns]")
    lead_time = np.array([0, 3], dtype="timedelta64[h]")
    data = np.arange(2 * 2 * 2 * 4 * 5, dtype=np.float32).reshape(2, 2, 2, 4, 5)
    ds = xr.Dataset(
        data_vars={
            "precipitation_surface": (
                ("init_time", "ensemble_member", "lead_time", "latitude", "longitude"),
                data,
                {
                    "units": "kg m-2 s-1",
                    "coordinates": "valid_time spatial_ref ingested_forecast_length expected_forecast_length",
                },
            )
        },
        coords={
            "init_time": init_times,
            "ensemble_member": np.array([0, 1], dtype=np.int32),
            "lead_time": (
                "lead_time",
                lead_time,
                {"statistics_approximate": {"min": "0 days 00:00:00", "max": "35 days 00:00:00"}},
            ),
            "valid_time": (("init_time", "lead_time"), _valid_time(init_times, lead_time)),
            "latitude": np.array([53.0, 52.0, 51.0, 50.0], dtype=np.float32),
            "longitude": np.array([-171.0, -170.0, -169.0, -168.0, -167.0], dtype=np.float32),
            "spatial_ref": ((), np.int64(0), {"grid_mapping_name": "latitude_longitude"}),
            "ingested_forecast_length": ((), np.int64(3)),
            "expected_forecast_length": ((), np.int64(3)),
        },
    )
    ds["precipitation_surface"].encoding["coordinates"] = (
        "valid_time spatial_ref ingested_forecast_length expected_forecast_length"
    )
    return ds


def _projected_dataset() -> xr.Dataset:
    init_times = np.array(["2026-04-29T00:00:00", "2026-04-29T06:00:00"], dtype="datetime64[ns]")
    lead_time = np.array([0, 1], dtype="timedelta64[h]")
    y = np.arange(5)
    x = np.arange(6)
    lat_2d, lon_2d = np.meshgrid(
        np.linspace(49.0, 53.0, len(y)),
        np.linspace(-171.0, -166.0, len(x)),
        indexing="ij",
    )
    data = np.zeros((2, 2, len(y), len(x)), dtype=np.float32)
    ds = xr.Dataset(
        data_vars={
            "temperature_2m": (
                ("init_time", "lead_time", "y", "x"),
                data,
                {"units": "degree_Celsius", "coordinates": "valid_time latitude longitude"},
            )
        },
        coords={
            "init_time": init_times,
            "lead_time": lead_time,
            "valid_time": (("init_time", "lead_time"), _valid_time(init_times, lead_time)),
            "y": y,
            "x": x,
            "latitude": (("y", "x"), lat_2d.astype(np.float32)),
            "longitude": (("y", "x"), lon_2d.astype(np.float32)),
        },
    )
    ds["temperature_2m"].encoding["coordinates"] = "valid_time latitude longitude"
    return ds


def _cfg() -> dict:
    return {
        "dataset_id": "noaa-gefs-forecast-35-day",
        "delay_hours": 6,
        "forecast_selection": "pad",
        "max_run_age_hours": 24,
        "bbox": {"lon_min": -170.5, "lon_max": -168.5, "lat_min": 50.5, "lat_max": 52.5},
        "variables": [
            {
                "source": "precipitation_surface",
                "name": "precipitation_flux",
                "standard_name": "precipitation_flux",
                "units": "kg m-2 s-1",
            }
        ],
    }


def test_prepare_fews_dataset_selects_run_from_reference_minus_delay() -> None:
    ds = _regular_ensemble_dataset()
    out, run_time = dynamical_catalog.prepare_fews_dataset(
        ds,
        _cfg(),
        reference_time=datetime(2026, 4, 29, 13, 0),
    )

    assert run_time == datetime(2026, 4, 29, 6, 0)
    assert "precipitation_flux" in out.data_vars
    assert "precipitation_surface" not in out.data_vars
    assert "realization" in out.dims
    assert out["realization"].attrs["standard_name"] == "realization"
    assert "time" in out.dims
    assert "lead_time" not in out.dims
    assert out.sizes["latitude"] == 2
    assert out.sizes["longitude"] == 2
    assert out.attrs["Conventions"] == "CF-1.8"
    assert out.attrs["title"]
    assert out["precipitation_flux"].attrs["standard_name"] == "precipitation_flux"
    assert "valid_time" not in out["precipitation_flux"].attrs.get("coordinates", "")
    assert "valid_time" not in out["precipitation_flux"].encoding.get("coordinates", "")
    assert out["spatial_ref"].attrs["long_name"] == "coordinate reference system"
    assert out["lead_time"].attrs["statistics_approximate"] == (
        '{"max": "35 days 00:00:00", "min": "0 days 00:00:00"}'
    )


def test_prepare_fews_dataset_limits_lead_times_from_config() -> None:
    cfg = {**_cfg(), "lead_time_hours": {"start": 0, "end": 0}}

    out, run_time = dynamical_catalog.prepare_fews_dataset(
        _regular_ensemble_dataset(),
        cfg,
        reference_time=datetime(2026, 4, 29, 13, 0),
    )

    assert run_time == datetime(2026, 4, 29, 6, 0)
    assert out.sizes["time"] == 1
    assert out["time"].values[0] == np.datetime64("2026-04-29T06:00:00")


def test_prepare_fews_dataset_uses_global_settings_bbox_when_model_omits_bbox() -> None:
    cfg = dict(_cfg())
    del cfg["bbox"]
    settings = {"bounding_box": {"lon_min": -170.5, "lon_max": -168.5, "lat_min": 50.5, "lat_max": 52.5}}
    out, run_time = dynamical_catalog.prepare_fews_dataset(
        _regular_ensemble_dataset(),
        cfg,
        reference_time=datetime(2026, 4, 29, 13, 0),
        settings=settings,
    )
    assert run_time == datetime(2026, 4, 29, 6, 0)
    assert out.sizes["latitude"] == 2
    assert out.sizes["longitude"] == 2


def test_select_lead_times_accepts_scalar_max_hours() -> None:
    out = dynamical_catalog.select_lead_times(_regular_ensemble_dataset(), {"lead_time_hours": 0})

    assert out.sizes["lead_time"] == 1
    assert out["lead_time"].values[0] == np.timedelta64(0, "h")


def test_prepare_fews_dataset_clips_projected_2d_lat_lon_grid() -> None:
    cfg = {
        "dataset_id": "noaa-hrrr-forecast-48-hour",
        "delay_hours": 6,
        "bbox": {"lon_min": -170.2, "lon_max": -168.2, "lat_min": 50.2, "lat_max": 52.2},
        "variables": [{"source": "temperature_2m", "name": "air_temperature"}],
    }

    out, run_time = dynamical_catalog.prepare_fews_dataset(
        _projected_dataset(),
        cfg,
        reference_time=datetime(2026, 4, 29, 13, 0),
    )

    assert run_time == datetime(2026, 4, 29, 6, 0)
    assert "air_temperature" in out.data_vars
    assert out.sizes["y"] < 5
    assert out.sizes["x"] < 6
    assert out["latitude"].ndim == 2
    assert out["longitude"].ndim == 2
    assert "valid_time" not in out["air_temperature"].attrs.get("coordinates", "")
    assert "valid_time" not in out["air_temperature"].encoding.get("coordinates", "")


def test_clip_to_bbox_raises_when_bbox_misses_grid() -> None:
    with pytest.raises(ValueError, match="does not intersect"):
        dynamical_catalog.clip_to_bbox(
            _regular_ensemble_dataset(),
            {"lon_min": -20.0, "lon_max": -10.0, "lat_min": 10.0, "lat_max": 20.0},
        )


def test_download_writes_single_cf_netcdf_with_mocked_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    open_calls = []

    def open_dataset(dataset_id: str, **kwargs: object) -> xr.Dataset:
        open_calls.append((dataset_id, kwargs))
        return _regular_ensemble_dataset()

    fake_catalog = types.SimpleNamespace(
        identify=lambda value: None,
        open=open_dataset,
    )
    monkeypatch.setitem(sys.modules, "dynamical_catalog", fake_catalog)

    settings = {
        "output_dir": str(tmp_path),
        "reference_time": datetime(2026, 4, 29, 13, 0),
        "DYNAMICAL_CATALOG": {
            "default_model": "GEFS",
            "GEFS": {
                **_cfg(),
                "output_filename_template": "gefs_{run_time:%Y%m%d%H%M}.nc",
                "compression": False,
            },
        },
    }

    dynamical_catalog.download(settings, data_source="DYNAMICAL_CATALOG")

    assert open_calls == [("noaa-gefs-forecast-35-day", {"chunks": None})]
    output = tmp_path / "gefs_202604290600.nc"
    assert output.is_file()
    with xr.open_dataset(output) as ds:
        assert ds.attrs["Conventions"] == "CF-1.8"
        assert ds.attrs["title"]
        assert "precipitation_flux" in ds.data_vars
        assert "realization" in ds.dims
        assert ds["realization"].attrs["standard_name"] == "realization"
        assert "valid_time" not in ds["precipitation_flux"].attrs.get("coordinates", "")
        assert ds["spatial_ref"].attrs["long_name"] == "coordinate reference system"

    netcdf4 = pytest.importorskip("netCDF4")
    with netcdf4.Dataset(output) as ds:
        coordinates = getattr(ds.variables["precipitation_flux"], "coordinates", "")
        assert "valid_time" not in coordinates
        for name in (
            "ingested_forecast_length",
            "expected_forecast_length",
            "lead_time",
            "spatial_ref",
            "forecast_reference_time",
            "time",
        ):
            assert ds.variables[name].dtype != np.dtype("int64")


def _minimal_catalog_source() -> dict:
    return {
        "default_model": "GEFS",
        "GEFS": {"dataset_id": "noaa-gfs"},
        "ECMWF_IFS_ENS": {"dataset_id": "ecmwf-ifs-ens-forecast-15-day-0-25-degree"},
    }


def test_resolve_dynamical_catalog_model_key_ifs_alias() -> None:
    src = _minimal_catalog_source()
    assert dynamical_catalog.resolve_dynamical_catalog_model_key(src, "IFS") == "ECMWF_IFS_ENS"
    assert dynamical_catalog.resolve_dynamical_catalog_model_key(src, "ifs") == "ECMWF_IFS_ENS"


def test_resolve_dynamical_catalog_model_key_gefs_case_insensitive() -> None:
    src = _minimal_catalog_source()
    assert dynamical_catalog.resolve_dynamical_catalog_model_key(src, "gefs") == "GEFS"
    assert dynamical_catalog.resolve_dynamical_catalog_model_key(src, "GEFS") == "GEFS"


def test_model_config_accepts_default_model_ifs_alias() -> None:
    source = {
        **_minimal_catalog_source(),
        "default_model": "IFS",
    }
    selected, cfg = dynamical_catalog._model_config(
        {"DYNAMICAL_CATALOG": source},
        "DYNAMICAL_CATALOG",
        None,
    )
    assert selected == "ECMWF_IFS_ENS"
    assert cfg["dataset_id"] == "ecmwf-ifs-ens-forecast-15-day-0-25-degree"


def test_model_config_accepts_cli_model_gefs_mixed_case() -> None:
    selected, _ = dynamical_catalog._model_config(
        {"DYNAMICAL_CATALOG": _minimal_catalog_source()},
        "DYNAMICAL_CATALOG",
        "gefs",
    )
    assert selected == "GEFS"
