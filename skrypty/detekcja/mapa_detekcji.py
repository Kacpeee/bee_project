"""
Dowod, ze detekcja satelitarna zastepuje deklaracje: dwie mapy obok siebie.

CZEGO TO DOWODZI
Lewa mapa powstala WYLACZNIE ze zdjec Sentinel-2 z jesieni 2024 i marca 2025 -
ani jednej liczby od rolnika. Prawa to deklaracje ARiMR za 2025, czyli stan
faktyczny. Jesli uklad plam jest ten sam, klasyfikator mozna puscic na sezon,
dla ktorego deklaracji jeszcze nie ma.

DLACZEGO ZAGESZCZENIE, A NIE SUROWE PIKSELE
Pole rzepaku ma kilka hektarow. Na mapie 180 km w poprzek to punkt mniejszy od
piksela ekranu - obie mapy wygladalyby na szum. Dlatego oba rastry przechodza
przez to samo jadro zasiegu lotu co mapa potencjalu i pokazuja HEKTARY RZEPAKU
W ZASIEGU LOTU. To jest zreszta wielkosc, ktora interesuje pszczelarza.

Uruchomienie:
    python mapa_detekcji.py
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
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
import wojewodztwo as W

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    # prog AREALOWY (ten sam co w mapie cukru) zamiast progu najlepszego F1:
    # tamten gubi 29% arealu i lewa mapa wyglada na bledsza, niz jest
    with rasterio.open(WYNIKI / "rastry" / "woj_rzepak_prawd.tif") as f:
        prawd, b, ksztalt = f.read(1), f.bounds, f.shape
    with rasterio.open(WYNIKI / "rastry" / "woj_rzepak_gsa.tif") as f:
        gsa = f.read(1)
    j = json.loads((WYNIKI / "json" / "detekcja_wojewodztwo.json").read_text(encoding="utf-8"))
    naj = json.loads((WYNIKI / "json" / "teledetekcja_mapy.json")
                     .read_text(encoding="utf-8"))["prog_arealowy"]
    det = np.where(np.isnan(prawd), np.nan,
                   (np.nan_to_num(prawd) > naj["prog"]).astype("float32"))

    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ksztalt[0], 0:ksztalt[1]]
    px = b.left + (xx + .5) * 100
    py = b.top - (yy + .5) * 100
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(ksztalt)

    K = W.jadro()
    zag = {}
    for n, a in (("det", det), ("gsa", gsa)):
        zag[n] = np.where(maska, fftconvolve(np.nan_to_num(a), K, mode="same"),
                          np.nan).astype("float32")
        print(f"{n}: maks {np.nanmax(zag[n]):.0f} ha w zasiegu, "
              f"areal {np.nansum(np.where(maska, a, 0)):,.0f} ha")

    # wspolna skala - inaczej porownanie bylo by nieuczciwe
    v = zag["gsa"][~np.isnan(zag["gsa"])]
    progi = [0.0] + [float(np.percentile(v, q)) for q in (60, 80, 92, 98)] + \
            [float(max(np.nanmax(zag["det"]), np.nanmax(zag["gsa"])))]
    cmap, norm = ListedColormap(MW.KLASY), BoundaryNorm(progi, 5)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 9.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO)
    ext = [b.left, b.right, b.bottom, b.top]
    for ax, n, tyt, pod in (
        (a1, "det", "Wykryte z satelity",
         "Sentinel-2, jesień 2024 i marzec 2025 — bez deklaracji"),
        (a2, "gsa", "Zadeklarowane przez rolników",
         "ARiMR GSA 2025 — dostępne dopiero po sezonie")):
        MW.rysuj(ax, zag[n], None, cmap, norm, ext, drogi, miasta, granice,
                 min_pop=45_000, lw=.45)
        ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
        ax.set_title(tyt, fontsize=14, weight="bold", color=MW.ATRAMENT,
                     loc="left", pad=22)
        ax.text(0, 1.005, pod, transform=ax.transAxes, fontsize=10,
                color=MW.MUTED, va="bottom")
    MW.podzialka(a1, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    a1.legend(handles=[Patch(facecolor=MW.KLASY[i],
                             label=f"{progi[i]:.0f}–{progi[i+1]:.0f} ha")
                       for i in range(5)],
              loc="lower right", fontsize=9, frameon=True, facecolor="#ffffff",
              edgecolor="#dde3dd", framealpha=.95,
              title="rzepak w zasięgu lotu", title_fontsize=9).set_zorder(9)

    p = naj
    a2.text(.02, .02,
            f"zgodność na pikselach dominujących\n"
            f"precyzja {p['precyzja']:.2f} · czułość {p['czulosc']:.2f}\n"
            f"areał {naj['areal_ha']:,.0f} ha wobec "
            f"{j['areal_gsa_ha']:,.0f} ha deklarowanych",
            transform=a2.transAxes, fontsize=9, color=MW.ATRAMENT,
            va="bottom", family="monospace", zorder=9,
            bbox=dict(facecolor="#ffffff", edgecolor="#dde3dd", pad=6))
    fig.subplots_adjust(left=.01, right=.99, top=.92, bottom=.02, wspace=.03)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_detekcji.png").write_bytes(buf.getvalue())

    # korelacja przestrzenna zageszczen - to jest wlasciwa miara podobienstwa map
    ok = ~np.isnan(zag["det"]) & ~np.isnan(zag["gsa"])
    r = float(np.corrcoef(zag["det"][ok], zag["gsa"][ok])[0, 1])
    print(f"\nkorelacja zageszczen: r = {r:.3f} (n = {ok.sum():,} px)")
    j["korelacja_zageszczen"] = r
    (WYNIKI / "json" / "detekcja_wojewodztwo.json").write_text(
        json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano mapa_detekcji.png")
