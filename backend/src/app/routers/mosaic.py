import hashlib
import json
import os
from pathlib import Path

from cogeo_mosaic.mosaic import MosaicJSON
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/mosaic", tags=["mosaic"])

MOSAIC_DIR = Path(os.getenv("MOSAIC_DIR", "/data/mosaic_cache"))


class MosaicRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=32)


@router.post("")
def create_mosaic(req: MosaicRequest) -> dict:
    """Buduje MosaicJSON z listy COG (TiTiler /mosaicjson/tiles/...)."""
    urls = sorted(set(req.urls))
    digest = hashlib.sha256("|".join(urls).encode()).hexdigest()[:16]
    MOSAIC_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MOSAIC_DIR / f"mosaic_{digest}.json"

    if not out_path.is_file():
        try:
            mosaic = MosaicJSON.from_urls(urls)
            out_path.write_text(json.dumps(mosaic.model_dump()), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"Mosaic build failed: {exc}") from exc

    return {
        "mosaic_url": f"file://{out_path.as_posix()}",
        "path": str(out_path),
        "tile_count": len(urls),
    }
