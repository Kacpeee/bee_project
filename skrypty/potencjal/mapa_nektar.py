"""
Cukier z rzepaku PO SPLOCIE z jadrem zasiegu lotu - liczony Z SAMEJ SATELITY.

DLACZEGO NIE Z DEKLARACJI
Raster woj_rzepak.tif powstaje z rasteryzacji wnioskow ARiMR, wiec pokazuje,
co rolnicy ZADEKLAROWALI. To nie jest dowod, ze model dziala - deklaracje sa
tylko za 2025 i 2026, a produkt ma dzialac takze tam, gdzie ich nie ma.

Ta mapa bierze warstwe detekcyjna: wielo_klasy_{rok}.npz, czyli wynik
klasyfikatora wielogatunkowego Sentinel-1+2 - tego samego, o ktorym mowi
raport. Zaden wniosek rolnika w to nie wchodzi.

DOMYSLNY ROK: 2022
Bo dla niego istnieje NIEZALEZNA kontrola - EUCROPMAP (JRC) tez ma warstwe
rzepaku za 2022 i zgadza sie z nasza w r = 0,918. Deklaracji za 2022 nie ma
zadnych, wiec ten rok pokazuje model dzialajacy samodzielnie.

DLACZEGO PLAMA JEST SZERSZA NIZ POLA
Jadro wiosenne ma zasieg ok. 1,2 km, wiec pojedyncze pole podnosi potencjal
takze wokol siebie. Rozmycie nie jest wygladzaniem - to tresc modelu:
pszczola nie zbiera z piksela, na ktorym stoi ul.

Uruchomienie:
    python skrypty/potencjal/mapa_nektar.py              # 2022, oba kadry
    python skrypty/potencjal/mapa_nektar.py --rok 2019
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import matplotlib                                             # noqa: E402
matplotlib.use("Agg")
import matplotlib.patheffects as pe                           # noqa: E402
import matplotlib.pyplot as plt                               # noqa: E402
import numpy as np                                            # noqa: E402
import rasterio                                               # noqa: E402
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D                           # noqa: E402
from matplotlib.patches import Circle                         # noqa: E402
from scipy.signal import fftconvolve                          # noqa: E402

sys.path[:0] = [str(p) for p in Path(__file__).resolve().parents[1].iterdir()
                if p.is_dir()]
import mapa_wojewodztwa as MW                                 # noqa: E402
import potencjal_gsa as P                                     # noqa: E402
import wojewodztwo as W                                       # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

# HEATMAPA CIEPLA - konwencja: malo = jasne, duzo = czerwone.
# Dzialki rzepaku ida na ZIELONO, bo to jedyny kolor nieobecny w tej rampie;
# zolte oznaczenia zlewalyby sie z podkladem dokladnie tam, gdzie rzepaku
# jest najwiecej, czyli tam, gdzie mapa ma byc najczytelniejsza.
BARWY = ["#fdf9f0", "#fde3ab", "#fbc25c", "#f2913a", "#dc562a", "#96170f"]
CMAP = LinearSegmentedColormap.from_list("nektar", BARWY)
RZEPAK_LIC, RZEPAK_OBR = "#2f9e5f", "#0f3d26"
KG = P.POZYTKI["rzepak ozimy"][0]


def maska_woj(T, ksztalt):
    from matplotlib.path import Path as MplPath
    from shapely.geometry import MultiLineString
    from shapely.ops import polygonize, unary_union
    _, _, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    ny, nx = ksztalt
    yy, xx = np.mgrid[0:ny, 0:nx]
    px = T.c + (xx + .5) * 100
    py = T.f - (yy + .5) * 100
    w = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(ny, nx)
    return w


def warstwa(rok: int):
    """Cukier rzepaku w tonach, wylacznie z detekcji satelitarnej.

    ZRODLO: wielo_klasy_{rok}.npz - klasyfikator WIELOGATUNKOWY S1+S2, ten
    sam, ktory opisuje raport (F1 rzepaku 0,940).

    Pierwsza wersja tej mapy siegala po woj_prawd_{rok}.npy. To jest starszy,
    BINARNY klasyfikator 8-cechowy z wczesniejszego etapu projektu - inny
    model, inne cechy, gorszy wynik. Dla 2022 dawal 103 tys. ha wobec
    138 tys. z modelu wielogatunkowego i 148 tys. z EUCROPMAP, czyli
    zanizal o okolo 30%. Mapa ilustrowala wiec model, o ktorym raport
    nie mowi.

    Kalibracja arealowa mnozona jest w locie, tak samo jak w kalendarzu -
    osobne pliki *_skalibrowane sa zbedne.
    """
    f = WYNIKI / "cache" / f"wielo_klasy_{rok}.npz"
    if not f.exists():
        raise SystemExit(f"brak {f.name} - detekcja dla {rok} nie policzona")
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as r:
        T = r.transform
    wsp = json.loads((WYNIKI / "json" / "kalibracja_arealowa.json")
                     .read_text(encoding="utf-8"))["wspolczynniki"]
    with np.load(f) as z:
        udzial = np.nan_to_num(z["rzepak ozimy"]) * wsp.get("rzepak ozimy", 1.0)
    Kj = W.jadro_dla("rzepak ozimy")                   # jadro WIOSENNE
    v = fftconvolve(udzial, Kj, mode="same") * KG / 1000.0     # -> tony
    w = maska_woj(T, v.shape)
    print(f"rok {rok}: {udzial[w].sum():,.0f} ha rzepaku wg detekcji "
          f"(po kalibracji), maks {v[w].max():.1f} t w zasiegu lotu")
    return np.where(w, v, np.nan), T


def progi(v):
    """Percentyle - rozklad skrajnie skosny, rowne przedzialy nie dzialaja."""
    d = v[np.isfinite(v) & (v > 0)]
    return [0.0] + [float(np.percentile(d, q)) for q in (55, 78, 91, 97, 99.7)]


def legenda(ax, br, rzepak=False):
    et = [f"{br[i]:,.1f} – {br[i+1]:,.1f}" for i in range(len(br) - 1)]
    et[-1] = f"> {br[-2]:,.1f}"
    uchw = [Line2D([], [], marker="s", ls="", ms=13, mec="#8d968f",
                   mfc=CMAP(i / (len(et) - 1)), label=e)
            for i, e in enumerate(et)]
    if rzepak:
        uchw += [Line2D([], [], marker="s", ls="", ms=13, mfc=RZEPAK_LIC,
                        mec=RZEPAK_OBR, mew=1.3, label="detected rapeseed"),
                 Line2D([], [], marker="s", ls="", ms=13, mfc="none",
                        mec="#6b7a72", label="other parcels")]
    ax.legend(handles=uchw,
              title="tonnes of rapeseed sugar within flight range",
              loc="upper center", bbox_to_anchor=(.5, -.012),
              ncol=4, frameon=False, fontsize=9.5, title_fontsize=9.5,
              columnspacing=1.5)


def wojewodztwo(rok, v, T, br):
    norm = BoundaryNorm(br + [float(np.nanmax(v))], CMAP.N, clip=True)
    _, miasta, granice = MW.podklad()
    fig, ax = plt.subplots(figsize=(10, 12.4))
    fig.patch.set_facecolor(MW.TLO)
    ax.set_facecolor(MW.TLO)
    ny, nx = v.shape
    ax.imshow(v, extent=[T.c, T.c + nx*100, T.f - ny*100, T.f],
              cmap=CMAP, norm=norm, interpolation="nearest")
    for g in granice:
        if len(g) > 1:
            xs, ys = zip(*g)
            ax.plot(xs, ys, color=MW.ATRAMENT, lw=1.0, alpha=.6, zorder=4)
    for n, pop, typ, c in miasta:
        if pop < 60_000:
            continue
        ax.plot(*c, "o", ms=5, mfc="white", mec=MW.ATRAMENT, mew=1.2, zorder=5)
        ax.text(c[0] + 2600, c[1] + 2600, n, fontsize=10.5, zorder=6,
                color=MW.ATRAMENT,
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    legenda(ax, br)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Rapeseed nectar sugar reachable from each point — {rok}\n"
                 f"detected from satellite imagery alone, "
                 f"no farmer declarations used",
                 fontsize=15, weight="bold", color=MW.ATRAMENT, pad=14)
    fig.text(.5, -.035,
             "rapeseed found by the Sentinel-1+2 classifier, then convolved "
             "with the spring flight-range kernel\n"
             "(exponential, λ = 294 m, effective range 1.2 km, calibrated on "
             "waggle-dance distances — Couvillon 2014) · 1 px = 1 ha\n"
             f"{rok} has no ARiMR declarations at all; the independent check "
             "is EUCROPMAP 2022, which agrees at r = 0.918",
             ha="center", fontsize=9.5, color=MW.MUTED)
    out = MAPY / f"nectar_voivodeship_{rok}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=MW.TLO)
    plt.close(fig)
    print(f"zapisano {out.name}")


def wycinek(rok, nr, prom, v, T, br):
    import pandas as pd
    import pyogrio
    norm = BoundaryNorm(br + [float(np.nanmax(v))], CMAP.N, clip=True)
    m = next(x for x in json.loads(
        (WYNIKI / "json" / "najlepsze_punkty.json").read_text(encoding="utf-8")
    )["miejsca"] if x["nr"] == nr)
    cx, cy = m["x_2180"], m["y_2180"]

    fig, ax = plt.subplots(figsize=(9.5, 10.6))
    fig.patch.set_facecolor(MW.TLO)
    ax.set_facecolor(MW.TLO)
    ny, nx = v.shape
    ax.imshow(v, extent=[T.c, T.c + nx*100, T.f - ny*100, T.f],
              cmap=CMAP, norm=norm, interpolation="nearest")

    # WSZYSTKIE dzialki cienkim obrysem + rzepak na zielono.
    # Granice pochodza z deklaracji 2025 i sluza WYLACZNIE za podklad -
    # kolor bierze sie z klasyfikacji satelitarnej, nie z wniosku rolnika.
    cache = WYNIKI / "cache" / f"pola_wokol_{nr}_{prom}.csv"
    n_rz = 0
    if cache.exists():
        g = pyogrio.read_dataframe(SHP, encoding="utf-8",
                                   bbox=(cx-prom, cy-prom, cx+prom, cy+prom))
        g = g[g.geometry.area >= 2000].copy()
        g["pred"] = g.index.map(pd.read_csv(cache, index_col=0)["pred"])
        rz = g[g.pred == "rzepak ozimy"]
        n_rz = len(rz)
        for geom in g[g.pred != "rzepak ozimy"].geometry:
            for gm in ([geom] if geom.geom_type == "Polygon"
                       else list(geom.geoms)):
                ax.fill(*gm.exterior.xy, facecolor="none", edgecolor="#6b7a72",
                        lw=.3, alpha=.5, zorder=4)
        for geom in rz.geometry:
            for gm in ([geom] if geom.geom_type == "Polygon"
                       else list(geom.geoms)):
                ax.fill(*gm.exterior.xy, facecolor=RZEPAK_LIC, alpha=.78,
                        edgecolor=RZEPAK_OBR, lw=1.3, zorder=6)

    for r_, st in ((1000, ":"), (3000, "--")):
        if r_ <= prom * 1.05:
            ax.add_patch(Circle((cx, cy), r_, fill=False, ls=st, lw=1.6,
                                ec="#243b33", alpha=.8, zorder=7))
            ax.text(cx, cy + r_, f" {r_/1000:.0f} km", fontsize=9.5, zorder=8,
                    ha="center", va="bottom", color="#243b33",
                    path_effects=[pe.withStroke(linewidth=3,
                                                foreground="white")])
    ax.plot(cx, cy, marker="*", ms=23, mfc=RZEPAK_OBR, mec="white", mew=2.0,
            zorder=9)

    legenda(ax, br, rzepak=True)
    ax.set_xlim(cx - prom, cx + prom)
    ax.set_ylim(cy - prom, cy + prom)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Site {nr} — reachable rapeseed sugar, {prom/1000:.0f} km "
                 f"around the hive\n"
                 f"green: {n_rz} parcels the classifier called rapeseed — "
                 f"the input to the convolution",
                 fontsize=13.5, weight="bold", color=MW.ATRAMENT, pad=14)
    fig.text(.5, -.04,
             "the coloured surface is the convolution result, the green "
             "parcels are its input — one field lifts the potential around "
             "it,\nbecause a colony forages over kilometres, not from the "
             "pixel it stands on · parcel outlines are a backdrop only, "
             "the colour comes from satellite classification",
             ha="center", fontsize=9.5, color=MW.MUTED)
    out = MAPY / f"nectar_site_{nr}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=MW.TLO)
    plt.close(fig)
    print(f"zapisano {out.name}  ({n_rz} dzialek rzepaku)")


if __name__ == "__main__":
    a = sys.argv[1:]
    # DWA ROZNE LATA - celowo.
    # Kadr wojewodzki ma pokazac model dzialajacy BEZ deklaracji, wiec bierze
    # 2022: rok, dla ktorego nie ma zadnych wnioskow ARiMR, a jest niezalezna
    # kontrola EUCROPMAP.
    # Wycinek pokazuje dzialki, a te maja granice tylko w 2025 i 2026. Gdyby
    # powierzchnia byla z 2022, a dzialki z klasyfikacji 2025, zielone pola
    # lezalyby czesciowo na bialym tle - rzepak wedruje w plodozmianie i po
    # trzech latach jest gdzie indziej. Wycinek uzywa wiec 2025 dla OBU
    # warstw; klasyfikacja nadal pochodzi z satelity, nie z wniosku.
    rok_woj = int(a[a.index("--rok") + 1]) if "--rok" in a else 2022
    rok_wyc = 2025
    MAPY.mkdir(exist_ok=True)

    v, T = warstwa(rok_woj)
    br = progi(v)
    print("progi legendy (t):", ", ".join(f"{x:.2f}" for x in br))
    wojewodztwo(rok_woj, v, T, br)

    nry = [int(x) for x in a if x.isdigit() and len(x) < 3] or [1, 2]
    if nry:
        v2, T2 = warstwa(rok_wyc)
        for nr in nry:
            wycinek(rok_wyc, nr, 3000, v2, T2, br)
