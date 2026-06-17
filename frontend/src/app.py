import json
import os
import urllib.parse
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
import altair as alt
import folium
from folium import GeoJson
from folium.map import CustomPane

from maplibre import Map, MapOptions
from maplibre.controls import NavigationControl, ScaleControl
from maplibre.layer import Layer, LayerType
from maplibre.sources import GeoJSONSource, RasterTileSource, VectorTileSource
from maplibre.streamlit import st_maplibre

from config import settings

MONTH_LABELS = [
    "Sty", "Lut", "Mar", "Kwi", "Maj", "Cze",
    "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru",
]

LUBELSKIE_CENTER = [22.57, 51.25]
CARTO_POSITRON = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
CARTO_POSITRON_XY = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
# bbox sluzy WYLACZNIE do wyszukiwania scen w STAC (zapytanie wymaga prostokata).
# Do wyswietlania obraz jest przycinany do realnych granic (patrz load_boundary()).
LUBELSKIE_BBOX = [21.5, 50.2, 24.2, 52.3]

# Kafle MGRS Sentinel-2 nachodzace na woj. lubelskie (bbox STAC 21.5–24.2°E, 50.2–52.3°N).
# Wczesniej bylo 9 kafli — brakowalo m.in. 34UEA (polnocny zachod) i 34UGC/35ULU.
LUBELSKIE_MGRS_TILES = frozenset({
    "MGRS-34UEA", "MGRS-34UEB", "MGRS-34UEC", "MGRS-34UED",
    "MGRS-34UFA", "MGRS-34UFB", "MGRS-34UFC", "MGRS-34UFD",
    "MGRS-34UGA", "MGRS-34UGB", "MGRS-34UGC", "MGRS-34UGD",
    "MGRS-35ULR", "MGRS-35ULS", "MGRS-35ULT", "MGRS-35ULU",
})
LUBELSKIE_MGRS_TILE_COUNT = len(LUBELSKIE_MGRS_TILES)

# STAC Earth Search uzywa 35UL*; starsze aliasy 35UK* mapujemy na te same kafle.
STAC_TO_MGRS_TILE = {
    "MGRS-35UKR": "MGRS-35ULR",
    "MGRS-35UKS": "MGRS-35ULS",
}


def _is_lubelskie_mgrs_tile(tile: str) -> bool:
    return tile in LUBELSKIE_MGRS_TILES

# Szeroki bbox warstwy mozaiki (TiTiler skleja COG po quadkey, bez nakladania warstw).
MOSAIC_BOUNDS = (20.95, 49.43, 25.85, 52.40)
MOSAIC_TILE_SIZE = 512
MOSAIC_MAX_ZOOM = 13

# --- Sentinel-2 (Element84 Earth Search) ---------------------------------------

SENTINEL_STAC_URL = "https://earth-search.aws.element84.com/v1"
SENTINEL_COLLECTION = "sentinel-2-l2a"

# Granica woj. lubelskiego (GeoJSON). Kolejnosc sprawdzania:
#   1) zmienna srodowiskowa BOUNDARY_GEOJSON
#   2) data/lubelskie_boundary.geojson w katalogu repo / frontendu / obok app.py
_BOUNDARY_CANDIDATES = [
    os.getenv("BOUNDARY_GEOJSON"),
    str(Path(__file__).resolve().parents[2] / "data" / "lubelskie_boundary.geojson"),
    str(Path(__file__).resolve().parents[1] / "data" / "lubelskie_boundary.geojson"),
    str(Path(__file__).resolve().parent / "lubelskie_boundary.geojson"),
]

# Pierscien "calego swiata" - zewnetrzny obrys maski (w jego srodku wycinamy dziure).
_WORLD_RING = [[-180.0, -85.0], [180.0, -85.0], [180.0, 85.0], [-180.0, 85.0], [-180.0, -85.0]]


# --- Helpers -------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_stac_collections() -> list[dict]:
    try:
        return httpx.get(f"{settings.stac_api_url}/collections", timeout=5).json().get("collections", [])
    except httpx.RequestError:
        return []


