from types import SimpleNamespace

import pytest

from coldcast.download import DownloadRequest
from coldcast.settings import load_settings
from coldcast.sources import eccc_api
from coldcast.sources.eccc_api import _download_one_eccc, build_requests
from coldcast.sources.eccc_fews_csv import (
    geojson_features_to_fews_rows,
    geojson_features_to_fews_wide_rows,
)


def test_eccc_api_request_carries_collection_key():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings)
    assert requests_list[0].eccc_collection_key == "hydrometric-realtime"


def test_eccc_api_hydro_url_uses_station_number():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings)
    hydro = [r for r in requests_list if "hydrometric-realtime" in r.url and "STATION_NUMBER=" in r.url]
    assert hydro
    assert "STATION_NUMBER=09AA001" in hydro[0].url
    assert hydro[0].filename == "09AA001_hydrometric-realtime.csv"


def test_eccc_api_swob_url_uses_msc_id_and_properties():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings)
    swob = [r for r in requests_list if "swob-realtime" in r.url]
    assert swob
    req = swob[0]
    assert "msc_id-value=" in req.url
    assert "f=json" in req.url
    assert "properties=air_temp" in req.url
    assert req.filename.endswith("_swob-realtime.csv")


def test_eccc_api_legacy_station_csv_for_hydro_only(tmp_path):
    hydro_csv = tmp_path / "hydro.csv"
    hydro_csv.write_text("ID,NAME\n01AA001,Test\n", encoding="utf-8")
    settings = {
        "ECCC_API": {
            "url_base": "https://api.weather.gc.ca/collections",
            "limit": 10,
            "time_range": "",
            "station_csv": str(hydro_csv),
            "url_template": "{url_base}/{collection}/items?STATION_NUMBER={station}&limit={limit}",
            "filename_template": "{station}_{collection}.csv",
            "collections": {
                "hydrometric-realtime": {
                    "collection": "hydrometric-realtime",
                    "station_list": "hydro",
                },
            },
        }
    }
    requests_list = build_requests(settings)
    assert len(requests_list) == 1
    assert "STATION_NUMBER=01AA001" in requests_list[0].url


def test_fews_csv_rows_hydro_long_format():
    features = [
        {
            "type": "Feature",
            "properties": {
                "STATION_NUMBER": "10CD001",
                "DATETIME": "2020-01-01T12:00:00Z",
                "DISCHARGE": 1.5,
                "LEVEL": 10.0,
            },
        }
    ]
    collection_cfg = {
        "station_list": "hydro",
        "datetime_column": "DATETIME",
        "download_variables": ["DISCHARGE", "LEVEL"],
    }
    rows = geojson_features_to_fews_rows(
        features,
        collection_cfg,
        fews_csv_cfg={"layout": "long"},
        parameter_id_map={"DISCHARGE": "Q.m3s"},
    )
    assert len(rows) == 2
    assert {r["parameterId"] for r in rows} == {"Q.m3s", "LEVEL"}
    assert all(r["locationId"] == "10CD001" for r in rows)


def test_fews_csv_wide_hydro_matches_fews_value_columns():
    features = [
        {
            "type": "Feature",
            "properties": {
                "STATION_NUMBER": "10CD001",
                "DATETIME": "2020-01-01T12:00:00Z",
                "DISCHARGE": 1.5,
                "LEVEL": 10.0,
            },
        },
        {
            "type": "Feature",
            "properties": {
                "STATION_NUMBER": "10CD001",
                "DATETIME": "2020-01-01T13:00:00Z",
                "DISCHARGE": 2.0,
                "LEVEL": 10.5,
            },
        },
    ]
    collection_cfg = {
        "station_list": "hydro",
        "datetime_column": "DATETIME",
        "download_variables": ["DISCHARGE", "LEVEL"],
    }
    rows, fieldnames = geojson_features_to_fews_wide_rows(
        features,
        collection_cfg,
        fews_csv_cfg={"table_datetime_column": "DATETIME"},
        value_column_names={},
    )
    assert fieldnames == ["DATETIME", "DISCHARGE", "LEVEL"]
    assert len(rows) == 2
    assert rows[0]["DATETIME"] == "2020-01-01T12:00:00Z"
    assert rows[0]["DISCHARGE"] == "1.5"
    assert rows[0]["LEVEL"] == "10"
    assert rows[1]["DISCHARGE"] == "2"
    assert rows[1]["LEVEL"] == "10.5"


