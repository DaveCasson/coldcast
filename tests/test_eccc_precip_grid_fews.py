from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from coldcast.download import DownloadRequest
from coldcast.sources.eccc_precip_grid import (
    clip_rlat_rlon_slices,
    maybe_postprocess_hrepa_fews,
    postprocess_hrepa_netcdf,
)


def _synthetic_hrepa_like() -> xr.Dataset:
    n_rlat, n_rlon = 8, 10
    n_ens, n_time = 2, 1
    rlat = np.linspace(40.0, 60.0, n_rlat)
    rlon = np.linspace(-120.0, -100.0, n_rlon)
    lat_2d, lon_2d = np.meshgrid(np.linspace(45.0, 55.0, n_rlat), np.linspace(-115.0, -105.0, n_rlon), indexing="ij")
    data = np.zeros((n_ens, n_time, n_rlat, n_rlon), dtype=np.float32)
    ds = xr.Dataset(
        data_vars={
            "Precip-Accum06h": (
                ("ensemble", "time", "rlat", "rlon"),
                data,
                {
                    "standard_name": "precipitation_amount",
                    "units": "kg.m-2",
                    "grid_mapping": "rotated_pole",
                },
            ),
            "lat": (("rlat", "rlon"), lat_2d.astype(np.float32)),
            "lon": (("rlat", "rlon"), lon_2d.astype(np.float32)),
        },
        coords={
            "rlat": ("rlat", rlat.astype(np.float32)),
            "rlon": ("rlon", rlon.astype(np.float32)),
            "ensemble": np.arange(n_ens, dtype=np.int32),
            "time": ("time", np.array([0.0]), {"units": "hours since 2026-04-12 18:00:00", "calendar": "gregorian"}),
        },
        attrs={"Conventions": "CF-1.6", "history": "--"},
    )
    ds["rotated_pole"] = xr.DataArray(
        np.array(0, dtype=np.int8),
        attrs={"grid_mapping_name": "rotated_latitude_longitude"},
    )
    return ds


def test_clip_rlat_rlon_slices_reduces_extent() -> None:
    lat = np.array([[40.0, 40.0], [50.0, 50.0], [60.0, 60.0]])
    lon = np.array([[-120.0, -110.0], [-120.0, -110.0], [-120.0, -110.0]])
    rlat_sl, rlon_sl = clip_rlat_rlon_slices(
        lat, lon, lon_min=-121.0, lon_max=-109.0, lat_min=49.0, lat_max=51.0
    )
    assert rlat_sl == slice(1, 2)
    assert rlon_sl == slice(0, 2)


def test_clip_rlat_rlon_slices_empty_raises() -> None:
    lat = np.array([[0.0, 0.0], [1.0, 1.0]])
    lon = np.array([[10.0, 11.0], [10.0, 11.0]])
    with pytest.raises(ValueError, match="does not intersect"):
        clip_rlat_rlon_slices(lat, lon, lon_min=-170.0, lon_max=-160.0, lat_min=50.0, lat_max=55.0)


def test_postprocess_hrepa_netcdf_clip_and_rename(tmp_path: Path) -> None:
    raw = tmp_path / "sample.nc"
    out = tmp_path / "sample_fews.nc"
    _synthetic_hrepa_like().to_netcdf(raw)

    ok = postprocess_hrepa_netcdf(
        raw,
        out,
        {
            "clip_to_bbox": True,
            "clip_bbox": {"lon_min": -112.0, "lon_max": -106.0, "lat_min": 48.0, "lat_max": 52.0},
            "include_confidence_index": False,
            "output_variable_name": "precipitation_amount",
        },
    )
    assert ok is True
    assert out.is_file()

    with xr.open_dataset(out) as ds:
        assert "precipitation_amount" in ds.data_vars
        assert "Precip-Accum06h" not in ds.data_vars
        assert ds.attrs["Conventions"] == "CF-1.8"
        assert "coldcast" in str(ds.attrs.get("history", ""))
        assert ds["precipitation_amount"].attrs["units"] == "kg m-2"
        assert ds.sizes["rlat"] < 8
        assert ds.sizes["rlon"] < 10


def test_postprocess_hrepa_netcdf_skips_existing(tmp_path: Path) -> None:
    raw = tmp_path / "a.nc"
    out = tmp_path / "a_fews.nc"
    _synthetic_hrepa_like().to_netcdf(raw)
    out.write_text("x")
    ok = postprocess_hrepa_netcdf(
        raw,
        out,
        {"clip_to_bbox": False, "include_confidence_index": False},
    )
    assert ok is False


def test_maybe_postprocess_merges_partial_clip_bbox_with_settings(tmp_path: Path) -> None:
    raw_path = tmp_path / "hrepa_raw.nc"
    ds0 = _synthetic_hrepa_like()
    ds0.to_netcdf(raw_path)
    n_rlat_full = int(ds0.sizes["rlat"])
    settings = {
        "bounding_box": {"lon_min": -115.0, "lon_max": -105.0, "lat_min": 45.0, "lat_max": 55.0},
        "ECCC_PRECIP_GRID": {
            "HREPA": {
                "fews_netcdf": {
                    "enabled": True,
                    "clip_to_bbox": True,
                    # Only lat edges: lon bounds come from ``bounding_box``.
                    "clip_bbox": {"lat_min": 51.0, "lat_max": 53.0},
                    "output_suffix": "_glob.nc",
                    "include_confidence_index": False,
                },
            },
        },
    }
    maybe_postprocess_hrepa_fews(
        settings,
        "HREPA",
        [DownloadRequest(url="http://example.invalid/x", filename="hrepa_raw.nc")],
        str(tmp_path),
    )
    merged = tmp_path / "hrepa_raw_glob.nc"
    assert merged.is_file()
    with xr.open_dataset(merged) as ds:
        assert ds.sizes["rlat"] < n_rlat_full
