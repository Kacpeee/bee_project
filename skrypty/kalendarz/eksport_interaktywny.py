"""
ETAP 15b - eksport warstw modelu do interaktywnego kalendarza (HTML).

CO WYCHODZI
kalendarz.html w katalogu glownym: jedna strona, dziala bez serwera.
W srodku warstwy 1.2 km/px (12x zgrubienie - pola i tak sa rozmyte
jadrem 3 km):

  rzepak_gsa      tylko deklaracje 2025 i 2026
  rzepak_sat      detekcja Sentinel-2 2019-2025 (w tym 2025 z klasyfikatora,
                  nie z GSA)
  stale_gsa       pozostale uprawy per rok deklaracji (laki TUZ tylko tu)
  data_rzepak / data_sad   siatki terminow GDD (per rok + mediana)
  przecietny, niezawodnosc  gotowe rastry z sredni_rok.py
  maska, granica, miasta, paleta, okna kwitnienia

KALENDARZ SKLADA SIE W PRZEGLADARCE: strona liczy stos dekadowy z tych
warstw ta sama arytmetyka co wojewodztwo_kalendarz.py (rozklad
trojkatny, okno rzepaku z mediany NDYI od lokalnej daty GDD, sad przesuwany
wzgledem pelni literaturowej). To jest model wrzucony do strony.

Uruchomienie:
    python skrypty/kalendarz/eksport_interaktywny.py
"""

from __future__ import annotations

import base64
import json
import os
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import pandas as pd
import rasterio
from matplotlib.path import Path as MplPath
from scipy.interpolate import griddata
from scipy.signal import fftconvolve
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import mapa_wojewodztwa as MW
import potencjal_gsa as P
import wojewodztwo as W
from podzial_upraw import WEDRUJACE

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SZABLON = Path(__file__).with_name("szablon.html")
D = 12                       # zgrubienie: 100 m -> 1.2 km
LATA = list(range(2019, 2027))
LATA_DET = list(range(2019, 2025))
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def lowres(a: np.ndarray, ny2: int, nx2: int) -> np.ndarray:
    b = np.nan_to_num(a[:ny2 * D, :nx2 * D], nan=0.0).astype("float32")
    return b.reshape(ny2, D, nx2, D).mean(axis=(1, 3))


def u8(a: np.ndarray, skala: float) -> str:
    q = np.clip(np.nan_to_num(a) / max(skala, 1e-9) * 255, 0, 255).astype("uint8")
    return base64.b64encode(q.tobytes()).decode()


def raw(a: np.ndarray) -> str:
    q = np.clip(np.nan_to_num(a), 0, 255).astype("uint8")
    return base64.b64encode(q.tobytes()).decode()


