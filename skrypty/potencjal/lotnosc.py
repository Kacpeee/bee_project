"""
ETAP 4 - warstwa lotnosci: ile z dostepnego nektaru pszczola zdazy zebrac.

PO CO
Kalendarz pozytku mowi, ILE nektaru wisi na polach w danej dekadzie. Nie mowi,
czy pogoda pozwoli po niego polecec. Przy dwoch tygodniach deszczu w pelni
kwitnienia potencjal jest ten sam, a zbior zerowy. Ta warstwa jest mnoznikiem,
ktory zamienia "ile jest" na "ile da sie zebrac".

PROGI - ZRODLA
  temperatura   10 °C   Woyke: przy 10 °C najczesciej zaczyna sie zbieranie
                        pokarmu; ponizej pszczoly wylatuja bardzo rzadko
  optimum       20 °C   najwieksza aktywnosc lotna
  wiatr        5 m/s    od tej wartosci zaczyna sie wyrazne ograniczenie lotow
  wiatr stop  8.3 m/s   30 km/h - loty ustaja
  opad         > 0      pszczoly nie latuja w deszczu
Patrz ZRODLA.md.

DWIE MIARY
  godziny lotne - prosta liczba godzin spelniajacych warunki (latwa do
                  zakomunikowania, ale traktuje 10 °C i 20 °C tak samo)
  indeks        - te same godziny wazone efektywnoscia: pelna przy 20 °C
                  i bezwietrznie, malejaca ku progom
Do modulacji kalendarza uzywany jest indeks.

Uruchomienie:
    python lotnosc.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

PUNKT_LAT, PUNKT_LON = 50.755, 23.600
ROK_OD, ROK_DO = 2000, 2026

T_MIN, T_OPT = 10.0, 20.0
# Progi wiatru wg BEEHAVE (Becher i in. 2014), kanonicznego modelu
# rodziny pszczelej: loty ustaja przy 15 km/h = 4.2 m/s. Wczesniej
# stalo tu 8.3 m/s (30 km/h) z opracowan wtornych - dwukrotnie zbyt
# liberalnie, przez co warstwa zawyzala sprawnosc lotna.
W_OGR, W_STOP = 3.0, 4.2

API = "https://archive-api.open-meteo.com/v1/archive"


def pobierz(lat: float, lon: float, od: date, do: date) -> pd.DataFrame:
    """Godzinowe dane; pobierane blokami, bo 26 lat naraz to duza odpowiedz."""
    czesci = []
    a = od
    while a <= do:
        b = min(date(a.year + 4, 12, 31), do)
        r = requests.get(API, params={
            "latitude": lat, "longitude": lon,
            "start_date": a.isoformat(), "end_date": b.isoformat(),
            "hourly": "temperature_2m,wind_speed_10m,precipitation,is_day",
            "wind_speed_unit": "ms", "timezone": "Europe/Warsaw",
        }, timeout=300)
        r.raise_for_status()
        h = r.json()["hourly"]
        czesci.append(pd.DataFrame({
            "czas": pd.to_datetime(h["time"]), "T": h["temperature_2m"],
            "wiatr": h["wind_speed_10m"], "opad": h["precipitation"],
            "dzien": h["is_day"]}))
        print(f"  {a.year}-{b.year}: {len(czesci[-1]):,} godzin")
        a = date(b.year + 1, 1, 1)
    return pd.concat(czesci, ignore_index=True)


def lotnosc(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["lot"] = ((d["T"] >= T_MIN) & (d["wiatr"] <= W_STOP)
                & (d["opad"] <= 0) & (d["dzien"] == 1))
    # efektywnosc: pelna przy 20 °C i bezwietrznie, liniowo malejaca ku progom
    wT = ((d["T"] - T_MIN) / (T_OPT - T_MIN)).clip(0, 1)
    wW = ((W_STOP - d["wiatr"]) / (W_STOP - W_OGR)).clip(0, 1)
    d["waga"] = d["lot"] * wT * wW

    d["data"] = d["czas"].dt.date
    d["rok"] = d["czas"].dt.year
    d["doy"] = d["czas"].dt.dayofyear
    dob = d.groupby(["rok", "doy"]).agg(
        godziny_lotne=("lot", "sum"), indeks=("waga", "sum"),
        godziny_dnia=("dzien", "sum"), T_sr=("T", "mean")).reset_index()
    dob["udzial"] = dob["godziny_lotne"] / dob["godziny_dnia"].clip(lower=1)
    return dob


def dekady(dob: pd.DataFrame, dek: list[int]) -> pd.DataFrame:
    d = dob.copy()
    d["dekada"] = pd.cut(d["doy"], bins=dek + [dek[-1] + 10], right=False,
                         labels=dek)
    g = d.dropna(subset=["dekada"]).groupby(["rok", "dekada"], observed=True).agg(
        godziny=("godziny_lotne", "sum"), indeks=("indeks", "sum"),
        mozliwe=("godziny_dnia", "sum")).reset_index()
    g["sprawnosc"] = g["indeks"] / g["mozliwe"].clip(lower=1)
    return g


if __name__ == "__main__":
    print(f"Godzinowe meteo {ROK_OD}-{ROK_DO} dla {PUNKT_LAT}, {PUNKT_LON}")
    df = pobierz(PUNKT_LAT, PUNKT_LON, date(ROK_OD, 1, 1),
                 date.today() - timedelta(days=6))
    print(f"razem {len(df):,} godzin\n")

    dob = lotnosc(df)
    WYNIKI.mkdir(exist_ok=True)
    dob.to_csv(WYNIKI / "cache" / "lotnosc_dobowa.csv", index=False)

    pot = json.loads((WYNIKI / "json" / "potencjal_gsa.json").read_text(encoding="utf-8"))
    DEK = pot["dekady"]
    dek = dekady(dob, DEK)
    rok = pot["rok"]

    b = dek[dek["rok"] == rok].set_index("dekada")
    klim = dek[dek["rok"] < rok].groupby("dekada", observed=True)["sprawnosc"].mean()

    print(f"SPRAWNOSC LOTNA w sezonie {rok} (udzial efektywnych godzin dnia)\n")
    print(f"{'dekada':>8}{'godz. lotnych':>15}{'sprawnosc':>11}{'norma':>9}{'odchyl.':>9}")
    for d_ in DEK:
        if d_ not in b.index:
            continue
        s, n = b.loc[d_, "sprawnosc"], klim.get(d_, np.nan)
        print(f"{pot['daty'][str(d_)]:>8}{b.loc[d_, 'godziny']:>15.0f}"
              f"{s:>11.1%}{n:>9.1%}{s - n:>+9.1%}")

    # --- modulacja kalendarza
    print(f"\nKALENDARZ: dostepne vs mozliwe do zebrania (t cukrow)\n")
    print(f"{'dekada':>8}{'dostepne':>10}{'sprawnosc':>11}{'realne':>9}")
    kal = pot["kalendarze"]["caly sezon"]
    real = {}
    for d_ in DEK:
        dost = kal[str(d_)] / 1000
        s = b.loc[d_, "sprawnosc"] if d_ in b.index else 0.0
        real[str(d_)] = dost * s
        if dost > 0.05:
            print(f"{pot['daty'][str(d_)]:>8}{dost:>10.2f}{s:>11.1%}{dost*s:>9.2f}")
    print(f"{'RAZEM':>8}{sum(kal.values())/1000:>10.2f}"
          f"{sum(real.values())/(sum(kal.values())/1000):>11.1%}"
          f"{sum(real.values()):>9.2f}")

    (WYNIKI / "json" / "lotnosc.json").write_text(json.dumps({
        "punkt": {"lat": PUNKT_LAT, "lon": PUNKT_LON},
        "progi": {"T_min": T_MIN, "T_opt": T_OPT, "wiatr_ogr": W_OGR,
                  "wiatr_stop": W_STOP},
        "rok": rok, "dekady": DEK,
        "sprawnosc": {str(d_): float(b.loc[d_, "sprawnosc"])
                      for d_ in DEK if d_ in b.index},
        "sprawnosc_norma": {str(d_): float(klim[d_]) for d_ in klim.index},
        "godziny_lotne": {str(d_): float(b.loc[d_, "godziny"])
                          for d_ in DEK if d_ in b.index},
        "kalendarz_dostepny": kal,
        "kalendarz_realny": {k: v * 1000 for k, v in real.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'lotnosc.json'} i lotnosc_dobowa.csv")
