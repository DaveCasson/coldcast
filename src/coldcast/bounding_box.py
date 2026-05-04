from __future__ import annotations

import math
from typing import Dict, Mapping, Optional, Sequence, Tuple

GEO_KEYS: Tuple[str, ...] = ("lon_min", "lon_max", "lat_min", "lat_max")
NOMADS_BBOX_KEYS: Tuple[str, ...] = ("leftlon", "rightlon", "toplat", "bottomlat")


def mapping_to_partial_geographic(value: object) -> Optional[Dict[str, float]]:
    """Extract any of lon_min, lon_max, lat_min, lat_max from a mapping, or None if value is empty."""
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        raise TypeError("bounding_box must be a mapping or a length-4 sequence, not a string.")
    if isinstance(value, Mapping):
        out: Dict[str, float] = {}
        for key in GEO_KEYS:
            if key in value:
                out[key] = float(value[key])  # type: ignore[arg-type]
        return out or None
    return None


def cds_sequence_to_partial_geographic(seq: Sequence[object]) -> Dict[str, float]:
    """CDS ``area`` list order: North, West, South, East (lat/lon extents)."""
    if len(seq) != 4:
        raise ValueError("CDS bounding box sequence must have length 4 (North, West, South, East).")
    north, west, south, east = (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    return {
        "lon_min": west,
        "lon_max": east,
        "lat_min": south,
        "lat_max": north,
    }


def _geo_from_value(value: object) -> Optional[Dict[str, float]]:
    """Parse top-level ``bounding_box`` / nested ERA5-like values into partial geographic keys."""
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        raise TypeError("bounding_box must be a mapping or a length-4 sequence, not a string.")
    if isinstance(value, (list, tuple)):
        return cds_sequence_to_partial_geographic(value)
    if isinstance(value, Mapping):
        return mapping_to_partial_geographic(value)
    raise TypeError(f"Unsupported bounding_box type: {type(value)!r}")


def merge_geographic_bbox(
    base: Optional[Mapping[str, object]],
    overlay: Optional[Mapping[str, object]],
) -> Dict[str, float]:
    """Overlay wins per key; keys only from GEO_KEYS."""
    merged: Dict[str, float] = {}
    for key in GEO_KEYS:
        if base and key in base:
            merged[key] = float(base[key])  # type: ignore[arg-type]
    if overlay:
        for key in GEO_KEYS:
            if key in overlay:
                merged[key] = float(overlay[key])  # type: ignore[arg-type]
    return merged


def require_complete_geographic_bbox(bbox: Mapping[str, float], *, label: str = "bounding_box") -> None:
    missing = [k for k in GEO_KEYS if k not in bbox]
    if missing:
        raise ValueError(f"{label} missing keys after merge: {', '.join(missing)}")


def geographic_lon_lat_bounds(bbox: Mapping[str, object]) -> Tuple[float, float, float, float]:
    require_complete_geographic_bbox(bbox, label="bbox")  # type: ignore[arg-type]
    return (
        float(bbox["lon_min"]),
        float(bbox["lon_max"]),
        float(bbox["lat_min"]),
        float(bbox["lat_max"]),
    )


def resolve_merged_geographic_bbox(
    settings: Mapping[str, object],
    nested: Optional[object],
) -> Optional[Dict[str, float]]:
    """
    Merge top-level ``settings['bounding_box']`` with optional nested bbox (product wins per key).

    ``nested`` may be any value accepted by the top-level box (mapping with geographic keys or CDS sequence).

    Returns None when neither side defines any geographic keys; raises if keys remain incomplete.
    """
    global_part = _geo_from_value(settings.get("bounding_box"))
    nested_part = _geo_from_value(nested) if nested is not None else None
    merged = merge_geographic_bbox(global_part, nested_part)
    if not merged:
        return None
    require_complete_geographic_bbox(merged)
    return merged


def cds_sequence_from_geographic(bbox: Mapping[str, float]) -> Tuple[float, float, float, float]:
    """CDS retrieve ``area``: North, West, South, East."""
    require_complete_geographic_bbox(bbox)
    return (
        float(bbox["lat_max"]),
        float(bbox["lon_min"]),
        float(bbox["lat_min"]),
        float(bbox["lon_max"]),
    )


def resolve_era5_cds_sequence(
    settings: Mapping[str, object],
    cfg: Mapping[str, object],
) -> Tuple[float, float, float, float]:
    cfg_raw = cfg.get("bounding_box", cfg.get("bbox"))
    global_part = _geo_from_value(settings.get("bounding_box"))
    cfg_part = _geo_from_value(cfg_raw)
    merged = merge_geographic_bbox(global_part, cfg_part)
    if not merged:
        raise ValueError("bounding_box is required for ERA5 downloads (global and/or ERA5 block).")
    require_complete_geographic_bbox(merged)
    return cds_sequence_from_geographic(merged)


def round_cds_area_string(coords: Sequence[float]) -> str:
    """Format CDS ``area`` string with ERA5-era quarter-degree rounding."""
    lon = [coords[1], coords[3]]
    lat = [coords[2], coords[0]]

    rounded_lon = [math.floor(lon[0] * 4) / 4, math.ceil(lon[1] * 4) / 4]
    rounded_lat = [math.floor(lat[0] * 4) / 4, math.ceil(lat[1] * 4) / 4]

    if lat[0] > rounded_lat[0] + 0.125:
        rounded_lat[0] += 0.25
    if lon[0] > rounded_lon[0] + 0.125:
        rounded_lon[0] += 0.25
    if lat[1] < rounded_lat[1] - 0.125:
        rounded_lat[1] -= 0.25
    if lon[1] < rounded_lon[1] - 0.125:
        rounded_lon[1] -= 0.25

    return "{}/{}/{}/{}".format(rounded_lat[1], rounded_lon[0], rounded_lat[0], rounded_lon[1])


def merge_clip_bbox(
    settings: Mapping[str, object],
    clip_bbox: Optional[Mapping[str, object]],
) -> Dict[str, float]:
    """Merge global geographic box with FEWS/product clip_bbox (overlay wins per key)."""
    global_part = _geo_from_value(settings.get("bounding_box"))
    nested_part = mapping_to_partial_geographic(clip_bbox) if clip_bbox else None
    merged = merge_geographic_bbox(global_part, nested_part)
    require_complete_geographic_bbox(merged, label="clip_bbox")
    return merged


def nomads_bbox_params(source: Mapping[str, object]) -> Dict[str, object]:
    """NOMADS Grib Filter CGI parameters (subregion omitted; caller adds it)."""
    box = source["bbox"]
    return {key: box[key] for key in NOMADS_BBOX_KEYS}
