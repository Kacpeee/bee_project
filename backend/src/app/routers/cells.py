import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database
from ..dependencies import get_db
from ..models import (
    CellAtPoint,
    MeteoMonthlyPoint,
    MeteoMonthlySummary,
    MeteoSeries,
    MeteoSeriesPoint,
    StationInfo,
)
from ..precip_cache import monthly_precip_sum, read_precip_cache

router = APIRouter()

STATION_LOCATIONS_PATH = Path("/data/lubelskie_edwin_voronoi.geojson")


def _row_to_feature(row) -> dict:
    return {
        "type": "Feature",
        "geometry": json.loads(row["geometry"]),
        "properties": {
            "cell_id": row["cell_id"],
            "station_id": row["station_id"],
            "station_name": row["station_name"],
            "area_ha": row["area_ha"],
            "bloom_start_date": str(row["bloom_start_date"]) if row["bloom_start_date"] else None,
            "bloom_end_date": str(row["bloom_end_date"]) if row["bloom_end_date"] else None,
            "bloom_tooltip": row["bloom_tooltip"],
        },
    }


@router.get("/stations/points")
async def station_points_geojson() -> dict:
    """Punkty stacji meteorologicznych eDWIN (wspolrzedne z pliku Voronoi)."""
    if not STATION_LOCATIONS_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="Brak pliku lubelskie_edwin_voronoi.geojson w /data",
        )

    geojson = json.loads(STATION_LOCATIONS_PATH.read_text(encoding="utf-8"))
    features: list[dict] = []
    seen: set[str] = set()
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        station_id = props.get("station_id")
        if not station_id or station_id in seen:
            continue
        lat = props.get("latitude")
        lon = props.get("longitude")
        if lat is None or lon is None:
            continue
        seen.add(station_id)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "station_id": station_id,
                    "station_name": props.get("station_name", station_id),
                    "station_type": props.get("stationType"),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


@router.get("/stations", response_model=list[StationInfo])
async def list_stations(db: Database = Depends(get_db)) -> list[StationInfo]:
    rows = await db.fetch("""
        SELECT DISTINCT station_id, station_name, area_ha
        FROM app.weather_cells
        ORDER BY station_name
    """)
    return [StationInfo(**dict(row)) for row in rows]


@router.get("/geojson")
async def cells_geojson(db: Database = Depends(get_db)) -> dict:
    rows = await db.fetch("""
        SELECT cell_id, station_id, station_name, area_ha,
               bloom_start_date, bloom_end_date, bloom_tooltip,
               ST_AsGeoJSON(geom) AS geometry
        FROM app.weather_cells
    """)
    return {
        "type": "FeatureCollection",
        "features": [_row_to_feature(row) for row in rows],
    }


@router.get("/geojson/map")
async def cells_geojson_map(db: Database = Depends(get_db)) -> dict:
    """Uproszczone geometrie pod Folium (mniejszy payload do st_folium)."""
    rows = await db.fetch("""
        SELECT cell_id, station_id, station_name, area_ha,
               bloom_start_date, bloom_end_date, bloom_tooltip,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.02)) AS geometry
        FROM app.weather_cells
    """)
    return {
        "type": "FeatureCollection",
        "features": [_row_to_feature(row) for row in rows],
    }


