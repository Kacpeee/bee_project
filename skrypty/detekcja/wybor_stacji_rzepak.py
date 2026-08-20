"""
Pelna historia z JEDNEJ stacji eDWIN -> surowe rekordy + agregaty dobowe.

Zmiany wzgledem poprzedniej wersji:
  - zapisuje WSZYSTKIE pola, nie tylko temperature (okno lotne wymaga danych godzinowych)
  - sam wykrywa, od kiedy stacja ma dane (sonda wstecz)
  - retry z backoffem + przerwy miedzy zapytaniami (to bylo zrodlo 503)
  - zapis przyrostowy po kazdym oknie - przerwanie nie kasuje dorobku
  - czas lokalny Europe/Warsaw przy grupowaniu na doby
  - agregaty: GDD + godziny lotne pszczoly

Uruchom najpierw z SONDUJ_START = True, zeby poznac zakres i schemat pol.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://edwin-meteo.apps.paas.psnc.pl/meteo/station/"

# ---------------------------------------------------------------- konfiguracja
STACJA = "PME35"                      # <- wstaw ID zwyciezcy rankingu rzepaku
DATA_DO = date.today()
SONDUJ_START = True                   # True = znajdz najstarsze dane automatycznie
DATA_OD_RECZNIE = date(2021, 1, 1)    # uzywane gdy SONDUJ_START = False

SUROWE = ROOT / "wyniki" / "cache" / f"meteo_{STACJA}_surowe.parquet"
DOBOWE = ROOT / "wyniki" / "cache" / f"meteo_{STACJA}_dobowe.csv"

NAGLOWKI = {
    "accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

PRZERWA_S = 0.6        # miedzy zapytaniami - nie zajezdzaj API
MAX_STRON = 200        # bezpiecznik przed petla nieskonczona

# Progi lotnosci pszczoly miodnej (dostosuj i uzasadnij w pracy)
T_LOT_MIN = 12.0       # °C - ponizej pszczoly praktycznie nie wylatuja
WIATR_MAX = 6.0        # m/s
GDD_BAZA = 5.0         # °C - baza dla rzepaku ozimego

# Nazwy pol w API - ZWERYFIKUJ po pierwszym pobraniu (skrypt wypisze liste)
POLA = {
    "czas":       "measurementDate",
    "temp":       "airTemperature",
    "wilgotnosc": "airHumidity",
    "opad":       "rainfall",
    "wiatr":      "windSpeed",
}


# ---------------------------------------------------------------- pobieranie
def pobierz_okno(station_id: str, od: date, do: date, proby: int = 4) -> list[dict]:
    """Jedno okno <=90 dni, ze stronicowaniem i ponawianiem."""
    rekordy, page = [], 0
    while page < MAX_STRON:
        params = {
            "after": f"{od.isoformat()}T00:00:00Z",
            "before": f"{do.isoformat()}T23:59:59Z",
            "page": page,
            "size": 5000,
        }
        odp = None
        for i in range(proby):
            try:
                r = requests.get(f"{BASE}{station_id}", params=params,
                                 headers=NAGLOWKI, timeout=90)
                if r.status_code in (429, 500, 502, 503, 504):
                    if i < proby - 1:
                        czekaj = 3 * 2 ** i
                        print(f"    {r.status_code}, ponawiam za {czekaj}s")
                        time.sleep(czekaj)
                        continue
                r.raise_for_status()
                odp = r
                break
            except requests.RequestException as e:
                if i == proby - 1:
                    print(f"    NIEUDANE {od}..{do} str.{page}: {e}")
                    return rekordy
                time.sleep(3 * 2 ** i)

        if odp is None:
            return rekordy

        dane = odp.json()
        partia = dane if isinstance(dane, list) else dane.get("content", [])
        if not partia:
            break

        rekordy.extend(partia)
        if len(partia) < params["size"]:
            break          # ostatnia strona
        page += 1
        time.sleep(PRZERWA_S)

    return rekordy


def znajdz_poczatek(station_id: str, najstarszy: date = date(2019, 1, 1)) -> date:
    """Cofa sie rok po roku, az przestana pojawiac sie dane."""
    print("Sonduje poczatek historii stacji...")
    rok = date.today().year
    ostatni_z_danymi = None
    while rok >= najstarszy.year:
        proba = pobierz_okno(station_id, date(rok, 5, 1), date(rok, 5, 15))
        if proba:
            ostatni_z_danymi = rok
            print(f"  {rok}: sa dane ({len(proba)} rekordow w polowie maja)")
        else:
            print(f"  {rok}: brak danych -> koniec sondowania")
            break
        rok -= 1
        time.sleep(PRZERWA_S)

    if ostatni_z_danymi is None:
        raise SystemExit("Stacja nie zwraca zadnych danych - sprawdz ID.")
    return date(ostatni_z_danymi, 1, 1)


def pobierz_wszystko(station_id: str, od: date, do: date) -> pd.DataFrame:
    kawalki, start = [], od
    while start <= do:
        koniec = min(start + timedelta(days=89), do)
        print(f"  {start} .. {koniec}", end=" ", flush=True)
        partia = pobierz_okno(station_id, start, koniec)
        print(f"-> {len(partia)} rekordow")
        if partia:
            kawalki.append(pd.DataFrame(partia))
            # zapis przyrostowy - przerwanie nie kasuje dorobku
            pd.concat(kawalki, ignore_index=True).to_parquet(SUROWE, index=False)
        start = koniec + timedelta(days=1)
        time.sleep(PRZERWA_S)

    return pd.concat(kawalki, ignore_index=True) if kawalki else pd.DataFrame()


# ---------------------------------------------------------------- agregacja
def do_dobowych(df: pd.DataFrame) -> pd.DataFrame:
    """Agregaty dobowe w czasie lokalnym, z metrykami pod model pszczeli."""
    kol_czas = POLA["czas"]
    df = df.copy()
    df["ts"] = pd.to_datetime(df[kol_czas], utc=True).dt.tz_convert("Europe/Warsaw")
    df["doba"] = df["ts"].dt.date

    t, w, o, h = POLA["temp"], POLA["wiatr"], POLA["opad"], POLA["wilgotnosc"]
    obecne = df.columns

    # warunek lotu - skladniki liczone tylko z dostepnych pol
    lot = df[t] >= T_LOT_MIN if t in obecne else pd.Series(False, index=df.index)
    if w in obecne:
        lot &= df[w].fillna(0) <= WIATR_MAX
    if o in obecne:
        lot &= df[o].fillna(0) <= 0.1
    df["_lot"] = lot

    agg = {"n_pomiarow": (t, "size")}
    if t in obecne:
        agg |= {"T_min": (t, "min"), "T_max": (t, "max"), "T_avg": (t, "mean")}
    if h in obecne:
        agg |= {"RH_avg": (h, "mean")}
    if o in obecne:
        agg |= {"opad_suma": (o, "sum")}
    if w in obecne:
        agg |= {"wiatr_avg": (w, "mean"), "wiatr_max": (w, "max")}

    d = df.groupby("doba").agg(**agg).reset_index()

    # udzial pomiarow spelniajacych warunek lotu -> przelicz na godziny
    udzial = df.groupby("doba")["_lot"].mean()
    d["godz_lotne"] = (udzial.values * 24).round(1)

    if "T_min" in d and "T_max" in d:
        d["T_sr_klim"] = ((d["T_max"] + d["T_min"]) / 2).round(2)
        d["GDD"] = (d["T_sr_klim"] - GDD_BAZA).clip(lower=0).round(2)
        d["GDD_skum"] = d.groupby(pd.to_datetime(d["doba"]).dt.year)["GDD"].cumsum()

    d.insert(0, "stationId", df.get("stationId", pd.Series([STACJA])).iloc[0])
    return d.round(2)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    poczatek = znajdz_poczatek(STACJA) if SONDUJ_START else DATA_OD_RECZNIE
    print(f"\nStacja {STACJA}: pobieram {poczatek} .. {DATA_DO}")

    surowe = pobierz_wszystko(STACJA, poczatek, DATA_DO)
    if surowe.empty:
        raise SystemExit("Brak danych.")

    print(f"\nSurowe rekordy: {len(surowe):,} -> {SUROWE.name}")
    print(f"Dostepne pola: {sorted(surowe.columns)}")
    print("^ sprawdz, czy slownik POLA na gorze skryptu sie zgadza\n")

    dobowe = do_dobowych(surowe)
    dobowe.to_csv(DOBOWE, index=False)

    print(f"Doby: {len(dobowe)} ({dobowe['doba'].min()} .. {dobowe['doba'].max()})")
    oczekiwane = (dobowe["doba"].max() - dobowe["doba"].min()).days + 1
    print(f"Kompletnosc dobowa: {len(dobowe) / oczekiwane:.1%}")
    print(f"Mediana pomiarow na dobe: {dobowe['n_pomiarow'].median():.0f}")
    print(f"\nZapisano: {DOBOWE.name}")
    print(dobowe.tail(5).to_string(index=False))