from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from coldcast.settings import load_settings
from coldcast.sources import alberta_api


def test_years_before_calendar():
    assert alberta_api._years_before_calendar(date(2026, 4, 8), 2) == date(2024, 4, 8)
    assert alberta_api._years_before_calendar(date(2024, 2, 29), 2) == date(2022, 2, 28)


def test_resolve_from_date_auto_two_years_back():
    with patch("coldcast.sources.alberta_api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 8)
        source = {"from_date": "auto", "default_years_back": 2}
        assert alberta_api._resolve_from_date(source) == "2024-04-08"


def test_resolve_from_date_literal_unchanged():
    source = {"from_date": "1984-01-03", "default_years_back": 2}
    assert alberta_api._resolve_from_date(source) == "1984-01-03"


def test_load_settings_resolves_alberta_mapping_csv():
    bundle = load_settings()
    path = Path(bundle.settings["ALBERTA_API"]["mapping_csv"])
    assert path.is_absolute()
    assert path.name == "ALBERTA_API_Stations.csv"
    assert path.exists()


def _settings(mapping_csv: str) -> dict:
    return {
        "output_dir": ".",
        "max_num_threads": 2,
        "ALBERTA_API": {
            "url_base": "https://rivers.alberta.ca/WiskiLiveDataService/Download",
            "from_date": "1984-01-03",
            "to_date": "2026-04-08",
            "mapping_csv": mapping_csv,
            "remote_filename_suffix": "C.Corrected-Sensor",
            "zip": True,
            "json": True,
            "http_timeout_seconds": 30,
            "fews_csv": {
                "layout": "wide",
                "table_datetime_column": "DATETIME",
                "value_column_names": {},
            },
        },
    }


def test_alberta_build_requests_from_mapping_csv(tmp_path):
    mapping = tmp_path / "alberta_stations.csv"
    mapping.write_text("Station,Parameter,TsID\n05BJ805,TA,160424042\n", encoding="utf-8")
    settings = _settings(str(mapping))

    requests_list = alberta_api.build_requests(settings)
    assert len(requests_list) == 1
    req = requests_list[0]
    assert "tsId=160424042" in req.url
    assert "from=1984-01-03" in req.url
    assert "to=2026-04-08" in req.url
    assert "zip=true" in req.url
    assert "json=true" in req.url
    assert req.filename == "05BJ805_TA_C.Corrected-Sensor.csv"


def test_alberta_parse_time_values_from_points_ms_array():
    """WISKI-style Points: [[epoch_ms, value], ...]."""
    raw = '{"Unit":"mm","Points":[[946684800000,-2.5],[946688400000,-1.0]]}'
    rows = alberta_api._parse_time_values(raw.encode("utf-8"))
    assert len(rows) == 2
    assert rows[0].date_time == "2000-01-01T00:00:00Z"
    assert rows[0].value == -2.5
    assert rows[1].value == -1.0


def test_alberta_parse_time_values_zip_prefers_json_member():
    """Non-JSON first member should not block parsing a later .json file."""
    good = b'{"Points":[[946684800000,1.0],[946688400000,2.0]]}'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", b"not json")
        zf.writestr("series.json", good)

    rows = alberta_api._parse_time_values(buf.getvalue())
    assert len(rows) == 2
    assert rows[0].value == 1.0


def test_alberta_parse_time_values_from_zipped_json():
    payload = b'{"data":[{"time":"2026-04-08T00:00:00Z","value":1.5},{"time":"2026-04-08T01:00:00Z","value":2}]}'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("series.json", payload)

    rows = alberta_api._parse_time_values(buf.getvalue())
    assert [r.date_time for r in rows] == ["2026-04-08T00:00:00Z", "2026-04-08T01:00:00Z"]
    assert [r.value for r in rows] == [1.5, 2.0]


def test_alberta_pr_rate_to_interval_amounts_hourly():
    """PR: rate * hours since previous sample (hourly spacing => amount = rate * 1)."""
    rows = [
        alberta_api.TimeValue(date_time="2026-04-08T00:00:00Z", value=1.0),
        alberta_api.TimeValue(date_time="2026-04-08T01:00:00Z", value=2.5),
        alberta_api.TimeValue(date_time="2026-04-08T02:00:00Z", value=0.5),
    ]
    converted = alberta_api._transform_parameter_series("PR", rows)
    assert [r.value for r in converted] == [1.0, 2.5, 0.5]


def test_alberta_pr_rate_uses_timestep_duration():
    """30 min at 2 mm/h => 1 mm in that interval."""
    rows = [
        alberta_api.TimeValue(date_time="2026-04-08T10:00:00Z", value=2.0),
        alberta_api.TimeValue(date_time="2026-04-08T10:30:00Z", value=2.0),
    ]
    converted = alberta_api._transform_parameter_series("PR", rows)
    assert len(converted) == 2
    assert converted[0].value == 2.0
    assert abs(converted[1].value - 1.0) < 1e-9


def test_alberta_pc_cumulative_quarter_hourly_to_hourly():
    """PC: cumulative counter every 15 min, summed to hourly increments."""
    rows = [
        alberta_api.TimeValue(date_time="2026-04-08T10:00:00Z", value=100.0),
        alberta_api.TimeValue(date_time="2026-04-08T10:15:00Z", value=104.0),
        alberta_api.TimeValue(date_time="2026-04-08T10:30:00Z", value=108.0),
        alberta_api.TimeValue(date_time="2026-04-08T10:45:00Z", value=112.0),
    ]
    converted = alberta_api._transform_parameter_series("PC", rows)
    assert len(converted) == 1
    assert converted[0].date_time == "2026-04-08T10:00:00"
    assert converted[0].value == 12.0


def test_alberta_pc_spans_two_hours():
    rows = [
        alberta_api.TimeValue(date_time="2026-04-08T10:00:00Z", value=100.0),
        alberta_api.TimeValue(date_time="2026-04-08T10:15:00Z", value=104.0),
        alberta_api.TimeValue(date_time="2026-04-08T11:00:00Z", value=108.0),
    ]
    converted = alberta_api._transform_parameter_series("PC", rows)
    by_hour = {r.date_time: r.value for r in converted}
    assert by_hour["2026-04-08T10:00:00"] == 4.0
    assert by_hour["2026-04-08T11:00:00"] == 4.0


def test_alberta_download_writes_fews_wide_csv(tmp_path, monkeypatch):
    source = {
        "url_base": "https://rivers.alberta.ca/WiskiLiveDataService/Download",
        "from_date": "1984-01-03",
        "to_date": "2026-04-08",
        "remote_filename_suffix": "C.Corrected-Sensor",
        "zip": False,
        "json": True,
        "save_raw_response": True,
    }
    fews_csv_cfg = {"layout": "wide", "table_datetime_column": "DATETIME", "value_column_names": {}}
    entry = alberta_api.MappingEntry(station="05BJ805", parameter="TA", ts_id="160424042")
    body = b'[{"time":"2026-04-08T00:00:00Z","value":-2},{"time":"2026-04-08T01:00:00Z","value":-1.5}]'

    def fake_get(*_a, **_k):
        return SimpleNamespace(status_code=200, content=body)

    monkeypatch.setattr(alberta_api.requests, "get", fake_get)
    ok = alberta_api._download_one(entry, source, tmp_path, 30, fews_csv_cfg)
    assert ok is True
    out = tmp_path / "05BJ805_TA.csv"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "DATETIME,TA" in text
    assert "2026-04-08T00:00:00Z,-2" in text
    raw = tmp_path / "05BJ805_TA.download"
    assert raw.exists()
    assert raw.read_bytes() == body


def test_alberta_download_writes_fews_long_csv_with_pr_interval_amounts(tmp_path, monkeypatch):
    source = {
        "url_base": "https://rivers.alberta.ca/WiskiLiveDataService/Download",
        "from_date": "1984-01-03",
        "to_date": "2026-04-08",
        "remote_filename_suffix": "C.Corrected-Sensor",
        "zip": False,
        "json": True,
        "save_raw_response": True,
    }
    fews_csv_cfg = {
        "layout": "long",
        "location_column": "locationId",
        "parameter_column": "parameterId",
        "datetime_column": "dateTime",
        "value_column": "value",
        "unit_column": "unit",
        "quality_column": "qualityFlag",
        "parameter_id_map": {"PR": "P.obs"},
    }
    entry = alberta_api.MappingEntry(station="05BJ805", parameter="PR", ts_id="437695042")
    body = b'{"data":[{"time":"2026-04-08T00:00:00Z","value":1},{"time":"2026-04-08T01:00:00Z","value":2}]}'

    def fake_get(*_a, **_k):
        return SimpleNamespace(status_code=200, content=body)

    monkeypatch.setattr(alberta_api.requests, "get", fake_get)
    ok = alberta_api._download_one(entry, source, tmp_path, 30, fews_csv_cfg)
    assert ok is True
    out = tmp_path / "05BJ805_PR.csv"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "locationId,parameterId,dateTime,value,unit,qualityFlag" in text
    assert "05BJ805,P.obs,2026-04-08T00:00:00Z,1,," in text
    assert "05BJ805,P.obs,2026-04-08T01:00:00Z,2,," in text
    raw = tmp_path / "05BJ805_PR.download"
    assert raw.exists()
    assert raw.read_bytes() == body


def test_alberta_download_saves_raw_zip_when_parse_returns_no_records(tmp_path, monkeypatch):
    source = {
        "url_base": "https://rivers.alberta.ca/WiskiLiveDataService/Download",
        "from_date": "1984-01-03",
        "to_date": "2026-04-08",
        "remote_filename_suffix": "C.Corrected-Sensor",
        "zip": True,
        "json": True,
        "save_raw_response": True,
    }
    fews_csv_cfg = {"layout": "wide", "table_datetime_column": "DATETIME", "value_column_names": {}}
    entry = alberta_api.MappingEntry(station="05BJ805", parameter="TA", ts_id="160424042")
    inner = b"[]"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("empty.json", inner)

    def fake_get(*_a, **_k):
        return SimpleNamespace(status_code=200, content=buf.getvalue())

    monkeypatch.setattr(alberta_api.requests, "get", fake_get)
    ok = alberta_api._download_one(entry, source, tmp_path, 30, fews_csv_cfg)
    assert ok is False
    raw_zip = tmp_path / "05BJ805_TA.zip"
    assert raw_zip.exists()
    assert raw_zip.read_bytes() == buf.getvalue()
    assert not (tmp_path / "05BJ805_TA.csv").exists()


def test_alberta_build_requests_raises_on_missing_columns(tmp_path):
    mapping = tmp_path / "bad.csv"
    mapping.write_text("Station,Parameter\n05BJ805,TA\n", encoding="utf-8")
    settings = _settings(str(mapping))
    with pytest.raises(KeyError, match="Missing mapping CSV columns"):
        alberta_api.build_requests(settings)
