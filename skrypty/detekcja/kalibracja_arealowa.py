"""
ETAP 20 - kalibracja arealowa map wielogatunkowych.

PROBLEM
Klasyfikator uczony byl na probce ZROWNOWAZONEJ - po 1400 dzialek na gatunek,
zeby zaden nie byl pokrzywdzony w treningu. Model wyniosl z tego przekonanie,
ze wszystkich upraw jest po rowno, i tak rozdaje piksele. W terenie jest
inaczej: rzepak 150 626 ha, slonecznik 7 136 ha - dwadziescia razy mniej.
Efekt: surowe wyjscie dla 2024 dawalo 83 661 ha slonecznika, czyli
dwunastokrotne zawyzenie.

Co WAZNE: to jest blad POZIOMU, nie wzoru. Test przenoszenia mierzyl
korelacje ukladu przestrzennego i wyszla 0.85-0.96 - model trafia, GDZIE
rosnie dany gatunek, myli sie tylko ILE go jest.

METODA
Sezon 2025 to jedyny rok z pelnymi deklaracjami, wiec sluzy za wzorzec:

    wspolczynnik = areal deklarowany 2025 / areal wykryty 2025

i ten sam wspolczynnik nakladany jest na pozostale sezony. To ta sama
logika co "prog arealowy" przy klasyfikatorze rzepaku, gdzie dala trafienie
w 0.5% (151 264 ha wykrytych wobec 150 559 deklarowanych).

ZALOZENIE I JEGO SPRAWDZENIE
Mnozenie przez stala zaklada, ze model myli sie ROWNOMIERNIE w przestrzeni.
Dla rzepaku da sie to sprawdzic niezaleznie: EUCROPMAP podaje areal dla 2018
i 2022, wiec porownujemy skorygowany wynik z tamta mapa. Jesli sie zgadza,
wspolczynnik przenosi sie miedzy latami i mozna mu ufac takze dla gatunkow,
dla ktorych niezaleznego zrodla nie ma.

Uruchomienie:
    python skrypty/detekcja/kalibracja_arealowa.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import pandas as pd
import pyogrio
import rasterio

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

ROK_WZORCOWY = 2025
LATA = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
# nazwy w deklaracjach skladajace sie na kazda klase modelu
SKLAD = {
    "rzepak ozimy": ["rzepak ozimy"],
    "gryka zwyczajna": ["gryka zwyczajna"],
    "malina": ["malina"],
    "słonecznik": ["słonecznik", "słonecznik oleisty"],
}


def areal_gsa() -> dict[str, float]:
    """Hektary z deklaracji 2025 - wzorzec kalibracji."""
    d = pyogrio.read_dataframe(SHP, columns=["roslina", "pow"],
                               read_geometry=False, encoding="utf-8")
    d["ha"] = pd.to_numeric(
        d["pow"].astype(str).str.replace(" ha", "", regex=False)
        .str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    return {k: float(d.loc[d.roslina.isin(v), "ha"].sum())
            for k, v in SKLAD.items()}


if __name__ == "__main__":
    wzor = WYNIKI / "cache" / f"wielo_klasy_{ROK_WZORCOWY}.npz"
    if not wzor.exists():
        raise SystemExit(f"brak {wzor.name} - najpierw dolicz sezon "
                         f"{ROK_WZORCOWY}, to on jest wzorcem")

    # Areal wykryty MUSI byc liczony na tym samym obszarze co deklaracje.
    # Pierwsza wersja sumowala cala tablice, a ta obejmuje takze wykrycia
    # POZA wojewodztwem (prostokat kafli siega Mazowsza i Podkarpacia),
    # podczas gdy GSA konczy sie na granicy. Wspolczynnik wychodzil przez to
    # za maly i zanizal wszystkie gatunki o kilkanascie procent.
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        maska = ~np.isnan(f.read(1))
    print(f"obszar odniesienia: {maska.sum():,} px w granicy wojewodztwa\n")

    gsa = areal_gsa()
    with np.load(wzor) as z:
        wykryte = {n: float(z[n][maska].sum()) for n in SKLAD}

    print(f"KALIBRACJA NA SEZONIE {ROK_WZORCOWY}\n")
    print(f"{'gatunek':22s}{'wykryte ha':>12}{'deklarowane':>13}"
          f"{'wspolczynnik':>14}")
    wsp = {}
    for n in SKLAD:
        wsp[n] = gsa[n] / max(wykryte[n], 1e-9)
        print(f"{n[:20]:22s}{wykryte[n]:>12,.0f}{gsa[n]:>13,.0f}"
              f"{wsp[n]:>14.3f}")

    # --- korekta wszystkich sezonow
    print(f"\nAREAL PO KOREKCIE (ha)\n{'rok':>6}" +
          "".join(f"{n[:10]:>12}" for n in SKLAD))
    skorygowane = {}
    for rok in LATA:
        f = WYNIKI / "cache" / f"wielo_klasy_{rok}.npz"
        if not f.exists():
            continue
        with np.load(f) as z:
            war = {n: z[n] * wsp[n] for n in SKLAD}
        skorygowane[rok] = {n: float(v[maska].sum()) for n, v in war.items()}
        np.savez_compressed(
            WYNIKI / "cache" / f"wielo_skalibrowane_{rok}.npz", **war)
        print(f"{rok:>6}" + "".join(f"{skorygowane[rok][n]:>12,.0f}"
                                    for n in SKLAD))

    # --- sprawdzian niezalezny: rzepak wobec EUCROPMAP
    print("\nSPRAWDZIAN: rzepak wobec EUCROPMAP (niezalezne zrodlo)")
    kontrola = {}
    for rok in (2018, 2022):
        eu = WYNIKI / "cache" / f"eucropmap_rzepak_{rok}.npy"
        if not eu.exists() or rok not in skorygowane:
            print(f"  {rok}: brak danych do porownania")
            continue
        ha_eu = float(np.load(eu).sum())
        ha_my = skorygowane[rok]["rzepak ozimy"]
        kontrola[rok] = {"eucropmap_ha": ha_eu, "model_ha": ha_my,
                         "odchylenie_pct": (ha_my / max(ha_eu, 1) - 1) * 100}
        print(f"  {rok}: EUCROPMAP {ha_eu:,.0f} ha, model {ha_my:,.0f} ha "
              f"({kontrola[rok]['odchylenie_pct']:+.0f}%)")
    if kontrola:
        print("  Odchylenie do ok. 20% oznacza, ze wspolczynnik z 2025")
        print("  przenosi sie na inne lata i korekcie mozna ufac.")

    (WYNIKI / "json" / "kalibracja_arealowa.json").write_text(json.dumps({
        "rok_wzorcowy": ROK_WZORCOWY, "areal_gsa": gsa,
        "areal_wykryty": wykryte, "wspolczynniki": wsp,
        "areal_po_korekcie": skorygowane, "kontrola_eucropmap": kontrola,
        "zalozenie": "blad modelu jest rownomierny w przestrzeni; "
                     "uzasadnienie: korelacja ukladu 0.85-0.96 w tescie "
                     "przenoszenia, wiec myli sie poziom a nie wzor",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano wielo_skalibrowane_*.npz i kalibracja_arealowa.json")
