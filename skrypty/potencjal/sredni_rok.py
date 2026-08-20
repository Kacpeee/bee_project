"""
ETAP 11 (finalny) - mapa PRZECIETNEGO ROKU pozytkowego i mapa NIEZAWODNOSCI.

SKLAD
Osiem sezonow warstwy rzepakowej:
  2019-2024  detekcja satelitarna (pelny klasyfikator, 8 cech)
  2025-2026  deklaracje GSA (prawda)
plus czesc nierzepakowa (laki, gryka, maliny, sady...) jako warstwa stala
ze sredniej deklaracji 2025/26 - uzasadnienie: uprawy trwale nie wedruja,
a pelne mapy 2025 i 2026 koreluja na 0.945, wiec blad zamrozenia jest maly.

PROG DETEKCJI: kalibrowany arealowo na 2025 (jedyny rok detekcji z prawda
GSA), stosowany do wszystkich lat.

WALIDACJA MIEDZYROCZNA: detekcja 2022 vs EUCROPMAP 2022 (niezalezna mapa).

DWA PRODUKTY
  1. PRZECIETNY ROK - srednia cukru z 8 sezonow. Odpowiada na "gdzie
     najczesciej jest najwiecej".
  2. NIEZAWODNOSC - w ilu sezonach z 8 miejsce bylo w najlepszych 20%
     rzepakowej warstwy. Rejon dobry co roku != rejon dobry raz na 4 lata.

Uruchomienie:
    python sredni_rok.py
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
import potencjal_gsa as P
import wojewodztwo as W

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL = 100
KG_RZEPAK = P.POZYTKI["rzepak ozimy"][0]
LATA_DET = [2019, 2020, 2021, 2022, 2023, 2024]
AREAL_GSA_2025 = None   # odczytany z detekcja_wojewodztwo.json


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx), tf = f.bounds, f.shape, f.transform

    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ny, 0:nx]
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([b.left + (xx.ravel() + .5) * PIKSEL,
                         b.top - (yy.ravel() + .5) * PIKSEL])).reshape(ny, nx)
    marg = int(W.ZASIEG_M / PIKSEL)
    maska[:marg] = maska[-marg:] = False
    maska[:, :marg] = maska[:, -marg:] = False

    # ---------------------------------------------- prog arealowy na 2025
    AREAL_GSA_2025 = json.loads(
        (WYNIKI / "json" / "detekcja_wojewodztwo.json")
        .read_text(encoding="utf-8"))["areal_gsa_ha"]
    p25 = np.nan_to_num(np.load(WYNIKI / "cache" / "woj_prawd_2025.npy"))
    progi_t = np.arange(0.30, 0.96, 0.01)
    areale = [(p25[maska] > t).sum() for t in progi_t]
    prog = float(progi_t[int(np.argmin(
        [abs(a - AREAL_GSA_2025) for a in areale]))])
    print(f"prog arealowy (pelny klasyfikator): {prog:.2f} -> "
          f"{(p25[maska] > prog).sum():,} ha (GSA {AREAL_GSA_2025:,.0f} ha)")

    # ---------------------------------------------- warstwy rzepakowe 8 sezonow
    # Jadro WIOSENNE i znormalizowane - cala ta warstwa to rzepak, ktory
    # kwitnie w maju, kiedy pszczoly lataja srednio 493 m (Couvillon 2014).
    # Wczesniej bylo tu stale W.jadro() o zasiegu 3000 m, czyli 2.5x za
    # szerokie; suma sie zgadzala, ale rzepak byl rozmyty poza swoj zasieg.
    Kj = W.jadro_dla("rzepak ozimy")
    rzepak = {}
    print("\nareal rzepaku wg detekcji:")
    for rok in LATA_DET:
        p = np.nan_to_num(np.load(WYNIKI / "cache" / f"woj_prawd_{rok}.npy"))
        binarna = (p > prog).astype("float32")
        print(f"  {rok}: {binarna[maska].sum():9,.0f} ha")
        rzepak[rok] = fftconvolve(binarna, Kj, mode="same")
    for rok in (2025, 2026):
        z = np.load(WYNIKI / "cache" / f"woj_splot_{rok}.npz")
        rzepak[rok] = z["rzepak ozimy"]

    # ---------------------------------------------- walidacje
    wal = {}
    eu22 = fftconvolve(np.load(WYNIKI / "cache" / "eucropmap_rzepak_2022.npy"),
                       Kj, mode="same")
    wal["det2022_vs_eucropmap2022"] = float(
        np.corrcoef(rzepak[2022][maska], eu22[maska])[0, 1])
    wal["det2025_vs_gsa2025"] = float(
        np.corrcoef(fftconvolve((p25 > prog).astype("float32"), Kj,
                                mode="same")[maska],
                    rzepak[2025][maska])[0, 1])
    print(f"\nwalidacja: det2022 vs EUCROPMAP2022  "
          f"r = {wal['det2022_vs_eucropmap2022']:.3f}")
    print(f"walidacja: det2025 vs GSA2025        "
          f"r = {wal['det2025_vs_gsa2025']:.3f}")

    # ---------------------------------------------- mapa 1: przecietny rok
    sr_rzepak = np.mean([rzepak[r] for r in sorted(rzepak)], axis=0)
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        dekl_sr = f.read(1)
    z25 = np.load(WYNIKI / "cache" / "woj_splot_2025.npz")
    z26 = np.load(WYNIKI / "cache" / "woj_splot_2026.npz")
    reszta = dekl_sr - (z25["rzepak ozimy"] + z26["rzepak ozimy"]) / 2 * KG_RZEPAK
    przecietny = np.where(maska, sr_rzepak * KG_RZEPAK + reszta, np.nan) / 1000.0

    # ---------------------------------------------- mapa 2: niezawodnosc
    ile = np.zeros((ny, nx), "int16")
    for r in rzepak:
        prg = np.percentile(rzepak[r][maska], 80)
        ile += (rzepak[r] >= prg).astype("int16")
    niezaw = np.where(maska, ile.astype("float32"), np.nan)

    prof = {"driver": "GTiff", "height": ny, "width": nx, "count": 1,
            "dtype": "float32", "crs": "EPSG:2180", "transform": tf,
            "compress": "deflate", "nodata": np.nan}
    for nazwa, arr in (("woj_przecietny_rok", przecietny),
                       ("woj_niezawodnosc", niezaw)):
        with rasterio.open(WYNIKI / "rastry" / f"{nazwa}.tif", "w", **prof) as dst:
            dst.write(arr.astype("float32"), 1)

    # ---------------------------------------------- rysunek
    v = przecietny[maska & ~np.isnan(przecietny)]
    progi = [0.0] + [float(np.percentile(v, q)) for q in (60, 80, 92, 98)] + \
            [float(v.max())]
    progi_n = [-.5, 2.5, 4.5, 6.5, 7.5, 8.5]
    et_n = ["0–2 z 8", "3–4 z 8", "5–6 z 8", "7 z 8", "8 z 8"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 9.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO)
    ext = [b.left, b.right, b.bottom, b.top]
    for ax, dane, nm, tyt, pod in (
        (a1, przecietny, BoundaryNorm(progi, 5),
         "Przeciętny rok pożytkowy",
         "średnia z 8 sezonów 2019–2026 · tony cukrów w zasięgu lotu"),
        (a2, niezaw, BoundaryNorm(progi_n, 5),
         "Niezawodność rejonu",
         "w ilu sezonach z ośmiu miejsce było w najlepszych 20% "
         "warstwy rzepakowej")):
        MW.rysuj(ax, dane, None, ListedColormap(MW.KLASY), nm, ext,
                 drogi, miasta, granice, min_pop=45_000, lw=.45)
        ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
        ax.set_title(tyt, fontsize=14, weight="bold", color=MW.ATRAMENT,
                     loc="left", pad=22)
        ax.text(0, 1.005, pod, transform=ax.transAxes, fontsize=10,
                color=MW.MUTED, va="bottom")
    MW.podzialka(a1, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    for ax, hnd in (
        (a1, [Patch(facecolor=MW.KLASY[i],
                    label=f"{progi[i]:.1f}–{progi[i+1]:.1f} t")
              for i in range(5)]),
        (a2, [Patch(facecolor=MW.KLASY[i], label=et_n[i])
              for i in range(5)])):
        ax.legend(handles=hnd, loc="upper center", bbox_to_anchor=(.5, -.002),
                  ncol=5, fontsize=9.5, frameon=False, handlelength=1.5,
                  handleheight=1.15, columnspacing=1.1, handletextpad=.5)
    fig.text(.5, .012, "rzepak: detekcja Sentinel-2 (2019–2024) + deklaracje "
             "GSA (2025–2026) · pozostałe gatunki: stała warstwa ze średniej "
             "deklaracji · walidacja detekcji: r = "
             f"{wal['det2022_vs_eucropmap2022']:.2f} z EUCROPMAP 2022, "
             f"r = {wal['det2025_vs_gsa2025']:.2f} z GSA 2025",
             ha="center", fontsize=9, color=MW.MUTED)
    fig.subplots_adjust(left=.01, right=.99, top=.92, bottom=.075, wspace=.03)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_sredni_rok.png").write_bytes(buf.getvalue())

    (WYNIKI / "json" / "sredni_rok.json").write_text(json.dumps({
        "prog": prog, "lata_detekcji": LATA_DET, "walidacje": wal,
        "areal_det_ha": {r: float((np.nan_to_num(
            np.load(WYNIKI / "cache" / f"woj_prawd_{r}.npy"))[maska] > prog).sum())
            for r in LATA_DET},
        "progi_przecietny_t": progi,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano mapa_sredni_rok.png, woj_przecietny_rok.tif, "
          "woj_niezawodnosc.tif i JSON")
