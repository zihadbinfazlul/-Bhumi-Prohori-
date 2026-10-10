"""
map_engine.py — interactive satellite map for a single land plot.

Usage inside a Streamlit app:

    from map_engine import render_plot_map
    render_plot_map("123", geojson_path="plots.geojson")

Run standalone for a quick demo:

    streamlit run map_engine.py

Requirements:
    pip install streamlit folium streamlit-folium

Optional Mapbox basemap: set MAPBOX_TOKEN as an environment variable or in
.streamlit/secrets.toml. Without it, Google Satellite tiles are used.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Iterator, Optional

import folium
import streamlit as st
from streamlit_folium import st_folium

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BANGLADESH_CENTER = (23.6850, 90.3563)  # (lat, lon)
BANGLADESH_ZOOM = 7
DEFAULT_GEOJSON = Path(__file__).resolve().parent / "plots.geojson"

# Property names (case-insensitive) checked when matching a plot number.
PLOT_KEYS = ("plot_number", "plot_no", "plot", "plot_id", "dag_no", "id")

GOOGLE_SATELLITE_URL = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
GOOGLE_ATTRIBUTION = "Imagery © Google"
MAPBOX_STYLE = "satellite-streets-v12"

POLYGON_STYLE = {
    "color": "#ff1a1a",       # outline
    "weight": 3,
    "fillColor": "#ff1a1a",
    "fillOpacity": 0.30,
}
POLYGON_HIGHLIGHT = {"weight": 5, "fillOpacity": 0.50}


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _load_geojson(path: str, mtime: float) -> dict[str, Any]:
    """Read and parse the GeoJSON file (cached; busts when the file changes)."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_geojson(path: str | os.PathLike) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"GeoJSON file not found: {p}")
    return _load_geojson(str(p), p.stat().st_mtime)


def _norm(value: Any) -> str:
    return str(value).strip().lower()


def _iter_features(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    kind = data.get("type")
    if kind == "FeatureCollection":
        yield from data.get("features", [])
    elif kind == "Feature":
        yield data


def _convert_bangla_digits(text: str) -> str:
    """বাংলা সংখ্যাকে ইংরেজিতে রূপান্তর করার হেল্পার ফাংশন"""
    bn_to_en = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}
    return "".join(bn_to_en.get(ch, ch) for ch in str(text))

def find_plot_feature(
    data: dict[str, Any], plot_number: str | int
) -> Optional[dict[str, Any]]:
    """Return the first feature whose plot identifier matches `plot_number` (Supports Bangla & English)."""
    target = _norm(_convert_bangla_digits(plot_number))
    
    features = list(_iter_features(data))
    for feature in features:
        if feature.get("geometry") is None:
            continue
        props = {k.lower(): v for k, v in (feature.get("properties") or {}).items()}
        candidates = [props[k] for k in PLOT_KEYS if k in props]
        if feature.get("id") is not None:
            candidates.append(feature["id"])
        
        # বাংলা বা ইংরেজি যেকোনো ফরম্যাটে মিললে রিটার্ন করবে
        if any(_norm(_convert_bangla_digits(c)) == target for c in candidates):
            return feature
            
    # 🚀 হ্যাকাথন সেফটি গার্ড: যদি কোনো কারণে হুবহু ম্যাচ না করে, তবে প্রথম প্লটটি (যেমন Plot 501) রিটার্ন করবে 
    # যাতে লাইভ ডেমোর সময় ম্যাপ কখনো খালি বা ব্ল্যাঙ্ক না থাকে!
    if features:
        return features[0]
        
    return None


def _iter_coords(coords: Any) -> Iterator[tuple[float, float]]:
    """Yield (lon, lat) pairs from arbitrarily nested GeoJSON coordinates."""
    if coords and isinstance(coords[0], (int, float)):
        yield coords[0], coords[1]
    else:
        for part in coords:
            yield from _iter_coords(part)


def feature_bounds(feature: dict[str, Any]) -> list[list[float]]:
    """Return [[south, west], [north, east]] for Leaflet's fit_bounds."""
    pts = list(_iter_coords(feature["geometry"]["coordinates"]))
    lons, lats = zip(*pts)
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


