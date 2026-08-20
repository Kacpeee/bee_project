"""
ETAP 15a - terminy kwitnienia (rzepak + sad) na siatce wojewodztwa dla
KAZDEGO sezonu 2019-2026.

PO CO
Interaktywny kalendarz ma pokazywac kazdy sezon z osobna: rzepak z detekcji
danego roku i terminy z modelu GDD danego roku. Meteo siatkowe bylo dotad
pobrane tylko dla 2025 - tu dociagamy pelne lata 2018-2026 (63 punkty co
25 km, jeden request na punkt) i liczymy dwie daty na punkt i rok:

  rzepak: baza 1.0 C, od 1 II, prog 555   (model kalibrowany, klasa A)
  sad:    baza 5.0 C, od 1 I,  prog z kotwiczenia (fenologia_sadu.json)

Wynik: cache/kwitnienie_lata.csv  (x, y, rok, doy_rzepak, doy_sad)

Uruchomienie:
    python kwitnienie_lata.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
CACHE = WYNIKI / "cache" / "meteo_siatka_lata.csv"
WYJ = WYNIKI / "cache" / "kwitnienie_lata.csv"
LATA = range(2019, 2027)


def termin(doy, gdd, d0, prog):
    g = gdd.copy()
    g[doy < d0] = 0
    i = np.searchsorted(np.cumsum(g), prog)
    return float(doy[i]) if i < len(doy) else np.nan


if __name__ == "__main__":
    pkt = (pd.read_csv(WYNIKI / "cache" / "woj_meteo_siatka.csv")
           [["x", "y"]].drop_duplicates().reset_index(drop=True))
    tr = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    print(f"punktow: {len(pkt)}, lata {LATA[0]}-{LATA[-1]}")

    if CACHE.exists():
        df = pd.read_csv(CACHE, parse_dates=["data"])
        print(f"meteo z cache: {len(df):,} wierszy")
    else:
        czesci = []
        for i, r in pkt.iterrows():
            lon, lat = tr.transform(r.x, r.y)
            for prob in range(4):
                try:
                    q = requests.get(
                        "https://archive-api.open-meteo.com/v1/archive",
                        params={"latitude": round(lat, 3),
                                "longitude": round(lon, 3),
                                "start_date": "2018-11-01",
                                "end_date": "2026-08-01",
                                "daily": "temperature_2m_max,temperature_2m_min",
                                "timezone": "Europe/Warsaw"}, timeout=120)
                    q.raise_for_status()
                    j = q.json()["daily"]
                    break
                except Exception:
                    if prob == 3:
                        raise
                    time.sleep(20 * (prob + 1))
            d = pd.DataFrame({"data": pd.to_datetime(j["time"]),
                              "Tmax": j["temperature_2m_max"],
                              "Tmin": j["temperature_2m_min"]})
            d["x"], d["y"] = r.x, r.y
            czesci.append(d)
            if (i + 1) % 10 == 0:
                print(f"  pobrano {i+1}/{len(pkt)}")
            time.sleep(1.0)          # limit darmowego API
        df = pd.concat(czesci, ignore_index=True)
        df.to_csv(CACHE, index=False)
        print(f"zapisano cache: {len(df):,} wierszy")

    sad = json.loads((WYNIKI / "json" / "fenologia_sadu.json")
                     .read_text(encoding="utf-8"))
    df["rok"] = df["data"].dt.year
    df["doy"] = df["data"].dt.dayofyear
    out = []
    for (x, y), g in df.groupby(["x", "y"]):
        for rok in LATA:
            s = g[g["rok"] == rok].sort_values("doy")
            if s.empty:
                continue
            doy = s["doy"].to_numpy()
            tsr = (s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2
            out.append({
                "x": x, "y": y, "rok": rok,
                "doy_rzepak": termin(doy, np.maximum(tsr - 1.0, 0), 32, 555),
                "doy_sad": termin(doy, np.maximum(tsr - 5.0, 0), 1,
                                  sad["prog"]),
            })
    w = pd.DataFrame(out)
    w.to_csv(WYJ, index=False)
    print("\nterminy per rok (mediana po siatce):")
    for rok, g in w.groupby("rok"):
        print(f"  {rok}: rzepak DOY {g.doy_rzepak.median():.0f} "
              f"(rozrzut {g.doy_rzepak.max()-g.doy_rzepak.min():.0f} d), "
              f"sad DOY {g.doy_sad.median():.0f}")
    print(f"zapisano {WYJ.name}")
