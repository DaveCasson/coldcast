from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from coldcast.sources.eccc_water_office import build_requests, _http_verify, _time_range


def test_build_requests_query_matches_water_office_api(tmp_path):
    csv_path = tmp_path / "st.csv"
    csv_path.write_text("ID\n05BJ004\n", encoding="utf-8")
    settings = {
        "ECCC_WATER_OFFICE": {
            "url_base": "https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline",
            "station_csv": str(csv_path),
            "station_column": "ID",
            "parameters": ["6", "47"],
            "start_date": "2026-04-24 00:00:00",
            "end_date": "2026-04-26 23:59:59",
            "filename_template": "{station}_wo.csv",
        }
    }
    reqs = build_requests(settings)
    assert len(reqs) == 1
    assert reqs[0].filename == "05BJ004_wo.csv"
    parsed = urlparse(reqs[0].url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "wateroffice.ec.gc.ca"
    assert parsed.path == "/services/real_time_data/csv/inline"
    qs = parse_qs(parsed.query)
    assert qs.get("stations[]") == ["05BJ004"]
    assert qs.get("parameters[]") == ["6", "47"]
    assert qs.get("start_date") == ["2026-04-24 00:00:00"]
    assert qs.get("end_date") == ["2026-04-26 23:59:59"]


def test_build_requests_stations_csv_override(tmp_path):
    csv_default = tmp_path / "default.csv"
    csv_default.write_text("ID\nAAA\n", encoding="utf-8")
    csv_override = tmp_path / "override.csv"
    csv_override.write_text("ID\nBBB\n", encoding="utf-8")
    settings = {
        "ECCC_WATER_OFFICE": {
            "url_base": "https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline",
            "station_csv": str(csv_default),
            "station_column": "ID",
            "parameters": ["6"],
            "start_date": "2026-04-24 00:00:00",
            "end_date": "2026-04-26 23:59:59",
            "filename_template": "{station}.csv",
        }
    }
    reqs = build_requests(settings, stations_csv=str(csv_override))
    assert len(reqs) == 1
    assert "BBB" in reqs[0].url
    assert reqs[0].filename == "BBB.csv"


def test_time_range_requires_both_explicit_dates():
    with pytest.raises(ValueError, match="both start_date and end_date"):
        _time_range({"start_date": "2026-01-01 00:00:00", "end_date": ""})


def test_time_range_auto_uses_days_back():
    start_s, end_s = _time_range({"days_back": 1})
    assert len(start_s) == 19
    assert len(end_s) == 19
    assert start_s[10] == " "
    assert end_s[10] == " "


def test_build_requests_defaults_verify_true(tmp_path):
    csv_path = tmp_path / "st.csv"
    csv_path.write_text("ID\nX\n", encoding="utf-8")
    settings = {
        "ECCC_WATER_OFFICE": {
            "url_base": "https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline",
            "station_csv": str(csv_path),
            "station_column": "ID",
            "parameters": ["6"],
            "start_date": "2026-04-24 00:00:00",
            "end_date": "2026-04-26 23:59:59",
            "filename_template": "{station}.csv",
        }
    }
    reqs = build_requests(settings)
    assert reqs[0].verify is True


def test_build_requests_respects_http_verify_ssl_false(tmp_path):
    csv_path = tmp_path / "st.csv"
    csv_path.write_text("ID\nX\n", encoding="utf-8")
    settings = {
        "ECCC_WATER_OFFICE": {
            "url_base": "https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline",
            "station_csv": str(csv_path),
            "station_column": "ID",
            "parameters": ["6"],
            "start_date": "2026-04-24 00:00:00",
            "end_date": "2026-04-26 23:59:59",
            "filename_template": "{station}.csv",
            "http_verify_ssl": False,
        }
    }
    reqs = build_requests(settings)
    assert reqs[0].verify is False


def test_http_ca_bundle_overrides_verify_ssl(tmp_path):
    pem = tmp_path / "custom.pem"
    pem.write_text("# test", encoding="utf-8")
    v = _http_verify({"http_ca_bundle": str(pem), "http_verify_ssl": False})
    assert v == str(pem.resolve())


def test_download_one_passes_verify_to_requests(tmp_path, monkeypatch):
    from coldcast.download import DownloadRequest, _download_one

    captured = {}

    class FakeResp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_content(self, chunk_size=1024 * 512):
            yield b"x"

    def fake_get(url, **kwargs):
        captured["verify"] = kwargs.get("verify")
        return FakeResp()

    monkeypatch.setattr("coldcast.download.requests.get", fake_get)
    req = DownloadRequest(url="https://example.invalid/x", filename="a.bin", verify=False)
    assert _download_one(req, tmp_path, timeout=1) is True
    assert captured.get("verify") is False
