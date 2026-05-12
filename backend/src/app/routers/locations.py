import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database
from ..dependencies import get_db
from ..models import Location, LocationCollection

router = APIRouter()


def _row_to_location(row) -> Location:
    return Location(
        id=row["id"],
        geometry=json.loads(row["geometry"]),
        properties={"name": row["name"], "category": row["category"]},
    )


@router.get("/", response_model=LocationCollection)
async def list_locations(db: Database = Depends(get_db)) -> LocationCollection:
    rows = await db.fetch("""
        SELECT id, name, category, ST_AsGeoJSON(geom) AS geometry
        FROM app.locations
    """)
    return LocationCollection(features=[_row_to_location(r) for r in rows])


@router.get("/within", response_model=LocationCollection)
async def locations_within_bbox(
    minx: float = Query(..., description="Min longitude"),
    miny: float = Query(..., description="Min latitude"),
    maxx: float = Query(..., description="Max longitude"),
    maxy: float = Query(..., description="Max latitude"),
    db: Database = Depends(get_db),
) -> LocationCollection:
    rows = await db.fetch(
        """
        SELECT id, name, category, ST_AsGeoJSON(geom) AS geometry
        FROM app.locations
        WHERE ST_Within(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
        """,
        minx, miny, maxx, maxy,
    )
    return LocationCollection(features=[_row_to_location(r) for r in rows])


@router.get("/{location_id}", response_model=Location)
async def get_location(location_id: int, db: Database = Depends(get_db)) -> Location:
    row = await db.fetchrow(
        """
        SELECT id, name, category, ST_AsGeoJSON(geom) AS geometry
        FROM app.locations WHERE id = $1
        """,
        location_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")
    return _row_to_location(row)
