"""
ETAP 14 - dynamiczne okno kwitnienia jabloni metoda KOTWICZENIA.

PROBLEM
Terminy kwitnienia gatunkow innych niz rzepak sa sztywne - te same co roku.
Dla roslin jarych (gryka, slonecznik) to jedyna uczciwa opcja, bo ich faza
zalezy od nieznanej daty siewu. Ale uprawy trwale (sad) zimuja w polu i ich
termin napedza wylacznie pogoda - a modele GDD dla jabloni to stara,
udokumentowana dziedzina sadownicza.

DLACZEGO NIE BIERZEMY CUDZEGO PROGU
Lekcja z rzepaku: literaturowa baza 4 C dala wynik o 38% gorszy od
kalibracji. Progi z innych klimatow i jednostek (GDD-Fahrenheit, inne
odmiany: 522-750 jednostek) nie przenosza sie wprost.

METODA: KOTWICZENIE
  baza 5 C (41 F) od 1 I     - z literatury sadowniczej (MSU, prace
                               fenologiczne dla jabloni)
  prog                       - skalibrowany tak, zeby MEDIANA wieloletnia
                               (2000-2026, pilot) trafila dokladnie
                               w udokumentowana pelnie kwitnienia (5 V,
                               srodek okna 28 IV - 12 V z tabel)
Zero nowych liczb bez zrodla: srednia z tabeli branzowej (klasa B),
mechanizm zmiennosci z literatury GDD, zmiennosc miedzyroczna z pogody.

Wynik: prog + daty per rok (pilot) + mapa terminu 2025 na siatce meteo.

Uruchomienie:
    python fenologia_sadu.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

BAZA = 5.0          # C - literatura sadownicza (41 F)
D0 = 1              # akumulacja od 1 stycznia
PELNIA_LIT = 125    # 5 V - srodek udokumentowanego okna 28 IV - 12 V
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def dz(doy: float, rok: int = 2025) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def suma_do(s: pd.DataFrame, doy_cel: int) -> float:
    doy = s["data"].dt.dayofyear.to_numpy()
    gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - BAZA, 0)
    gdd[doy < D0] = 0
    return float(np.cumsum(gdd)[np.searchsorted(doy, doy_cel)])


def termin(s: pd.DataFrame, prog: float) -> float:
    doy = s["data"].dt.dayofyear.to_numpy()
    gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - BAZA, 0)
    gdd[doy < D0] = 0
    i = np.searchsorted(np.cumsum(gdd), prog)
    return float(doy[i]) if i < len(doy) else np.nan


if __name__ == "__main__":
    d = pd.read_csv(WYNIKI / "cache" / "meteo_dobowe.csv",
                    parse_dates=["data"])
    d["rok"] = d["data"].dt.year

    # kotwica: mediana sumy GDD w dniu literaturowej pelni, po 26 sezonach
    sumy = [suma_do(s.sort_values("data"), PELNIA_LIT)
            for rok, s in d.groupby("rok") if rok <= 2025]
    prog = float(np.median(sumy))
    print(f"kotwica: mediana GDD(baza {BAZA:.0f}, od 1 I) w dniu {dz(PELNIA_LIT)}"
          f" = {prog:.0f} jednostek (rozrzut {min(sumy):.0f}-{max(sumy):.0f})")

    daty = {}
    for rok, s in d.groupby("rok"):
        t = termin(s.sort_values("data"), prog)
        if not np.isnan(t):
            daty[int(rok)] = t
    v = np.array(list(daty.values()))
    print(f"\npilot, {len(daty)} sezonow: mediana {dz(np.median(v))}, "
          f"zakres {dz(v.min())} - {dz(v.max())} "
          f"(rozrzut {v.max()-v.min():.0f} dni)")
    for rok in sorted(daty)[-8:]:
        print(f"  {rok}: {dz(daty[rok])}")

    # mapa 2025: termin na 63 punktach siatki wojewodzkiej
    g = pd.read_csv(WYNIKI / "cache" / "woj_meteo_siatka.csv",
                    parse_dates=["data"])
    pkt = []
    for (x, y), s in g.groupby(["x", "y"]):
        t = termin(s.sort_values("data"), prog)
        pkt.append({"x": x, "y": y, "doy": t})
    pk = pd.DataFrame(pkt)
    print(f"\nsiatka 2025: {dz(pk.doy.min())} - {dz(pk.doy.max())} "
          f"(rozrzut {pk.doy.max()-pk.doy.min():.0f} dni w wojewodztwie)")
    pk.to_csv(WYNIKI / "cache" / "kwitnienie_sad_2025.csv", index=False)

    (WYNIKI / "json" / "fenologia_sadu.json").write_text(json.dumps({
        "metoda": "kotwiczenie: baza z literatury, prog z mediany "
                  "wieloletniej w dniu literaturowej pelni",
        "baza": BAZA, "start": "1I", "prog": prog,
        "pelnia_literaturowa": PELNIA_LIT,
        "daty_pilot": daty,
        "mapa_2025": {"min": float(pk.doy.min()), "max": float(pk.doy.max())},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano fenologia_sadu.json i kwitnienie_sad_2025.csv")
