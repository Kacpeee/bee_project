import json
import os
from pathlib import Path

import psycopg
from pypgstac.db import PgstacDB
from pypgstac.load import Loader, Methods

DATA_DIR = Path("/data")


class DataIngester:
    def __init__(self, database_url: str) -> None:
        self._url = database_url

    def run(self) -> None:
        self._setup_tables()
        self._load_vector_data()
        self._load_stac_catalog()
        print("Ingestion complete.")

    def _setup_tables(self) -> None:
        with psycopg.connect(self._url) as conn:
            conn.execute("""
                CREATE SCHEMA IF NOT EXISTS app;

                CREATE TABLE IF NOT EXISTS app.locations (
                    id       SERIAL PRIMARY KEY,
                    name     TEXT NOT NULL,
                    category TEXT NOT NULL,
                    geom     GEOMETRY(Point, 4326)
                );

                CREATE INDEX IF NOT EXISTS locations_geom_idx
                    ON app.locations USING GIST (geom);
            """)
        print("Tables ready.")

    def _load_vector_data(self) -> None:
        geojson = json.loads((DATA_DIR / "sample_features.geojson").read_text())
        features = geojson["features"]

        with psycopg.connect(self._url) as conn:
            conn.execute("TRUNCATE app.locations RESTART IDENTITY")
            for feature in features:
                lon, lat = feature["geometry"]["coordinates"]
                props = feature["properties"]
                conn.execute(
                    """
                    INSERT INTO app.locations (name, category, geom)
                    VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    """,
                    (props["name"], props["category"], lon, lat),
                )
        print(f"Loaded {len(features)} locations.")

    def _load_stac_catalog(self) -> None:
        collection = json.loads((DATA_DIR / "stac_collection.json").read_text())
        items = json.loads((DATA_DIR / "stac_items.json").read_text())

        with psycopg.connect(self._url, autocommit=True) as conn:
            conn.execute("DELETE FROM pgstac.items WHERE collection = %s", (collection["id"],))

        with PgstacDB(dsn=self._url) as pgdb:
            loader = Loader(db=pgdb)
            loader.load_collections(iter([collection]), insert_mode=Methods.upsert)
            loader.load_items(iter(items), insert_mode=Methods.upsert)
        print(f"Loaded STAC collection '{collection['id']}' with {len(items)} item(s).")


if __name__ == "__main__":
    DataIngester(os.environ["DATABASE_URL"]).run()
