"""
Mapa koncowa: potencjal pozytkowy calego wojewodztwa lubelskiego z podkladem.

DLACZEGO NIE MA TU WSZYSTKICH DZIALEK
Przy szerokosci 181 km dzialka 1-hektarowa ma pol piksela. Narysowanie 1.5 mln
dzialek dalo by jednolita szarosc - ten sam blad, ktory popelnilem wczesniej
przy buforze 20 km, tylko szescdziesiat razy gorszy. Dzialki sa czytelne
dopiero w powiekszeniu i tam sa pokazane, we wstawce.

PODKLAD
Drogi glowne, miasta i granice z OpenStreetMap. Drogi rysowane sa ciemna linia
z bialym obrysem (kasetonowanie) - bez tego znikaja na ciemnych klasach mapy,
a w bieli gubia sie na jasnych.

Uruchomienie:
    python mapa_wojewodztwa.py
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pyogrio
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle
from shapely.geometry import MultiLineString, Point
from shapely.ops import polygonize, unary_union
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
OSM = ROOT / "dane" / "osm_podklad.json"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

KLASY = ["#fee0d2", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]
TLO, ATRAMENT, MUTED = "#fcfcfb", "#141b16", "#6b756e"
DROGA, DROGA_OBRYS = "#4a4a48", "#ffffff"

TR = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def podklad() -> tuple[list, list, list]:
    j = json.loads(OSM.read_text(encoding="utf-8"))
    drogi, miasta, granice = [], [], []
    for e in j["elements"]:
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e:
            xy = np.array([TR.transform(p["lon"], p["lat"]) for p in e["geometry"]])
            drogi.append((t.get("highway"), xy))
        elif e["type"] == "node" and t.get("place") in ("city", "town"):
            try:
                pop = int(str(t.get("population", "0")).replace(" ", ""))
            except ValueError:
                pop = 0
            miasta.append((t.get("name", ""), pop, t.get("place"),
                           TR.transform(e["lon"], e["lat"])))
        elif e["type"] == "relation" and t.get("name") == "województwo lubelskie":
            for m in e.get("members", []):
                if m.get("type") == "way" and "geometry" in m:
                    granice.append(np.array(
                        [TR.transform(p["lon"], p["lat"]) for p in m["geometry"]]))
    return drogi, miasta, granice


def rysuj(ax, dane, progi, cmap, norm, ext, drogi, miasta, granice,
          min_pop=0, lw=.6, etykiety=True):
    ax.imshow(np.ma.masked_invalid(dane), cmap=cmap, norm=norm, extent=ext,
              interpolation="nearest", zorder=2)
    for g in granice:
        ax.plot(g[:, 0], g[:, 1], color=ATRAMENT, lw=1.1, alpha=.55, zorder=5)
    for typ, xy in drogi:
        w = {"motorway": 1.5, "trunk": 1.1}.get(typ, .7) * lw
        ax.plot(xy[:, 0], xy[:, 1], color=DROGA, lw=w, zorder=4, solid_capstyle="round",
                path_effects=[pe.withStroke(linewidth=w + 1.4, foreground=DROGA_OBRYS,
                                            alpha=.75)])
    for nazwa, pop, typ, (x, y) in miasta:
        if pop < min_pop and typ != "city":
            continue
        if not (ext[0] < x < ext[1] and ext[2] < y < ext[3]):
            continue
        duze = typ == "city" or pop > 40_000
        ax.plot(x, y, "o", ms=4.5 if duze else 3, mfc="#ffffff", mec=ATRAMENT,
                mew=1.1, zorder=6)
        if etykiety:
            ax.annotate(nazwa, (x, y), xytext=(0, 6), textcoords="offset points",
                        ha="center", fontsize=8.5 if duze else 7,
                        weight="bold" if duze else "normal", color=ATRAMENT,
                        zorder=7, path_effects=[pe.withStroke(linewidth=2.6,
                                                              foreground="#ffffff")])
    ax.set_xticks([]); ax.set_yticks([])
    for k in ax.spines.values():
        k.set_visible(False)


def podzialka(ax, x0, y0, dl, etyk):
    ax.add_patch(Rectangle((x0, y0), dl, dl * .022, facecolor=ATRAMENT, zorder=9))
    ax.add_patch(Rectangle((x0, y0), dl / 2, dl * .022, facecolor="#ffffff",
                           edgecolor=ATRAMENT, lw=.5, zorder=10))
    ax.text(x0 + dl / 2, y0 + dl * .05, etyk, ha="center", va="bottom",
            fontsize=8, color=ATRAMENT, zorder=10)


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        sez = f.read(1) / 1000.0
        b = f.bounds
    ext = [b.left, b.right, b.bottom, b.top]
    v = sez[~np.isnan(sez)]
    progi = [max(0.0, float(np.percentile(v, q))) for q in (0, 60, 80, 92, 98, 100)]
    cmap, norm = ListedColormap(KLASY), BoundaryNorm(progi, 5)

    drogi, miasta, granice = podklad()
    print(f"podklad: {len(drogi)} drog, {len(miasta)} miast, {len(granice)} odcinkow granicy")

    # Maska wojewodztwa. Bez niej teren poza granica czyta sie jako niski
    # potencjal, a tam po prostu nie ma deklaracji - to jest brak danych,
    # nie brak pozytku.
    poly = max(polygonize(unary_union(MultiLineString([g for g in granice
                                                       if len(g) > 1]))),
               key=lambda q: q.area)
    print(f"  poligon wojewodztwa: {poly.area/1e10:.2f} tys. km2")
    yy, xx = np.mgrid[0:sez.shape[0], 0:sez.shape[1]]
    px = b.left + (xx + .5) * 100
    py = b.top - (yy + .5) * 100
    from matplotlib.path import Path as MplPath
    kontur = MplPath(np.array(poly.exterior.coords))
    w_woj = kontur.contains_points(np.column_stack([px.ravel(), py.ravel()])
                                   ).reshape(sez.shape)
    sez = np.where(w_woj, sez, np.nan)
    v = sez[~np.isnan(sez)]
    progi = [max(0.0, float(np.percentile(v, q))) for q in (0, 60, 80, 92, 98, 100)]
    norm = BoundaryNorm(progi, 5)
    print(f"  po maskowaniu: {len(v):,} pikseli, mediana {np.median(v):.1f} t")

    # statystyki MUSZA byc liczone po maskowaniu, inaczej blok liczbowy
    # przeczy mapie - poprzednio mediana z pikseli spoza wojewodztwa
    # zanizala wynik z 5.3 do 2.8 t
    stat = {q: float(np.percentile(v, q)) for q in (10, 25, 50, 75, 90, 99, 100)}
    TRp = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    hx, hy = TRp.transform(23.600, 50.755)
    jh, ih = int((hx - b.left) / 100), int((b.top - hy) / 100)
    pil = float(sez[ih, jh])
    pil_pc = float(100 * (v < pil).mean())
    print(f"  obszar pilotazowy: {pil:.1f} t -> percentyl {pil_pc:.0f}")
    woj_stat = {"percentyle_t": {str(k): val for k, val in stat.items()},
                "pilotazowy": {"wartosc_t": pil, "percentyl": pil_pc}}
    plik = WYNIKI / "json" / "wojewodztwo.json"
    z = json.loads(plik.read_text(encoding="utf-8"))
    z.update(woj_stat); z["maskowane_do_granicy"] = True
    plik.write_text(json.dumps(z, ensure_ascii=False, indent=1), encoding="utf-8")

    fig = plt.figure(figsize=(11.5, 12.2), dpi=170)
    fig.patch.set_facecolor(TLO)
    ax = fig.add_axes([.02, .07, .66, .87])
    rysuj(ax, sez, progi, cmap, norm, ext, drogi, miasta, granice, min_pop=18_000)
    ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
    podzialka(ax, b.left + 6000, b.bottom + 8000, 40_000, "40 km")
    ax.annotate("N", xy=(b.right - 12000, b.top - 12000), xytext=(0, -26),
                textcoords="offset points", ha="center", fontsize=10,
                weight="bold", color=ATRAMENT, zorder=9,
                arrowprops=dict(arrowstyle="-|>", color=ATRAMENT, lw=1.3))

    # --- wstawka: powiekszenie najlepszego rejonu z dzialkami
    woj = json.loads((WYNIKI / "json" / "wojewodztwo.json").read_text(encoding="utf-8"))
    i, j = np.unravel_index(np.nanargmax(np.where(np.isnan(sez), -np.inf, sez)),
                            sez.shape)
    cx = b.left + (j + .5) * 100
    cy = b.top - (i + .5) * 100
    R = 7000
    ax.add_patch(Rectangle((cx - R, cy - R), 2 * R, 2 * R, fill=False,
                           edgecolor=ATRAMENT, lw=1.6, zorder=8))

    axi = fig.add_axes([.68, .52, .30, .34])
    axi.set_facecolor(TLO)
    dz = pyogrio.read_dataframe(SHP, bbox=(cx-R, cy-R, cx+R, cy+R), encoding="utf-8")
    rz = dz[dz["roslina"] == "rzepak ozimy"]
    ii0, ii1 = int((b.top - (cy+R))/100), int((b.top - (cy-R))/100)
    jj0, jj1 = int(((cx-R) - b.left)/100), int(((cx+R) - b.left)/100)
    axi.imshow(np.ma.masked_invalid(sez[ii0:ii1, jj0:jj1]), cmap=cmap, norm=norm,
               extent=[cx-R, cx+R, cy-R, cy+R], interpolation="nearest", zorder=1)
    dz.plot(ax=axi, facecolor="none", edgecolor="#ffffff", lw=.25, alpha=.5, zorder=2)
    rz.plot(ax=axi, facecolor="none", edgecolor=ATRAMENT, lw=.45, alpha=.85, zorder=3)
    for typ, xy in drogi:
        axi.plot(xy[:, 0], xy[:, 1], color=DROGA, lw=1.2, zorder=4,
                 path_effects=[pe.withStroke(linewidth=2.6, foreground="#ffffff")])
    axi.plot(cx, cy, "o", ms=9, mfc="none", mec=ATRAMENT, mew=2, zorder=6)
    axi.set_xlim(cx-R, cx+R); axi.set_ylim(cy-R, cy+R)
    axi.set_xticks([]); axi.set_yticks([])
    for k in axi.spines.values():
        k.set_edgecolor(ATRAMENT); k.set_linewidth(1.6)
    podzialka(axi, cx - R + 700, cy - R + 900, 5000, "5 km")
    axi.set_title("Najlepszy rejon z bliska", fontsize=11, weight="bold",
                  color=ATRAMENT, loc="left", pad=6)
    fig.text(.68, .505, "ciemny obrys — działki rzepaku · jasny — pozostałe uprawy\n"
             "kółko — punkt o najwyższym potencjale w województwie",
             fontsize=8.5, color=MUTED, va="top")

    fig.legend(handles=[Patch(facecolor=KLASY[k],
                              label=f"{progi[k]:.1f}–{progi[k+1]:.1f}")
                        for k in range(5)],
               loc="upper left", bbox_to_anchor=(.68, .45), ncol=1,
               fontsize=9.5, frameon=False,
               title="tony cukrów w nektarze\nw zasięgu lotu pszczoły",
               title_fontsize=10)

    fig.text(.02, .975, "Potencjał pożytkowy województwa lubelskiego",
             fontsize=19, weight="bold", color=ATRAMENT, va="top")
    fig.text(.02, .947,
             f"sezon {woj['rok']} · deklaracje obszarowe ARiMR · "
             "zasięg lotu 3 km z zanikiem wykładniczym",
             fontsize=10.5, color=MUTED, va="top")
    fig.text(.68, .30,
             f"mediana województwa   {woj['percentyle_t']['50']:.1f} t\n"
             f"najlepsze 10%         > {woj['percentyle_t']['90']:.1f} t\n"
             f"maksimum              {woj['percentyle_t']['100']:.1f} t\n\n"
             f"obszar pilotażowy     {woj['pilotazowy']['wartosc_t']:.1f} t\n"
             f"  czyli percentyl     {woj['pilotazowy']['percentyl']:.0f}",
             fontsize=9.5, color=ATRAMENT, va="top", family="monospace")
    fig.text(.02, .022,
             "Pas 3 km przy granicy województwa jest zaniżony — splot nie ma tam "
             "pełnego otoczenia, bo deklaracje kończą się na granicy.",
             fontsize=8.5, color=MUTED)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_wojewodztwa.png").write_bytes(buf.getvalue())
    print(f"zapisano mapa_wojewodztwa.png ({len(buf.getvalue())/1e6:.1f} MB)")
