"""
ETAP 33 - mapa lokalna: heatmapa potencjalu na granicach dzialek.

PO CO
Mapa wojewodzka odpowiada "w ktorym rejonie", lista punktow daje
wspolrzedne - ale pszczelarz jedzie w teren i musi zobaczyc, KTORA
DZIALKA to jest i co na niej rosnie. Ta mapa domyka droge od
wojewodztwa do konkretnego pola.

DLACZEGO WYCINEK, A NIE CALE WOJEWODZTWO
Na 181 x 224 km granice dzialek zlewaja sie w szara plame - przy 1.5 mln
dzialek jedna ma na wydruku ulamek milimetra. Sens ma dopiero wycinek
rzedu kilku kilometrow, czyli mniej wiecej tyle, ile wynosi zasieg lotu.

CO JEST NA MAPIE
  - heatmapa potencjalu (rodziny pszczele w zasiegu lotu)
  - granice dzialek ARiMR, z podpisem uprawy dla wiekszych
  - punkt optimum z listy najlepszych miejsc
  - okregi rownowaznosci 95% i 80% - w ich obrebie mapa NIE rozstrzyga,
    decyduje dojazd, oslona od wiatru i woda

Uruchomienie:
    python skrypty/potencjal/mapa_dzialki.py           # miejsce nr 1
    python skrypty/potencjal/mapa_dzialki.py 5         # miejsce nr 5
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
import matplotlib.pyplot as plt                               # noqa: E402
import numpy as np                                            # noqa: E402
import pyogrio                                                # noqa: E402
import rasterio                                               # noqa: E402
from matplotlib.patches import Circle                         # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"
RASTER = WYNIKI / "rastry" / "woj_koncowa_pojemnosc.tif"
# Bok wycinka. 3 km to ok. 2.5x zasieg jadra wiosennego (1178 m), wiec
# w kadrze miesci sie cale wzniesienie pozytkowe i jeszcze jego otoczenie,
# a granice dzialek sa juz czytelne. Przy 6 km dzialki zlewaly sie w kreske.
BOK_M = 3000
MAX_PODPISOW = 10       # przy mniejszym kadrze miesci sie mniej
MIN_HA_PODPIS = 1.5     # przy kadrze 3 km widac juz mniejsze dzialki


if __name__ == "__main__":
    nr = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    dane = json.loads((WYNIKI / "json" / "najlepsze_punkty.json")
                      .read_text(encoding="utf-8"))
    m = next(q for q in dane["miejsca"] if q["nr"] == nr)
    cx, cy = m["x_2180"], m["y_2180"]
    print(f"miejsce nr {nr}: {m['rodzin']:.0f} rodzin, "
          f"{m['lat']:.4f} N {m['lon']:.4f} E")

    with rasterio.open(RASTER) as f:
        T = f.transform
        col, row = ~T * (cx, cy)
        pr = int(BOK_M / 2 / T.a)
        c0, r0 = int(col) - pr, int(row) - pr
        okno = rasterio.windows.Window(c0, r0, 2 * pr, 2 * pr)
        wyc = f.read(1, window=okno)
        l, t = T * (c0, r0)
        b = t - 2 * pr * T.a
        r = l + 2 * pr * T.a

    print(f"wycinek {BOK_M/1000:.0f} x {BOK_M/1000:.0f} km, "
          f"potencjal {np.nanmin(wyc):.0f}-{np.nanmax(wyc):.0f} rodzin")

    g = pyogrio.read_dataframe(SHP, encoding="utf-8", bbox=(l, b, r, t))
    print(f"dzialek w wycinku: {len(g):,}")

    fig, ax = plt.subplots(figsize=(11, 11))
    im = ax.imshow(wyc, extent=(l, r, b, t), origin="upper",
                   # interpolation="nearest" - kazdy piksel to realne 100 m modelu.
                   # Wczesniej bylo "bilinear", ktore dokladalo rozmycie
                   # CZYSTO KOSMETYCZNE, ponad rozmycie jadrem lotu. Mapa
                   # ma pokazywac rozdzielczosc modelu, a nie ladniejszy
                   # gradient.
                   cmap="YlOrRd", alpha=.92, interpolation="nearest",
                   zorder=1)

    # granice dzialek: cienka kreska, zeby nie zagluszyc heatmapy
    g.boundary.plot(ax=ax, linewidth=.35, edgecolor="#2b2b2b", alpha=.45,
                    zorder=3)
    ax.set_xlim(l, r); ax.set_ylim(b, t)

    # PODPISY BEZ NACHODZENIA.
    # Wczesniej podpisywana byla kazda dzialka powyzej 4 ha i przy gestych
    # sadach nazwy zlewaly sie w nieczytelna plame. Teraz: sortujemy malejaco
    # po powierzchni i kladziemy podpis tylko wtedy, gdy jego prostokat nie
    # koliduje z juz polozonymi. Najwieksze dzialki maja pierwszenstwo, bo to
    # one niosa pozytek.
    kol = g.geometry.area / 10_000
    kand = sorted(((ha, w) for (_, w), ha in zip(g.iterrows(), kol)
                   if ha >= MIN_HA_PODPIS), key=lambda q: -q[0])
    zajete = []
    wys = BOK_M * 0.030               # odstep pionowy miedzy etykietami
    znak = BOK_M * 0.0072             # przyblizona szerokosc znaku w metrach
    for ha, w in kand:
        if len(zajete) >= MAX_PODPISOW:
            break
        c = w.geometry.centroid
        etyk = f"{str(w.get('roslina', ''))[:20]}  ·  {ha:.0f} ha"
        # margines zalezy od DLUGOSCI napisu - staly margines wypuszczal
        # dlugie etykiety poza kadr (np. "pszenica zwyczajna o - 66 ha")
        polowa = len(etyk) * znak / 2
        if not (l + polowa < c.x < r - polowa and
                b + wys < c.y < t - wys):
            continue
        if any(abs(c.x - zx) < polowa + zp and abs(c.y - zy) < wys
               for zx, zy, zp in zajete):
            continue
        # narozniki zajete przez legende (prawy dol) i skale (lewy dol)
        if c.y < b + BOK_M * 0.14 and c.x > r - BOK_M * 0.40:
            continue
        if c.y < b + BOK_M * 0.10 and c.x < l + BOK_M * 0.28:
            continue
        # nie zaslaniaj punktu optimum ani okregow
        if abs(c.x - cx) < m["promien_80_m"] + 150 and            abs(c.y - cy) < m["promien_80_m"] + 150:
            continue
        zajete.append((c.x, c.y, polowa))
        ax.annotate(etyk,
                    (c.x, c.y), ha="center", va="center", fontsize=7.5,
                    color="#1a1a1a", zorder=6,
                    bbox=dict(boxstyle="round,pad=.28", fc="white",
                              ec="#999", lw=.5, alpha=.88))
    print(f"podpisow na mapie: {len(zajete)}")

    for prom, kolor, opis in ((m["promien_95_m"], "#0b6", "95% potencjalu"),
                              (m["promien_80_m"], "#08a", "80% potencjalu")):
        if prom > 0:
            ax.add_patch(Circle((cx, cy), prom, fill=False, lw=1.8,
                                ec=kolor, ls="--",
                                label=f"{opis} (r={prom:.0f} m)"))
    ax.plot(cx, cy, "o", ms=15, mfc="none", mec="white", mew=4, zorder=7)
    ax.plot(cx, cy, "o", ms=15, mfc="none", mec="#000", mew=2, zorder=8)
    ax.plot(cx, cy, "o", ms=5, color="#000", zorder=8)

    ax.set_title(f"Miejsce nr {nr} — {m['rodzin']:.0f} rodzin w zasięgu lotu\n"
                 f"{m['lat']:.4f} N  {m['lon']:.4f} E   ·   "
                 f"granice działek ARiMR 2025", fontsize=12)
    ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc="lower right", fontsize=9, framealpha=.9)
    cb = fig.colorbar(im, ax=ax, shrink=.6, pad=.02)
    cb.set_label("rodziny pszczele w zasięgu lotu")

    # skala
    ax.plot([l + 300, l + 1300], [b + 300, b + 300], "-", lw=4,
            color="white", zorder=9)
    ax.plot([l + 300, l + 1300], [b + 300, b + 300], "k-", lw=2, zorder=10)
    ax.text(l + 800, b + 420, "1 km", ha="center", fontsize=9, zorder=10,
            bbox=dict(boxstyle="round,pad=.2", fc="white", ec="none",
                      alpha=.8))

    MAPY.mkdir(exist_ok=True)
    out = MAPY / f"mapa_dzialki_{nr}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"zapisano {out.relative_to(ROOT)}")

    if "roslina" in g.columns:
        print("\nuprawy w wycinku (ha):")
        for nazwa, powierzchnia in (kol.groupby(g["roslina"]).sum()
                                    .sort_values(ascending=False).head(8)
                                    .items()):
            print(f"  {str(nazwa)[:28]:30s}{powierzchnia:8.1f}")
