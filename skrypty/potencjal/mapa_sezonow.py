"""
Mapa potencjalu na dwoch sezonach: srednia jako produkt, zmiana jako dowod.

LEWY PANEL - srednia 2025/2026. To jest nowa warstwa glowna projektu: mniej
podatna na przypadek jednego roku niz dotychczasowa mapa z samego 2025.

PRAWY PANEL - roznica 2026 minus 2025. Odpowiada na pytanie, czy mapie
z jednego roku mozna ufac: jesli rejony trzymaja poziom, roznice sa male
i rozproszone; jesli plodozmian przestawia rejony, zobaczymy plamy.

Uruchomienie:
    python mapa_sezonow.py
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

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import mapa_wojewodztwa as MW

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

# rozbieznosc: niebieski = mniej w 2026, cegla = wiecej w 2026
ROZN = ["#31688e", "#8bb1c9", "#f0efe9", "#e08a63", "#b23a1d"]


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        sr, b = f.read(1) / 1000.0, f.bounds
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        s25 = f.read(1) / 1000.0
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_2026.tif") as f:
        s26 = f.read(1) / 1000.0
    por = json.loads((WYNIKI / "json" / "sezony_porownanie.json").read_text(encoding="utf-8"))

    ok = ~np.isnan(sr)
    roz = np.where(~np.isnan(s25) & ~np.isnan(s26), s26 - s25, np.nan)

    v = sr[ok]
    progi = [0.0] + [float(np.percentile(v, q)) for q in (60, 80, 92, 98)] + \
            [float(v.max())]
    cmap = ListedColormap(MW.KLASY)

    a90 = float(np.nanpercentile(np.abs(roz), 90))
    pr_r = [-99, -a90, -a90 / 3, a90 / 3, a90, 99]
    cmap_r = ListedColormap(ROZN)

    drogi, miasta, granice = MW.podklad()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 9.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO)
    ext = [b.left, b.right, b.bottom, b.top]
    for ax, dane, cm, nm, tyt, pod in (
        (a1, sr, cmap, BoundaryNorm(progi, 5),
         "Potencjał pożytkowy — średnia dwóch sezonów",
         "deklaracje ARiMR 2025 i 2026 · tony cukrów w zasięgu lotu"),
        (a2, roz, cmap_r, BoundaryNorm(pr_r, 5),
         "Co zmieniło się między sezonami",
         "2026 minus 2025 · niebieski = mniej rzepaku w 2026, ceglasty = więcej")):
        MW.rysuj(ax, dane, None, cm, nm, ext, drogi, miasta, granice,
                 min_pop=45_000, lw=.45)
        ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
        ax.set_title(tyt, fontsize=13.5, weight="bold", color=MW.ATRAMENT,
                     loc="left", pad=22)
        ax.text(0, 1.005, pod, transform=ax.transAxes, fontsize=10,
                color=MW.MUTED, va="bottom")
    MW.podzialka(a1, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    a1.legend(handles=[Patch(facecolor=MW.KLASY[i],
                             label=f"{progi[i]:.1f}–{progi[i+1]:.1f} t")
                       for i in range(5)],
              loc="lower right", fontsize=9, frameon=True, facecolor="#ffffff",
              edgecolor="#dde3dd", framealpha=.95).set_zorder(9)
    et_r = [f"spadek > {a90:.1f} t", "spadek", "bez zmian",
            "wzrost", f"wzrost > {a90:.1f} t"]
    a2.legend(handles=[Patch(facecolor=ROZN[i], label=et_r[i])
                       for i in range(5)],
              loc="lower right", fontsize=9, frameon=True, facecolor="#ffffff",
              edgecolor="#dde3dd", framealpha=.95).set_zorder(9)
    a2.text(.02, .02,
            f"korelacja map: r = {por['korelacja']:.2f}\n"
            f"top-10% rejonów utrzymane w {por['top10_zgoda']*100:.0f}%",
            transform=a2.transAxes, fontsize=9.5, color=MW.ATRAMENT,
            va="bottom", family="monospace", zorder=9,
            bbox=dict(facecolor="#ffffff", edgecolor="#dde3dd", pad=6))
    fig.subplots_adjust(left=.01, right=.99, top=.92, bottom=.02, wspace=.03)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_sezonow.png").write_bytes(buf.getvalue())
    print("zapisano mapa_sezonow.png")
