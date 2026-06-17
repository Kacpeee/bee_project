from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database
from ..dependencies import get_db
from ..models import BloomStatus

router = APIRouter()

PHASE_LABELS = {
    "before": "Przed kwitnieniem",
    "blooming": "Kwitnie",
    "after": "Po kwitnieniu",
}


@router.get("/", response_model=BloomStatus)
async def get_blooming(
    station_id: str = Query(..., description="ID stacji pogodowej"),
    query_date: date = Query(..., alias="date", description="Data (YYYY-MM-DD)"),
    plant_id: str = Query("salix_caprea", description="ID rosliny"),
    db: Database = Depends(get_db),
) -> BloomStatus:
    row = await db.fetchrow(
        """
        SELECT
            g.station_id,
            c.station_name,
            g.date,
            p.id AS plant_id,
            p.name_pl AS plant_name,
            g.gdd_cumulative,
            g.bloom_day,
            g.bloom_phase,
            p.gdd_min,
            p.gdd_max
        FROM app.station_gdd g
        JOIN app.honey_plants p ON p.id = g.plant_id
        LEFT JOIN app.weather_cells c ON c.station_id = g.station_id
        WHERE g.station_id = $1 AND g.date = $2 AND g.plant_id = $3
        LIMIT 1
        """,
        station_id,
        query_date,
        plant_id,
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No GDD data for this station, date and plant",
        )
    data = dict(row)
    data["bloom_phase_label"] = PHASE_LABELS.get(data["bloom_phase"], data["bloom_phase"])
    return BloomStatus(**data)
