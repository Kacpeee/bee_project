"""
ETAP 4 (podstawa) - suma temperatur efektywnych i termin kwitnienia rzepaku.

Pobiera dobowe Tmax/Tmin z Open-Meteo dla punktu i liczy GDD:

    GDD_dobowe = max(0, (Tmax + Tmin) / 2 - BAZA)

Dlaczego Open-Meteo, a nie eDWIN:
  - eDWIN oddaje 503 od poczatku prac, a stacje montowano dopiero w 2021-2022,
    wiec nawet dzialajac dalby 5 sezonow. Do modelu, ktorego efektywna liczba
    obserwacji rowna sie liczbie LAT, to jest za malo.
  - Open-Meteo: archiwum na bazie ERA5 od 1940, bez klucza, plus prognoza 16 dni
    W TYM SAMYM API. To drugie jest kluczowe - system ma przewidywac termin
    kwitnienia w przod, a reanaliza ma kilka dni opoznienia.
  - eDWIN wroci jako warstwa lokalnej weryfikacji (rozdzial o reprezentatywnosci
    punktu wobec siatki), nie jako fundament.

MOMENT STARTU AKUMULACJI jest sporny i wynik mocno od niego zalezy, dlatego
liczone sa trzy warianty. Prog cieplny jest zakotwiczony na JEDNYM zmierzonym
kwitnieniu (2022, DOY 140 z piku NDYI) - to jest kalibracja na N = 1 i tak
trzeba ja traktowac, dopoki nie wyciagniemy dat z pozostalych sezonow.

Uruchomienie:
    python meteo_gdd.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

# ---------------------------------------------------------------- konfiguracja
PUNKT_LAT, PUNKT_LON = 50.755, 23.600
PUNKT_NAZWA = "srodek obszaru pilotazowego"

ROK_OD, ROK_DO = 2000, 2026
# Baza 4 °C, nie 5: przy 5 prog kalibrowany na zmierzonym kwitnieniu 2022
# rozjezdza sie z widelkami literaturowymi, a termin wypada 15 dni za pozno.
# Zrodlo podaje baze 4-5 °C i 400-600 GDD, ale NIE PODAJE, od kiedy liczy -
# a to zmienia wynik o miesiac (od 1 I przy bazie 5 i progu 600 kwitnienie
# wypada w polowie czerwca). Widelki sluza wiec za kontrole, nie za parametr.
BAZA = 4.0
START = "1I"                # wariant akumulacji uzywany przez inne skrypty

# Zmierzone kwitnienie: szczyt NDYI 2022 wypadl na DOY 139-141 (19-21 maja),
# ze spadkiem NDVI w tych samych datach. Bierzemy srodek jako BBCH 65.
KOTWICA_ROK, KOTWICA_DOY = 2022, 140

API = "https://archive-api.open-meteo.com/v1/archive"


# ---------------------------------------------------------------- pobieranie
def pobierz(lat: float, lon: float, od: date, do: date) -> pd.DataFrame:
    r = requests.get(API, params={
        "latitude": lat, "longitude": lon,
        "start_date": od.isoformat(), "end_date": do.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Warsaw",
    }, timeout=120)
    r.raise_for_status()
    d = r.json()["daily"]
    df = pd.DataFrame({
        "data": pd.to_datetime(d["time"]),
        "Tmax": d["temperature_2m_max"],
        "Tmin": d["temperature_2m_min"],
        "opad": d["precipitation_sum"],
    })
    df["rok"] = df["data"].dt.year
    df["doy"] = df["data"].dt.dayofyear
    df["Tsr"] = (df["Tmax"] + df["Tmin"]) / 2
    df["gdd"] = (df["Tsr"] - BAZA).clip(lower=0)
    return df


# ---------------------------------------------------------------- akumulacja
def ruszenie_wegetacji(rok_df: pd.DataFrame, prog: float = 5.0,
                       dni: int = 5) -> int:
    """Pierwszy dzien piecu z rzedu ze srednia dobowa powyzej progu, szukany
    od 1 lutego. Klasyczna definicja poczatku wegetacji."""
    d = rok_df[rok_df["doy"] >= 32]
    ponad = (d["Tsr"] > prog).astype(int)
    seria = ponad.rolling(dni).sum()
    trafienia = d.loc[seria >= dni, "doy"]
    return int(trafienia.iloc[0]) - dni + 1 if len(trafienia) else 60


def akumuluj(df: pd.DataFrame, start: str) -> pd.DataFrame:
    """Zwraca kolumne skumulowanego GDD wg wybranego momentu startu."""
    czesci = []
    for rok, g in df.groupby("rok"):
        g = g.sort_values("doy").copy()
        if start == "1I":
            d0 = 1
        elif start == "1II":
            d0 = 32
        else:
            d0 = ruszenie_wegetacji(g)
        g["start_doy"] = d0
        g["gdd_skum"] = g["gdd"].where(g["doy"] >= d0, 0).cumsum()
        czesci.append(g)
    return pd.concat(czesci, ignore_index=True)


def prog_z_kotwicy(akum: pd.DataFrame) -> float:
    w = akum[(akum["rok"] == KOTWICA_ROK) & (akum["doy"] == KOTWICA_DOY)]
    return float(w["gdd_skum"].iloc[0])


def termin(akum: pd.DataFrame, prog: float) -> pd.DataFrame:
    """Pierwszy dzien w roku, w ktorym suma przekracza prog cieplny."""
    wiersze = []
    for rok, g in akum.groupby("rok"):
        t = g.loc[g["gdd_skum"] >= prog, "doy"]
        wiersze.append({"rok": rok,
                        "doy": int(t.iloc[0]) if len(t) else None,
                        "start_doy": int(g["start_doy"].iloc[0])})
    return pd.DataFrame(wiersze)


def d(doy: int, rok: int = 2022) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(doy) - 1)
    return f"{x.day:02d}.{x.month:02d}"


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"Punkt: {PUNKT_NAZWA} ({PUNKT_LAT}, {PUNKT_LON})")
    print(f"Pobieram Open-Meteo {ROK_OD}-{ROK_DO}, baza GDD = {BAZA} °C\n")

    df = pobierz(PUNKT_LAT, PUNKT_LON, date(ROK_OD, 1, 1),
                 min(date(ROK_DO, 12, 31), date.today() - timedelta(days=6)))
    print(f"dni: {len(df):,}  lata: {df['rok'].min()}-{df['rok'].max()}")

    WYNIKI.mkdir(exist_ok=True)
    df.to_csv(WYNIKI / "cache" / "meteo_dobowe.csv", index=False)

    wyniki = {}
    for start, opis in (("1I", "1 stycznia"), ("1II", "1 lutego"),
                        ("weg", "ruszenie wegetacji")):
        akum = akumuluj(df, start)
        prog = prog_z_kotwicy(akum)
        t = termin(akum, prog).dropna(subset=["doy"])
        pelne = t[t["rok"] < df["rok"].max()]     # biezacy rok moze byc urwany

        sr, mn, mx = pelne["doy"].mean(), pelne["doy"].min(), pelne["doy"].max()
        # trend w dniach na dekade
        wsp = pelne["doy"].astype(float).corr(pelne["rok"].astype(float))
        nachyl = (pelne["doy"].cov(pelne["rok"]) / pelne["rok"].var()) * 10

        print(f"\nstart: {opis:22s} prog = {prog:6.0f} GDD")
        print(f"  termin kwitnienia: srednio {d(sr)}  zakres {d(mn)} - {d(mx)}  "
              f"(rozrzut {mx - mn:.0f} dni, sd {pelne['doy'].std():.1f})")
        print(f"  trend: {nachyl:+.1f} dnia/dekade (r = {wsp:+.2f})")
        if start == "weg":
            print(f"  ruszenie wegetacji: srednio {d(pelne['start_doy'].mean())}, "
                  f"zakres {d(pelne['start_doy'].min())} - "
                  f"{d(pelne['start_doy'].max())}")

        wyniki[start] = {
            "opis": opis, "prog_gdd": prog,
            "srednia_doy": sr, "min_doy": int(mn), "max_doy": int(mx),
            "sd": float(pelne["doy"].std()), "trend_dni_dekade": float(nachyl),
            "terminy": {int(r.rok): int(r.doy) for r in pelne.itertuples()},
        }

    # najskrajniejsze lata wg wariantu z ruszeniem wegetacji
    t = wyniki["weg"]["terminy"]
    naj = sorted(t.items(), key=lambda kv: kv[1])
    print(f"\nNajwczesniejsze: " + ", ".join(f"{r} ({d(v)})" for r, v in naj[:3]))
    print(f"Najpozniejsze:   " + ", ".join(f"{r} ({d(v)})" for r, v in naj[-3:]))

    # Szerokosc okna: mediana ramion NDYI z wielu lat (ksztalt_ndyi.py),
    # nie stala z krzywej 2022. Fallback tylko gdy fenologia.json jeszcze nie ma
    # tego pola.
    fen_p = WYNIKI / "json" / "fenologia.json"
    KSZTALT = {"przed_pelnia": 10, "po_pelni": 12}
    if fen_p.exists():
        k = json.loads(fen_p.read_text(encoding="utf-8")).get("ksztalt_kwitnienia")
        if k and "przed_pelnia" in k:
            KSZTALT = {"przed_pelnia": int(k["przed_pelnia"]),
                       "po_pelni": int(k["po_pelni"]),
                       "zrodlo": "fenologia.json, mediana NDYI wielu lat"}

    (WYNIKI / "json" / "gdd.json").write_text(json.dumps({
        "punkt": {"nazwa": PUNKT_NAZWA, "lat": PUNKT_LAT, "lon": PUNKT_LON},
        "baza": BAZA, "kotwica": {"rok": KOTWICA_ROK, "doy": KOTWICA_DOY},
        "zrodlo": "Open-Meteo archive (ERA5)", "start_domyslny": START,
        "ksztalt_kwitnienia": KSZTALT, "warianty": wyniki,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'gdd.json'} i meteo_dobowe.csv")
