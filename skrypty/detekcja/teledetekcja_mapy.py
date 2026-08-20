"""
ETAP 9 - te same dwie mapy (GDZIE cukier / KIEDY szczyt), ale z TELEDETEKCJI.

PO CO
Wersja deklaracyjna wymaga danych ARiMR, ktore wychodza po sezonie i tylko
w UE. Ta wersja powstaje wylacznie ze zrodel satelitarnych:

  rzepak         - nasz klasyfikator przedkwitnieniowy (Sentinel-2,
                   jesien+marzec), prog kalibrowany do arealu GSA
  uzytki zielone - ESA WorldCover 2021, klasa 30 (grassland), z Sentinela-1/2
  terminy        - model GDD (meteo), kalibrowany na datach zmierzonych
                   z Sentinela-2

CZEGO TU NIE MA I DLACZEGO
Gryka, malina, porzeczka, fasola itd. - z orbity nieodroznialne naszymi
metodami (fasola: F1 0.69, za malo). Rzepak + TUZ pokrywaja ok. 75% cukru
wersji deklaracyjnej; brakujace 25% to glownie pozytki letnie. Walidacja:
korelacja z mapa deklaracyjna liczona na koncu.

PROG DETEKCJI: dobierany tak, by areal wykryty zgadzal sie z arealem GSA
(kalibracja arealowa) - dla mapy potencjalu wazniejsza jest wlasciwa SUMA
rzepaku niz maksymalne F1 pojedynczych pikseli.

Uruchomienie:
    python teledetekcja_mapy.py
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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from matplotlib.path import Path as MplPath
from scipy.signal import fftconvolve
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import mapa_wojewodztwa as MW
import potencjal_gsa as P
import wojewodztwo as W
from wojewodztwo_kalendarz import CZAS_KOLOR, CZAS_OPIS, udzialy

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL = 100
KAFEL_PX = 300   # 600 dawalo "Reprojection output too large" przy zrodle 10 m
KG_RZEPAK = P.POZYTKI["rzepak ozimy"][0]
KG_TUZ = P.POZYTKI["TUZ"][0]
CACHE_TUZ = WYNIKI / "cache" / "worldcover_tuz.npy"


def pobierz_kafel(img, l, t, w, h, prob=4):
    import ee
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
        except Exception:
            if i == prob - 1:
                raise
            time.sleep(6 * (i + 1))


def tuz_worldcover(b, nx, ny) -> np.ndarray:
    if CACHE_TUZ.exists():
        print("WorldCover TUZ z cache")
        return np.load(CACHE_TUZ)
    import ee
    import gee_klasyfikator_rzepaku as K
    K.start()
    wc = ee.Image("ESA/WorldCover/v200/2021").select("Map")
    # unmask() gubi natywna projekcje (globalna WGS84/1 stopien), a wtedy
    # reduceResolution odpowiada bledem 400 - trzeba ja przywrocic jawnie
    img = (wc.eq(30).unmask(0).setDefaultProjection(wc.projection())
           .reduceResolution(ee.Reducer.mean(), maxPixels=256)
           .reproject(crs="EPSG:2180", scale=PIKSEL).toFloat())
    out = np.zeros((ny, nx), "float32")
    n = 0
    for y0 in range(0, ny, KAFEL_PX):
        for x0 in range(0, nx, KAFEL_PX):
            w = min(KAFEL_PX, nx - x0)
            h = min(KAFEL_PX, ny - y0)
            out[y0:y0 + h, x0:x0 + w] = pobierz_kafel(
                img, b.left + x0 * PIKSEL, b.top - y0 * PIKSEL, w, h)
            n += 1
            print(f"  WorldCover: kafel {n}")
    np.save(CACHE_TUZ, out)
    return out


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(WYNIKI / "rastry" / "woj_rzepak_prawd.tif") as f:
        prawd, b, (ny, nx), tf = f.read(1), f.bounds, f.shape, f.transform
    det_json = json.loads(
        (WYNIKI / "json" / "detekcja_wojewodztwo.json").read_text(encoding="utf-8"))

    # prog arealowy: najmniejsza roznica |areal(prog) - areal GSA|
    g_ha = det_json["areal_gsa_ha"]
    kr = det_json["krzywa_progu"]
    naj = min(kr, key=lambda x: abs(x["areal_ha"] - g_ha))
    print(f"prog arealowy {naj['prog']:.2f}: {naj['areal_ha']:,} ha "
          f"(GSA {g_ha:,.0f} ha), precyzja {naj['precyzja']:.3f}, "
          f"czulosc {naj['czulosc']:.3f}")
    rzepak = np.nan_to_num(prawd) > naj["prog"]

    tuz = tuz_worldcover(b, nx, ny)

    # maska wojewodztwa
    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ny, 0:nx]
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([b.left + (xx.ravel() + .5) * PIKSEL,
                         b.top - (yy.ravel() + .5) * PIKSEL])).reshape(ny, nx)

    Kj = W.jadro()
    spl_rz = fftconvolve(rzepak.astype("float32"), Kj, mode="same")
    spl_tuz = fftconvolve(tuz, Kj, mode="same")
    sezon = np.where(maska, spl_rz * KG_RZEPAK + spl_tuz * KG_TUZ,
                     np.nan) / 1000.0

    # --- walidacja wobec wersji deklaracyjnej
    z25 = np.load(WYNIKI / "cache" / "woj_splot_2025.npz")
    dekl_rt = (z25["rzepak ozimy"] * KG_RZEPAK + z25["TUZ"] * KG_TUZ) / 1000.0
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        dekl_full = f.read(1) / 1000.0
    ok = maska & ~np.isnan(sezon) & ~np.isnan(dekl_full)
    r_rt = float(np.corrcoef(sezon[ok], dekl_rt[ok])[0, 1])
    r_full = float(np.corrcoef(sezon[ok], dekl_full[ok])[0, 1])
    print(f"korelacja z deklaracyjna (rzepak+TUZ): r = {r_rt:.3f}")
    print(f"korelacja z deklaracyjna (pelna, wszystkie uprawy): r = {r_full:.3f}")

    # --- stos dekadowy: rzepak wg lokalnej daty GDD, TUZ z tabeli
    with rasterio.open(WYNIKI / "rastry" / "woj_kwitnienie.tif") as f:
        kw = f.read(1)
    DEK = P.DEKADY
    kw_bin = np.where(np.isnan(kw), 129, kw)
    grupy = np.clip(((kw_bin - 122) // 4).astype(int), 0, 3)
    stos = np.zeros((len(DEK),) + (ny, nx), "float32")
    for g in np.unique(grupy):
        pelnia = 124 + int(g) * 4 + 2
        r = udzialy(pelnia - 10, pelnia, pelnia + 12, DEK)
        sel = grupy == g
        for i, d in enumerate(DEK):
            if r[d]:
                stos[i][sel] += spl_rz[sel] * KG_RZEPAK * r[d]
    r = udzialy(*P.POZYTKI["TUZ"][1:4], DEK)
    for i, d in enumerate(DEK):
        if r[d]:
            stos[i] += spl_tuz * KG_TUZ * r[d]
    szczyt = np.array(DEK)[np.nanargmax(stos, axis=0)].astype("float32")
    szczyt[~maska] = np.nan
    norm_cz = BoundaryNorm([100, 120, 140, 160, 180, 260], 5)

    v = sezon[ok]
    progi = [0.0] + [float(np.percentile(v, q)) for q in (60, 80, 92, 98)] + \
            [float(v.max())]

    # --- rysunek w ukladzie identycznym jak wersja deklaracyjna
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 9.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO)
    ext = [b.left, b.right, b.bottom, b.top]
    for ax, dane, cm, nm, tyt, pod in (
        (a1, szczyt, ListedColormap(CZAS_KOLOR), norm_cz,
         "Kiedy wypada szczyt pożytku — z teledetekcji",
         "dekada z największą ilością cukru w zasięgu lotu"),
        (a2, sezon, ListedColormap(MW.KLASY), BoundaryNorm(progi, 5),
         "Gdzie jest najwięcej cukru — z teledetekcji",
         "rzepak z Sentinela-2 + użytki zielone z ESA WorldCover")):
        MW.rysuj(ax, dane, None, cm, nm, ext, drogi, miasta, granice,
                 min_pop=45_000, lw=.45)
        ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
        ax.set_title(tyt, fontsize=13.5, weight="bold", color=MW.ATRAMENT,
                     loc="left", pad=22)
        ax.text(0, 1.005, pod, transform=ax.transAxes, fontsize=10,
                color=MW.MUTED, va="bottom")
    MW.podzialka(a1, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    for ax, hnd in (
        (a1, [Patch(facecolor=CZAS_KOLOR[i], label=CZAS_OPIS[i])
              for i in range(5)]),
        (a2, [Patch(facecolor=MW.KLASY[i],
                    label=f"{progi[i]:.1f}–{progi[i+1]:.1f} t")
              for i in range(5)])):
        ax.legend(handles=hnd, loc="upper center", bbox_to_anchor=(.5, -.002),
                  ncol=5, fontsize=9.5, frameon=False, handlelength=1.5,
                  handleheight=1.15, columnspacing=1.1, handletextpad=.5)
    fig.text(.5, .012, "bez danych od rolników: klasyfikator Sentinel-2 "
             "(jesień+marzec) + WorldCover + model GDD · pokrywa ~75% cukru "
             f"wersji deklaracyjnej · zgodność z nią r = {r_full:.2f}",
             ha="center", fontsize=9, color=MW.MUTED)
    fig.subplots_adjust(left=.01, right=.99, top=.92, bottom=.075, wspace=.03)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_teledetekcja.png").write_bytes(buf.getvalue())

    (WYNIKI / "json" / "teledetekcja_mapy.json").write_text(json.dumps({
        "prog_arealowy": naj, "korelacja_rzepak_tuz": r_rt,
        "korelacja_pelna": r_full,
        "zrodla": {"rzepak": "klasyfikator S2 przedkwitnieniowy",
                   "TUZ": "ESA WorldCover 2021 klasa 30",
                   "terminy": "model GDD"},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano mapa_teledetekcja.png i JSON")