@router.get("/at-point", response_model=CellAtPoint)
async def cell_at_point(
    lon: float = Query(..., description="Longitude"),
    lat: float = Query(..., description="Latitude"),
    db: Database = Depends(get_db),
) -> CellAtPoint:
    row = await db.fetchrow(
        """
        SELECT station_id, station_name, area_ha
        FROM app.weather_cells
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
        LIMIT 1
        """,
        lon,
        lat,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No weather cell at this point")
    return CellAtPoint(**dict(row))


@router.get("/stations/{station_id}/monthly", response_model=MeteoMonthlySummary)
async def station_meteo_monthly(
    station_id: str,
    year: int = Query(2024, ge=2000, le=2100),
    plant_id: str = Query("salix_caprea"),
    db: Database = Depends(get_db),
) -> MeteoMonthlySummary:
    """Miesieczne podsumowanie — tylko PostGIS (+ opcjonalnie lokalny cache opadow)."""
    meta = await db.fetchrow(
        """
        SELECT DISTINCT station_id, station_name
        FROM app.weather_cells
        WHERE station_id = $1
        LIMIT 1
        """,
        station_id,
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Unknown station")

    rows = await db.fetch(
        """
        SELECT
            EXTRACT(MONTH FROM d.date)::int AS month,
            AVG(d.t_mean) AS t_mean,
            SUM(g.gdd_daily) AS gdd_monthly,
            MAX(g.gdd_cumulative) AS gdd_cumulative,
            COUNT(*) AS day_count
        FROM app.station_daily d
        LEFT JOIN app.station_gdd g
            ON g.station_id = d.station_id
           AND g.date = d.date
           AND g.plant_id = $3
        WHERE d.station_id = $1
          AND EXTRACT(YEAR FROM d.date) = $2
        GROUP BY 1
        ORDER BY 1
        """,
        station_id,
        year,
        plant_id,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No meteo data for this station/year")

    precip_by_month = monthly_precip_sum(station_id, year)
    months = [
        MeteoMonthlyPoint(
            month=row["month"],
            t_mean=float(row["t_mean"]) if row["t_mean"] is not None else None,
            gdd_monthly=float(row["gdd_monthly"])
            if row["gdd_monthly"] is not None
            else None,
            gdd_cumulative=float(row["gdd_cumulative"])
            if row["gdd_cumulative"] is not None
            else None,
            precip_mm=precip_by_month.get(row["month"]),
        )
        for row in rows
    ]

    stats = await db.fetchrow(
        """
        SELECT
            AVG(d.t_mean) AS t_mean_annual,
            MAX(g.gdd_cumulative) AS gdd_max,
            COUNT(*) AS day_count
        FROM app.station_daily d
        LEFT JOIN app.station_gdd g
            ON g.station_id = d.station_id
           AND g.date = d.date
           AND g.plant_id = $3
        WHERE d.station_id = $1
          AND EXTRACT(YEAR FROM d.date) = $2
        """,
        station_id,
        year,
        plant_id,
    )

    precip_annual = sum(precip_by_month.values()) if precip_by_month else None

    return MeteoMonthlySummary(
        station_id=station_id,
        station_name=meta["station_name"],
        year=year,
        plant_id=plant_id,
        day_count=stats["day_count"],
        t_mean_annual=float(stats["t_mean_annual"])
        if stats["t_mean_annual"] is not None
        else None,
        gdd_max=float(stats["gdd_max"]) if stats["gdd_max"] is not None else None,
        precip_annual=precip_annual,
        months=months,
    )


@router.get("/stations/{station_id}/series", response_model=MeteoSeries)
async def station_meteo_series(
    station_id: str,
    year: int = Query(2024, ge=2000, le=2100),
    plant_id: str = Query("salix_caprea"),
    db: Database = Depends(get_db),
) -> MeteoSeries:
    """Szereg dzienny: temperatura + GDD z PostGIS (bez HTTP)."""
    meta = await db.fetchrow(
        """
        SELECT DISTINCT station_id, station_name
        FROM app.weather_cells
        WHERE station_id = $1
        LIMIT 1
        """,
        station_id,
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Unknown station")

    rows = await db.fetch(
        """
        SELECT
            d.date,
            d.t_min,
            d.t_max,
            d.t_mean,
            g.gdd_daily,
            g.gdd_cumulative
        FROM app.station_daily d
        LEFT JOIN app.station_gdd g
            ON g.station_id = d.station_id
           AND g.date = d.date
           AND g.plant_id = $3
        WHERE d.station_id = $1
          AND EXTRACT(YEAR FROM d.date) = $2
        ORDER BY d.date
        """,
        station_id,
        year,
        plant_id,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No meteo data for this station/year")

    precip_by_day = read_precip_cache(station_id, year)

    points = [
        MeteoSeriesPoint(
            date=row["date"],
            t_min=row["t_min"],
            t_max=row["t_max"],
            t_mean=row["t_mean"],
            gdd_daily=row["gdd_daily"],
            gdd_cumulative=row["gdd_cumulative"],
            precip_mm=precip_by_day.get(row["date"]),
        )
        for row in rows
    ]
    return MeteoSeries(
        station_id=station_id,
        station_name=meta["station_name"],
        year=year,
        plant_id=plant_id,
        points=points,
    )