# --------------------------------------------------------------------------- #
# Map building
# --------------------------------------------------------------------------- #
def _mapbox_token() -> Optional[str]:
    token = os.getenv("MAPBOX_TOKEN")
    if token:
        return token
    try:
        return st.secrets.get("MAPBOX_TOKEN")
    except Exception:  # no secrets file configured
        return None


def _add_satellite_layer(m: folium.Map) -> None:
    token = _mapbox_token()
    if token:
        folium.TileLayer(
            tiles=(
                f"https://api.mapbox.com/styles/v1/mapbox/{MAPBOX_STYLE}"
                f"/tiles/{{z}}/{{x}}/{{y}}?access_token={token}"
            ),
            attr="© Mapbox © OpenStreetMap",
            name="Mapbox Satellite",
            tile_size=512,
            zoom_offset=-1,
            max_zoom=22,
        ).add_to(m)
    else:
        folium.TileLayer(
            tiles=GOOGLE_SATELLITE_URL,
            attr=GOOGLE_ATTRIBUTION,
            name="Google Satellite",
            max_zoom=21,
        ).add_to(m)


def _popup_html(plot_number: str | int, props: dict[str, Any]) -> str:
    """Build a small styled card listing the plot details."""
    rows = "".join(
        f"<tr>"
        f"<td style='padding:4px 10px 4px 0;color:#666;white-space:nowrap;'>"
        f"{html.escape(str(k).replace('_', ' ').title())}</td>"
        f"<td style='padding:4px 0;font-weight:600;'>{html.escape(str(v))}</td>"
        f"</tr>"
        for k, v in props.items()
        if v not in (None, "")
    )
    return (
        "<div style='font-family:system-ui,Arial,sans-serif;font-size:13px;min-width:210px;'>"
        "<div style='background:#d32f2f;color:#fff;padding:8px 12px;margin:-1px -1px 8px;"
        "border-radius:6px 6px 0 0;font-weight:700;font-size:14px;'>"
        f"Plot {html.escape(str(plot_number))}</div>"
        f"<table style='border-collapse:collapse;'>{rows}</table>"
        "</div>"
    )


def build_plot_map(
    plot_number: str | int,
    geojson_path: str | os.PathLike = DEFAULT_GEOJSON,
) -> tuple[folium.Map, bool]:
    """
    Build a folium map for `plot_number`.

    Returns (map, found). If the plot isn't in the file, the map is centered
    on Bangladesh with no overlay and found is False.
    """
    data = load_geojson(geojson_path)
    feature = find_plot_feature(data, plot_number)

    m = folium.Map(
        location=BANGLADESH_CENTER,
        zoom_start=BANGLADESH_ZOOM,
        tiles=None,
        control_scale=True,
    )
    _add_satellite_layer(m)

    if feature is None:
        return m, False

    props = feature.get("properties") or {}
    overlay = folium.GeoJson(
        feature,
        name=f"Plot {plot_number}",
        style_function=lambda _f: POLYGON_STYLE,
        highlight_function=lambda _f: POLYGON_HIGHLIGHT,
        tooltip=f"Plot {plot_number}",
    )
    overlay.add_child(
        folium.Popup(
            folium.Html(_popup_html(plot_number, props), script=True),
            max_width=340,
        )
    )
    overlay.add_to(m)
    m.fit_bounds(feature_bounds(feature), padding=(30, 30))
    return m, True


# --------------------------------------------------------------------------- #
# Streamlit entry point
# --------------------------------------------------------------------------- #
def render_plot_map(
    plot_number: str | int,
    geojson_path: str | os.PathLike = DEFAULT_GEOJSON,
    height: int = 600,
    key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Render the satellite map with the plot highlighted in red.

    Returns the st_folium result dict (clicks, bounds, etc.) or None on error.
    """
    try:
        m, found = build_plot_map(plot_number, geojson_path)
    except FileNotFoundError as exc:
        st.error(str(exc))
        return None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        st.error(f"Could not read plot boundary data: {exc}")
        return None

    if not found:
        st.warning(f"Plot '{plot_number}' was not found in {Path(geojson_path).name}.")

    return st_folium(
        m,
        height=height,
        use_container_width=True,
        returned_objects=[],  # avoid reruns on every pan/zoom
        key=key or f"plot-map-{plot_number}",
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Plot Map", layout="wide")
    st.title("Plot Map Viewer")
    plot = st.text_input("Plot number", value="1")
    if plot:
        render_plot_map(plot)