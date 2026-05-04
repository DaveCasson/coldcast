from __future__ import annotations

import pytest

from coldcast import bounding_box


def test_merge_geographic_bbox_overlay_wins_per_key() -> None:
    base = {"lon_min": -120.0, "lon_max": -110.0, "lat_min": 49.0, "lat_max": 60.0}
    overlay = {"lon_max": -100.0}
    merged = bounding_box.merge_geographic_bbox(base, overlay)
    assert merged["lon_min"] == -120.0
    assert merged["lon_max"] == -100.0
    assert merged["lat_min"] == 49.0
    assert merged["lat_max"] == 60.0


def test_resolve_merged_geographic_bbox_dict_overrides_cds_global() -> None:
    settings = {"bounding_box": [60.0, -120.0, 49.0, -110.0]}
    nested = {"lon_min": -117.0, "lon_max": -113.0, "lat_min": 50.0, "lat_max": 52.0}
    merged = bounding_box.resolve_merged_geographic_bbox(settings, nested)
    assert merged["lon_min"] == -117.0
    assert merged["lon_max"] == -113.0
    assert merged["lat_min"] == 50.0
    assert merged["lat_max"] == 52.0


def test_resolve_merged_geographic_bbox_partial_nested_inherits_global() -> None:
    settings = {"bounding_box": {"lon_min": -120.0, "lon_max": -110.0, "lat_min": 49.0, "lat_max": 60.0}}
    nested = {"lon_max": -100.0}
    merged = bounding_box.resolve_merged_geographic_bbox(settings, nested)
    assert merged["lon_min"] == -120.0
    assert merged["lon_max"] == -100.0


def test_resolve_merged_geographic_bbox_returns_none_when_undefined() -> None:
    assert bounding_box.resolve_merged_geographic_bbox({}, None) is None


def test_resolve_merged_geographic_bbox_raises_when_incomplete() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        bounding_box.resolve_merged_geographic_bbox({"bounding_box": {"lon_min": -120.0}}, None)


def test_merge_clip_bbox_full_replacement_mapping() -> None:
    settings = {"bounding_box": {"lon_min": -120.0, "lon_max": -110.0, "lat_min": 49.0, "lat_max": 60.0}}
    clip = {"lon_max": -113.0, "lon_min": -117.0, "lat_min": 50.0, "lat_max": 52.0}
    out = bounding_box.merge_clip_bbox(settings, clip)
    assert out == {
        "lon_min": -117.0,
        "lon_max": -113.0,
        "lat_min": 50.0,
        "lat_max": 52.0,
    }


def test_merge_clip_bbox_inherits_partial_from_global() -> None:
    settings = {"bounding_box": {"lon_min": -120.0, "lon_max": -110.0, "lat_min": 49.0, "lat_max": 60.0}}
    clip = {"lon_max": -113.0, "lon_min": -117.0}
    out = bounding_box.merge_clip_bbox(settings, clip)
    assert out["lon_min"] == -117.0
    assert out["lon_max"] == -113.0
    assert out["lat_min"] == 49.0
    assert out["lat_max"] == 60.0


def test_resolve_era5_cds_sequence_precedence_cfg_over_global() -> None:
    settings = {
        "bounding_box": {"lon_min": -120.0, "lon_max": -110.0, "lat_min": 49.0, "lat_max": 60.0},
    }
    cfg = {"bounding_box": [61.0, -119.0, 48.0, -111.0]}
    seq = bounding_box.resolve_era5_cds_sequence(settings, cfg)
    assert seq == (61.0, -119.0, 48.0, -111.0)


def test_round_cds_area_string_stable() -> None:
    s = bounding_box.round_cds_area_string((60.0, -120.0, 49.0, -110.0))
    assert "/" in s
    assert isinstance(s, str)


def test_nomads_bbox_params() -> None:
    source = {"bbox": {"leftlon": 190, "rightlon": 240, "toplat": 75, "bottomlat": 50}}
    p = bounding_box.nomads_bbox_params(source)
    assert p["leftlon"] == 190
    assert p["bottomlat"] == 50
