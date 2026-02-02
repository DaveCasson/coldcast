import sys
import types

import datetime as dt
import pytest

from coldcast.settings import load_settings
from coldcast.sources import era5, ecmwf_nwp


def _patch_cdsapi(monkeypatch):
    clients = []

    class DummyClient:
        def __init__(self):
            self.calls = []

        def retrieve(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    def factory():
        client = DummyClient()
        clients.append(client)
        return client

    monkeypatch.setitem(sys.modules, "cdsapi", types.SimpleNamespace(Client=factory))
    return clients


@pytest.mark.api_client
def test_era5_download_calls_cdsapi(monkeypatch, tmp_path):
    clients = _patch_cdsapi(monkeypatch)
    bundle = load_settings(output_dir=str(tmp_path))
    settings = bundle.settings

    settings["bounding_box"] = [60, -120, 49, -110]
    era5.download(settings, "ERA5")
    assert clients, "cdsapi.Client was never instantiated"
    assert clients[0].calls, "cdsapi.Client.retrieve was not called for ERA5"
    assert clients[0].calls[0][0][0] == "reanalysis-era5-single-levels"


@pytest.mark.api_client
def test_era5_land_download_calls_cdsapi(monkeypatch, tmp_path):
    clients = _patch_cdsapi(monkeypatch)
    bundle = load_settings(output_dir=str(tmp_path))
    settings = bundle.settings

    era5.download(settings, "ERA5_LAND")
    assert clients, "cdsapi.Client was never instantiated"
    assert clients[0].calls, "cdsapi.Client.retrieve was not called for ERA5_LAND"
    assert clients[0].calls[0][0][0] == "reanalysis-era5-land"


@pytest.mark.api_client
def test_ecmwf_nwp_download_uses_client(monkeypatch):
    bundle = load_settings()
    settings = bundle.settings

    retrieved = []

    class DummyLatest:
        def __init__(self):
            self._date = dt.date(2025, 1, 1)
            self.hour = 0

        def date(self):
            return self._date

    class DummyClient:
        def __init__(self):
            self.calls = []

        def latest(self, **kwargs):
            return DummyLatest()

        def retrieve(self, **kwargs):
            retrieved.append(kwargs)

    def factory(*args, **kwargs):
        return DummyClient()

    monkeypatch.setattr(ecmwf_nwp, "Client", factory)
    ecmwf_nwp.download(settings, "ECMWF_NWP")
    assert retrieved, "No retrieve call was made to Client"
