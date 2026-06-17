import csv
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
        self._load_weather_cells()
        self._load_honey_plants()
        self._load_station_daily()
        self._load_station_gdd()
        self._update_bloom_dates()
        self._load_stac_catalog()
        print("Ingestion complete.")

    def _setup_tables(self) -> None:
        with psycopg.connect(self._url) as conn:
            conn.execute("""
                CREATE SCHEMA IF NOT EXISTS app;

                CREATE TABLE IF NOT EXISTS app.weather_cells (
                    id               SERIAL PRIMARY KEY,
                    cell_id          INTEGER,
                    station_id       TEXT NOT NULL,
                    station_name     TEXT NOT NULL,
                    area_ha          DOUBLE PRECISION,
                    bloom_start_date DATE,
                    bloom_end_date   DATE,
                    bloom_tooltip    TEXT,
                    geom             GEOMETRY(Geometry, 4326)
                );

                ALTER TABLE app.weather_cells
                    ADD COLUMN IF NOT EXISTS bloom_start_date DATE;
                ALTER TABLE app.weather_cells
                    ADD COLUMN IF NOT EXISTS bloom_end_date DATE;
                ALTER TABLE app.weather_cells
                    ADD COLUMN IF NOT EXISTS bloom_tooltip TEXT;

                CREATE TABLE IF NOT EXISTS app.honey_plants (
                    id            TEXT PRIMARY KEY,
                    name_pl       TEXT NOT NULL,
                    name_latin    TEXT NOT NULL,
                    base_temp_c   DOUBLE PRECISION NOT NULL,
                    gdd_min       DOUBLE PRECISION NOT NULL,
                    gdd_max       DOUBLE PRECISION NOT NULL,
                    season        TEXT
                );

                CREATE TABLE IF NOT EXISTS app.station_daily (
                    station_id    TEXT NOT NULL,
                    date          DATE NOT NULL,
                    t_min         DOUBLE PRECISION,
                    t_max         DOUBLE PRECISION,
                    t_mean        DOUBLE PRECISION,
                    PRIMARY KEY (station_id, date)
                );

                CREATE TABLE IF NOT EXISTS app.station_gdd (
                    station_id      TEXT NOT NULL,
                    plant_id          TEXT NOT NULL,
                    date              DATE NOT NULL,
                    gdd_daily         DOUBLE PRECISION,
                    gdd_cumulative    DOUBLE PRECISION,
                    bloom_day         INTEGER,
                    bloom_phase       TEXT,
                    PRIMARY KEY (station_id, plant_id, date)
                );

                CREATE INDEX IF NOT EXISTS weather_cells_geom_idx
                    ON app.weather_cells USING GIST (geom);
            """)
        print("Tables ready.")

    def _load_weather_cells(self) -> None:
        geojson = json.loads(
            (DATA_DIR / "lubelskie_edwin_voronoi.geojson").read_text(encoding="utf-8")
        )
        features = geojson["features"]

        with psycopg.connect(self._url) as conn:
            conn.execute("TRUNCATE app.weather_cells RESTART IDENTITY")
            for feature in features:
                props = feature["properties"]
                geom_json = json.dumps(feature["geometry"])
                conn.execute(
                    """
                    INSERT INTO app.weather_cells
                        (cell_id, station_id, station_name, area_ha, geom)
                    VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    """,
                    (
                        props["cell_id"],
                        props["station_id"],
                        props["station_name"],
                        props.get("area_ha"),
                        geom_json,
                    ),
                )
        print(f"Loaded {len(features)} weather cells.")

    def _load_honey_plants(self) -> None:
        plants = json.loads((DATA_DIR / "honey_plants.json").read_text(encoding="utf-8"))

        with psycopg.connect(self._url) as conn:
            conn.execute("TRUNCATE app.honey_plants")
            for plant in plants:
                conn.execute(
                    """
                    INSERT INTO app.honey_plants
                        (id, name_pl, name_latin, base_temp_c, gdd_min, gdd_max, season)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        plant["id"],
                        plant["name_pl"],
                        plant["name_latin"],
                        plant["base_temp_c"],
                        plant["gdd_min"],
                        plant["gdd_max"],
                        plant.get("season"),
                    ),
                )
        print(f"Loaded {len(plants)} honey plants.")

    def _load_station_daily(self) -> None:
        path = DATA_DIR / "station_temperatures.csv"
        with psycopg.connect(self._url) as conn:
            conn.execute("TRUNCATE app.station_daily")
            with path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        """
                        INSERT INTO app.station_daily
                            (station_id, date, t_min, t_max, t_mean)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            row["station_id"],
                            row["date"],
                            row["t_min"],
                            row["t_max"],
                            row["t_mean"],
                        ),
                    )
        print(f"Loaded station daily temperatures from {path.name}.")

    def _load_station_gdd(self) -> None:
        path = DATA_DIR / "station_gdd_cache.csv"
        with psycopg.connect(self._url) as conn:
            conn.execute("TRUNCATE app.station_gdd")
            with path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        """
                        INSERT INTO app.station_gdd
                            (station_id, plant_id, date, gdd_daily, gdd_cumulative,
                             bloom_day, bloom_phase)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            row["station_id"],
                            row["plant_id"],
                            row["date"],
                            row["gdd_daily"],
                            row["gdd_cumulative"],
                            row["bloom_day"],
                            row["bloom_phase"],
                        ),
                    )
        print("Loaded station GDD cache.")

    def _update_bloom_dates(self) -> None:
        with psycopg.connect(self._url) as conn:
            conn.execute("""
                UPDATE app.weather_cells wc
                SET
                    bloom_start_date = t.date_start_100,
                    bloom_end_date = t.date_exceed_200,
                    bloom_tooltip = 'Wierzba iwa: od ' || t.date_start_100
                        || ' do ' || t.date_exceed_200
                FROM (
                    SELECT DISTINCT ON (station_id)
                        station_id,
                        date_start_100,
                        date_exceed_200
                    FROM (
                        SELECT
                            station_id,
                            EXTRACT(YEAR FROM date)::int AS yr,
                            MIN(date) FILTER (WHERE gdd_cumulative >= 100)
                                AS date_start_100,
                            MIN(date) FILTER (WHERE gdd_cumulative > 200)
                                AS date_exceed_200
                        FROM app.station_gdd
                        WHERE plant_id = 'salix_caprea'
                        GROUP BY station_id, EXTRACT(YEAR FROM date)
                    ) yearly
                    WHERE date_start_100 IS NOT NULL
                      AND date_exceed_200 IS NOT NULL
                    ORDER BY station_id, yr DESC
                ) t
                WHERE wc.station_id = t.station_id
                  AND t.date_start_100 IS NOT NULL
                  AND t.date_exceed_200 IS NOT NULL
            """)
            conn.execute("""
                UPDATE app.weather_cells
                SET bloom_tooltip = 'Wierzba iwa: brak danych'
                WHERE bloom_tooltip IS NULL
            """)
        print("Updated bloom dates on weather cells.")

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
