from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Database
from .routers import blooming, cells, health, mosaic, plants


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.database_url)
    await db.connect()
    app.state.db = db
    yield
    await db.disconnect()


app = FastAPI(title="Geoinformatics API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cells.router, prefix="/cells", tags=["cells"])
app.include_router(blooming.router, prefix="/blooming", tags=["blooming"])
app.include_router(plants.router, prefix="/blooming", tags=["blooming"])
app.include_router(mosaic.router)
