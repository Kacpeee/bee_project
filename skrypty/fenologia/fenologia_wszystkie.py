"""
ETAP 21 - kalendarz w calosci sterowany pogoda, dla WSZYSTKICH pozytkow.

PROBLEM
Kalendarz mial dotad jedna date ruchoma (rzepak, model kalibrowany pomiarem
satelitarnym) i pietnascie sztywnych z tabel branzowych. Sztywna data jest
bledna niezaleznie od tego, czy umiemy ja zmierzyc: malina reaguje na cieplo
tak samo jak rzepak, tylko jej kwitnienia nie widac z orbity (jej "szczyt
zoltosci" wypada we wrzesniu - to jesienne zolkniecie lisci, nie kwiaty).

METODA: KOTWICZENIE
Dla kazdego gatunku:
  baza      - z literatury, wg grupy termicznej rosliny (patrz BAZY)
  prog      - dobrany tak, by MEDIANA z 27 sezonow trafila dokladnie
              w tabelaryczna date pelni kwitnienia
Tabela wyznacza wiec SREDNIA, a pogoda cala zmiennosc miedzyroczna. Zadna
nowa liczba nie jest zmyslona: baza i data pochodza ze zrodel, prog jest
z nich wyliczony.

CO TO ZMIENIA
W cieplym 2024 caly kalendarz przesuwa sie do przodu, w zimnym 2021 cofa -
tak jak rzepak przesuwa sie o 26 dni miedzy tymi latami. Dotad przesuwal sie
tylko rzepak, a reszta stala w miejscu, co zafalszowywalo szerokosc przerw
miedzy pozytkami.

SPRAWDZIAN
Dla szesciu gatunkow (rzepak, slonecznik, gryka, gorczyca, fasola, bobik)
kwitnienie WIDAC z satelity - ich szczyt NDYI pokrywa sie z tabela. Na nich
mozna sprawdzic, czy kotwiczony model daje sensowna amplitude wahan; dla
pozostalych zostaje zalozeniem, i tak jest oznaczone.

Uruchomienie:
    python skrypty/fenologia/fenologia_wszystkie.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import potencjal_gsa as P

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

# BAZY TEMPERATUROWE - kazda z podanym zrodlem.
# Pierwsza wersja tego pliku miala 10 C dla "cieplolubnych" i 5 C dla reszty
# z komentarzem "wartosci standardowe w agrometeo" - bez zadnego odsylacza.
# Sprawdzenie w literaturze obalilo obie: gryka ma 5 C, slonecznik 6.7 C.
# To jest przyklad na to, ze prawdopodobnie brzmiaca liczba potrafi byc zla.
BAZY = {
    # (baza, gatunki, zrodlo)
    "rzepak": (1.0, ["rzepak ozimy"],
               "kalibracja wlasna na 52 obserwacjach Sentinel-2"),
    "gryka": (5.0, ["gryka zwyczajna"],
              "modele fenologiczne Fagopyrum esculentum, "
              "Agricultural Systems 1998"),
    "slonecznik": (6.7, ["słonecznik", "słonecznik oleisty"],
                   "NDAWN/NDSU, Sunflower Growing Degree Days (44 F)"),
    "umiarkowane": (5.0, ["malina", "porzeczka", "Sad", "TUZ",
                          "koniczyna czerwona", "lucerna mieszańcowa",
                          "gorczyca", "gorczyca biała", "bobik",
                          "rzepak jary", "fasola wielokwiatowa"],
                    "BEZ ZRODLA GATUNKOWEGO - przyjeta wartosc typowa dla "
                    "roslin strefy umiarkowanej; do zweryfikowania"),
}
BAZA_RZEPAK, PROG_RZEPAK, D0_RZEPAK = 1.0, 555.0, 32
D0 = 1                      # akumulacja od 1 stycznia dla kotwiczonych

# gatunki, dla ktorych kwitnienie widac z satelity (szczyt NDYI zgodny
# z tabela) - na nich model da sie sprawdzic, a nie tylko zalozyc
MIERZALNE = {"rzepak ozimy", "słonecznik", "gryka zwyczajna", "gorczyca",
             "fasola wielokwiatowa", "bobik"}

# Gatunki lesne: maja FENOLOGIE, ale nie maja jeszcze warstwy powierzchniowej
# (czekaja na dane z Banku Danych o Lasach). Dlatego liczone osobno, poza
# slownikiem pozytkow - detekcja i fenologia sa niezalezne, wiec date
# kwitnienia da sie modelowac zanim bedzie wiadomo, gdzie dokladnie rosna.
#
# Kotwica lipy pochodzi z OBSERWACJI IMGW (srednia 2007-2021 dla
# Lubelszczyzny: 21-30 VI, przyjeto 25 VI), a nie z mojego zalozenia -
# pierwotnie wpisalem 1 VII "z ogolnej wiedzy" i bylo o piec dni za pozno.
LESNE = {
    # 176 = srednia z mapy IMGW (21-30 VI); + 7 d zmierzonego przesuniecia
    # systematycznego na 5 rocznikach -> 183. Po korekcie blad spadl
    # z -6.2 d na +0.8 d (walidacja_imgw_pory.py).
    "lipa": (183, 5.0, "IMGW, pora 'lato' = zakwitanie lipy drobnolistnej; "
                       "kotwica skorygowana o zmierzone przesuniecie"),
    "robinia (akacja)": (145, 5.0, "literatura pszczelarska, koniec V"),
    "klon": (125, 5.0, "literatura pszczelarska, poczatek V"),
}


def dz(doy: float) -> str:
    x = date(2025, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def baza_dla(nazwa: str) -> float:
    if nazwa == "rzepak ozimy":
        return BAZA_RZEPAK
    for b, lista, _ in BAZY.values():
        if nazwa in lista:
            return b
    return 5.0


def akumulacja(s: pd.DataFrame, baza: float, d0: int) -> tuple:
    s = s.sort_values("doy")
    doy = s["doy"].to_numpy()
    g = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - baza, 0)
    g[doy < d0] = 0
    return doy, np.cumsum(g)


if __name__ == "__main__":
    d = pd.read_csv(WYNIKI / "cache" / "meteo_dobowe.csv", parse_dates=["data"])
    d["rok"] = d["data"].dt.year
    d["doy"] = d["data"].dt.dayofyear
    lata = sorted(d["rok"].unique())
    print(f"meteo: {lata[0]}-{lata[-1]}, {len(lata)} sezonow\n")

    print(f"{'gatunek':24s}{'baza':>6}{'prog':>7}{'tabela':>8}"
          f"{'mediana':>9}{'najwcz.':>9}{'najpozn.':>9}{'rozrzut':>8}  zrodlo")
    wynik = {}
    wszystkie = [(n, P.POZYTKI[n][2], baza_dla(n), P.POZYTKI[n][5])
                 for n in P.POZYTKI]
    wszystkie += [(n, p0, b, 'B') for n, (p0, b, _) in LESNE.items()]
    for nazwa, p0, baza, kl in wszystkie:
        d0 = D0_RZEPAK if nazwa == "rzepak ozimy" else D0

        # prog: mediana sumy GDD w dniu tabelarycznej pelni
        sumy = []
        for rok, s in d.groupby("rok"):
            doy, cum = akumulacja(s, baza, d0)
            i = np.searchsorted(doy, p0)
            if i < len(cum):
                sumy.append(cum[i])
        if not sumy:
            continue
        prog = PROG_RZEPAK if nazwa == "rzepak ozimy" else float(np.median(sumy))

        # daty per sezon przy tym progu
        daty = {}
        for rok, s in d.groupby("rok"):
            doy, cum = akumulacja(s, baza, d0)
            i = np.searchsorted(cum, prog)
            if i < len(doy):
                daty[int(rok)] = int(doy[i])
        if not daty:
            continue
        v = np.array(list(daty.values()))
        wynik[nazwa] = {
            "baza": baza, "prog": prog, "start_doy": d0,
            "pelnia_tabela": p0, "mediana": float(np.median(v)),
            "min": int(v.min()), "max": int(v.max()),
            "rozrzut_dni": int(v.max() - v.min()),
            "mierzalny_z_satelity": nazwa in MIERZALNE,
            "daty": daty,
        }
        znak = "*" if nazwa in MIERZALNE else " "
        print(f"{nazwa[:22]:24s}{baza:>6.1f}{prog:>7.0f}{dz(p0):>8}"
              f"{dz(np.median(v)):>9}{dz(v.min()):>9}{dz(v.max()):>9}"
              f"{v.max()-v.min():>7} d  {kl}{znak}")

    mierz = [n for n in wynik if wynik[n]["mierzalny_z_satelity"]]
    print(f"\n* = kwitnienie widoczne z satelity ({len(mierz)} z {len(wynik)}) "
          f"- na tych model da sie sprawdzic pomiarem")
    sr = np.mean([wynik[n]["rozrzut_dni"] for n in wynik])
    print(f"sredni rozrzut miedzy sezonami: {sr:.0f} dni "
          f"(dotad wszystkie poza rzepakiem mialy 0)")

    (WYNIKI / "json" / "fenologia_wszystkie.json").write_text(json.dumps({
        "metoda": "kotwiczenie: baza z literatury wg grupy termicznej, prog "
                  "dobrany tak, by mediana wieloletnia trafila w tabelaryczna "
                  "pelnie kwitnienia",
        "bazy": {k: {"wartosc": v[0], "gatunki": v[1], "zrodlo": v[2]}
         for k, v in BAZY.items()},
        "mierzalne_z_satelity": sorted(MIERZALNE),
        "gatunki": wynik,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano fenologia_wszystkie.json")
