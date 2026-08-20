"""
ETAP 8 - stabilnosc rejonow rzepakowych na przestrzeni OSMIU lat (2018-2026).

PO CO
Porownanie GSA 2025/2026 dalo r=0.945, ale to tylko rok do roku. Zarzut
"dwa sezony to za malo" jest sluszny - plodozmian rzepaku ma cykl 3-4 lata,
wiec dopiero dluzszy odstep mowi, czy rejony sa trwale.

Deklaracji sprzed 2025 nie ma, ale rzepak (57% cukru w wojewodztwie) mozna
wziac z EUCROPMAP - unijnej mapy upraw z Sentinela-1, roczniki 2018 i 2022,
dokladnosc ok. 80% dla rzepaku. Razem cztery warstwy:

    2018 EUCROPMAP | 2022 EUCROPMAP | 2025 GSA | 2026 GSA

Kazda sprowadzona do tej samej wielkosci: HEKTARY RZEPAKU W ZASIEGU LOTU
(udzial w pikselu 100 m -> splot jadrem wykladniczym lambda=1 km).
Korelacje miedzy nimi mowia, jak szybko rejony sie rozjezdzaja.

UWAGA METODYCZNA: r(2018,2022) miedzy dwoma warstwami EUCROPMAP jest czysty;
r(EUCROPMAP, GSA) miesza zmiane w czasie z bledem samej mapy EUCROPMAP,
wiec jest DOLNYM oszacowaniem stabilnosci.

Uruchomienie:
    python stabilnosc_rzepaku.py
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
import rasterio
import requests
from matplotlib.path import Path as MplPath
from scipy.signal import fftconvolve
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import gee_klasyfikator_rzepaku as K
import mapa_wojewodztwa as MW
import wojewodztwo as W

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL = 100
KAFEL_PX = 600          # EUCROPMAP to gotowy raster, kafle moga byc duze
LATA_EU = (2018, 2022)
KOD_RZEPAKU = 232


def pobierz_kafel(img, l, t, w, h, prob=4):
    region = ee.Geometry.Rectangle(
        [l, t - h * PIKSEL, l + w * PIKSEL, t], "EPSG:2180", False)
    for i in range(prob):
        try:
            url = img.getDownloadURL({"region": region, "scale": PIKSEL,
                                      "crs": "EPSG:2180", "format": "GEO_TIFF"})
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            b = r.content
            if b[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    b = z.read([n for n in z.namelist()
                                if n.endswith(".tif")][0])
            with rasterio.open(io.BytesIO(b)) as f:
                a = f.read(1).astype("float32")
            out = np.zeros((h, w), "float32")
            out[:min(h, a.shape[0]), :min(w, a.shape[1])] = \
                a[:min(h, a.shape[0]), :min(w, a.shape[1])]
            return out
        except Exception as e:
            if i == prob - 1:
                raise
            time.sleep(6 * (i + 1))


def eucropmap_udzial(rok: int, b, nx, ny) -> np.ndarray:
    """Udzial rzepaku EUCROPMAP w pikselu 100 m, kafelkowo, z cache."""
    cache = WYNIKI / "cache" / f"eucropmap_rzepak_{rok}.npy"
    if cache.exists():
        print(f"  {rok}: z cache")
        return np.load(cache)
    img = (ee.ImageCollection("JRC/D5/EUCROPMAP/V1")
           .filterDate(f"{rok}-01-01", f"{rok}-12-31").first()
           .select("classification").eq(KOD_RZEPAKU).unmask(0)
           .reduceResolution(ee.Reducer.mean(), maxPixels=256)
           .reproject(crs="EPSG:2180", scale=PIKSEL).toFloat())
    out = np.zeros((ny, nx), "float32")
    kafli = 0
    for y0 in range(0, ny, KAFEL_PX):
        for x0 in range(0, nx, KAFEL_PX):
            w = min(KAFEL_PX, nx - x0)
            h = min(KAFEL_PX, ny - y0)
            out[y0:y0 + h, x0:x0 + w] = pobierz_kafel(
                img, b.left + x0 * PIKSEL, b.top - y0 * PIKSEL, w, h)
            kafli += 1
            print(f"  {rok}: kafel {kafli} gotowy")
    np.save(cache, out)
    return out


if __name__ == "__main__":
    K.start()
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx) = f.bounds, f.shape

    # maska wojewodztwa + margines splotu
    _, _, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ny, 0:nx]
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([b.left + (xx.ravel() + .5) * PIKSEL,
                         b.top - (yy.ravel() + .5) * PIKSEL])).reshape(ny, nx)
    marg = int(W.ZASIEG_M / PIKSEL)
    maska[:marg] = maska[-marg:] = False
    maska[:, :marg] = maska[:, -marg:] = False

    Kj = W.jadro()
    warstwy = {}

    print("EUCROPMAP -> udzial rzepaku:")
    for rok in LATA_EU:
        u = eucropmap_udzial(rok, b, nx, ny)
        warstwy[f"{rok} EUCROPMAP"] = fftconvolve(u, Kj, mode="same")
        print(f"  {rok}: {u.sum():,.0f} ha rzepaku wg EUCROPMAP")

    for rok in (2025, 2026):
        z = np.load(WYNIKI / "cache" / f"woj_splot_{rok}.npz")
        warstwy[f"{rok} GSA"] = z["rzepak ozimy"]

    nazwy = list(warstwy)
    print(f"\nKORELACJE rzepaku w zasiegu lotu (n = {maska.sum():,} px)")
    print(f"{'':>16}" + "".join(f"{n:>16}" for n in nazwy))
    macierz = {}
    for a in nazwy:
        wiersz = []
        for c in nazwy:
            r = float(np.corrcoef(warstwy[a][maska], warstwy[c][maska])[0, 1])
            macierz[f"{a} vs {c}"] = r
            wiersz.append(f"{r:>16.3f}")
        print(f"{a:>16}" + "".join(wiersz))

    # trwalosc najlepszych rejonow na 8 lat
    a18 = warstwy["2018 EUCROPMAP"][maska]
    a26 = warstwy["2026 GSA"][maska]
    top18 = a18 >= np.percentile(a18, 90)
    top26 = a26 >= np.percentile(a26, 90)
    utrz = float((top18 & top26).sum() / max(top18.sum(), 1))
    print(f"\ntop-10% rejonow z 2018 nadal w top-10% w 2026: {utrz*100:.0f}%")

    (WYNIKI / "json" / "stabilnosc_rzepaku.json").write_text(json.dumps({
        "warstwy": nazwy, "korelacje": macierz, "top10_2018_w_2026": utrz,
        "uwaga": "EUCROPMAP ~80% dokladnosci dla rzepaku; korelacje "
                 "EUCROPMAP-GSA sa dolnym oszacowaniem stabilnosci",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano stabilnosc_rzepaku.json")
