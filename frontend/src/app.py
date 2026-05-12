import urllib.parse

import httpx
import streamlit as st
from maplibre import Map, MapOptions
from maplibre.controls import NavigationControl, ScaleControl
from maplibre.layer import Layer, LayerType
from maplibre.sources import RasterTileSource, VectorTileSource
from maplibre.streamlit import st_maplibre

from config import settings

KRAKOW_CENTER = [19.94, 50.06]
CARTO_POSITRON = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"


# --- Helpers -------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_stac_collections() -> list[dict]:
    try:
        return httpx.get(f"{settings.stac_api_url}/collections", timeout=5).json().get("collections", [])
    except httpx.RequestError:
        return []


@st.cache_data(ttl=60)
def fetch_stac_items(collection_id: str) -> list[dict]:
    try:
        return httpx.get(
            f"{settings.stac_api_url}/collections/{collection_id}/items", timeout=5
        ).json().get("features", [])
    except httpx.RequestError:
        return []


# --- Tab: Mapa -----------------------------------------------------------------


def _visibility(visible: bool) -> dict:
    return {"visibility": "visible" if visible else "none"}


def build_map(visible_layers: set[str], items: list[dict]) -> Map:
    m = Map(MapOptions(center=KRAKOW_CENTER, zoom=9, style=CARTO_POSITRON))
    m.add_control(NavigationControl())
    m.add_control(ScaleControl())

    # TiTiler - po jednej warstwie rastrowej na kazdy kafel DEM z STAC
    for item in items:
        item_id = item["id"]
        cog_url = urllib.parse.quote(item["assets"]["visual"]["href"], safe="")
        titiler_tiles = (
            f"{settings.public_titiler_url}"
            f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}"
            f"?url={cog_url}&colormap_name=terrain&rescale=100,1000"
        )
        m.add_source(item_id, RasterTileSource(tiles=[titiler_tiles], tile_size=256))
        m.add_layer(Layer(
            type=LayerType.RASTER,
            id=f"{item_id}-layer",
            source=item_id,
            paint={"raster-opacity": 0.7},
            layout=_visibility(item_id in visible_layers),
        ))

    # tipg - kafle wektorowe MVT z PostGIS
    tipg_tiles = (
        f"{settings.public_tipg_url}"
        "/collections/app.locations/tiles/WebMercatorQuad/{z}/{x}/{y}"
    )
    m.add_source("locations", VectorTileSource(tiles=[tipg_tiles]))
    m.add_layer(Layer(
        type=LayerType.CIRCLE,
        id="locations-layer",
        source="locations",
        source_layer="default",
        paint={"circle-color": "#e63946", "circle-radius": 8, "circle-opacity": 0.9},
        layout=_visibility("locations" in visible_layers),
    ))

    return m