def etykieta(doy: int) -> str:
    x = date(2025, 1, 1) + timedelta(days=int(doy) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


if __name__ == "__main__":
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        srednia, b, (ny, nx) = f.read(1), f.bounds, f.shape
    ny2, nx2 = ny // D, nx // D
    print(f"siatka {nx2} x {ny2} @ {D * 100} m")
    K = W.jadro()

    prog = json.loads((WYNIKI / "json" / "sredni_rok.json")
                      .read_text(encoding="utf-8"))["prog"]
    z25 = np.load(WYNIKI / "cache" / "woj_splot_2025.npz")
    z26 = np.load(WYNIKI / "cache" / "woj_splot_2026.npz")

    # --- ROLNICY: tylko deklaracje GSA 2025 i 2026
    rz_gsa = {}
    for rok, z in ((2025, z25), (2026, z26)):
        rz_gsa[rok] = lowres(z["rzepak ozimy"], ny2, nx2)
        print(f"  rolnicy rzepak {rok}: GSA")
    rz_gsa["sr"] = (rz_gsa[2025] + rz_gsa[2026]) / 2
    sk_gsa = float(max(r.max() for r in rz_gsa.values()))

    stale_gsa, meta_st = {}, {}
    for n in P.POZYTKI:
        if n == "rzepak ozimy":
            continue
        war = {}
        for rok, z in ((2025, z25), (2026, z26)):
            if n in z.files:
                war[rok] = lowres(z[n], ny2, nx2)
        if not war:
            continue
        if 2025 in war and 2026 in war:
            war["sr"] = (war[2025] + war[2026]) / 2
        else:
            war["sr"] = next(iter(war.values()))
        kg, s0, p0, k0 = P.POZYTKI[n][:4]
        sk = float(max(float(a.max()) for a in war.values()) or 1e-6)
        stale_gsa[n] = {str(k): u8(v, sk) for k, v in war.items()}
        meta_st[n] = {"kg": kg, "s0": s0, "p0": p0, "k0": k0, "skala": sk}

    # --- SATELITA: detekcja WIELOGATUNKOWA 2019-2025.
    #
    # Wczesniej byl tu wylacznie rzepak z jednogatunkowego klasyfikatora
    # (woj_prawd_*.npy), splatany stalym jadrem 3 km. Teraz warstwa idzie
    # z klasyfikatora wielogatunkowego (wielo_klasy_*.npz), po kalibracji
    # arealowej i z jadrami sezonowymi - tak samo jak reszta projektu.
    #
    # Gatunki: te z WEDRUJACE, czyli takie, dla ktorych detekcja BIJE
    # odniesienie "roslo tam, gdzie rok temu". Malina jest wykrywana, ale
    # to krzew wieloletni - pamiec dziala dla niej lepiej, wiec siedzi
    # w warstwie stalej, a nie tutaj.
    wsp_kal = json.loads((WYNIKI / "json" / "kalibracja_arealowa.json")
                         .read_text(encoding="utf-8"))["wspolczynniki"]
    gat_sat = [n for n in WEDRUJACE if n in P.POZYTKI]
    _jd = {}
    rz_sat, sez_sat, sat_gat = {}, {}, {n: {} for n in gat_sat}
    for rok in list(LATA_DET) + [2025]:
        f = WYNIKI / "cache" / f"wielo_klasy_{rok}.npz"
        with np.load(f) as z:
            brak = [n for n in gat_sat if n not in z.files]
            if brak:
                raise SystemExit(f"wielo_klasy_{rok}.npz bez klas: {brak}")
            suma = np.zeros((ny2, nx2), "float32")
            for n in gat_sat:
                u = z[n] * wsp_kal.get(n, 1.0)          # kalibracja arealowa
                s = lowres(fftconvolve(u, W.jadro_dla(n, _jd), "same"),
                           ny2, nx2)
                sat_gat[n][rok] = s
                suma += s * P.POZYTKI[n][0]
            sez_sat[rok] = suma
        # UWAGA: rz_sat trzyma POWIERZCHNIE rzepaku, nie cukier. Interfejs
        # mnozy ja przez D.rzepak_kg po swojej stronie, wiec wpisanie tu
        # sumy cukrow dawalo mnozenie przez wydajnosc DWA RAZY - legenda
        # pokazywala 549 t zamiast 6,7 t. Cukier calej warstwy idzie
        # osobno, w sez_sat.
        rz_sat[rok] = sat_gat["rzepak ozimy"][rok]
        print(f"  satelita {rok}: " + ", ".join(n.split()[0] for n in gat_sat))
    rz_sat["sr"] = np.mean([rz_sat[r] for r in rz_sat], axis=0)
    sez_sat["sr"] = np.mean([sez_sat[r] for r in sez_sat], axis=0)
    for n in gat_sat:
        sat_gat[n]["sr"] = np.mean(list(sat_gat[n].values()), axis=0)
    sk_sat = float(max(r.max() for r in rz_sat.values()) or 1e-6)
    sk_gat = {n: float(max(a.max() for a in sat_gat[n].values()) or 1e-6)
              for n in gat_sat}
    poj = json.loads((WYNIKI / "json" / "pojemnosc.json")
                     .read_text(encoding="utf-8"))

    # sezonowe sumy do zakładki "gdzie stawiać"
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        gsa25 = lowres(f.read(1) / 1000.0, ny2, nx2)
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_2026.tif") as f:
        gsa26 = lowres(f.read(1) / 1000.0, ny2, nx2)
    gsa_sr = (gsa25 + gsa26) / 2
    sat_sezon = sez_sat["sr"] / 1000.0

    # --- maska i granica
    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ny2, 0:nx2]
    px = b.left + (xx + .5) * 100 * D
    py = b.top - (yy + .5) * 100 * D
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(ny2, nx2)
    gr = poly.exterior.simplify(600)
    gx = [(float((x - b.left) / (100 * D)), float((b.top - y) / (100 * D)))
          for x, y in gr.coords]
    msta = []
    for n, pop, typ, c in miasta:
        if pop < 45_000:
            continue
        jj = (c[0] - b.left) / (100 * D)
        ii = (b.top - c[1]) / (100 * D)
        i, j = int(ii), int(jj)
        if 0 <= i < ny2 and 0 <= j < nx2 and maska[i, j]:
            msta.append({"n": n, "x": float(jj), "y": float(ii)})

    # --- siatki terminow z modelu GDD (per rok + mediana)
    kw = pd.read_csv(WYNIKI / "cache" / "kwitnienie_lata.csv")
    daty_rz, daty_sad = {}, {}
    for rok in LATA:
        g = kw[kw["rok"] == rok]
        pts = g[["x", "y"]].to_numpy()
        for kol, cel in (("doy_rzepak", daty_rz), ("doy_sad", daty_sad)):
            v = griddata(pts, g[kol].to_numpy(), (px, py), method="linear")
            v2 = griddata(pts, g[kol].to_numpy(), (px, py), method="nearest")
            v = np.where(np.isnan(v), v2, v)
            cel[rok] = v
    daty_rz["sr"] = np.median([daty_rz[r] for r in LATA], axis=0)
    daty_sad["sr"] = np.median([daty_sad[r] for r in LATA], axis=0)

    # NIEZAWODNOSC liczona z CALEJ warstwy wedrujacej (sez_sat: rzepak,
    # gryka, slonecznik wazone wydajnoscia), a nie z samego rzepaku.
    # Wczesniej szla z rz_sat, czyli z powierzchni rzepaku - a podpis mowil
    # o "warstwie wedrujacej". Mapa i jej opis musza dotyczyc tego samego.
    lata_sat = [r for r in sez_sat if r != "sr"]
    ile = np.zeros((ny2, nx2), "float32")
    for r in lata_sat:
        v = sez_sat[r]
        prg = np.percentile(v[maska], 80)
        ile += (v >= prg).astype("float32")

    def progi(a):
        v = a[maska]
        return [0.0] + [float(np.percentile(v, q)) for q in (60, 80, 92, 98)] + \
               [float(v.max())]

    def enc_lat(d, sk):
        return {str(k): u8(v, sk) for k, v in d.items()}

    sad = json.loads((WYNIKI / "json" / "fenologia_sadu.json")
                     .read_text(encoding="utf-8"))
    srj = json.loads((WYNIKI / "json" / "sredni_rok.json").read_text(encoding="utf-8"))
    sk_gsa_sez = float(max(gsa25.max(), gsa26.max(), 1e-6))
    sk_sat_sez = float(max(sat_sezon.max(), 1e-6))
    klucze_dat = [str(r) for r in LATA] + ["sr"]
    przed, po = P.ksztalt_rzepaku()
    dane = {
        "nx": nx2, "ny": ny2, "px_km": D * 0.1,
        # Przeliczenie piksel -> wspolrzedne geograficzne.
        # Strona operuje na pikselach w ukladzie 2180, a mikroserwis prognozy
        # przyjmuje WGS84. Interpolacja po czterech naroznikach dawala blad
        # do 800 m (uklad 2180 jest odwzorowaniem poprzecznym Merkatora, wiec
        # nie jest liniowy na 230 km). Eksportujemy siatke 9x9 i interpolujemy
        # w jej komorkach - blad spada do kilku metrow.
        "geo": (lambda T, K: {
            "n": K,
            "lat": [[float(T.transform(b.left + (jj / (K - 1)) * nx2 * 100 * D,
                                       b.top - (ii / (K - 1)) * ny2 * 100 * D)[1])
                     for jj in range(K)] for ii in range(K)],
            "lon": [[float(T.transform(b.left + (jj / (K - 1)) * nx2 * 100 * D,
                                       b.top - (ii / (K - 1)) * ny2 * 100 * D)[0])
                     for jj in range(K)] for ii in range(K)],
        })(__import__("pyproj").Transformer.from_crs(2180, 4326,
                                                     always_xy=True), 9),
        "dekady": P.DEKADY,
        "daty": {str(d): etykieta(d) for d in P.DEKADY},
        "rzepak_kg": P.POZYTKI["rzepak ozimy"][0],
        "rzepak_okno": [-przed, po],
        "sad_pelnia_lit": sad["pelnia_literaturowa"],
        "data_rzepak": {k: raw(daty_rz[int(k) if k != "sr" else "sr"])
                        for k in klucze_dat},
        "data_sad": {k: raw(daty_sad[int(k) if k != "sr" else "sr"])
                     for k in klucze_dat},
        "maska": raw(maska.astype("uint8")),
        "granica": gx, "miasta": msta,
        "walidacje": srj["walidacje"],
        "paleta": {"klasy": MW.KLASY, "tlo": MW.TLO,
                   "atrament": MW.ATRAMENT, "muted": MW.MUTED,
                   "niezawodnosc": ["#e7eee0", "#b7c9a4", "#6d8a54",
                                    "#3d5c30", "#1a2e14"]},
        "rolnicy": {
            "lata": [2025, 2026],
            "rzepak": enc_lat(rz_gsa, sk_gsa),
            "rzepak_skala": sk_gsa,
            "stale": stale_gsa,
            "stale_meta": meta_st,
            "sezon": {"2025": u8(gsa25, sk_gsa_sez),
                      "2026": u8(gsa26, sk_gsa_sez),
                      "sr": u8(gsa_sr, sk_gsa_sez)},
            "sezon_skala": sk_gsa_sez,
            "progi_sezon": progi(gsa_sr),
        },
        "satelita": {
            "lata": lata_sat,
            "rzepak": enc_lat(rz_sat, sk_sat),
            "rzepak_skala": sk_sat,
            "sezon": u8(sat_sezon, sk_sat_sez),
            "sezon_skala": sk_sat_sez,
            "progi_sezon": progi(sat_sezon),
            "niezawodnosc": raw(ile),
            "niezaw_lat": len(lata_sat),
            "gatunki": gat_sat,
            "gatunki_meta": {n: {"kg": P.POZYTKI[n][0], "s0": P.POZYTKI[n][1],
                                 "p0": P.POZYTKI[n][2], "k0": P.POZYTKI[n][3],
                                 "kalibracja": wsp_kal.get(n, 1.0),
                                 "skala": sk_gat[n]}
                             for n in gat_sat},
            # warstwy per gatunek - potrzebne zakladce "produkt koncowy",
            # ktora sklada detekcje (wedrujace) z deklaracjami (trwale)
            "warstwy": {n: u8(sat_gat[n]["sr"], sk_gat[n]) for n in gat_sat},
        },
        # PRODUKT KONCOWY - to, do czego caly projekt zmierza. Wczesniej
        # istnial wylacznie jako woj_koncowa_*.tif i liczby w logu, wiec
        # osoba otwierajaca strone widziala dwa polprodukty, a nie wynik.
        "koncowy": {
            # tylko rok typowy: warstwa satelitarna to srednia z 7 sezonow,
            # a deklaracje istnieja jedynie dla 2025 i 2026 - pokazywanie
            # pojedynczych lat mieszaloby dwie rozne dlugosci szeregu
            "lata": [],
            "wedrujace": gat_sat,
            "trwale": [n for n in stale_gsa if n not in gat_sat],
            "kg_cukrow_na_rodzine": poj["zapotrzebowanie_kg_cukrow"],
            "zastrzezenie": "przecietny rok z 7 sezonow - typowy uklad "
                            "sezonu, nie prognoza na konkretny rok",
        },
    }
    wyj_json = WYNIKI / "cache" / "kalendarz_dane.json"
    blob = json.dumps(dane, ensure_ascii=False, separators=(",", ":"))
    wyj_json.write_text(blob, encoding="utf-8")
    print(f"zapisano {wyj_json.name}: {wyj_json.stat().st_size / 1e6:.1f} MB, "
          f"rolnicy {len(stale_gsa)} gatunkow, satelita {len(lata_sat)} sezonow")

    html = SZABLON.read_text(encoding="utf-8").replace("%%DANE%%", blob)
    wyj_html = ROOT / "kalendarz.html"
    wyj_html.write_text(html, encoding="utf-8")
    print(f"zapisano {wyj_html.name}: {wyj_html.stat().st_size / 1e6:.1f} MB")