def test_fews_csv_wide_value_column_rename():
    features = [
        {
            "type": "Feature",
            "properties": {
                "DATETIME": "2020-01-01T12:00:00Z",
                "DISCHARGE": 1.0,
                "LEVEL": 5.0,
            },
        }
    ]
    collection_cfg = {
        "station_list": "hydro",
        "datetime_column": "DATETIME",
        "download_variables": ["DISCHARGE", "LEVEL"],
    }
    rows, fieldnames = geojson_features_to_fews_wide_rows(
        features,
        collection_cfg,
        fews_csv_cfg={"table_datetime_column": "DATETIME"},
        value_column_names={"DISCHARGE": "Q", "LEVEL": "H"},
    )
    assert fieldnames == ["DATETIME", "Q", "H"]
    assert rows[0]["Q"] == "1"


def test_fews_csv_rows_swob_long_format():
    features = [
        {
            "type": "Feature",
            "properties": {
                "date_tm-value": "2026-02-19T00:00:00Z",
                "msc_id-value": "8400416",
                "air_temp": -2.0,
                "air_temp-uom": "°C",
                "air_temp-qa": 100,
                "pcpn_amt_pst1hr": 0,
                "pcpn_amt_pst1hr-uom": "mm",
            },
        }
    ]
    collection_cfg = {
        "station_list": "meteo",
        "datetime_column": "date_tm-value",
        "download_variables": ["air_temp", "pcpn_amt_pst1hr"],
    }
    rows = geojson_features_to_fews_rows(
        features,
        collection_cfg,
        fews_csv_cfg={"layout": "long"},
        parameter_id_map={},
    )
    assert len(rows) == 2
    params = {r["parameterId"]: r["value"] for r in rows}
    assert params["air_temp"] == "-2"
    assert params["pcpn_amt_pst1hr"] == "0"


def test_fews_csv_wide_swob():
    features = [
        {
            "type": "Feature",
            "properties": {
                "date_tm-value": "2026-02-19T00:00:00Z",
                "msc_id-value": "8400416",
                "air_temp": -2.0,
                "pcpn_amt_pst1hr": 0,
            },
        }
    ]
    collection_cfg = {
        "station_list": "meteo",
        "datetime_column": "date_tm-value",
        "download_variables": ["air_temp", "pcpn_amt_pst1hr"],
    }
    rows, fieldnames = geojson_features_to_fews_wide_rows(
        features,
        collection_cfg,
        fews_csv_cfg={"table_datetime_column": "DATETIME"},
        value_column_names={},
    )
    assert fieldnames == ["DATETIME", "air_temp", "pcpn_amt_pst1hr"]
    assert rows[0]["DATETIME"] == "2026-02-19T00:00:00Z"
    assert rows[0]["air_temp"] == "-2"
    assert rows[0]["pcpn_amt_pst1hr"] == "0"


@pytest.fixture
def _minimal_eccc_source():
    return {
        "collections": {
            "hydrometric-realtime": {
                "collection": "hydrometric-realtime",
                "station_list": "hydro",
                "datetime_column": "DATETIME",
                "download_variables": ["DISCHARGE", "LEVEL"],
            },
        },
    }


def test_eccc_skip_csv_when_geojson_has_no_features(tmp_path, monkeypatch, _minimal_eccc_source):
    out = tmp_path / "09AA001_hydrometric-realtime.csv"

    def fake_get(*_a, **_k):
        return SimpleNamespace(status_code=200, content=b'{"type":"FeatureCollection","features":[]}')

    monkeypatch.setattr(eccc_api.requests, "get", fake_get)
    req = DownloadRequest(
        url="https://example.invalid/items",
        filename=out.name,
        eccc_collection_key="hydrometric-realtime",
    )
    ok = _download_one_eccc(
        req,
        tmp_path,
        _minimal_eccc_source,
        {},
        {},
        {},
        30,
    )
    assert ok is False
    assert not out.exists()


def test_eccc_skip_csv_when_features_have_no_datetime(tmp_path, monkeypatch, _minimal_eccc_source):
    out = tmp_path / "09AA001_hydrometric-realtime.csv"
    payload = (
        b'{"type":"FeatureCollection","features":['
        b'{"type":"Feature","properties":{"STATION_NUMBER":"X","DISCHARGE":1}}'
        b"]}"
    )

    def fake_get(*_a, **_k):
        return SimpleNamespace(status_code=200, content=payload)

    monkeypatch.setattr(eccc_api.requests, "get", fake_get)
    req = DownloadRequest(
        url="https://example.invalid/items",
        filename=out.name,
        eccc_collection_key="hydrometric-realtime",
    )
    ok = _download_one_eccc(req, tmp_path, _minimal_eccc_source, {}, {}, {}, 30)
    assert ok is False
    assert not out.exists()
