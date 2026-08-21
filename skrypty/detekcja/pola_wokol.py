"""
Konkretne POLA wokol wybranego punktu, rozpoznane ze zdjec satelitarnych.

PO CO
Mapa potencjalu odpowiada, ile cukru pszczola dosiegnie z danego miejsca -
i celowo jest rozmyta, bo pszczola lata kilometrami. Nie mowi jednak, KTORE
pole jest rzepakiem. Pszczelarz stojacy na miedzy potrzebuje wlasnie tego.

DLACZEGO DZIALKI, A NIE PIKSELE
Surowy piksel 10 m ma w proporcjach terenowych F1 0,658 - mniej wiecej co
drugie wskazanie "tu rzepak" jest bledne, bo 87% gruntow to cos innego
i piksel przy miedzy zawiera dwie uprawy naraz. Po przyklejeniu do granic
dzialek ARiMR i glosowaniu wiekszosciowym wraca 0,910 (zmierzone
w ocena_pikselowa.py). Dlatego rysunek pokazuje DZIALKI pokolorowane
rozpoznana uprawa, a nie kolorowe piksele.

ZASTRZEZENIE
To jest widok PRODUKTU, nie ocena. Model klasyfikuje tu dowolny teren,
takze taki, ktory widzial w treningu - jak w normalnym uzyciu. Liczby
jakosci pochodza z osobnego pomiaru na blokach testowych.

Uruchomienie:
    python skrypty/detekcja/pola_wokol.py [nr_miejsca] [promien_m]
    python skrypty/detekcja/pola_wokol.py 1 3000
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from shapely.geometry import Point

sys.path[:0] = [str(p) for p in Path(__file__).resolve().parents[1].iterdir()
                if p.is_dir()]

import ee                                                     # noqa: E402
import gee_klasyfikator_rzepaku as K                          # noqa: E402
import mapa_wojewodztwa as MW                                 # noqa: E402
from cechy_s1s2 import cechy                                  # noqa: E402
from wielo_diagnoza import ODRZUC, SCAL                       # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"
ROK, DRZEW, ZIARNO = 2025, 300, 42
PIKSELI = 3               # glosow na dzialke
GRUPA = {"koniczyna czerwona": "motylkowe pastewne",
         "lucerna mieszańcowa": "motylkowe pastewne"}

# kolory: rzepak wyrazny, reszta pozytkow ciepla, niepozytki szare
BARWY = {
    "rzepak ozimy": "#e8b81e", "gorczyca": "#f0d060",
    "gryka zwyczajna": "#c65d3a", "malina": "#a83e5c",
    "porzeczka": "#8e4a72", "Sad": "#7a9e4f", "TUZ": "#9fbf7a",
    "słonecznik": "#d98f2b", "fasola wielokwiatowa": "#b5793f",
    "motylkowe pastewne": "#87a96b", "bobik": "#9c8f5f",
    "inne": "#d8d8d4",
}
SZARY = "#d8d8d4"


def model():
    """Las losowy uczony na blokach treningowych - ten sam, co w ocenie."""
    C = WYNIKI / "cache"
    tr = pd.read_csv(C / "wielo_punkty.csv")
    X = (pd.read_csv(C / "wielo_cechy.csv").set_index("i")
         .join(pd.read_csv(C / "wielo_cechy_s1.csv").set_index("i")))
    tr = tr.reset_index(drop=True).join(X)
    tr = tr[(tr.test == 0) & (~tr.etykieta.isin(ODRZUC))].copy()
    tr["grupa"] = tr.etykieta.replace(SCAL).replace(GRUPA)
    kol = [c for c in X.columns
           if c.startswith(("ndvi", "ndyi", "vv_", "vh_", "rat_"))]
    tr = tr.dropna(subset=kol)
    from sklearn.ensemble import RandomForestClassifier
    las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                 random_state=ZIARNO).fit(tr[kol], tr.grupa)
    print(f"model: {len(tr):,} dzialek treningowych, {len(kol)} cech")
    return las, kol


def rysuj(g, cx, cy, prom, nr, podsum):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=(9.5, 10.2))
    fig.patch.set_facecolor(MW.TLO)
    ax.set_facecolor(MW.TLO)
    for _, r in g.iterrows():
        kol = BARWY.get(r.pred, SZARY)
        rz = r.pred == "rzepak ozimy"
        geoms = ([r.geometry] if r.geometry.geom_type == "Polygon"
                 else list(r.geometry.geoms))
        for gm in geoms:
            ax.fill(*gm.exterior.xy, facecolor=kol, edgecolor="#5a6862",
                    lw=1.1 if rz else .35, alpha=.95 if rz else .8, zorder=2)

    for p, st in ((1000, ":"), (3000, "--")):
        if p <= prom * 1.05:
            ax.add_patch(Circle((cx, cy), p, fill=False, ls=st, lw=1.4,
                                ec="#2c3a34", alpha=.65, zorder=4))
            ax.text(cx, cy + p, f" {p/1000:.0f} km", fontsize=9,
                    color="#2c3a34", ha="center", va="bottom", zorder=5,
                    bbox=dict(boxstyle="round,pad=.18", fc="white",
                              ec="none", alpha=.75))
    ax.plot(cx, cy, marker="o", ms=13, mfc="#1d6f42", mec="white", mew=2.2,
            zorder=6)

    # LEGENDA POD MAPA, NIE NA NIEJ.
    # W kadrze 3 km miesci sie ~9 tys. dzialek; legenda w rogu zaslaniala
    # ich znaczna czesc, a to wlasnie uklad pol jest tu trescia.
    # Kolejnosc wg powierzchni - czytelnik chce wiedziec, czego jest duzo.
    obecne = sorted([k for k in BARWY if (g.pred == k).any()],
                    key=lambda k: -podsum["ha"].get(k, 0))
    ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=10,
                              mfc=BARWY[k], mec="#5a6862",
                              label=f"{k} — {podsum['ha'].get(k, 0):,.0f} ha")
                       for k in obecne],
              loc="upper center", bbox_to_anchor=(.5, -.02), ncol=4,
              frameon=False, fontsize=9.5, handletextpad=.5,
              columnspacing=1.6)

    ax.set_xlim(cx - prom, cx + prom)
    ax.set_ylim(cy - prom, cy + prom)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Pola wokół miejsca nr {nr} — co rozpoznał model\n"
                 f"rzepak w promieniu {prom/1000:.0f} km: "
                 f"{podsum['ha'].get('rzepak ozimy', 0):,.0f} ha "
                 f"na {podsum['dzialek_rzepaku']} działkach",
                 fontsize=14, weight="bold", color=MW.ATRAMENT, pad=16)
    fig.text(.5, -.055,
             "działki ARiMR pokolorowane uprawą rozpoznaną z Sentinel-1+2 "
             "(głosowanie 3 pikseli na działkę, F1 rzepaku 0,910)\n"
             "granice działek z deklaracji 2025; klasyfikacja jest wynikiem "
             "modelu, nie odczytem deklaracji",
             ha="center", fontsize=9, color=MW.MUTED)

    MAPY.mkdir(exist_ok=True)
    out = MAPY / f"pola_wokol_{nr}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=MW.TLO)
    plt.close(fig)
    return out


if __name__ == "__main__":
    nr = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    prom = int(sys.argv[2]) if len(sys.argv) > 2 else 3000

    miejsca = json.loads((WYNIKI / "json" / "najlepsze_punkty.json")
                         .read_text(encoding="utf-8"))["miejsca"]
    m = next(x for x in miejsca if x["nr"] == nr)
    cx, cy = m["x_2180"], m["y_2180"]
    print(f"miejsce {nr}: {m['lat']:.4f} N {m['lon']:.4f} E, promien {prom} m")

    g = pyogrio.read_dataframe(SHP, encoding="utf-8",
                               bbox=(cx - prom, cy - prom, cx + prom, cy + prom))
    g = g[g.geometry.area >= 2000].copy()
    print(f"dzialek w kadrze: {len(g):,}")

    zapis = WYNIKI / "cache" / f"pola_wokol_{nr}_{prom}.csv"
    if zapis.exists():
        gl = pd.read_csv(zapis, index_col=0)["pred"]
        g["pred"] = g.index.map(gl).fillna("inne")
        print(f"klasyfikacja z cache: {zapis.name}")
        g["ha"] = g.geometry.area / 10_000
        ha = g.groupby("pred")["ha"].sum().to_dict()
        podsum = {"ha": ha,
                  "dzialek_rzepaku": int((g.pred == "rzepak ozimy").sum())}
        print("zapisano " + str(rysuj(g, cx, cy, prom, nr, podsum)))
        raise SystemExit

    K.start()
    rng = np.random.default_rng(ZIARNO)
    wiersze = []
    for idx, geom in zip(g.index, g.geometry):
        wn = geom.buffer(-8)
        wn = wn if not wn.is_empty else geom
        minx, miny, maxx, maxy = wn.bounds
        ile, prob = 0, 0
        while ile < PIKSELI and prob < 120:
            prob += 1
            p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
            if wn.contains(p):
                wiersze.append({"dz": idx, "x": p.x, "y": p.y})
                ile += 1
        if ile == 0:
            c = geom.representative_point()
            wiersze.append({"dz": idx, "x": c.x, "y": c.y})
    pk = pd.DataFrame(wiersze).reset_index(drop=True)
    pk["i"] = pk.index
    from pyproj import Transformer
    pk["lon"], pk["lat"] = Transformer.from_crs(2180, 4326, always_xy=True) \
        .transform(pk.x.values, pk.y.values)
    print(f"pikseli do sprawdzenia: {len(pk):,}")

    K.AOI = ee.Geometry.Rectangle(
        [pk.lon.min() - .05, pk.lat.min() - .05,
         pk.lon.max() + .05, pk.lat.max() + .05], "EPSG:4326", False)
    obraz, _ = cechy(ROK, z_radarem=True)
    las, kol = model()

    czesci = []
    for i in range(0, len(pk), 1000):
        pod = pk.iloc[i:i + 1000]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"i": int(r.i)})
            for r in pod.itertuples()])
        d = obraz.reduceRegions(fc, ee.Reducer.first(), 10).getInfo()
        czesci.append(pd.DataFrame([f["properties"] for f in d["features"]]))
        print(f"  {min(i+1000, len(pk)):,}/{len(pk):,}", flush=True)
    X = pd.concat(czesci, ignore_index=True).set_index("i").sort_index()

    pk = pk.join(X[[c for c in kol if c in X.columns]], on="i")
    pk = pk.dropna(subset=kol)
    pk["pred"] = las.predict(pk[kol])
    # GLOSOWANIE: dzialka dostaje uprawe, ktora model wskazal najczesciej
    gl = pk.groupby("dz")["pred"].agg(lambda s: s.value_counts().index[0])
    g["pred"] = g.index.map(gl).fillna("inne")
    gl.to_frame("pred").to_csv(zapis)

    g["ha"] = g.geometry.area / 10_000
    ha = g.groupby("pred")["ha"].sum().to_dict()
    podsum = {"ha": ha,
              "dzialek_rzepaku": int((g.pred == "rzepak ozimy").sum())}
    print("\nCO MODEL ROZPOZNAL W KADRZE")
    for k, v in sorted(ha.items(), key=lambda x: -x[1])[:8]:
        print(f"   {k:24s} {v:8,.0f} ha")

    out = rysuj(g, cx, cy, prom, nr, podsum)
    print(f"\nzapisano {out}")
