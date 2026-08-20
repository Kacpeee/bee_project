"""
ETAP 23 - z ton cukru na POJEMNOSC PASIECZNA: ile rodzin utrzyma to miejsce.

PROBLEM, KTORY TO ROZWIAZUJE
Mapa sumowala cukier liniowo: 20 ton to dwa razy wiecej niz 10 ton. Ale
jedna rodzina zbierze najwyzej kilkadziesiat kilogramow, wiec powyzej
pewnego poziomu roznice na mapie przestawaly cokolwiek znaczyc dla decyzji.
Brak nasycenia byl najwiekszym zalozeniem konstrukcyjnym calej mapy.

ROZWIAZANIE: ZMIANA JEDNOSTKI
Zamiast "ile cukru jest" liczymy "ile rodzin ten cukier wyzywi":

    pojemnosc = cukier dostepny w zasiegu lotu / zapotrzebowanie rodziny

UWAGA - SPROSTOWANIE WCZESNIEJSZEGO TWIERDZENIA.
Pierwotnie bylo tu napisane, ze to "znosi problem z definicji, bo pojemnosc
jest wielkoscia nasycona sama w sobie". TO BYLA NIEPRAWDA. Powyzsze dzielenie
jest dzieleniem PRZEZ STALA, a takie przeksztalcenie nie moze zniesc braku
nasycenia: kolejnosc miejsc zostaje identyczna, mapa wyglada tak samo, zmienia
sie wylacznie podpis na legendzie. Blad wyszedl dopiero wtedy, gdy dodano
przelacznik jednostek na stronie i okazalo sie, ze mapa sie nie zmienia.

Co ta jednostka DAJE naprawde: liczbe, ktora pszczelarz umie porownac ze
swoim stanem posiadania. "87 rodzin" znaczy dla niego cos wprost, "6,3 tony
cukrow" nie znaczy nic. To jest zaleta KOMUNIKACYJNA, nie modelowa.

Nasycenie realnie wprowadza dopiero BILANS DEKADOWY (nizej): porownanie
podazy z popytem w danej dekadzie ma progi i deficyty, wiec jest wielkoscia
nieliniowa i daje INNA mape, a nie te sama w innych jednostkach.

ZAPOTRZEBOWANIE RODZINY
90 kg miodu rocznie (zakres 70-110) - wartosc standardowa dla warunkow
polskich, z rozkladem miesiecznym. Po przeliczeniu na cukry (/1.25) daje
72 kg cukrow na rodzine na sezon.

BILANS DEKADOWY - drugi, wazniejszy wynik
Rozklad miesieczny zuzycia pozwala porownac PODAZ z POPYTEM w kazdej
dekadzie osobno, a nie tylko w skali sezonu. Czerwiec jest miesiacem
najwyzszego zuzycia (20 kg) i jednoczesnie okresem "June Gap" - dopiero
takie zestawienie pokazuje, gdzie rodzina realnie glodzi.

ZASTRZEZENIE
Liczymy nektar WYTWORZONY przez rosliny, nie zebrany. Harris i in. (2024)
wykazali, ze wiekszosc nektaru rzepaku pozostaje niezebrana. Pojemnosc jest
wiec GORNYM oszacowaniem - mowi, gdzie na pewno nie warto jechac, a nie ile
miodu bedzie.

Uruchomienie:
    python skrypty/potencjal/pojemnosc.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import rasterio

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

MIOD_ROCZNIE_KG = 90.0          # zapotrzebowanie rodziny, warunki polskie
CUKRY_NA_MIOD = 1.25            # miod to ok. 80% cukrow
ZAPOTRZEBOWANIE = MIOD_ROCZNIE_KG / CUKRY_NA_MIOD    # kg cukrow / rodzine
# rozklad miesieczny zuzycia (kg miodu), suma ~89
ZUZYCIE_MIES = {1: 1, 2: 1, 3: 3, 4: 8, 5: 15, 6: 20, 7: 15, 8: 13,
                9: 8, 10: 3, 11: 2, 12: 1}


if __name__ == "__main__":
    print(f"zapotrzebowanie rodziny: {MIOD_ROCZNIE_KG:.0f} kg miodu = "
          f"{ZAPOTRZEBOWANIE:.0f} kg cukrow na sezon\n")

    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        cukier_kg, prof = f.read(1), f.profile
    ok = ~np.isnan(cukier_kg)
    pojemnosc = np.where(ok, cukier_kg / ZAPOTRZEBOWANIE, np.nan)

    print("POJEMNOSC PASIECZNA (rodzin w zasiegu lotu 3 km)")
    for q in (50, 75, 90, 99, 100):
        print(f"  percentyl {q:>3}: {np.nanpercentile(pojemnosc, q):7.0f} rodzin")

    # ile powierzchni wojewodztwa utrzyma co najmniej N rodzin
    print("\nudzial powierzchni wg pojemnosci")
    v = pojemnosc[ok]
    for n in (10, 30, 60, 100, 200):
        print(f"  >= {n:>3} rodzin: {100 * (v >= n).mean():5.1f}% powierzchni")

    prof.update(dtype="float32", nodata=np.nan)
    with rasterio.open(WYNIKI / "rastry" / "woj_pojemnosc.tif", "w",
                       **prof) as dst:
        dst.write(pojemnosc.astype("float32"), 1)

    # --- bilans dekadowy: podaz kontra popyt jednej rodziny
    kal = json.loads((WYNIKI / "json" / "wojewodztwo_kalendarz.json")
                     .read_text(encoding="utf-8"))
    dek, kalendarze = kal["dekady"], kal["kalendarze"]
    print(f"\nBILANS DEKADOWY dla jednej rodziny (kg cukrow)\n"
          f"{'dekada':>8}{'popyt':>8}" +
          "".join(f"{n[:10]:>12}" for n in kalendarze))
    bilans = {}
    for i, d in enumerate(dek):
        mies = min(12, max(1, int(d / 30.5) + 1))
        popyt = ZUZYCIE_MIES[mies] / 3 / CUKRY_NA_MIOD      # dekada = 1/3 mies.
        wiersz = {}
        for n, w in kalendarze.items():
            podaz_kg = w[i] * 1000            # krzywe sa w tonach
            wiersz[n] = podaz_kg / ZAPOTRZEBOWANIE
        bilans[d] = {"popyt_kg": popyt, "podaz_rodzin": wiersz}
        print(f"{d:>8}{popyt:>8.1f}" +
              "".join(f"{wiersz[n]:>12.0f}" for n in kalendarze))

    (WYNIKI / "json" / "pojemnosc.json").write_text(json.dumps({
        "zapotrzebowanie_kg_miodu_rocznie": MIOD_ROCZNIE_KG,
        "zapotrzebowanie_kg_cukrow": ZAPOTRZEBOWANIE,
        "zuzycie_miesieczne_kg_miodu": ZUZYCIE_MIES,
        "percentyle_pojemnosci": {str(q): float(np.nanpercentile(pojemnosc, q))
                                  for q in (50, 75, 90, 99, 100)},
        "bilans_dekadowy": {str(k): v for k, v in bilans.items()},
        "zastrzezenie": "nektar wytworzony, nie zebrany - gorne oszacowanie",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano woj_pojemnosc.tif i pojemnosc.json")
