"""
Rysunek pokazujacy SAM MODEL - bez ani jednej liczby z deklaracji ARiMR.

PO CO
Mapa potencjalu jest arytmetyka na deklaracjach: rosliny sa z ARiMR, wydajnosci
z literatury, jadro z zalozenia. Model fenologiczny nie ma tam gdzie zablysnac,
bo suma po sezonie nie zalezy od dat. Stad wrazenie, ze modele sa niewidoczne.

Ten rysunek pokazuje wylacznie to, co model produkuje:
  lewy panel  - mapa TERMINU kwitnienia rzepaku w wojewodztwie
  prawy panel - ten sam termin rok po roku od 2000 do 2026

Na obu wszystko pochodzi z sum temperatur: baza, prog i meteo. Deklaracje nie
wchodza tu wcale - one mowia GDZIE rosnie rzepak, a nie KIEDY zakwitnie.

Uruchomienie:
    python mapa_modelu.py
"""

from __future__ import annotations

import io
import json
import os
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from matplotlib.path import Path as MplPath
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import mapa_wojewodztwa as MW

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

# rampa czasowa: wczesnie -> pozno
RAMPA = ["#fff0b3", "#fbc26b", "#f08a3c", "#d4542a", "#9c2f1f"]
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def dz(doy: float, rok: int = 2025) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json").read_text(encoding="utf-8"))
    m = fin["model"]
    d0 = m.get("start_doy", {"1I": 1, "1II": 32}.get(m["start"], 32))

    with rasterio.open(WYNIKI / "rastry" / "woj_kwitnienie.tif") as f:
        kw = f.read(1)
        b = f.bounds
    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:kw.shape[0], 0:kw.shape[1]]
    px = b.left + (xx + .5) * 100
    py = b.top - (yy + .5) * 100
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(kw.shape)
    kw = np.where(maska, kw, np.nan)
    lo, hi = np.nanmin(kw), np.nanmax(kw)
    print(f"termin kwitnienia 2025 w wojewodztwie: {dz(lo)} - {dz(hi)} "
          f"({hi-lo:.0f} dni)")

    progi = np.linspace(lo, hi + .01, 6)
    cmap, norm = ListedColormap(RAMPA), BoundaryNorm(progi, 5)

    fig = plt.figure(figsize=(14.5, 8.6), dpi=170)
    fig.patch.set_facecolor(MW.TLO)

    # ---- lewy: mapa terminu
    ax = fig.add_axes([.01, .05, .44, .84])
    MW.rysuj(ax, kw, None, cmap, norm, [b.left, b.right, b.bottom, b.top],
             drogi, miasta, granice, min_pop=45_000, lw=.45)
    ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
    MW.podzialka(ax, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    ax.legend(handles=[Patch(facecolor=RAMPA[i],
                             label=f"{dz(progi[i])} – {dz(progi[i+1])}")
                       for i in range(5)],
              loc="lower right", fontsize=9, frameon=True, facecolor="#ffffff",
              edgecolor="#dde3dd", framealpha=.95, title="pełnia kwitnienia",
              title_fontsize=9).set_zorder(9)
    ax.set_title("Termin kwitnienia rzepaku w sezonie 2025", fontsize=14,
                 weight="bold", color=MW.ATRAMENT, loc="left", pad=22)
    ax.text(0, 1.005, "wyłącznie z modelu sum temperatur — deklaracje ARiMR "
            "nie wchodzą tu wcale", transform=ax.transAxes, fontsize=10,
            color=MW.MUTED, va="bottom")

    # ---- prawy: szereg 2000-2026 dla obszaru pilotazowego
    df = pd.read_csv(WYNIKI / "cache" / "meteo_dobowe.csv", parse_dates=["data"])
    seria = {}
    for rok, s in df.groupby("rok"):
        s = s.sort_values("doy")
        gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2
                         - m["baza"], 0)
        gdd[s["doy"].to_numpy() < d0] = 0
        i = np.searchsorted(np.cumsum(gdd), m["prog"])
        if i < len(s):
            seria[int(rok)] = int(s["doy"].to_numpy()[i])
    obs = {int(r): v for r, v in fin["obserwacje"][fin["glowny"]].items()}

    ax2 = fig.add_axes([.53, .13, .45, .74])
    ax2.set_facecolor(MW.TLO)
    lata = sorted(seria)
    ax2.plot(lata, [seria[r] for r in lata], color="#d4542a", lw=2, marker="o",
             ms=4, label="model GDD, 2000–2026")
    wsp = sorted(set(obs) & set(seria))
    ax2.plot(wsp, [obs[r] for r in wsp], "o", ms=8, mfc="none",
             mec=MW.ATRAMENT, mew=1.8, label="obserwacja z Sentinel-2")
    sr = np.mean([seria[r] for r in lata])
    ax2.axhline(sr, color=MW.MUTED, ls=":", lw=1.5)
    ax2.text(lata[0], sr + .8, f"średnia {dz(sr)}", fontsize=9, color=MW.MUTED)
    ax2.set_yticks(range(110, 151, 10))
    ax2.set_yticklabels([dz(v) for v in range(110, 151, 10)], fontsize=9.5)
    ax2.set_xlim(lata[0] - .5, lata[-1] + .5)
    ax2.legend(fontsize=9.5, frameon=False, loc="upper right")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="y", color="#e1e0d9", lw=.8); ax2.set_axisbelow(True)
    ax2.set_title("Ten sam model, dwadzieścia siedem sezonów",
                  fontsize=14, weight="bold", color=MW.ATRAMENT, loc="left", pad=22)
    ax2.text(0, 1.005, f"obszar pilotażowy · rozrzut "
             f"{max(seria.values())-min(seria.values())} dni między latami",
             transform=ax2.transAxes, fontsize=10, color=MW.MUTED, va="bottom")

    fig.text(.53, .045,
             f"baza {m['baza']:.1f} °C · akumulacja od 1 lutego · próg {m['prog']} GDD\n"
             f"kalibrowane na {m['n']} obserwacjach z 7 obszarów, "
             f"błąd {m['rmse']:.1f} dnia",
             fontsize=9.5, color=MW.ATRAMENT, va="top", family="monospace")

    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_modelu.png").write_bytes(buf.getvalue())
    print(f"najwczesniej {min(seria, key=seria.get)}: {dz(min(seria.values()))}")
    print(f"najpozniej   {max(seria, key=seria.get)}: {dz(max(seria.values()))}")
    print("zapisano mapa_modelu.png")
