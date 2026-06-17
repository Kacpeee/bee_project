"""Pobieranie temperatur z API Edwin → historia_meteo_2024_2025.csv"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
BASE_URL = "https://edwin-meteo.apps.paas.psnc.pl/meteo/station/"
PLIK_WYJSCIOWY = ROOT / "historia_meteo_2024_2025.csv"

# edytuj daty przed uruchomieniem
DATA_OD = date(2024, 1, 1)
DATA_DO = date(2025, 12, 31)

geojson = json.loads(
    (ROOT.parent / "data" / "lubelskie_edwin_voronoi.geojson").read_text(encoding="utf-8")
)
id_stacji = sorted({f["properties"]["station_id"] for f in geojson["features"]})

pomiary = []
print(f"Pobieram {len(id_stacji)} stacji: {DATA_OD} - {DATA_DO}")

for station_id in id_stacji:
    print(f"Stacja {station_id}...")
    start = DATA_OD
    while start <= DATA_DO:
        koniec = min(start + timedelta(days=89), DATA_DO)
        after = f"{start.isoformat()}T00:00:00Z"
        before = f"{koniec.isoformat()}T23:59:59Z"
        page = 0

        while True:
            url = f"{BASE_URL}{station_id}?after={after}&before={before}&page={page}&size=10000"
            try:
                resp = requests.get(url, headers={"accept": "application/json"}, timeout=60)
                resp.raise_for_status()
                content = resp.json().get("content", [])
            except requests.RequestException as e:
                print(f"  blad: {e}")
                break

            if not content:
                break

            pomiary.extend(content)
            page += 1

        start = koniec + timedelta(days=1)

df = pd.DataFrame(pomiary)
df["data_dnia"] = pd.to_datetime(df["measurementDate"]).dt.date
df_wynik = df.groupby(["stationId", "data_dnia"]).agg(
    T_min=("airTemperature", "min"),
    T_max=("airTemperature", "max"),
).reset_index()
df_wynik["T_srednia"] = round((df_wynik["T_max"] + df_wynik["T_min"]) / 2, 2)

if PLIK_WYJSCIOWY.exists():
    stary = pd.read_csv(PLIK_WYJSCIOWY)
    stary["data_dnia"] = pd.to_datetime(stary["data_dnia"]).dt.date
    df_wynik = pd.concat([stary, df_wynik]).drop_duplicates(
        subset=["stationId", "data_dnia"], keep="last"
    )

df_wynik = df_wynik.sort_values(["stationId", "data_dnia"])
df_wynik.to_csv(PLIK_WYJSCIOWY, index=False)
print(f"Zapisano: {PLIK_WYJSCIOWY} ({len(df_wynik)} wierszy)")
