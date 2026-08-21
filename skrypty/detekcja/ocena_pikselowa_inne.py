"""
Dobranie klasy "inne" do oceny pikselowej.

PO CO
Pierwsza wersja ocena_pikselowa.py probkowala wylacznie gatunki pozytkowe.
Rzepak nie mial przez to szansy pomylic sie ze zbozem czy kukurydza, choc
to wlasnie one zajmuja wiekszosc gruntow ornych i sa realnym zrodlem
falszywych alarmow. Zmierzona precyzja 0,844 dotyczyla wiec swiata,
w ktorym istnieja same rosliny miododajne.

Bez tej klasy nie da sie tez przewazyc wyniku na prewalencje rzeczywista -
brakuje najliczniejszej kategorii.

Skrypt dobiera dzialki "inne" z blokow TESTOWYCH (ta sama regula bloku) i
pobiera dla nich cechy. ocena_pikselowa.py doklada je, jesli plik istnieje.

Uruchomienie:
    python skrypty/detekcja/ocena_pikselowa_inne.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import Point

sys.path[:0] = [str(p) for p in Path(__file__).resolve().parents[1].iterdir()
                if p.is_dir()]

import gee_klasyfikator_rzepaku as K                          # noqa: E402
import potencjal_gsa as P                                     # noqa: E402
import ocena_pikselowa as O                                   # noqa: E402

CACHE = O.WYNIKI / "cache" / "piksele_inne_punkty.csv"
CACHE_CECH = O.WYNIKI / "cache" / "piksele_inne_cechy.csv"
DZIALEK = 1100          # klasa zbiorcza, wiec szersza niz pojedynczy gatunek


if __name__ == "__main__":
    K.start()
    if CACHE.exists():
        d = pd.read_csv(CACHE)
        print(f"punkty 'inne' z cache: {len(d):,}")
    else:
        # ta sama definicja "inne", co w klasyfikator_wielo.py:
        # 12 najczestszych upraw NIEpozytkowych
        nazwy = pyogrio.read_dataframe(O.SHP, columns=["roslina"],
                                       read_geometry=False, encoding="utf-8")
        licz = nazwy["roslina"].value_counts()
        inne = [n for n in licz.index if n not in P.POZYTKI][:12]
        print("klasa 'inne': " + ", ".join(x[:20] for x in inne))

        lst = ", ".join("'" + n.replace("'", "''") + "'" for n in inne)
        g = pyogrio.read_dataframe(O.SHP, encoding="utf-8",
                                   where=f"roslina IN ({lst})")
        sr = g.geometry.representative_point()
        bx = np.floor(sr.x.values / O.BLOK_M).astype(int)
        by = np.floor(sr.y.values / O.BLOK_M).astype(int)
        g = g[((bx + by) % 10) < O.UDZIAL_TESTU * 10]
        g = g[g.geometry.area >= 3000]
        g = g.sample(n=min(DZIALEK, len(g)), random_state=O.ZIARNO)
        print(f"dzialek 'inne' w blokach testowych: {len(g):,}")

        rng = np.random.default_rng(O.ZIARNO + 1)
        wiersze = []
        for idx, geom in zip(g.index, g.geometry):
            minx, miny, maxx, maxy = geom.bounds
            proby, ile = 0, 0
            while ile < O.PIKSELI_NA_DZIALKE and proby < 200:
                proby += 1
                p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
                if not geom.contains(p):
                    continue
                gr = (geom.exterior if geom.geom_type == "Polygon"
                      else geom.boundary)
                wiersze.append({"x": p.x, "y": p.y, "etykieta": "inne",
                                "dzialka": 900_000 + int(idx),
                                "od_granicy_m": float(gr.distance(p)),
                                "pow_ha": float(geom.area) / 10_000})
                ile += 1
        d = pd.DataFrame(wiersze)
        do4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        d["lon"], d["lat"] = do4326.transform(d["x"].values, d["y"].values)
        # numeracja od 500 000, zeby nie kolidowala z pierwsza proba
        d = d.reset_index(drop=True)
        d["i"] = d.index + 500_000
        d.to_csv(CACHE, index=False)
        print(f"pikseli 'inne': {len(d):,}")

    O.CACHE_CECH = CACHE_CECH          # osobny plik cech
    X = O.pobierz_cechy(d)
    print(f"gotowe: cechy {X.shape} -> {CACHE_CECH.name}")
