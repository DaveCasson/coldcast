"""Tests for FEWS runinfo netCDF reference time (``time0``)."""

from datetime import datetime
from pathlib import Path

import netCDF4 as nc

from coldcast.run_info import read_netcdf_reference_time


def _write_fews_like_runinfo(path: Path) -> None:
    with nc.Dataset(path, "w") as ds:
        t0 = ds.createVariable("time0", "f8", ())
        t0.units = "minutes since 2026-01-16 15:00:00.0 +0000"
        t0.standard_name = "time"
        t0[:] = 120.0

        st = ds.createVariable("start_time", "f8", ())
        st.units = "minutes since 2026-01-16 15:00:00.0 +0000"
        st[:] = 0.0

        et = ds.createVariable("end_time", "f8", ())
        et.units = "minutes since 2026-01-16 15:00:00.0 +0000"
        et[:] = 300.0


def test_read_netcdf_reference_time_prefers_time0(tmp_path: Path) -> None:
    path = tmp_path / "runinfo.nc"
    _write_fews_like_runinfo(path)
    out = read_netcdf_reference_time(path)
    assert out == datetime(2026, 1, 16, 17, 0, 0)


def test_read_netcdf_fallback_named_time(tmp_path: Path) -> None:
    path = tmp_path / "legacy.nc"
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("time", 1)
        tv = ds.createVariable("time", "f8", ("time",))
        tv.units = "hours since 2020-06-01 00:00:00"
        tv[:] = [3.0]
    out = read_netcdf_reference_time(path)
    assert out == datetime(2020, 6, 1, 3, 0, 0)