@st.cache_data(ttl=60)
def fetch_stations() -> list[dict]:
    try:
        return httpx.get(f"{settings.backend_url}/cells/stations", timeout=5).json()
    except httpx.RequestError:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_station_points() -> dict | None:
    """GeoJSON punktow stacji eDWIN (latitude/longitude z Voronoi)."""
    try:
        resp = httpx.get(f"{settings.backend_url}/cells/stations/points", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            return data
    except httpx.HTTPError:
        pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_cells_geojson_map() -> dict | None:
    """Uproszczone strefy stacji pod Folium."""
    try:
        resp = httpx.get(f"{settings.backend_url}/cells/geojson/map", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            return data
    except httpx.HTTPError:
        pass
    return None


def resolve_station_at(lon: float, lat: float) -> dict | None:
    try:
        resp = httpx.get(
            f"{settings.backend_url}/cells/at-point",
            params={"lon": lon, "lat": lat},
            timeout=5,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


@st.cache_data(ttl=60)
def fetch_stac_items(collection_id: str) -> list[dict]:
    try:
        return httpx.get(
            f"{settings.stac_api_url}/collections/{collection_id}/items", timeout=5
        ).json().get("features", [])
    except httpx.RequestError:
        return []


@st.cache_data(ttl=300)
def search_sentinel(date_start: str, date_end: str, max_cloud: int) -> list[dict]:
    """Szuka scen Sentinel-2 L2A w STAC Earth Search dla bboxu woj. lubelskiego."""
    try:
        resp = httpx.post(
            f"{SENTINEL_STAC_URL}/search",
            json={
                "collections": [SENTINEL_COLLECTION],
                "bbox": LUBELSKIE_BBOX,
                "datetime": f"{date_start}T00:00:00Z/{date_end}T23:59:59Z",
                "query": {"eo:cloud_cover": {"lt": max_cloud}},
                "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                "limit": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except httpx.HTTPError:
        return []

    return [
        feat
        for feat in features
        if feat.get("collection") == SENTINEL_COLLECTION
        and feat.get("assets", {}).get("visual", {}).get("href")
    ]


@st.cache_data(ttl=3600)
def request_mosaic_file(cog_urls: tuple[str, ...]) -> str | None:
    """Buduje (lub zwraca z cache) MosaicJSON dla listy COG — jedna warstwa na mapie."""
    if not cog_urls:
        return None
    try:
        resp = httpx.post(
            f"{settings.backend_url}/mosaic",
            json={"urls": list(cog_urls)},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json().get("mosaic_url")
    except httpx.HTTPError:
        return None


def _mgrs_tile_id(feat: dict) -> str:
    code = feat.get("properties", {}).get("grid:code")
    if code:
        return STAC_TO_MGRS_TILE.get(code, code)
    parts = feat.get("id", "").split("_")
    if len(parts) >= 2 and len(parts[1]) == 5:
        raw = f"MGRS-{parts[1]}"
        return STAC_TO_MGRS_TILE.get(raw, raw)
    return feat.get("id", "")


def _nodata_pct(feat: dict) -> float:
    """Procent pustych pikseli sceny (krawedz pasa orbity = wysoki nodata)."""
    return float(feat["properties"].get("s2:nodata_pixel_percentage") or 0.0)


def _scene_platform(feat: dict) -> str:
    """S2A / S2B / S2C — platforma Sentinel-2 ze STAC lub z id sceny."""
    parts = feat.get("id", "").split("_")
    if parts and parts[0].startswith("S2") and len(parts[0]) == 3:
        return parts[0]
    platform = (feat.get("properties", {}).get("platform") or "").lower()
    for key, label in (
        ("sentinel-2a", "S2A"),
        ("sentinel-2b", "S2B"),
        ("sentinel-2c", "S2C"),
    ):
        if key in platform:
            return label
    return "?"


def best_scene_per_tile(features: list[dict]) -> dict[str, dict]:
    """Dla kazdego kafla MGRS najlepsza scena z zakresu dat (S2A, S2B, S2C).

    Kryterium: najpierw najmniej pustych pikseli, potem najmniej chmur.
    Satelita nie ma znaczenia — wybierana jest po prostu najlepsza scena.
    """
    best: dict[str, dict] = {}
    for feat in features:
        tile = _mgrs_tile_id(feat)
        if not _is_lubelskie_mgrs_tile(tile):
            continue
        cloud = feat["properties"].get("eo:cloud_cover") or 0.0
        score = (_nodata_pct(feat), cloud)
        current = best.get(tile)
        if current is None:
            best[tile] = feat
            continue
        cur_score = (_nodata_pct(current), current["properties"].get("eo:cloud_cover") or 0.0)
        if score < cur_score:
            best[tile] = feat
    return best


@st.cache_data(ttl=3600)
def fetch_mosaic_bounds(mosaic_file_url: str) -> tuple[float, float, float, float] | None:
    try:
        resp = httpx.get(
            f"{settings.public_titiler_url}/mosaicjson/info",
            params={"url": mosaic_file_url},
            timeout=30,
        )
        resp.raise_for_status()
        bounds = resp.json().get("bounds")
        if bounds and len(bounds) == 4:
            return tuple(bounds)
    except httpx.HTTPError:
        pass
    return None


@st.cache_data
def load_boundary() -> dict | None:
    """Wczytuje GeoJSON granicy woj. lubelskiego z pierwszej dostepnej lokalizacji."""
    for path in _BOUNDARY_CANDIDATES:
        if path and Path(path).is_file():
            try:
                return json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _exterior_rings(geojson: dict) -> list[list]:
    """Zwraca zewnetrzne pierscienie wszystkich poligonow (obsluga Multi/Feature/FC)."""
    if geojson.get("type") == "FeatureCollection":
        feats = geojson.get("features", [])
    elif geojson.get("type") == "Feature":
        feats = [geojson]
    else:  # samo geometry
        feats = [{"geometry": geojson}]

    rings: list[list] = []
    for feat in feats:
        geom = feat.get("geometry", feat)
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype == "Polygon" and coords:
            rings.append(coords[0])
        elif gtype == "MultiPolygon":
            for poly in coords:
                if poly:
                    rings.append(poly[0])
    return rings


def build_inverse_mask(boundary: dict) -> dict:
    """Buduje maske: prostokat 'swiata' z dziura w ksztalcie granicy.

    Wyrysowana na wierzchu rastra zaslania wszystko POZA granica - dzieki temu
    obraz satelitarny widac tylko w obrebie wojewodztwa (zamiast prostokata).
    """
    holes = _exterior_rings(boundary)
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [_WORLD_RING, *holes]},
    }


# --- Tab: Mapa -----------------------------------------------------------------


def add_boundary_clip(m: Map, boundary: dict, mask_color: str = "#f2f2ee") -> None:
    """Dodaje maske przycinajaca + obrys granicy. Wywolac PO dodaniu rastra."""
    m.add_source("aoi-mask", GeoJSONSource(data=build_inverse_mask(boundary)))
    m.add_layer(Layer(
        type=LayerType.FILL,
        id="aoi-mask-fill",
        source="aoi-mask",
        paint={"fill-color": mask_color, "fill-opacity": 1.0},
    ))
    m.add_source("aoi-outline", GeoJSONSource(data=boundary))
    m.add_layer(Layer(
        type=LayerType.LINE,
        id="aoi-outline-line",
        source="aoi-outline",
        paint={"line-color": "#c0392b", "line-width": 1.5},
    ))


def mosaic_tile_url(mosaic_file_url: str, *, tile_size: int = MOSAIC_TILE_SIZE) -> str:
    """Jedna warstwa XYZ — TiTiler laczy COG w mozaice (brak 9 nakladajacych sie rastrów)."""
    return (
        f"{settings.public_titiler_url}"
        f"/mosaicjson/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}"
        f"?url={urllib.parse.quote(mosaic_file_url, safe='')}"
        f"&format=png&tilesize={tile_size}&resampling=lanczos&pixel_selection=first"
    )


def build_map(
    *,
    mosaic_url: str | None = None,
    mosaic_bounds: tuple[float, float, float, float] | None = None,
    boundary: dict | None = None,
    clip_boundary: bool = True,
    show_weather_cells: bool = True,
    show_station_pins: bool = True,
    show_satellite: bool = True,
    selected_station_id: str | None = None,
    station_points: dict | None = None,
) -> Map:
    has_mosaic = bool(mosaic_url)
    sat_on = has_mosaic and show_satellite

    m = Map(MapOptions(
        center=LUBELSKIE_CENTER,
        zoom=8,
        min_zoom=0,
        max_zoom=16,
        style=CARTO_POSITRON,
    ))
    m.add_control(NavigationControl())
    m.add_control(ScaleControl())

    if has_mosaic:
        raster_bounds = mosaic_bounds or MOSAIC_BOUNDS
        m.add_source("s2-mosaic", RasterTileSource(
            tiles=[mosaic_tile_url(mosaic_url)],
            tile_size=MOSAIC_TILE_SIZE,
            scheme="xyz",
            bounds=raster_bounds,
            max_zoom=MOSAIC_MAX_ZOOM,
            min_zoom=0,
        ))
        m.add_layer(Layer(
            type=LayerType.RASTER,
            id="s2-mosaic-layer",
            source="s2-mosaic",
            paint={
                "raster-opacity": 1.0 if sat_on else 0.0,
                "raster-fade-duration": 0,
            },
        ))

    if show_weather_cells:
        tipg_tiles = (
            f"{settings.public_tipg_url}"
            "/collections/app.weather_cells/tiles/WebMercatorQuad/{z}/{x}/{y}"
        )
        cell_opacity = 0.20 if sat_on else 0.30
        m.add_source("weather-cells", VectorTileSource(tiles=[tipg_tiles]))
        m.add_layer(Layer(
            type=LayerType.FILL,
            id="weather-cells-fill",
            source="weather-cells",
            source_layer="default",
            paint={"fill-color": "#4a90d9", "fill-opacity": cell_opacity},
        ))
        m.add_layer(Layer(
            type=LayerType.LINE,
            id="weather-cells-line",
            source="weather-cells",
            source_layer="default",
            paint={"line-color": "#2c5282", "line-width": 1},
        ))
        if selected_station_id:
            m.add_layer(Layer(
                type=LayerType.FILL,
                id="weather-cells-highlight",
                source="weather-cells",
                source_layer="default",
                filter=["==", ["get", "station_id"], selected_station_id],
                paint={"fill-color": "#4a90d9", "fill-opacity": min(cell_opacity + 0.15, 0.9)},
            ))
            m.add_layer(Layer(
                type=LayerType.LINE,
                id="weather-cells-highlight-line",
                source="weather-cells",
                source_layer="default",
                filter=["==", ["get", "station_id"], selected_station_id],
                paint={"line-color": "#2c5282", "line-width": 2},
            ))
        m.add_tooltip(
            "weather-cells-fill",
            template="{{ station_name }}{{# bloom_start_date }} · {{ bloom_start_date }} – {{ bloom_end_date }}{{/ bloom_start_date }}",
        )
        m.add_popup(
            "weather-cells-fill",
            template=(
                "<b>{{ station_name }}</b><br>"
                "{{# bloom_start_date }}Kwitnienie: {{ bloom_start_date }} – {{ bloom_end_date }}"
                "{{/ bloom_start_date }}"
                "{{^ bloom_start_date }}{{ bloom_tooltip }}{{/ bloom_start_date }}"
            ),
        )

    if show_station_pins and station_points:
        m.add_source("station-pins", GeoJSONSource(data=station_points))
        m.add_layer(Layer(
            type=LayerType.CIRCLE,
            id="station-pins-circle",
            source="station-pins",
            paint={
                "circle-radius": 6,
                "circle-color": "#e74c3c",
                "circle-stroke-color": "#922b21",
                "circle-stroke-width": 1.5,
                "circle-opacity": 0.95,
            },
        ))
        if selected_station_id:
            m.add_layer(Layer(
                type=LayerType.CIRCLE,
                id="station-pins-selected",
                source="station-pins",
                filter=["==", ["get", "station_id"], selected_station_id],
                paint={
                    "circle-radius": 9,
                    "circle-color": "#c0392b",
                    "circle-stroke-color": "#641e16",
                    "circle-stroke-width": 2.5,
                    "circle-opacity": 1.0,
                },
            ))
        m.add_tooltip("station-pins-circle", template="{{ station_name }} ({{ station_id }})")

    if boundary and clip_boundary and sat_on:
        add_boundary_clip(m, boundary)
    elif boundary:
        m.add_source("aoi-outline", GeoJSONSource(data=boundary))
        m.add_layer(Layer(
            type=LayerType.LINE,
            id="aoi-outline-line",
            source="aoi-outline",
            paint={"line-color": "#c0392b", "line-width": 1.5},
        ))

    return m


_BOUNDARY_MASK_COLOR = "#f2f2ee"
_BOUNDARY_MASK_PANE = "boundaryMask"
_SATELLITE_PANE = "satelliteRaster"
_FOLIUM_TILE_SIZE = 256


def _disable_geojson_layer(_feature, layer) -> None:
    layer.interactive = False
    layer.options["interactive"] = False


def _boundary_mask_style(_feature) -> dict:
    return {
        "fillColor": _BOUNDARY_MASK_COLOR,
        "fillOpacity": 1.0,
        "color": "#c0392b",
        "weight": 1.5,
        "fillRule": "evenodd",
    }


def _make_cells_style(selected_id: str | None, *, on_satellite: bool):
    fill_opacity = 0.20 if on_satellite else 0.30
    sel_opacity = min(fill_opacity + 0.15, 0.9)

    def style(feature) -> dict:
        props = feature.get("properties", {}) or {}
        is_sel = bool(selected_id) and props.get("station_id") == selected_id
        return {
            "fillColor": "#4a90d9",
            "color": "#2c5282" if is_sel else "#3d6f9c",
            "weight": 2 if is_sel else 1,
            "fillOpacity": sel_opacity if is_sel else fill_opacity,
            "opacity": 0.9,
        }

    return style


def _cells_on_each_feature(feature, layer) -> None:
    props = feature.get("properties", {}) or {}
    name = props.get("station_name") or props.get("station_id") or ""
    if props.get("bloom_start_date") and props.get("bloom_end_date"):
        tip = f"{name} · {props['bloom_start_date']} – {props['bloom_end_date']}"
    else:
        tip = props.get("bloom_tooltip") or name
    layer.bind_tooltip(tip)


def _attach_map_resize_fix(m: folium.Map) -> None:
    """Bezpieczne invalidateSize tylko dla tej mapy Folium (nie skanuje calego window)."""
    map_var = m.get_name()
    m.get_root().html.add_child(folium.Element(f"""
<script>
(function() {{
  var tries = 0;
  var timer = setInterval(function() {{
    try {{
      var map = {map_var};
      if (map && map.invalidateSize) map.invalidateSize(true);
    }} catch (e) {{}}
    if (++tries > 10) clearInterval(timer);
  }}, 250);
}})();
</script>
"""))


def _station_at_pin(lon: float, lat: float) -> dict | None:
    """Dopasowuje klikniecie pinezki do najblizszej stacji eDWIN."""
    points = fetch_station_points()
    if not points:
        return None
    best: dict | None = None
    best_dist = 0.03 ** 2
    for feature in points.get("features", []):
        slon, slat = feature["geometry"]["coordinates"]
        dist = (slon - lon) ** 2 + (slat - lat) ** 2
        if dist < best_dist:
            best_dist = dist
            props = feature["properties"]
            best = {
                "station_id": props["station_id"],
                "station_name": props.get("station_name", props["station_id"]),
            }
    return best


def _add_station_pins(
    m: folium.Map,
    station_points: dict,
    selected_id: str | None,
) -> None:
    group = folium.FeatureGroup(name="Stacje eDWIN", show=True)

    for feature in station_points.get("features", []):
        props = feature.get("properties", {})
        sid = props.get("station_id", "")
        selected = sid == selected_id
        lon, lat = feature["geometry"]["coordinates"]
        folium.CircleMarker(
            location=[lat, lon],
            radius=9 if selected else 7,
            color="#641e16" if selected else "#922b21",
            weight=2 if selected else 1.5,
            fill=True,
            fill_color="#c0392b" if selected else "#e74c3c",
            fill_opacity=0.95,
            tooltip=f"{props.get('station_name', '')} ({sid})",
        ).add_to(group)

    group.add_to(m)


def build_folium_map(
    boundary: dict | None,
    selected_id: str | None,
    *,
    mosaic_url: str | None = None,
    clip_boundary: bool = True,
    show_cells: bool = True,
    show_station_pins: bool = True,
    show_satellite: bool = True,
    station_points: dict | None = None,
    cells_geojson: dict | None = None,
) -> folium.Map:
    has_mosaic = bool(mosaic_url)
    sat_on = has_mosaic and show_satellite

    m = folium.Map(
        location=[51.25, 22.57],
        zoom_start=8,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )

    if has_mosaic:
        CustomPane(_SATELLITE_PANE, z_index=250).add_to(m)
        folium.TileLayer(
            tiles=mosaic_tile_url(mosaic_url, tile_size=_FOLIUM_TILE_SIZE),
            attr="Sentinel-2 © ESA",
            name="Sentinel-2",
            overlay=True,
            control=False,
            show=True,
            opacity=1.0 if sat_on else 0.0,
            min_zoom=7,
            max_native_zoom=MOSAIC_MAX_ZOOM,
            max_zoom=16,
            pane=_SATELLITE_PANE,
        ).add_to(m)

    if boundary and clip_boundary and sat_on:
        CustomPane(_BOUNDARY_MASK_PANE, z_index=350).add_to(m)
        GeoJson(
            build_inverse_mask(boundary),
            name="Przyciecie do granic",
            style_function=_boundary_mask_style,
            pane=_BOUNDARY_MASK_PANE,
            zoom_on_click=False,
        ).add_to(m)

    if boundary and not (clip_boundary and sat_on):
        GeoJson(
            boundary,
            name="Granica woj.",
            style_function=lambda _f: {
                "color": "#c0392b",
                "weight": 1.5,
                "fillOpacity": 0,
            },
            on_each_feature=_disable_geojson_layer,
            zoom_on_click=False,
        ).add_to(m)

    if show_cells and cells_geojson:
        GeoJson(
            cells_geojson,
            name="Strefy stacji",
            style_function=_make_cells_style(selected_id, on_satellite=sat_on),
            on_each_feature=_cells_on_each_feature,
            zoom_on_click=False,
        ).add_to(m)

    if show_station_pins and station_points:
        _add_station_pins(m, station_points, selected_id)

    _attach_map_resize_fix(m)

    return m


def handle_station_map_click(map_output: dict | None) -> None:
    if not map_output:
        return

    hit = None
    lat = lon = None

    obj = map_output.get("last_object_clicked")
    if obj:
        props = obj.get("properties") or {}
        lat, lon = obj.get("lat"), obj.get("lng")
        if "station_id" in props:
            hit = {
                "station_id": props["station_id"],
                "station_name": props.get("station_name", props["station_id"]),
            }

    if not hit:
        pt = map_output.get("last_clicked")
        if pt:
            lat, lon = pt.get("lat"), pt.get("lng")
            if lat is not None and lon is not None:
                hit = _station_at_pin(lon, lat) or resolve_station_at(lon, lat)

    if not hit or lat is None or lon is None:
        return
    key = f"{lat:.5f},{lon:.5f}"
    if key == st.session_state.get("map_click_key"):
        return
    st.session_state["map_click_key"] = key
    st.session_state["map_selected_station"] = hit
    st.session_state["map_station_select"] = hit["station_id"]
    st.rerun()


def _search_fingerprint(date_start: date, date_end: date, max_cloud: int) -> str:
    return f"{date_start.isoformat()}|{date_end.isoformat()}|{max_cloud}"


@st.cache_data(ttl=3600)
def fetch_honey_plants() -> list[dict]:
    try:
        resp = httpx.get(f"{settings.backend_url}/blooming/plants", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return []


@st.cache_data(ttl=3600)
def fetch_station_monthly(
    station_id: str, year: int, plant_id: str,
) -> tuple[dict | None, str | None]:
    try:
        resp = httpx.get(
            f"{settings.backend_url}/cells/stations/{station_id}/monthly",
            params={"year": year, "plant_id": plant_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPError as exc:
        detail = ""
        if hasattr(exc, "response") and exc.response is not None:
            detail = exc.response.text[:300]
        return None, str(exc) if not detail else detail


def _monthly_df(months: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(months).sort_values("month")
    df["miesiac"] = df["month"].apply(lambda m: f"{m:02d}. {MONTH_LABELS[m - 1]}")
    return df


def _month_order(df: pd.DataFrame) -> list[str]:
    return df["miesiac"].tolist()


def _temp_chart(df: pd.DataFrame) -> alt.Chart:
    order = _month_order(df)
    vals = df["t_mean"].dropna()
    pad = max(1.0, float(vals.max() - vals.min()) * 0.15) if len(vals) else 2.0
    y_lo = float(vals.min() - pad) if len(vals) else 0.0
    y_hi = float(vals.max() + pad) if len(vals) else 10.0
    return (
        alt.Chart(df)
        .mark_line(color="#4a90d9", point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X("miesiac:N", sort=order, title=None),
            y=alt.Y("t_mean:Q", title="°C", scale=alt.Scale(domain=[y_lo, y_hi], nice=False)),
            tooltip=[alt.Tooltip("miesiac:N"), alt.Tooltip("t_mean:Q", format=".1f", title="°C")],
        )
        .properties(height=240)
    )


def _precip_chart(df: pd.DataFrame) -> alt.Chart:
    order = _month_order(df)
    y_max = float(df["precip_mm"].max()) * 1.2 if df["precip_mm"].notna().any() else 10.0
    return (
        alt.Chart(df)
        .mark_bar(color="#5dade2")
        .encode(
            x=alt.X("miesiac:N", sort=order, title=None),
            y=alt.Y(
                "precip_mm:Q",
                title="mm",
                scale=alt.Scale(domain=[0, max(y_max, 1)], nice=False),
            ),
            tooltip=[alt.Tooltip("miesiac:N"), alt.Tooltip("precip_mm:Q", format=".1f", title="mm")],
        )
        .properties(height=240)
    )


def _gdd_chart(
    df: pd.DataFrame,
    gdd_min: float | None = None,
    gdd_max: float | None = None,
) -> alt.Chart:
    order = _month_order(df)
    if "gdd_cumulative" not in df.columns or df["gdd_cumulative"].isna().all():
        df = df.copy()
        df["gdd_cumulative"] = df["gdd_monthly"].fillna(0).cumsum()

    vals = df["gdd_cumulative"].dropna()
    data_max = float(vals.max()) if len(vals) else 0.0
    threshold_max = max(gdd_min or 0, gdd_max or 0)
    y_hi = max(data_max * 1.1, threshold_max * 1.25, 10.0)

    line = (
        alt.Chart(df)
        .mark_line(color="#27ae60", point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X("miesiac:N", sort=order, title=None),
            y=alt.Y(
                "gdd_cumulative:Q",
                title="GDD",
                scale=alt.Scale(domain=[0, y_hi], nice=False),
            ),
            tooltip=[
                alt.Tooltip("miesiac:N"),
                alt.Tooltip("gdd_cumulative:Q", format=".0f", title="GDD skumulowane"),
            ],
        )
        .properties(height=260)
    )

    if gdd_min is None and gdd_max is None:
        return line

    rules_rows = []
    if gdd_min is not None:
        rules_rows.append({"y": gdd_min, "label": "Próg kwitnienia od"})
    if gdd_max is not None:
        rules_rows.append({"y": gdd_max, "label": "Próg kwitnienia do"})
    rules = (
        alt.Chart(pd.DataFrame(rules_rows))
        .mark_rule(color="#e67e22", strokeDash=[6, 4], opacity=0.85)
        .encode(
            y="y:Q",
            tooltip=[
                alt.Tooltip("label:N"),
                alt.Tooltip("y:Q", format=".0f", title="GDD"),
            ],
        )
    )
    return line + rules


def render_station_meteo_charts(station_id: str, year: int) -> None:
    """Temperatura i opady — niezalezne od rosliny."""
    summary, err = fetch_station_monthly(station_id, year, "salix_caprea")
    if not summary:
        st.error(f"Blad danych: {err or 'nieznany'}")
        return

    months = summary.get("months", [])
    if not months:
        st.warning("Brak pomiarow w tym roku.")
        return

    df = _monthly_df(months)
    st.caption(f"{summary.get('day_count', 0)} dni pomiarow • rok {year}")

    t_ann = summary.get("t_mean_annual")
    precip = summary.get("precip_annual")
    c1, c2 = st.columns(2)
    c1.metric("Sr. temp. roczna", f"{t_ann:.1f} °C" if t_ann is not None else "—")
    c2.metric("Opady roczne", f"{precip:.0f} mm" if precip is not None else "—")

    st.markdown("**Srednia temperatura w miesiacu**")
    st.altair_chart(_temp_chart(df), use_container_width=True)

    st.markdown("**Opady — suma miesieczna**")
    if df["precip_mm"].notna().any():
        st.altair_chart(_precip_chart(df), use_container_width=True)
    else:
        st.caption("Brak lokalnych danych opadow.")


def render_plant_gdd_panel(station_id: str, year: int) -> None:
    plants = fetch_honey_plants()
    if not plants:
        st.warning("Brak slownika roslin miododajnych w bazie.")
        return

    labels = {p["id"]: f"{p['name_pl']} ({p['name_latin']})" for p in plants}
    plant_id = st.selectbox(
        "Roslina miododajna",
        options=[p["id"] for p in plants],
        format_func=lambda pid: labels[pid],
        key="map_plant_select",
    )
    plant = next(p for p in plants if p["id"] == plant_id)

    summary, err = fetch_station_monthly(station_id, year, plant_id)
    if not summary:
        st.error(f"Blad danych GDD: {err or 'nieznany'}")
        return

    months = summary.get("months", [])
    if not months:
        st.warning("Brak danych GDD dla tej rosliny w wybranym roku.")
        return

    df = _monthly_df(months)
    gdd_max = summary.get("gdd_max")
    gdd_min_p = plant.get("gdd_min", 100)
    gdd_max_p = plant.get("gdd_max", 200)
    base = plant.get("base_temp_c", 5)

    c1, c2, c3 = st.columns(3)
    c1.metric("GDD skumulowane (max)", f"{gdd_max:.0f}" if gdd_max is not None else "—")
    c2.metric("Prog kwitnienia od", f"{gdd_min_p:.0f} GDD")
    c3.metric("Prog kwitnienia do", f"{gdd_max_p:.0f} GDD")

    if gdd_max is not None:
        if gdd_max < gdd_min_p:
            bloom_status = "Przed kwitnieniem"
        elif gdd_max <= gdd_max_p:
            bloom_status = "W okresie kwitnienia"
        else:
            bloom_status = "Po kwitnieniu"
    else:
        bloom_status = "—"
    st.caption(
        f"Temperatura bazowa: {base} °C • sezon: {plant.get('season', '—')} • "
        f"status w {year}: **{bloom_status}**"
    )

    st.markdown(f"**GDD skumulowane — {plant['name_pl']}**")
    st.altair_chart(
        _gdd_chart(df, gdd_min=gdd_min_p, gdd_max=gdd_max_p),
        use_container_width=True,
    )
    st.caption(
        "Linia pokazuje narastanie GDD od stycznia. Pomarańczowe linie — próg kwitnienia."
    )


def _station_label(station: dict) -> str:
    return station.get("station_name") or station.get("station_id") or "—"


def render_map_tab() -> None:
    st.subheader("Mapa")

    boundary = load_boundary()
    if boundary is None:
        st.warning(
            "Brak pliku `data/lubelskie_boundary.geojson` — obraz satelitarny nie "
            "zostanie przyciety do granic wojewodztwa."
        )

    stations = fetch_stations()
    station_by_id = {
        s["station_id"]: s for s in stations if s.get("station_id")
    }

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.0, 1.0, 1.2, 0.8])
        with c1:
            date_start = st.date_input("Od", value=date(2024, 8, 27), key="map_sat_start")
        with c2:
            date_end = st.date_input("Do", value=date(2024, 8, 29), key="map_sat_end")
        with c3:
            max_cloud = st.slider("Maks. chmury (%)", 0, 100, 20, key="map_sat_cloud")
        with c4:
            st.number_input(
                "Rok meteo",
                min_value=2020,
                max_value=2030,
                value=2025,
                step=1,
                key="map_meteo_year",
            )

        if date_end < date_start:
            st.error("Data „Do” musi byc nie wczesniejsza niz „Od”.")
            date_end = date_start

        fingerprint = _search_fingerprint(date_start, date_end, max_cloud)

        if st.button("Szukaj scen", type="primary", key="map_sat_search"):
            with st.spinner("Szukam scen Sentinel-2 (S2A / S2B / S2C)..."):
                st.session_state["sat_scenes"] = search_sentinel(
                    date_start.isoformat(), date_end.isoformat(), max_cloud
                )
            st.session_state["sat_date_fingerprint"] = fingerprint
            st.session_state.pop("map_mosaic_url", None)
            st.session_state.pop("map_mosaic_bounds", None)
            st.session_state.pop("map_mosaic_cog_key", None)
            st.rerun()

        scenes: list[dict] = []
        if st.session_state.get("sat_date_fingerprint") == fingerprint:
            scenes = st.session_state.get("sat_scenes", [])
        elif st.session_state.get("sat_scenes"):
            st.info("Filtry sie zmienily — kliknij „Szukaj scen”, aby odswiezyc wyniki.")

        satellite_scenes: dict[str, dict] = {}
        if scenes:
            satellite_scenes = best_scene_per_tile(scenes)
            span_days = (date_end - date_start).days + 1
            st.caption(
                f"Dla kazdego kafla MGRS wybrano najlepsza scene z przedzialu "
                f"**{date_start.isoformat()} – {date_end.isoformat()}** ({span_days} dni). "
                f"Satelity S2A, S2B i S2C sa traktowane rownowaznie "
                f"(najpierw najmniej pustych pikseli, potem najmniej chmur)."
            )

        covered = len(satellite_scenes)
        missing = sorted(t.replace("MGRS-", "") for t in LUBELSKIE_MGRS_TILES
                         if t not in satellite_scenes)

        if satellite_scenes:
            clouds = [f["properties"].get("eo:cloud_cover") or 0 for f in satellite_scenes.values()]
            avg = sum(clouds) / len(clouds)
            mx = max(clouds)
            max_nodata = max(_nodata_pct(f) for f in satellite_scenes.values())
            dates_used = sorted(
                {f["properties"].get("datetime", "")[:10] for f in satellite_scenes.values()}
            )
            platforms_used = sorted({_scene_platform(f) for f in satellite_scenes.values()})
            scope = (
                f"**{date_start.isoformat()} – {date_end.isoformat()}** • "
                f"{len(dates_used)} dat • {', '.join(platforms_used)}"
            )
            partial_tiles = sorted(
                t.replace("MGRS-", "")
                for t, f in satellite_scenes.items()
                if _nodata_pct(f) > 5.0
            )
            if covered == LUBELSKIE_MGRS_TILE_COUNT:
                st.success(
                    f"{scope}: {covered}/{LUBELSKIE_MGRS_TILE_COUNT} kafli MGRS • "
                    f"srednie zachmurzenie {avg:.1f}% (max {mx:.1f}%) • "
                    f"max pustych pikseli {max_nodata:.0f}%."
                )
            else:
                st.warning(
                    f"{scope}: pokrycie {covered}/{LUBELSKIE_MGRS_TILE_COUNT}. "
                    f"Brakuje kafli: {', '.join(missing)}. "
                    "Rozszerz przedzial dat lub zwieksz limit chmur, potem kliknij „Szukaj scen”."
                )
            if partial_tiles:
                st.info(
                    "Czesciowe kafle (krawedz orbity, duzo pustych pikseli): "
                    + ", ".join(partial_tiles)
                    + ". W tym przedziale Sentinel nie obrazowal calego zachodu wojewodztwa — "
                    "sprobuj dluzszego okna (np. 5–7 dni)."
                )
            with st.expander("Szczegoly kafli (data + satelita + zachmurzenie + puste piksele)"):
                for tile in sorted(satellite_scenes):
                    feat = satellite_scenes[tile]
                    p = feat["properties"]
                    st.write(
                        f"`{tile.replace('MGRS-', '')}` — {p.get('datetime', '')[:10]} • "
                        f"{_scene_platform(feat)} • "
                        f"chmury {p.get('eo:cloud_cover', 0):.1f}% • "
                        f"puste {_nodata_pct(feat):.0f}%"
                    )

            cog_urls = tuple(
                sorted(f["assets"]["visual"]["href"] for f in satellite_scenes.values())
            )
            cog_key = "|".join(cog_urls)
            if st.session_state.get("map_mosaic_cog_key") != cog_key:
                st.session_state.pop("map_mosaic_url", None)
                st.session_state.pop("map_mosaic_bounds", None)
                st.session_state["map_mosaic_cog_key"] = cog_key

            if "map_mosaic_url" not in st.session_state:
                with st.spinner("Laduje obraz satelitarny..."):
                    mosaic_url = request_mosaic_file(cog_urls)
                if mosaic_url:
                    st.session_state["map_mosaic_url"] = mosaic_url
                    bounds = fetch_mosaic_bounds(mosaic_url)
                    if bounds:
                        st.session_state["map_mosaic_bounds"] = bounds
                    st.rerun()
                else:
                    st.error(
                        "Nie udalo sie zbudowac mozaiki satelitarnej (backend /mosaic). "
                        "Sprawdz logi backendu."
                    )
        elif st.session_state.get("sat_date_fingerprint") == fingerprint:
            st.info("Brak scen w przedziale — zmien daty lub zwieksz limit chmur.")
        else:
            st.caption("Kliknij „Szukaj scen”, aby naniesc obraz Sentinel na mape.")

    mosaic_url = st.session_state.get("map_mosaic_url")
    mosaic_bounds = st.session_state.get("map_mosaic_bounds")

    lc1, lc2, lc3 = st.columns([1, 1, 1])
    with lc1:
        st.checkbox("Strefy stacji", value=True, key="map_show_stations")
    with lc2:
        st.checkbox("Pinezki eDWIN", value=True, key="map_show_pins")
    with lc3:
        st.checkbox(
            "Sentinel",
            value=True,
            key="map_show_satellite",
            disabled=not bool(mosaic_url),
        )

    # Zawsze przytnij do granicy wojewodztwa gdy jest obraz satelitarny.
    clip_boundary = boundary is not None and bool(mosaic_url)
    show_cells = st.session_state.get("map_show_stations", True)
    show_pins = st.session_state.get("map_show_pins", True)
    show_satellite = st.session_state.get("map_show_satellite", True)
    station_points = fetch_station_points()
    if show_pins and station_points is None:
        st.warning(
            "Brak wspolrzednych stacji eDWIN — sprawdz plik "
            "`data/lubelskie_edwin_voronoi.geojson`."
        )

    col_map, col_charts = st.columns([1.15, 1], gap="medium")

    with col_map:
        station_query = st.text_input(
            "Szukaj stacji",
            placeholder="Wpisz nazwe lub ID, np. Konskowola...",
            key="map_station_search",
        ).strip().lower()

        station_ids = sorted(station_by_id)
        if station_query:
            station_ids = [
                sid
                for sid in station_ids
                if station_query in sid.lower()
                or station_query in _station_label(station_by_id[sid]).lower()
            ]
            if not station_ids:
                st.caption("Brak stacji pasujacych do wyszukiwania.")

        station_id = st.selectbox(
            "Stacja",
            options=[""] + station_ids,
            format_func=lambda sid: (
                "Wybierz stacje z listy..."
                if not sid
                else _station_label(station_by_id[sid])
            ),
            key="map_station_select",
        )
        if station_id:
            st.session_state["map_selected_station"] = {
                "station_id": station_id,
                "station_name": _station_label(station_by_id[station_id]),
            }
        elif not st.session_state.get("map_selected_station"):
            st.session_state.pop("map_selected_station", None)

        st_maplibre(
            build_map(
                mosaic_url=mosaic_url,
                mosaic_bounds=mosaic_bounds,
                boundary=boundary,
                clip_boundary=clip_boundary,
                show_weather_cells=show_cells,
                show_station_pins=show_pins,
                show_satellite=show_satellite,
                selected_station_id=station_id or None,
                station_points=station_points,
            ),
            height=520,
        )

    with col_charts:
        selected = st.session_state.get("map_selected_station")
        if selected:
            chart_year = st.session_state.get("map_meteo_year", 2025)
            st.markdown(f"### {selected['station_name']}")
            st.caption(f"ID: `{selected['station_id']}`")
            render_station_meteo_charts(selected["station_id"], int(chart_year))
        else:
            st.info(
                "Wybierz stacje z listy powyzej, aby zobaczyc temperature i opady."
            )

        if selected:
            with st.container(border=True):
                st.markdown("#### Kwitnienie roslin miododajnych")
                render_plant_gdd_panel(
                    selected["station_id"],
                    int(st.session_state.get("map_meteo_year", 2025)),
                )


# --- Tab: FastAPI --------------------------------------------------------------


def render_fastapi_tab() -> None:
    st.subheader("FastAPI - zapytania przestrzenne do PostGIS")
    st.markdown(
        "Backend laczy dane z PostGIS. Endpoint `GET /cells/at-point` uzywa `ST_Contains`, "
        "a `GET /blooming` zwraca faze kwitnienia wierzby iwy dla wybranej stacji."
    )

    col1, col2 = st.columns(2)
    with col1:
        lon = st.number_input("Longitude", value=22.57, format="%.4f")
    with col2:
        lat = st.number_input("Latitude", value=51.25, format="%.4f")

    if st.button("Znajdz strefe stacji (ST_Contains)"):
        try:
            resp = httpx.get(
                f"{settings.backend_url}/cells/at-point",
                params={"lon": lon, "lat": lat},
                timeout=5,
            )
            if resp.status_code == 404:
                st.warning("Brak strefy dla tego punktu.")
            else:
                data = resp.json()
                st.success(
                    f"Stacja: **{data['station_name']}** ({data['station_id']}), "
                    f"powierzchnia: {data.get('area_ha', 0):.0f} ha"
                )
        except httpx.RequestError as e:
            st.error(f"Blad polaczenia z backendem: {e}")

    with st.expander("Wywolany URL"):
        st.code(f"GET {settings.backend_url}/cells/at-point?lon={lon}&lat={lat}")


# --- Tab: TiTiler --------------------------------------------------------------


STAC_COLLECTION = "lubelskie-dem"


def render_titiler_tab() -> None:
    st.subheader("TiTiler - metadane i statystyki rastra (COG)")

    items = fetch_stac_items(STAC_COLLECTION)
    if not items:
        st.warning("Brak itemow w STAC.")
        return

    item_ids = [item["id"] for item in items]
    selected_id = st.selectbox("Wybierz kafel DEM", item_ids)
    item = next(i for i in items if i["id"] == selected_id)
    cog_url = item["assets"]["visual"]["href"]
    st.markdown(f"**COG URL:** `{cog_url}`")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Pobierz metadane (/cog/info)"):
            try:
                resp = httpx.get(
                    f"{settings.titiler_url}/cog/info",
                    params={"url": cog_url},
                    timeout=15,
                )
                info = resp.json()
                st.json({
                    "bounds": info.get("bounds"),
                    "crs": info.get("crs"),
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "dtype": info.get("dtype"),
                    "nodata_type": info.get("nodata_type"),
                    "band_descriptions": info.get("band_descriptions"),
                })
            except httpx.RequestError as e:
                st.error(str(e))

    with col2:
        if st.button("Pobierz statystyki (/cog/statistics)"):
            try:
                resp = httpx.get(
                    f"{settings.titiler_url}/cog/statistics",
                    params={"url": cog_url},
                    timeout=15,
                )
                st.json(resp.json())
            except httpx.RequestError as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("**Podglad kafla** - TiTiler generuje kafle XYZ na zywo z COG:")
    tile_url = (
        f"{settings.public_titiler_url}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}"
        f"?url={urllib.parse.quote(cog_url, safe='')}&colormap_name=terrain&rescale=100,1000"
    )
    st.code(tile_url)


# --- Tab: STAC -----------------------------------------------------------------


def render_stac_tab() -> None:
    st.subheader("STAC API - katalog danych przestrzennych")

    tab_browse, tab_search = st.tabs(["Przegladarka", "Wyszukiwanie przestrzenne"])

    with tab_browse:
        collections = fetch_stac_collections()
        if not collections:
            st.warning("Brak polaczenia z STAC API lub brak kolekcji.")
            return
        for collection in collections:
            with st.expander(f"Kolekcja: **{collection['id']}**"):
                st.write(collection.get("description", ""))
                items = fetch_stac_items(collection["id"])
                st.write(f"Liczba itemow: **{len(items)}**")
                for item in items:
                    with st.expander(f"Item: {item['id']}"):
                        st.json(item)

    with tab_search:
        st.markdown("STAC `POST /search` - wyszukiwanie po bbox i przedziale czasowym:")
        col1, col2 = st.columns(2)
        with col1:
            bbox_str = st.text_input("bbox (minx,miny,maxx,maxy)", "21.0,50.0,24.5,52.0")
        with col2:
            datetime_str = st.text_input("datetime", "2020-01-01T00:00:00Z/..")

        if st.button("Szukaj w STAC"):
            try:
                bbox = [float(x) for x in bbox_str.split(",")]
                resp = httpx.post(
                    f"{settings.stac_api_url}/search",
                    json={"bbox": bbox, "datetime": datetime_str},
                    timeout=10,
                )
                result = resp.json()
                features = result.get("features", [])
                st.success(f"Znaleziono **{len(features)}** itemow.")
                for feat in features:
                    st.json({"id": feat["id"], "bbox": feat.get("bbox"),
                             "datetime": feat["properties"].get("datetime"),
                             "assets": list(feat.get("assets", {}).keys())})
            except Exception as e:
                st.error(str(e))


# --- Tab: tipg -----------------------------------------------------------------


def render_tipg_tab() -> None:
    st.subheader("tipg - OGC API Features + kafle wektorowe MVT")

    st.markdown(
        "tipg automatycznie odkrywa tabele PostGIS i udostepnia je jako "
        "**OGC API Features** (GeoJSON) i **MVT tiles**."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Kolekcje odkryte w PostGIS:**")
        try:
            resp = httpx.get(f"{settings.tipg_url}/collections", timeout=5)
            colls = resp.json().get("collections", [])
            for c in colls:
                st.write(f"- `{c['id']}`")
        except httpx.RequestError as e:
            st.error(str(e))

    with col2:
        st.markdown("**Featury z OGC API Features (`/items`):**")
        try:
            resp = httpx.get(
                f"{settings.tipg_url}/collections/app.weather_cells/items",
                params={"limit": 5},
                timeout=5,
            )
            features = resp.json().get("features", [])
            for f in features:
                props = f["properties"]
                st.write(
                    f"- **{props['station_name']}** ({props['station_id']}) "
                    f"- {props.get('area_ha', 0):.0f} ha"
                )
        except httpx.RequestError as e:
            st.error(str(e))

    st.markdown("---")
    st.markdown("**Format kafla MVT** (uzywany przez MapLibre na mapie):")
    st.code(
        f"{settings.public_tipg_url}"
        "/collections/app.weather_cells/tiles/WebMercatorQuad/{z}/{x}/{y}"
    )
    st.caption("Warstwa w kaflu MVT zawsze nazywa sie `default` (niezaleznie od nazwy tabeli).")


# --- Tab: Kwitnienie -----------------------------------------------------------


def render_blooming_tab() -> None:
    st.subheader("Kwitnienie wierzby iwy")
    st.markdown(
        "Wybierz strefe (stacje pogodowa) i date. "
        "Dane GDD pochodza z pomiarow temperatury stacji PME/IUNG (styczen-czerwiec 2025)."
    )

    stations = fetch_stations()
    if not stations:
        st.warning("Brak listy stacji z backendu.")
        return

    station_labels = {
        s["station_id"]: f"{s['station_name']} ({s['station_id']})" for s in stations
    }
    station_ids = [s["station_id"] for s in stations]

    col1, col2 = st.columns(2)
    with col1:
        selected_id = st.selectbox(
            "Stacja / strefa",
            station_ids,
            format_func=lambda s: station_labels[s],
        )
    with col2:
        query_date = st.date_input("Data", value=date(2025, 4, 15))

    if st.button("Sprawdz kwitnienie"):
        try:
            resp = httpx.get(
                f"{settings.backend_url}/blooming/",
                params={
                    "station_id": selected_id,
                    "date": query_date.isoformat(),
                    "plant_id": "salix_caprea",
                },
                timeout=5,
            )
            if resp.status_code == 404:
                st.warning("Brak danych GDD dla tej stacji i daty.")
            else:
                data = resp.json()
                st.success(f"Faza: **{data['bloom_phase_label']}**")
                st.write(f"**Stacja:** {data.get('station_name', '-')} ({data['station_id']})")
                st.write(f"**Roslina:** {data['plant_name']}")
                st.write(f"**Data:** {data['date']}")
                st.write(f"**GDD (suma):** {data['gdd_cumulative']:.1f}")
                st.write(f"**Zakres kwitnienia:** {data['gdd_min']:.0f} - {data['gdd_max']:.0f}")
                bloom_day = data["bloom_day"] if data["bloom_day"] > 0 else "-"
                st.write(f"**Dzien kwitnienia:** {bloom_day}")
        except httpx.RequestError as e:
            st.error(f"Blad polaczenia z backendem: {e}")


# --- Main ----------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Pszczelarstwo - Lubelskie", layout="wide")
    st.title("Optymalizacja mobilnego pszczelarstwa - woj. lubelskie")

    tabs = st.tabs(["Mapa", "Kwitnienie", "FastAPI", "TiTiler", "STAC", "tipg"])

    with tabs[0]:
        render_map_tab()
    with tabs[1]:
        render_blooming_tab()
    with tabs[2]:
        render_fastapi_tab()
    with tabs[3]:
        render_titiler_tab()
    with tabs[4]:
        render_stac_tab()
    with tabs[5]:
        render_tipg_tab()


if __name__ == "__main__":
    main()