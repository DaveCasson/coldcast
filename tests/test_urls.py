import os
from urllib.parse import urlparse

import pytest
import requests

from coldcast.settings import load_settings
from coldcast.sources import SOURCES


NETWORK_ENV = "COLDCAST_RUN_NETWORK_TESTS"
URL_SOURCES = [
    "NOAA_HRRR",
    "NOAA_GFS",
    "NOAA_GEFS",
    "ECCC_NWP",
    "ECCC_PRECIP_GRID",
    "ECCC_RADAR",
    "ECCC_API",
    "SNOTEL",
    "SNOWCAST",
    "GLOBSNOW",
    "SNODAS",
    "ERA5",
    "ERA5_LAND",
    "ECMWF_NWP",
]


def _assert_valid_url(url: str) -> None:
    parsed = urlparse(url)
    assert parsed.scheme in ("http", "https")
    assert parsed.netloc
    assert parsed.path


@pytest.mark.parametrize("data_source", URL_SOURCES)
def test_source_builds_sample_url(data_source):
    bundle = load_settings()
    settings = bundle.settings
    requests_list = SOURCES[data_source](settings)
    if not requests_list:
        pytest.skip(f"{data_source} does not expose URLs to test")
    sample = requests_list[0]
    _assert_valid_url(sample.url)
    assert sample.filename


def _network_enabled() -> bool:
    return os.getenv(NETWORK_ENV, "") == "1"


def _check_url(req):
    try:
        response = requests.head(req.url, auth=req.auth, allow_redirects=True, timeout=15)
        if response.status_code == 405 or response.status_code >= 400:
            response = requests.get(req.url, auth=req.auth, stream=True, timeout=20)
        status = response.status_code
        length = response.headers.get("Content-Length")
        return status, length
    finally:
        try:
            response.close()
        except Exception:
            pass


@pytest.mark.network
@pytest.mark.parametrize("data_source", URL_SOURCES)
def test_source_url_has_downloadable_content(data_source):
    if not _network_enabled():
        pytest.skip(f"Set {NETWORK_ENV}=1 to enable network tests.")

    bundle = load_settings()
    settings = bundle.settings

    if data_source == "ECCC_RADAR" and not settings["ECCC_RADAR"].get("username"):
        pytest.skip("ECCC_RADAR requires credentials.")

    requests_list = SOURCES[data_source](settings)
    assert requests_list, f"No download requests produced for {data_source}"

    req = requests_list[-1]
    status, length = _check_url(req)
    assert status < 400, f"{data_source} URL returned status {status}: {req.url}"

    if length is not None:
        assert int(length) > 0, f"{data_source} response has zero length: {req.url}"
