"""
Warstwa rzepaku do interaktywnej mapy w mikroserwisie.

PO CO OSOBNA WARSTWA
Prognoza dotyczy kwitnienia RZEPAKU, wiec mapa, na ktorej uzytkownik
zaznacza obszar, tez musi pokazywac rzepak - nie ogolny potencjal
pozytkowy. Inaczej ktos zaznaczylby rejon czerwony od maliny i sadow,
dostal date kwitnienia rzepaku i uznal, ze tam warto jechac w maju,
choc rzepaku tam nie ma.

CO WYCHODZI
  mapy/warstwa_rzepak.png    heatmapa z przezroczystym tlem poza granica
  json/warstwa_rzepak.json   siatka 9x9 do przeliczania piksel <-> WGS84
                             oraz wartosci do odczytu ilosci rzepaku

Uruchomienie:
    python skrypty/serwis/warstwa_rzepak.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np                                            # noqa: E402
import rasterio                                               # noqa: E402
from PIL import Image, ImageDraw                              # noqa: E402
from pyproj import Transformer                                # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"
RASTER = WYNIKI / "rastry" / "woj_rzepak.tif"
ZGRUB = 3                 # 100 m -> 300 m; mapa 602 x 746 px, czytelna w oknie
SIATKA = 9                # gestosc siatki geo do interpolacji

# skala kolorow: od przezroczystego przez zolty po ciemna czerwien
PALETA = [
    (0.00, (255, 255, 255, 0)),
    (0.04, (255, 246, 222, 170)),
    (0.22, (254, 224, 160, 215)),
    (0.45, (252, 190, 100, 232)),
    (0.68, (244, 140, 62, 242)),
    (0.86, (214, 88, 44, 250)),
    (1.00, (150, 32, 24, 255)),
]


def koloruj(v: np.ndarray) -> np.ndarray:
    """Wartosci 0-1 na RGBA wg PALETA, liniowo miedzy punktami."""
    out = np.zeros(v.shape + (4,), "uint8")
    for (a, ca), (b, cb) in zip(PALETA[:-1], PALETA[1:]):
        m = (v >= a) & (v < b) if b < 1.0 else (v >= a)
        if not m.any():
            continue
        f = ((v[m] - a) / (b - a))[:, None]
        out[m] = (np.array(ca) * (1 - f) + np.array(cb) * f).astype("uint8")
    return out


if __name__ == "__main__":
    with rasterio.open(RASTER) as f:
        a = f.read(1).astype("float64")
        T = f.transform
    waz = np.isfinite(a) & (a > 0)
    print(f"raster {a.shape}, pikseli z danymi {waz.sum():,}")

    # zgrubienie przez srednia w blokach - zachowuje sumy, nie tylko wyglad
    ny, nx = (a.shape[0] // ZGRUB) * ZGRUB, (a.shape[1] // ZGRUB) * ZGRUB
    b = np.where(waz, a, np.nan)[:ny, :nx]
    m = b.reshape(ny // ZGRUB, ZGRUB, nx // ZGRUB, ZGRUB)
    with np.errstate(invalid="ignore"):
        mal = np.nanmean(m, axis=(1, 3))
    print(f"po zgrubieniu {ZGRUB}x: {mal.shape}")

    # SKALA PIERWIASTKOWA, nie liniowa.
    # Rozklad jest silnie skosny: mediana 410, percentyl 99 to 13 282,
    # maksimum 40 232. Przy skali liniowej 60% pikseli ladowalo w dolnych
    # kilku procentach palety i mapa wygladala na ziarnista - widac bylo
    # tylko punktowe maksima, a caly srodek rozkladu zlewal sie z tlem.
    # Pierwiastek rozciaga dolna czesc zakresu, wiec widac strukture
    # zageszczen, a nie same szczyty.
    # Wykladnik 0.5 z gora na p97 przesadzal w druga strone - cala mapa
    # robila sie ciemnoczerwona. 0.7 z gora na p995 rozciaga dol zakresu,
    # ale zostawia gore dla realnych zageszczen.
    gora = float(np.nanpercentile(mal, 99.5))
    v = np.clip(np.nan_to_num(mal) / gora, 0, 1) ** 0.7
    v[~np.isfinite(mal)] = 0.0
    rgba = koloruj(v)
    rgba[~np.isfinite(mal)] = (0, 0, 0, 0)

    # TLO I OBRYS WOJEWODZTWA.
    # Bez nich mapa jest nieczytelna: obszary bez rzepaku wygladaja jak dziury,
    # a bez granicy nie wiadomo, gdzie sie jest. Wnetrze dostaje bardzo jasny
    # wypelniacz, zeby bylo widac zasieg danych.
    import sys as _s
    _s.path.insert(0, str(ROOT / "skrypty" / "potencjal"))
    import mapa_wojewodztwa as MW
    from matplotlib.path import Path as MplPath
    from shapely.geometry import MultiLineString
    from shapely.ops import polygonize, unary_union

    _, _, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    H2, W2 = mal.shape
    yy, xx = np.mgrid[0:H2, 0:W2]
    px = T.c + (xx + .5) * 100 * ZGRUB
    py = T.f - (yy + .5) * 100 * ZGRUB
    w_woj = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([px.ravel(), py.ravel()])).reshape(H2, W2)

    puste = w_woj & (rgba[..., 3] == 0)
    rgba[puste] = (246, 248, 247, 235)          # jasne tlo wewnatrz granicy
    rgba[~w_woj] = (0, 0, 0, 0)                 # poza granica nic

    im = Image.fromarray(rgba, "RGBA")
    rys = ImageDraw.Draw(im)
    kontur = [((x - T.c) / (100 * ZGRUB), (T.f - y) / (100 * ZGRUB))
              for x, y in poly.exterior.simplify(400).coords]
    rys.line(kontur + [kontur[0]], fill=(90, 104, 98, 255), width=2)

    # MIASTA - bez nich mapa jest nieczytelna, bo nie wiadomo, gdzie sie jest.
    _, miasta, _ = MW.podklad()
    try:
        from PIL import ImageFont
        czcionka = ImageFont.truetype("segoeui.ttf", 12)
    except Exception:
        czcionka = None
    for nazwa, pop, typ, c in miasta:
        if pop < 60_000:
            continue
        mx = (c[0] - T.c) / (100 * ZGRUB)
        my = (T.f - c[1]) / (100 * ZGRUB)
        if not (0 <= mx < W2 and 0 <= my < H2) or not w_woj[int(my), int(mx)]:
            continue
        rys.ellipse([mx - 3, my - 3, mx + 3, my + 3],
                    fill=(255, 255, 255, 235), outline=(40, 48, 44, 255))
        # napis z biala obwodka, zeby byl czytelny na kazdym tle
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rys.text((mx + 7 + dx, my - 7 + dy), nazwa,
                     fill=(255, 255, 255, 220), font=czcionka)
        rys.text((mx + 7, my - 7), nazwa, fill=(30, 38, 34, 255), font=czcionka)

    MAPY.mkdir(exist_ok=True)
    im.save(MAPY / "warstwa_rzepak.png")
    print(f"zapisano warstwa_rzepak.png  ({rgba.shape[1]} x {rgba.shape[0]} px)")

    # siatka geo do przeliczania piksel <-> wspolrzedne po stronie przegladarki
    do4326 = Transformer.from_crs(2180, 4326, always_xy=True)
    H, W = mal.shape
    lat = [[0.0] * SIATKA for _ in range(SIATKA)]
    lon = [[0.0] * SIATKA for _ in range(SIATKA)]
    for i in range(SIATKA):
        for j in range(SIATKA):
            px = j / (SIATKA - 1) * W * ZGRUB
            py = i / (SIATKA - 1) * H * ZGRUB
            x, y = T * (px, py)
            lo, la = do4326.transform(x, y)
            lat[i][j], lon[i][j] = float(la), float(lo)

    (WYNIKI / "json" / "warstwa_rzepak.json").write_text(json.dumps({
        "zrodlo": "woj_rzepak.tif - rzepak po splocie jadrem zasiegu lotu",
        "szerokosc_px": W, "wysokosc_px": H,
        "zgrubienie": ZGRUB, "piksel_m": 100 * ZGRUB,
        "skala_gora": gora,
        "geo": {"n": SIATKA, "lat": lat, "lon": lon},
        "uwaga": "warstwa pokazuje RZEPAK, nie ogolny potencjal - prognoza "
                 "dotyczy kwitnienia rzepaku, wiec wybor miejsca musi opierac "
                 "sie na tym samym gatunku",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano json/warstwa_rzepak.json")
