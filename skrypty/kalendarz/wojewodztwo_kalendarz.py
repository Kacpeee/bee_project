"""
Wymiar czasowy w skali wojewodztwa: kiedy wypada szczyt i co zostaje po rzepaku.

DLACZEGO NIE SZESNASCIE MAP DEKADOWYCH
Probowalismy tego w buforze i wyszlo zle - szesc paneli bylo pustych, bo mapy
sluzyly do pokazania NIEOBECNOSCI. W skali wojewodztwa byloby jeszcze gorzej.
Zamiast tego dwie mapy, ktore skladaja wymiar czasowy w jedna warstwe:

  1. DEKADA SZCZYTU - kiedy w danym miejscu wypada najwiekszy pozytek.
     Tam gdzie to nie jest dekada rzepakowa, obowiazuje inna strategia.
  2. SUMA SEZONOWA - gdzie jest najwiecej cukru (srednia deklaracji 2025
     i 2026). Wczesniej byla tu mapa "po rzepaku", ale wygladala jak druga
     mapa potencjalu i mylila; jej tresc i tak siedzi w krzywych kalendarza.

Stos dekadowy liczony na SREDNIEJ splotow z obu sezonow deklaracji.

Plus kalendarze dla kilku kontrastowych punktow, bo krzywa pokazuje przerwy,
ktorych mapa pokazac nie potrafi.

TERMIN KWITNIENIA RZEPAKU JEST PRZESTRZENNY
Model GDD daje date osobno dla kazdego punktu siatki meteo. W 2025 rozrzut
w wojewodztwie to 10 dni, wiec piksele sa grupowane wg daty kwitnienia
i kazda grupa dostaje wlasny rozklad dekadowy.

Uruchomienie:
    python wojewodztwo_kalendarz.py
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
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from pyproj import Transformer

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import mapa_wojewodztwa as MW
import potencjal_gsa as P

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
TR = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)

# punkty kontrastowe do krzywych kalendarzowych
PUNKTY = {
    "Bełżec (najlepszy)":  (50.4645, 23.9150),
    "Hrubieszów (pilot)":  (50.7550, 23.6000),
    "Bychawa":             (51.0000, 22.5300),
    "Włodawa (Polesie)":   (51.5500, 23.5200),
}
# rampa czasowa: jeden odcien na miesiac szczytu
CZAS_KOLOR = ["#fde0a5", "#f6a44c", "#e0562a", "#9d3b8c", "#4b5bab"]
CZAS_OPIS = ["do 30 IV", "1–20 V", "21 V – 9 VI", "10–29 VI", "30 VI i później"]


def udzialy(s, p, k, dek):
    w = {}
    for d in dek:
        m = d + 5
        w[d] = (0.0 if m <= s or m >= k else
                (m - s) / (p - s) if m <= p else (k - m) / (k - p))
    su = sum(w.values())
    return {a: b / su for a, b in w.items()} if su else w


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    z25 = np.load(WYNIKI / "cache" / "woj_splot_2025.npz")
    z26 = np.load(WYNIKI / "cache" / "woj_splot_2026.npz")
    z = {n: ((z25[n] + z26[n]) / 2 if n in z26.files else z25[n])
         for n in z25.files}
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, ksztalt = f.bounds, f.shape
    with rasterio.open(WYNIKI / "rastry" / "woj_kwitnienie.tif") as f:
        kw = f.read(1)
    DEK = P.DEKADY
    przed, po = P.ksztalt_rzepaku()
    print(f"klas: {len(z)}, siatka {ksztalt}, "
          f"kwitnienie {np.nanmin(kw):.0f}-{np.nanmax(kw):.0f} DOY, "
          f"okno rzepaku -{przed}/+{po}")

    # maska wojewodztwa z modulu mapy
    drogi, miasta, granice = MW.podklad()
    from shapely.geometry import MultiLineString
    from shapely.ops import polygonize, unary_union
    from matplotlib.path import Path as MplPath
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ksztalt[0], 0:ksztalt[1]]
    px = b.left + (xx + .5) * 100
    py = b.top - (yy + .5) * 100
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(ksztalt)

    # --- stos dekadowy; rzepak grupowany wg lokalnej daty kwitnienia
    kw_bin = np.where(np.isnan(kw), 129, kw)
    grupy = np.clip(((kw_bin - 122) // 4).astype(int), 0, 3)   # 4 grupy po ~4 dni
    print("grupy dat kwitnienia:", {int(g): int((grupy == g).sum())
                                    for g in np.unique(grupy)})

    # STRAZNIK: kalendarz idzie po cache, wiec gatunek dodany do POZYTKI
    # po jego zapisaniu wypadlby z kalendarza bez sladu. Tak wlasnie
    # znikal drugi pokos TUZ (9.4% cukrow, kwitnienie 5 VII - 5 VIII).
    brak = [n for n in P.POZYTKI if n not in z]
    if brak:
        raise SystemExit("CACHE NIEAKTUALNY - brak klas: " + ", ".join(brak)
                         + " | usun woj_splot_*.npz i przelicz mape")

    stos = np.zeros((len(DEK),) + ksztalt, "float32")
    for nazwa in z:
        if nazwa not in P.POZYTKI:      # cache moze miec uprawy wykluczone
            continue
        kg, s0, p0, k0 = P.POZYTKI[nazwa][:4]
        m = z[nazwa]
        if nazwa == "rzepak ozimy":
            for g in np.unique(grupy):
                pelnia = 124 + int(g) * 4 + 2
                r = udzialy(pelnia - przed, pelnia, pelnia + po, DEK)
                sel = grupy == g
                for i, d in enumerate(DEK):
                    if r[d]:
                        stos[i][sel] += m[sel] * kg * r[d]
        else:
            if nazwa == "Sad":
                # uprawa trwala z dynamicznym oknem (fenologia_sadu.py):
                # cale okno przesuniete o roznice miedzy data GDD danego
                # roku a pelnia literaturowa; rozrzut przestrzenny w 2025
                # to 4 dni, wiec przesuniecie jednolite wystarcza
                sad = json.loads(
                    (WYNIKI / "json" / "fenologia_sadu.json")
                    .read_text(encoding="utf-8"))
                dl = ((sad["mapa_2025"]["min"] + sad["mapa_2025"]["max"]) / 2
                      - sad["pelnia_literaturowa"])
                s0, p0, k0 = s0 + dl, p0 + dl, k0 + dl
                print(f"  Sad: okno przesuniete o {dl:+.0f} dni (GDD 2025)")
            r = udzialy(s0, p0, k0, DEK)
            for i, d in enumerate(DEK):
                if r[d]:
                    stos[i] += m * kg * r[d]
    stos = np.where(maska, stos, np.nan)
    print(f"stos dekadowy gotowy: {stos.nbytes/1e6:.0f} MB")

    # --- mapa 1: dekada szczytu
    szczyt = np.nanargmax(np.nan_to_num(stos, nan=-1), axis=0)
    doy_szczyt = np.array(DEK)[szczyt].astype("float32")
    doy_szczyt[~maska] = np.nan
    progi_cz = [100, 120, 140, 160, 180, 260]
    cmap_cz = ListedColormap(CZAS_KOLOR)
    norm_cz = BoundaryNorm(progi_cz, 5)

    # --- mapa 2: suma sezonowa - gdzie jest najwiecej cukru (srednia 2 sezonow)
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        po = f.read(1) / 1000.0
    po = np.where(maska, po, np.nan)
    v = po[~np.isnan(po)]
    progi_po = [max(0.0, float(np.percentile(v, q)))
                for q in (0, 60, 80, 92, 98, 100)]
    cmap_po = ListedColormap(MW.KLASY)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 9.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO)
    ext = [b.left, b.right, b.bottom, b.top]
    for ax, dane, cm, nm, tyt, pod in (
        (a1, doy_szczyt, cmap_cz, norm_cz, "Kiedy wypada szczyt pożytku",
         "dekada z największą ilością cukru w zasięgu lotu"),
        (a2, po, cmap_po, BoundaryNorm(progi_po, 5),
         "Gdzie jest najwięcej cukru",
         "suma za cały sezon, tony cukrów w zasięgu lotu")):
        MW.rysuj(ax, dane, None, cm, nm, ext, drogi, miasta, granice,
                 min_pop=45_000, lw=.45)
        ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
        ax.set_title(tyt, fontsize=14, weight="bold", color=MW.ATRAMENT,
                     loc="left", pad=22)
        ax.text(0, 1.005, pod, transform=ax.transAxes, fontsize=10,
                color=MW.MUTED, va="bottom")
    MW.podzialka(a1, b.left + 6000, b.bottom + 8000, 40_000, "40 km")

    # legendy POD mapami - poziomo, zeby nigdy nie nachodzily na rysunek
    for ax, hnd in (
        (a1, [Patch(facecolor=CZAS_KOLOR[i], label=CZAS_OPIS[i])
              for i in range(5)]),
        (a2, [Patch(facecolor=MW.KLASY[i],
                    label=f"{progi_po[i]:.1f}–{progi_po[i+1]:.1f} t")
              for i in range(5)])):
        ax.legend(handles=hnd, loc="upper center", bbox_to_anchor=(.5, -.002),
                  ncol=5, fontsize=9.5, frameon=False, handlelength=1.5,
                  handleheight=1.15, columnspacing=1.1, handletextpad=.5)
    fig.text(.5, .012, "zasięg lotu 3 km · uprawy z deklaracji ARiMR 2025 "
             "i 2026 · terminy kwitnienia rzepaku z modelu sum temperatur",
             ha="center", fontsize=9, color=MW.MUTED)
    fig.subplots_adjust(left=.01, right=.99, top=.92, bottom=.075, wspace=.03)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "mapa_woj_czas.png").write_bytes(buf.getvalue())
    print(f"zapisano mapa_woj_czas.png")

    # --- kalendarze punktow kontrastowych
    kal = {}
    for n, (la, lo) in PUNKTY.items():
        x, y = TR.transform(lo, la)
        j, i = int((x - b.left) / 100), int((b.top - y) / 100)
        kal[n] = [float(stos[k, i, j]) / 1000 for k in range(len(DEK))]
    daty = {d: (P.d(d)) for d in DEK}

    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=165)
    fig.patch.set_facecolor(MW.TLO); ax.set_facecolor(MW.TLO)
    kolory = ["#a50f15", "#de2d26", "#fb6a4a", "#7f8f85"]
    for (n, w), c in zip(kal.items(), kolory):
        ax.plot(DEK, w, lw=2.2, color=c, marker="o", ms=4, label=n)
    ax.set_xticks(DEK[::2])
    ax.set_xticklabels([daty[d] for d in DEK[::2]], fontsize=9)
    ax.set_ylabel("tony cukrów w dekadzie", fontsize=10, color=MW.ATRAMENT)
    ax.legend(fontsize=9.5, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e1e0d9", lw=.8)
    ax.set_axisbelow(True)
    ax.set_title("Kalendarz pożytku w czterech rejonach województwa",
                 fontsize=13, weight="bold", color=MW.ATRAMENT, loc="left", pad=10)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=MW.TLO)
    plt.close(fig)
    (ROOT / "mapy" / "wykres_woj_kalendarz.png").write_bytes(buf.getvalue())

    print("\nKALENDARZE (t cukrow w dekadzie)")
    print(f"{'rejon':>22}" + "".join(f"{daty[d]:>7}" for d in DEK[:11]))
    for n, w in kal.items():
        print(f"{n:>22}" + "".join(f"{x:>7.1f}" for x in w[:11]))
    (WYNIKI / "json" / "wojewodztwo_kalendarz.json").write_text(json.dumps({
        "dekady": DEK, "daty": daty, "kalendarze": kal,
        "progi_po_rzepaku": progi_po,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano wykres_woj_kalendarz.png i JSON")
