from __future__ import annotations

import datetime as dt

import pytest

from coldcast.settings import load_settings
from coldcast.sources.eccc_precip_grid import build_requests


@pytest.mark.parametrize(
    "model,day_str,filename_part",
    [
        (
            "HREPA",
            "20260413",
            "20260413T00Z_MSC_HREPA_Precip-Accum06h_Sfc_RLatLon0.0225_PT0H.nc",
        ),
        (
            "HREPA_PCT25",
            "20260406",
            "20260406T00Z_MSC_HREPA_Precip-Accum06h-Pct25_Sfc_RLatLon0.0225_PT0H.nc",
        ),
        (
            "HREPA_PCT75",
            "20260406",
            "20260406T00Z_MSC_HREPA_Precip-Accum06h-Pct75_Sfc_RLatLon0.0225_PT0H.nc",
        ),
    ],
)
def test_hrepa_first_url(model: str, day_str: str, filename_part: str) -> None:
    bundle = load_settings()
    settings = bundle.settings
    settings["reference_time"] = dt.datetime(2026, 4, 14, 12, 0, 0)
    requests_list = build_requests(settings, model=model)
    assert requests_list
    first = requests_list[0]
    assert first.filename == filename_part
    assert first.url == (
        f"https://dd.weather.gc.ca/{day_str}/WXO-DD/model_hrepa/2.5km/00/" + filename_part
    )
