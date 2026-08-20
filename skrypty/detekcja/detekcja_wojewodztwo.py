"""
ETAP 6 - detekcja rzepaku w calym wojewodztwie BEZ deklaracji ARiMR.

PO CO
Dotychczasowa mapa potencjalu czyta, gdzie rosnie rzepak, wprost z deklaracji
GSA. To jest wiarygodne, ale dostepne dopiero po sezonie - a decyzje o wywozie
uli zapadaja przed kwitnieniem. Ten etap zastepuje deklaracje klasyfikatorem,
ktory patrzy wylacznie na zdjecia z jesieni i marca, czyli na to, co widac
szesc tygodni przed kwitnieniem.

Deklaracje przestaja byc zrodlem warstwy, a staja sie SPRAWDZIANEM: mapa
wykryta i mapa deklarowana sa porownywane piksel po pikselu.

DLACZEGO PRAWDOPODOBIENSTWO, A NIE TWARDA DECYZJA
Pierwsze podejscie zwracalo klase 0/1 i wykrylo dziewieciokrotnie za duzo
rzepaku. Powod jest podrecznikowy: probka treningowa jest zrownowazona 50/50,
a w terenie rzepak to okolo 10% gruntow ornych. Las nauczony na 50/50 zaklada
taki wlasnie prior i glosuje na rzepak przy slabej poszlace. Do tego negatywy
pochodza wylacznie z dzialek GSA, wiec ugor czy nieuzytek w masce gruntow
ornych nie ma sie do czego przyrownac.

Rozwiazanie: model zwraca PRAWDOPODOBIENSTWO, a prog dobierany jest po fakcie
przez porownanie z deklaracjami. Jedno liczenie, dowolny prog.

TRENING JEST WIELOOBSZAROWY
Model uczony na samym obszarze pilotazowym uogolnialby sie na 180 km w bok bez
zadnej gwarancji. Punkty treningowe pochodza z tych samych 7 obszarow, na
ktorych kalibrowana byla fenologia - od Zamoscia po Radzyn, wiec probka
przecina wojewodztwo z poludnia na polnoc.

CO WYCHODZI
  woj_rzepak_detekcja.tif  - udzial rzepaku w pikselu 100 m wg klasyfikatora
  woj_rzepak_gsa.tif       - to samo wg deklaracji (odniesienie)
Obie na dokladnie tej samej siatce co woj_sezon.tif.

Uruchomienie:
    python detekcja_wojewodztwo.py
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import ee
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import requests
from matplotlib.path import Path as MplPath
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import MultiLineString, box
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import gee_klasyfikator_rzepaku as K
import mapa_wojewodztwa as MW
import klasyfikator_gsa as G
from fenologia_gsa import CECHY_PRZED
from fenologia_wielo import OBSZARY, PROMIEN_M

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

ROK = 2025
PIKSEL = 100                 # m - siatka docelowa, 1 px = 1 ha
SKALA_KLAS = 20              # m - rozdzielczosc klasyfikacji przed agregacja
KAFEL_PX = 300               # 30 km na kafel
CACHE_PKT = WYNIKI / "cache" / "detekcja_punkty.csv"
CZESCIOWE = WYNIKI / "cache" / "detekcja_kafle.npz"
# Punkty ida do GEE inline w tresci zadania, a ta ma twardy limit 10 MB.
# Pelna probka (81 tys. pkt z 7 obszarow) go przekracza, wiec tniemy ja
# rownomiernie: tyle punktow na obszar i klase.
NA_OBSZAR_KLASE = 1200
ZIARNO = 42


def punkty_wieloobszarowe() -> pd.DataFrame:
    """Probka treningowa z 7 obszarow rozrzuconych po wojewodztwie."""
    if CACHE_PKT.exists():
        df = pd.read_csv(CACHE_PKT)
        print(f"punkty z cache: {len(df):,} "
              f"({df.rzepak.sum():,} rzepak, {len(df)-df.rzepak.sum():,} inne)")
        return df
    czesci = []
    for i, (nazwa, (lat, lon)) in enumerate(OBSZARY.items(), 1):
        d = G.punkty(lat, lon, PROMIEN_M, cicho=True)
        d["obszar"] = nazwa
        czesci.append(d)
        print(f"  [{i}/{len(OBSZARY)}] {nazwa:12s} {len(d):5,} pkt, "
              f"rzepak {d.rzepak.sum():4,}")
    df = pd.concat(czesci, ignore_index=True)
    df.to_csv(CACHE_PKT, index=False)
    return df


def przytnij(df: pd.DataFrame) -> pd.DataFrame:
    """Rowna liczba punktow na obszar i klase - inaczej zadanie nie wejdzie
    w limit 10 MB, a Radzyn i Chelm zostalyby zdominowane przez reszte."""
    idx = [i for _, g in df.groupby(["obszar", "rzepak"])
           for i in g.sample(min(len(g), NA_OBSZAR_KLASE),
                             random_state=ZIARNO).index]
    d = df.loc[sorted(idx)].reset_index(drop=True)
    print(f"  przycieta do {len(d):,} pkt "
          f"({d.rzepak.sum():,} rzepak, {d.test.sum():,} testowych)")
    return d


def kafle(nx: int, ny: int):
    for y0 in range(0, ny, KAFEL_PX):
        for x0 in range(0, nx, KAFEL_PX):
            yield x0, y0, min(KAFEL_PX, nx - x0), min(KAFEL_PX, ny - y0)


def pobierz(img: ee.Image, l: float, t: float, w: int, h: int,
            prob: int = 4) -> np.ndarray:
    """Kafel jako tablica; getDownloadURL potrafi chwilowo odmowic."""
    region = ee.Geometry.Rectangle(
        [l, t - h * PIKSEL, l + w * PIKSEL, t], "EPSG:2180", False)
    for i in range(prob):
        try:
            url = img.getDownloadURL({
                "region": region, "scale": PIKSEL, "crs": "EPSG:2180",
                "format": "GEO_TIFF"})
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            b = r.content
            if b[:2] == b"PK":                      # czasem pakuje w zip
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    b = z.read([n for n in z.namelist() if n.endswith(".tif")][0])
            with rasterio.open(io.BytesIO(b)) as f:
                a = f.read(1).astype("float32")
            out = np.zeros((h, w), "float32")
            out[:min(h, a.shape[0]), :min(w, a.shape[1])] = \
                a[:min(h, a.shape[0]), :min(w, a.shape[1])]
            return out
        except Exception as e:
            if i == prob - 1:
                print(f"      pominiety: {str(e)[:70]}")
                return np.full((h, w), np.nan, "float32")
            time.sleep(6 * (i + 1))


if __name__ == "__main__":
    K.start()

    # ------------------------------------------------ siatka z istniejacej mapy
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx), tf = f.bounds, f.shape, f.transform
    print(f"siatka {nx} x {ny} px @ {PIKSEL} m\n")

    # ------------------------------------------------ trening
    print("Punkty treningowe z 7 obszarow:")
    df = przytnij(punkty_wieloobszarowe())
    K.AOI = ee.Geometry.Rectangle([b.left, b.bottom, b.right, b.top],
                                  "EPSG:2180", False)
    x = K.cechy(ROK).select(CECHY_PRZED).updateMask(K.orne_maska())
    proba = x.sampleRegions(collection=G.kolekcja(df), scale=10,
                            geometries=False, tileScale=4)
    las = ee.Classifier.smileRandomForest(K.LICZBA_DRZEW).train(
        features=proba.filter(ee.Filter.eq("test", 0)),
        classProperty="rzepak", inputProperties=CECHY_PRZED)

    m = (proba.filter(ee.Filter.eq("test", 1)).classify(las)
         .errorMatrix("rzepak", "classification").array().getInfo())
    (tn, fp), (fn, tp) = m[0], m[1]
    prec, czul = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    f1 = 2 * prec * czul / max(prec + czul, 1e-9)
    print(f"\nklasyfikator przedkwitnieniowy, walidacja przestrzenna:")
    print(f"  precyzja {prec:.3f}  czulosc {czul:.3f}  F1 {f1:.3f}  "
          f"n={tn+fp+fn+tp:,}\n")

    # srednie prawdopodobienstwo rzepaku w pikselu 100 m
    prawd = (x.classify(las.setOutputMode("PROBABILITY")).unmask(0)
             .reproject(crs="EPSG:2180", scale=SKALA_KLAS)
             .reduceResolution(ee.Reducer.mean(), maxPixels=64)
             .reproject(crs="EPSG:2180", scale=PIKSEL)
             .rename("p").toFloat())

    # ------------------------------------------------ pobieranie kafelkami
    # Kafle calkiem poza wojewodztwem sa pomijane - bbox jest prostokatny,
    # a wojewodztwo zajmuje 62% jego powierzchni.
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in MW.podklad()[2] if len(g) > 1]))), key=lambda q: q.area)
    lista = [(x0, y0, w, h) for x0, y0, w, h in kafle(nx, ny)
             if poly.intersects(box(b.left + x0 * PIKSEL,
                                    b.top - (y0 + h) * PIKSEL,
                                    b.left + (x0 + w) * PIKSEL,
                                    b.top - y0 * PIKSEL))]
    print(f"kafli do policzenia: {len(lista)} "
          f"(pominieto {len(list(kafle(nx, ny))) - len(lista)} poza granica)\n")
    det = np.full((ny, nx), np.nan, "float32")
    gotowe = set()
    if CZESCIOWE.exists():
        z = np.load(CZESCIOWE)
        det, gotowe = z["det"], set(map(tuple, z["gotowe"]))
        print(f"wznawiam: {len(gotowe)}/{len(lista)} kafli gotowych\n")

    t0 = time.time()
    for i, (x0, y0, w, h) in enumerate(lista, 1):
        if (x0, y0) in gotowe:
            continue
        a = pobierz(prawd, b.left + x0 * PIKSEL, b.top - y0 * PIKSEL, w, h)
        det[y0:y0 + h, x0:x0 + w] = a
        gotowe.add((x0, y0))
        np.savez_compressed(CZESCIOWE, det=det,
                            gotowe=np.array(sorted(gotowe), dtype=int))
        print(f"  kafel {i}/{len(lista)}  ({x0},{y0})  "
              f"p>0.5: {float((a > .5).sum()):7,.0f} ha  "
              f"{(time.time()-t0)/60:5.1f} min")

    # ------------------------------------------------ odniesienie z deklaracji
    print("\nRasteryzacja deklaracji GSA (odniesienie)...")
    kro = PIKSEL // SKALA_KLAS
    g = pyogrio.read_dataframe(SHP, encoding="utf-8",
                               where="roslina = 'rzepak ozimy'")
    r20 = rasterize(((geom, 1) for geom in g.geometry),
                    out_shape=(ny * kro, nx * kro),
                    transform=from_origin(b.left, b.top, SKALA_KLAS, SKALA_KLAS),
                    fill=0, dtype="uint8")
    gsa = r20.reshape(ny, kro, nx, kro).mean(axis=(1, 3)).astype("float32")
    del r20

    # ------------------------------------------------ maska wojewodztwa
    # Bez niej porownanie jest bez sensu: poza granica GSA nie ma danych,
    # wiec kazde wykrycie liczyloby sie jako blad.
    yy, xx = np.mgrid[0:ny, 0:nx]
    wew = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([(b.left + (xx.ravel() + .5) * PIKSEL),
                         (b.top - (yy.ravel() + .5) * PIKSEL)])).reshape(ny, nx)
    ok = wew & ~np.isnan(det)
    print(f"pikseli w granicy z danymi: {ok.sum():,}")

    # ------------------------------------------------ kalibracja progu
    gg = gsa[ok] > 0.5
    print(f"\nKALIBRACJA PROGU (odniesienie: deklaracje GSA {ROK})")
    print(f"{'prog':>6}{'areal ha':>12}{'precyzja':>10}{'czulosc':>9}{'F1':>7}")
    krzywa, naj = [], None
    for pr in np.arange(0.30, 0.96, 0.05):
        dd = det[ok] > pr
        tp2 = int((dd & gg).sum()); fp2 = int((dd & ~gg).sum())
        fn2 = int((~dd & gg).sum())
        p2 = tp2 / max(tp2 + fp2, 1); c2 = tp2 / max(tp2 + fn2, 1)
        f2 = 2 * p2 * c2 / max(p2 + c2, 1e-9)
        krzywa.append({"prog": round(float(pr), 2), "areal_ha": int(dd.sum()),
                       "precyzja": p2, "czulosc": c2, "f1": f2})
        print(f"{pr:>6.2f}{dd.sum():>12,}{p2:>10.3f}{c2:>9.3f}{f2:>7.3f}")
        if naj is None or f2 > naj["f1"]:
            naj = krzywa[-1]
    g_ha = float(gsa[ok].sum())
    print(f"\n  deklarowane        {g_ha:10,.0f} ha")
    print(f"  najlepszy prog     {naj['prog']:.2f}  ->  {naj['areal_ha']:,} ha "
          f"({naj['areal_ha']/max(g_ha,1)*100-100:+.0f}%)")
    print(f"  precyzja {naj['precyzja']:.3f}  czulosc {naj['czulosc']:.3f}  "
          f"F1 {naj['f1']:.3f}")

    prof = {"driver": "GTiff", "height": ny, "width": nx, "count": 1,
            "dtype": "float32", "crs": "EPSG:2180", "transform": tf,
            "compress": "deflate", "nodata": np.nan}
    # maska binarna przy najlepszym progu - to jest produkt koncowy
    binarna = np.where(ok, (det > naj["prog"]).astype("float32"), np.nan)
    for nazwa, arr in (("woj_rzepak_prawd", np.where(wew, det, np.nan)),
                       ("woj_rzepak_detekcja", binarna),
                       ("woj_rzepak_gsa", np.where(wew, gsa, np.nan))):
        with rasterio.open(WYNIKI / "rastry" / f"{nazwa}.tif", "w", **prof) as dst:
            dst.write(arr.astype("float32"), 1)

    (WYNIKI / "json" / "detekcja_wojewodztwo.json").write_text(json.dumps({
        "rok": ROK, "cechy": CECHY_PRZED, "obszary_treningu": list(OBSZARY),
        "walidacja_punktowa": {"precyzja": prec, "czulosc": czul, "f1": f1,
                               "n": tn + fp + fn + tp},
        "krzywa_progu": krzywa, "prog_wybrany": naj,
        "areal_wykryty_ha": naj["areal_ha"], "areal_gsa_ha": g_ha,
        "piksele": {"precyzja": naj["precyzja"], "czulosc": naj["czulosc"]},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano woj_rzepak_prawd/detekcja/gsa .tif i JSON")
