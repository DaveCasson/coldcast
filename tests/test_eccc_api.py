import csv
import json
from pathlib import Path
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
    hydro_csv = Path(settings["ECCC_API"]["station_csv_hydro"])
    with hydro_csv.open(newline="", encoding="utf-8") as handle:
        first_row = next(csv.DictReader(handle))
    station_id = str(first_row["ID"]).strip()
    requests_list = build_requests(settings)
    hydro = [r for r in requests_list if "hydrometric-realtime" in r.url and "STATION_NUMBER=" in r.url]
    assert hydro
    assert f"STATION_NUMBER={station_id}" in hydro[0].url
    assert hydro[0].filename == f"{station_id}_hydrometric-realtime.csv"


def test_eccc_api_hydro_includes_clamped_page_limit_for_geomet():
    """Hydrometric collections use the same default url_template with limit= (pagination applies on download)."""
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings, model="hydrometric-realtime")
    assert requests_list
    assert "STATION_NUMBER=" in requests_list[0].url
    assert "limit=10000" in requests_list[0].url
    daily = build_requests(settings, model="hydrometric-daily-mean")
    assert daily
    assert "limit=10000" in daily[0].url
    assert "STATION_NUMBER=" in daily[0].url


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


def test_eccc_api_model_selects_single_collection_by_key():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings, model="swob-realtime")
    assert requests_list
    assert all(r.eccc_collection_key == "swob-realtime" for r in requests_list)
    assert all("swob-realtime" in r.url for r in requests_list)


def test_eccc_api_model_selects_single_collection_case_insensitive():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings, model="HYDROMETRIC-REALTIME")
    assert requests_list
    assert all(r.eccc_collection_key == "hydrometric-realtime" for r in requests_list)


def test_eccc_api_model_selects_collection_with_underscore_alias():
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(settings, model="climate_daily")
    assert requests_list
    assert all(r.eccc_collection_key == "climate-daily" for r in requests_list)
    assert all("climate-daily" in r.url for r in requests_list)


def test_eccc_api_climate_daily_uses_climate_identifier_when_available(tmp_path):
    stations_csv = tmp_path / "climate_stations.csv"
    stations_csv.write_text("CLIMATE_IDENTIFIER\n1022430\n", encoding="utf-8")
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(
        settings,
        model="climate-daily",
        stations_csv=str(stations_csv),
    )
    assert requests_list
    req = requests_list[0]
    assert "CLIMATE_IDENTIFIER=1022430" in req.url
    assert req.eccc_collection_key == "climate-daily"


def test_eccc_api_climate_identifier_strips_float_suffix(tmp_path):
    """Pandas reads numeric-looking cells as float; URLs must not use ``3050778.0``."""
    stations_csv = tmp_path / "climate_stations.csv"
    stations_csv.write_text("CLIMATE_IDENTIFIER\n3050778.0\n", encoding="utf-8")
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(
        settings,
        model="climate-daily",
        stations_csv=str(stations_csv),
    )
    assert requests_list
    assert "CLIMATE_IDENTIFIER=3050778" in requests_list[0].url


def test_eccc_api_climate_hourly_uses_climate_identifier_when_available(tmp_path):
    stations_csv = tmp_path / "climate_stations.csv"
    stations_csv.write_text("CLIMATE_IDENTIFIER\n1022430\n", encoding="utf-8")
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(
        settings,
        model="climate-hourly",
        stations_csv=str(stations_csv),
    )
    assert requests_list
    req = requests_list[0]
    assert "climate-hourly" in req.url
    assert "CLIMATE_IDENTIFIER=1022430" in req.url
    assert req.eccc_collection_key == "climate-hourly"


def test_eccc_api_model_unknown_collection_raises():
    bundle = load_settings()
    settings = bundle.settings
    with pytest.raises(KeyError, match="Unknown ECCC_API collection"):
        build_requests(settings, model="not-a-real-collection")


def test_eccc_api_stations_csv_overrides_default_hydro_list(tmp_path):
    custom = tmp_path / "custom_stations.csv"
    custom.write_text("ID,NAME\n99ZZ999,Custom\n", encoding="utf-8")
    bundle = load_settings()
    settings = bundle.settings
    requests_list = build_requests(
        settings,
        model="hydrometric-realtime",
        stations_csv=str(custom),
    )
    assert requests_list
    assert all("99ZZ999" in r.url for r in requests_list)
    assert all(r.eccc_collection_key == "hydrometric-realtime" for r in requests_list)


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


def test_fews_csv_wide_sort_datetime_descending():
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
        sort_datetime_descending=True,
    )
    assert fieldnames == ["DATETIME", "DISCHARGE", "LEVEL"]
    assert rows[0]["DATETIME"] == "2020-01-01T13:00:00Z"
    assert rows[1]["DATETIME"] == "2020-01-01T12:00:00Z"


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


def test_eccc_api_build_requests_clamps_limit_to_geomet_max(tmp_path):
    hydro_csv = tmp_path / "h.csv"
    hydro_csv.write_text("ID\n01AA001\n", encoding="utf-8")
    settings = {
        "ECCC_API": {
            "url_base": "https://api.weather.gc.ca/collections",
            "limit": 999999,
            "time_range": "",
            "station_csv": str(hydro_csv),
            "url_template": "{url_base}/{collection}/items?STATION_NUMBER={station}&limit={limit}",
            "filename_template": "{station}.csv",
            "collections": {
                "hydrometric-realtime": {
                    "collection": "hydrometric-realtime",
                    "station_list": "hydro",
                },
            },
        },
    }
    requests_list = eccc_api.build_requests(settings)
    assert len(requests_list) == 1
    assert "limit=10000" in requests_list[0].url


def test_eccc_download_follows_next_pagination(tmp_path, monkeypatch, _minimal_eccc_source):
    page1 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "STATION_NUMBER": "X",
                    "DATETIME": "2020-01-01T12:00:00Z",
                    "DISCHARGE": 1.0,
                    "LEVEL": 5.0,
                },
            }
        ],
        "links": [{"rel": "next", "href": "https://example.invalid/items?page=2"}],
    }
    page2 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "STATION_NUMBER": "X",
                    "DATETIME": "2020-01-02T12:00:00Z",
                    "DISCHARGE": 2.0,
                    "LEVEL": 6.0,
                },
            }
        ],
        "links": [],
    }
    calls = []

    def fake_get(url, timeout=60):
        calls.append(url)
        if "page=2" in url:
            return SimpleNamespace(status_code=200, content=json.dumps(page2).encode("utf-8"))
        return SimpleNamespace(status_code=200, content=json.dumps(page1).encode("utf-8"))

    monkeypatch.setattr(eccc_api.requests, "get", fake_get)
    source = {
        **_minimal_eccc_source,
        "fetch_all_pages": True,
        "max_pagination_pages": 100,
        "sort_output_datetime_descending": True,
    }
    req = DownloadRequest(
        url="https://example.invalid/items?page=1",
        filename="X_hydrometric-realtime.csv",
        eccc_collection_key="hydrometric-realtime",
    )
    ok = _download_one_eccc(req, tmp_path, source, {"layout": "wide", "table_datetime_column": "DATETIME"}, {}, {}, 30)
    assert ok is True
    assert len(calls) == 2
    out = tmp_path / "X_hydrometric-realtime.csv"
    text = out.read_text(encoding="utf-8")
    assert "2020-01-02T12:00:00Z" in text
    assert "2020-01-01T12:00:00Z" in text
    # Newest first (wide)
    assert text.index("2020-01-02") < text.index("2020-01-01")