def render_legend(items: list[dict]) -> set[str]:
    """Renders legend checkboxes and returns the set of visible layer IDs."""
    st.markdown("**Legenda**")

    visible: set[str] = set()

    if st.checkbox(
        "Lokalizacje",
        value=True,
        key="layer_locations",
        help="PostGIS -> tipg (MVT)",
    ):
        visible.add("locations")

    st.markdown(
        '<div style="display:flex;align-items:center;gap:6px;margin:2px 0 4px 24px">'
        '<div style="width:14px;height:14px;border-radius:50%;background:#e63946"></div>'
        "<small>PostGIS &rarr; tipg (MVT)</small></div>",
        unsafe_allow_html=True,
    )

    if items:
        st.markdown("---")
        st.markdown("**Warstwy rastrowe (COG &rarr; TiTiler):**", unsafe_allow_html=True)
        for item in items:
            item_id = item["id"]
            desc = item["properties"].get("description", item_id)
            bbox = item.get("bbox", [])
            bbox_str = (
                f"{bbox[0]:.0f}-{bbox[2]:.0f}°E, {bbox[1]:.0f}-{bbox[3]:.0f}°N"
                if len(bbox) == 4
                else ""
            )
            if st.checkbox(desc, value=True, key=f"layer_{item_id}", help=bbox_str):
                visible.add(item_id)
            st.markdown(
                '<div style="display:flex;align-items:center;gap:6px;margin:-4px 0 4px 24px">'
                '<div style="width:14px;height:9px;'
                'background:linear-gradient(to right,#1a5276,#27ae60,#f1c40f,#e74c3c);'
                'border:1px solid #aaa"></div>'
                f"<small>{bbox_str}</small></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("Brak warstw rastrowych w STAC.")

    return visible


def render_map_tab() -> None:
    st.subheader("Mapa")
    items = fetch_stac_items("sample-imagery")
    col1, col2 = st.columns([3, 1])
    with col2:
        visible_layers = render_legend(items)
    with col1:
        st_maplibre(build_map(visible_layers, items), height=520)


# --- Tab: FastAPI --------------------------------------------------------------


def render_fastapi_tab() -> None:
    st.subheader("FastAPI - zapytania przestrzenne do PostGIS")
    st.markdown(
        "Backend FastAPI przyjmuje bbox i odpytuje PostGIS funkcja `ST_Within`. "
        "Ponizej mozesz przetestowac endpoint `GET /locations/within`."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        minx = st.number_input("Min lon", value=19.85, format="%.4f")
    with col2:
        miny = st.number_input("Min lat", value=50.02, format="%.4f")
    with col3:
        maxx = st.number_input("Max lon", value=20.10, format="%.4f")
    with col4:
        maxy = st.number_input("Max lat", value=50.09, format="%.4f")

    if st.button("Wykonaj zapytanie"):
        try:
            resp = httpx.get(
                f"{settings.backend_url}/locations/within",
                params={"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy},
                timeout=5,
            )
            data = resp.json()
            features = data.get("features", [])
            st.success(f"Znaleziono **{len(features)}** lokalizacji w bbox.")
            if features:
                rows = [
                    {"id": f["id"], "name": f["properties"]["name"],
                     "category": f["properties"]["category"]}
                    for f in features
                ]
                st.table(rows)
        except httpx.RequestError as e:
            st.error(f"Blad polaczenia z backendem: {e}")

    with st.expander("Wywolany URL"):
        st.code(
            f"GET {settings.backend_url}/locations/within"
            f"?minx={minx}&miny={miny}&maxx={maxx}&maxy={maxy}"
        )


# --- Tab: TiTiler --------------------------------------------------------------


def render_titiler_tab() -> None:
    st.subheader("TiTiler - metadane i statystyki rastra (COG)")

    items = fetch_stac_items("sample-imagery")
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
            bbox_str = st.text_input("bbox (minx,miny,maxx,maxy)", "18.0,49.0,21.0,51.5")
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
                f"{settings.tipg_url}/collections/app.locations/items",
                params={"limit": 5},
                timeout=5,
            )
            features = resp.json().get("features", [])
            for f in features:
                coords = f["geometry"]["coordinates"]
                props = f["properties"]
                st.write(f"- **{props['name']}** ({props['category']}) @ {coords[0]:.4f}, {coords[1]:.4f}")
        except httpx.RequestError as e:
            st.error(str(e))

    st.markdown("---")
    st.markdown("**Format kafla MVT** (uzywany przez MapLibre na mapie):")
    st.code(
        f"{settings.public_tipg_url}"
        "/collections/app.locations/tiles/WebMercatorQuad/{z}/{x}/{y}"
    )
    st.caption("Warstwa w kaflu MVT zawsze nazywa sie `default` (niezaleznie od nazwy tabeli).")


# --- Main ----------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Geoinformatics App", layout="wide")
    st.title("Geoinformatics App")

    tabs = st.tabs(["Mapa", "FastAPI", "TiTiler", "STAC", "tipg"])

    with tabs[0]:
        render_map_tab()
    with tabs[1]:
        render_fastapi_tab()
    with tabs[2]:
        render_titiler_tab()
    with tabs[3]:
        render_stac_tab()
    with tabs[4]:
        render_tipg_tab()


if __name__ == "__main__":
    main()
