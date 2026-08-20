"""
ETAP 10 - detekcja rzepaku dla SIEDMIU sezonow (2019-2025): material na mape
przecietnego roku.

DLACZEGO PELNY ZESTAW CECH, A NIE PRZEDKWITNIENIOWY
Dla lat minionych nie ma wymogu operacyjnosci - to rekonstrukcja, nie
prognoza. Pelny klasyfikator (8 cech, z oknem kwitnienia) ma F1 0.92 wobec
0.84 przedkwitnieniowego, wiec do historii bierzemy lepszy.

TRENING RAZ, PREDYKCJA NA KAZDY ROK
Model uczy sie na etykietach GSA 2025 (jedyny pewny rocznik treningowy
z pelna geometria dzialek) i jest stosowany do cech policzonych osobno dla
kazdego sezonu. Cechy sa anomaliami wzgledem mediany sceny, wiec miedzyroczny
transfer jest z konstrukcji; jego koszt zmierzymy porownujac rok 2022
z EUCROPMAP 2022, a 2025 z GSA 2025.

ROK 2018 POMIJAMY: cecha jesienna wymaga zdjec z jesieni 2017, ktorych
w archiwum L2A dla Polski praktycznie nie ma.

Wszystko wznawialne: kazdy kafel zapisywany od razu.

Uruchomienie:
    python detekcja_lata.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import ee
import numpy as np
import rasterio

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import detekcja_wojewodztwo as D
import gee_klasyfikator_rzepaku as K
import klasyfikator_gsa as G

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

ROK_TRENINGU = 2025
LATA = [2025, 2024, 2023, 2022, 2021, 2020, 2019]   # 2025 najpierw: kalibracja progu
CECHY8 = [o[0] for o in K.OKNA]


if __name__ == "__main__":
    K.start()
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx) = f.bounds, f.shape
    K.AOI = ee.Geometry.Rectangle([b.left, b.bottom, b.right, b.top],
                                  "EPSG:2180", False)

    print("Trening (pelne 8 cech, etykiety GSA 2025):")
    df = D.przytnij(D.punkty_wieloobszarowe())
    xt = K.cechy(ROK_TRENINGU).updateMask(K.orne_maska())
    proba = xt.sampleRegions(collection=G.kolekcja(df), scale=10,
                             geometries=False, tileScale=4)
    las = (ee.Classifier.smileRandomForest(K.LICZBA_DRZEW)
           .train(features=proba.filter(ee.Filter.eq("test", 0)),
                  classProperty="rzepak", inputProperties=CECHY8)
           .setOutputMode("PROBABILITY"))
    m = (proba.filter(ee.Filter.eq("test", 1))
         .classify(las.setOutputMode("CLASSIFICATION"))
         .errorMatrix("rzepak", "classification").array().getInfo())
    (tn, fp), (fn, tp) = m[0], m[1]
    prec, czul = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    print(f"  walidacja przestrzenna: precyzja {prec:.3f} czulosc {czul:.3f} "
          f"F1 {2*prec*czul/max(prec+czul,1e-9):.3f}\n")

    lista = D.kafle(nx, ny)
    # te same kafle co w detekcji operacyjnej: tylko przecinajace wojewodztwo
    from shapely.geometry import MultiLineString, box
    from shapely.ops import polygonize, unary_union
    import mapa_wojewodztwa as MW
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in MW.podklad()[2] if len(g) > 1]))), key=lambda q: q.area)
    lista = [(x0, y0, w, h) for x0, y0, w, h in D.kafle(nx, ny)
             if poly.intersects(box(b.left + x0 * D.PIKSEL,
                                    b.top - (y0 + h) * D.PIKSEL,
                                    b.left + (x0 + w) * D.PIKSEL,
                                    b.top - y0 * D.PIKSEL))]
    t0 = time.time()
    for rok in LATA:
        wyj = WYNIKI / "cache" / f"woj_prawd_{rok}.npy"
        if wyj.exists():
            print(f"SEZON {rok}: gotowy, pomijam")
            continue
        print(f"SEZON {rok}:")
        xr = K.cechy(rok).updateMask(K.orne_maska())
        prawd = (xr.classify(las).unmask(0)
                 .reproject(crs="EPSG:2180", scale=D.SKALA_KLAS)
                 .reduceResolution(ee.Reducer.mean(), maxPixels=64)
                 .reproject(crs="EPSG:2180", scale=D.PIKSEL)
                 .rename("p").toFloat())
        cache = WYNIKI / "cache" / f"det_kafle_{rok}.npz"
        det = np.full((ny, nx), np.nan, "float32")
        gotowe = set()
        if cache.exists():
            z = np.load(cache)
            det, gotowe = z["det"], set(map(tuple, z["gotowe"]))
            print(f"  wznawiam: {len(gotowe)}/{len(lista)} kafli")
        for i, (x0, y0, w, h) in enumerate(lista, 1):
            if (x0, y0) in gotowe:
                continue
            a = D.pobierz(prawd, b.left + x0 * D.PIKSEL,
                          b.top - y0 * D.PIKSEL, w, h)
            det[y0:y0 + h, x0:x0 + w] = a
            gotowe.add((x0, y0))
            np.savez_compressed(cache, det=det,
                                gotowe=np.array(sorted(gotowe), dtype=int))
            print(f"  {rok} kafel {i}/{len(lista)}  "
                  f"{(time.time()-t0)/60:6.1f} min")
        np.save(wyj, det)
        cache.unlink(missing_ok=True)
        print(f"  zapisano {wyj.name}\n")

    (WYNIKI / "json" / "detekcja_lata.json").write_text(json.dumps({
        "lata": LATA, "trening": ROK_TRENINGU, "cechy": CECHY8,
        "walidacja": {"precyzja": prec, "czulosc": czul},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("KONIEC - wszystkie sezony policzone")
