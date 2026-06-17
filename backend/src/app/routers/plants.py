from fastapi import APIRouter, Depends

from ..database import Database
from ..dependencies import get_db

router = APIRouter()


@router.get("/plants")
async def list_plants(db: Database = Depends(get_db)) -> list[dict]:
    rows = await db.fetch("""
        SELECT id, name_pl, name_latin, base_temp_c, gdd_min, gdd_max, season
        FROM app.honey_plants
        ORDER BY name_pl
    """)
    return [dict(row) for row in rows]
