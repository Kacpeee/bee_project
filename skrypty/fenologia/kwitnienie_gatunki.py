"""
ETAP 37 - pomiar kwitnienia POZOSTALYCH gatunkow, nie tylko rzepaku.

ASYMETRIA, KTORA TO ADRESUJE
Model GDD jest kalibrowany POMIAROWO wylacznie dla rzepaku (baza i prog
dobrane na 45 obserwacjach z krzywych NDYI, blad 3.2 dnia w walidacji
krzyzowej). Pozostale gatunki maja model KOTWICZONY: baza z literatury,
a prog dobrany tak, zeby mediana wieloletnia trafiala w tabelaryczna date
kwitnienia. Mediana jest wiec poprawna z definicji, ale AMPLITUDA wahan
miedzyrocznych pozostaje zalozeniem - sprawdzona tylko dla lipy (2.8 d)
i robinii (-1 d) wobec obserwacji IMGW.

CO DA SIE ZMIERZYC, A CZEGO NIE
NDYI = (zielony - niebieski)/(zielony + niebieski) wykrywa ZOLC, wiec dziala
dla gatunkow o zoltych kwiatach i zwartym lanie. Dla kwiatow bialych
mierzymy JASNOSC (zielony + czerwony), bo biale platki podnosza odbicie
w calym zakresie widzialnym - sygnal slabszy, ale warto sprawdzic, czy
w ogole istnieje.

OGRANICZENIE ZRODLA
Deklaracje ARiMR istnieja tylko dla 2025 i 2026, wiec bez klasyfikatora
mamy DWA sezony na gatunek. To za malo, zeby skalibrowac model GDD
(potrzeba rozpietosci termicznej wielu lat), ale wystarczy, zeby SPRAWDZIC,
czy kotwiczony model trafia w zmierzona date.

To jest wiec WALIDACJA modeli kotwiczonych, nie ich kalibracja.

Uruchomienie:
    python skrypty/fenologia/kwitnienie_gatunki.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import ee
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skrypty" / "potencjal"))

WYNIKI = ROOT / "wyniki"
SKALA = 60
MAX_CHMUR = 40
MIN_DAT = 5
MIN_POKRYCIE = 0.05
# GEE odbija zapytania interaktywne przy zbyt zlozonej geometrii
# ("Too many concurrent aggregations"). 40 polaczonych wielokatow razy
# kilkadziesiat scen przekraczalo limit. Bierzemy mniej dzialek, upraszczamy
# ich obrys i redukujemy w jednym przebiegu po kolekcji zamiast per obraz.
# Redukcja po WIELOKATACH przekraczala najpierw limit rownoleglych agregacji,
# a po uproszczeniu - limit pamieci. Przechodzimy wiec na PROBKOWANIE
# PUNKTOWE: losujemy punkty wewnatrz dzialek i usredniamy po nich. Tak samo
# robi reszta projektu (wielo_punkty.csv), a koszt jest o rzad nizszy, bo
# GEE czyta pojedyncze piksele zamiast calych poligonow.
ILE_DZIALEK = 60          # z ilu dzialek losujemy punkty
ILE_PUNKTOW = 150         # tyle punktow na gatunek i sezon
MARGINES_M = -20          # wciecie do srodka dzialki, zeby uniknac brzegow

# gatunek -> (indeks sygnalu, opis kwiatu)
GATUNKI = {
    "rzepak ozimy":    ("NDYI", "zolty, zwarty lan"),
    "gorczyca biala":  ("NDYI", "zolty"),
    "gorczyca":        ("NDYI", "zolty"),
    "slonecznik":      ("NDYI", "zolty, duze koszyczki"),
    "rzepak jary":     ("NDYI", "zolty"),
    "gryka zwyczajna": ("JASN", "bialo-rozowy"),
    "malina":          ("JASN", "bialy, drobny"),
    "porzeczka":       ("JASN", "zielonkawy, niepozorny"),
}
# nazwy w shapefile maja polskie znaki - mapowanie na klucze POZYTKI
NAZWY = {
    "gorczyca biala": "gorczyca biała",
    "slonecznik": "słonecznik",
}
LATA = (2025, 2026)
SHP = {
    2025: ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp",
    2026: ROOT / "dane" / "gsa_lubelskie_2026" / "2026_uprawy_woj_06_akt_public.shp",
}


def dz(doy) -> str:
    x = date(2025, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day:02d}.{x.month:02d}"


def mmdd(doy) -> str:
    x = date(2025, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.month:02d}-{x.day:02d}"


def losuj_punkty(wieloklaty, ile, rng):
    """Punkty losowane wewnatrz dzialek, proporcjonalnie do powierzchni."""
    from shapely.geometry import Point
    pow_ = np.array([q.area for q in wieloklaty], float)
    udzial = pow_ / pow_.sum()
    out = []
    for i, q in enumerate(wieloklaty):
        n = max(1, int(round(ile * udzial[i])))
        x0, y0, x1, y1 = q.bounds
        prob = 0
        while n > 0 and prob < 200:
            p = Point(rng.uniform(x0, x1), rng.uniform(y0, y1))
            prob += 1
            if q.contains(p):
                out.append(p)
                n -= 1
                prob = 0
    return out[:ile]


def przygotuj(img: ee.Image) -> ee.Image:
    s = img.divide(10000)
    ndyi = s.normalizedDifference(["B3", "B2"]).rename("NDYI")
    jasn = s.select("B3").add(s.select("B4")).rename("JASN")
    czyste = img.select("SCL").remap([4, 5, 6, 7], [1, 1, 1, 1], 0)
    doy = ee.Date(img.get("system:time_start")).getRelative("day", "year").add(1)
    return img.addBands([ndyi, jasn]).updateMask(czyste).set("doy", doy)


def krzywa(rok: int, geom: ee.Geometry, indeks: str,
           od: str, do: str, tlo_geom: ee.Geometry) -> list[dict]:
    """Krzywa NADWYZKI indeksu nad tlem gruntow ornych z tej samej sceny.

    NORMALIZACJA SCENY JEST KONIECZNA, nie kosmetyczna. Pierwsza wersja
    liczyla surowa srednia i dawala dla rzepaku blad 9.5 dnia, choc jego
    model ma 3.2 - czyli mierzyla zmiennosc atmosferyczna, nie kwitnienie.
    Odejmujac mediane gruntow ornych z TEJ SAMEJ sceny usuwamy wplyw
    oswietlenia, aerozolu i kata patrzenia, ktory zmienia sie miedzy
    przelotami bardziej niz sam sygnal kwiatow.
    """
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(geom).filterDate(f"{rok}-{od}", f"{rok}-{do}")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
           .map(przygotuj))

    # Jedna redukcja na obraz, z maska wliczona w srednia - zamiast dwoch
    # osobnych reduceRegion. Polowa zapytan, ten sam wynik: pokrycie liczymy
    # z liczby wazychnych pikseli zwracanej przez ten sam reduktor.
    orne = (ee.ImageCollection("ESA/WorldCover/v200").first()
            .select("Map").eq(40))          # 40 = grunty orne

    def stat(img: ee.Image) -> ee.Feature:
        r = img.select(indeks).reduceRegion(
            ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
            geom, SKALA, maxPixels=1e8, bestEffort=True)
        tlo = img.select(indeks).updateMask(orne).reduceRegion(
            ee.Reducer.median(), tlo_geom, 300, maxPixels=1e8, bestEffort=True)
        return ee.Feature(None, {"doy": img.get("doy"),
                                 "v": r.get(indeks + "_mean"),
                                 "tlo": tlo.get(indeks),
                                 "n": r.get(indeks + "_count")})

    w = [f["properties"] for f in
         ee.FeatureCollection(col.map(stat)).getInfo()["features"]]
    maks = max((x.get("n") or 0) for x in w) if w else 0
    for x in w:
        x["pok"] = (x.get("n") or 0) / maks if maks else 0
        if x.get("v") is not None and x.get("tlo") is not None:
            x["v"] = x["v"] - x["tlo"]          # NADWYZKA nad tlem sceny
    return [x for x in w if x.get("v") is not None and x.get("tlo") is not None
            and (x.get("pok") or 0) > MIN_POKRYCIE]


def szczyt(w: list[dict]):
    """Wierzcholek paraboli przez trzy najwyzsze sasiadujace punkty.

    Bez tego argmax po kilkunastu scenach kwantyzuje wynik do dat przelotow.
    """
    scal = {}
    for v in w:
        scal.setdefault(int(v["doy"]), []).append(v["v"])
    p = [(k, sum(x) / len(x)) for k, x in sorted(scal.items())]
    if len(p) < MIN_DAT:
        return None, None, len(p)
    y = [v for _, v in p]
    i = int(np.argmax(y))
    if i == 0 or i == len(y) - 1:
        return float(p[i][0]), float(y[i]), len(p)
    (x1, y1), (x2, y2), (x3, y3) = p[i - 1], p[i], p[i + 1]
    d1, d2, d3 = (x1-x2)*(x1-x3), (x2-x1)*(x2-x3), (x3-x1)*(x3-x2)
    a = y1/d1 + y2/d2 + y3/d3
    b = -y1*(x2+x3)/d1 - y2*(x1+x3)/d2 - y3*(x1+x2)/d3
    if a >= 0:
        return float(x2), float(y2), len(p)
    v = -b / (2 * a)
    return (float(v) if x1 <= v <= x3 else float(x2)), float(y2), len(p)


if __name__ == "__main__":
    import pyogrio
    from shapely.geometry import mapping
    from shapely.ops import unary_union
    import potencjal_gsa as P

    rng = np.random.default_rng(42)
    ee.Initialize(project=(ROOT / ".ee_projekt").read_text().strip())
    fen = json.loads((WYNIKI / "json" / "fenologia_wszystkie.json")
                     .read_text(encoding="utf-8"))["gatunki"]

    print(f"{'gatunek':22s}{'rok':>6}{'scen':>6}{'zmierzone':>11}"
          f"{'model':>9}{'roznica':>10}")
    wyniki = {}
    for klucz, (indeks, opis) in GATUNKI.items():
        nazwa = NAZWY.get(klucz, klucz)
        if nazwa not in P.POZYTKI:
            continue
        s0, p0, k0 = P.POZYTKI[nazwa][1:4]
        od, do = mmdd(max(s0 - 25, 61)), mmdd(min(k0 + 25, 250))
        wyniki[nazwa] = {"indeks": indeks, "kwiat": opis,
                         "okno_modelu": [s0, p0, k0], "lata": {}}
        for rok in LATA:
            g = pyogrio.read_dataframe(SHP[rok], encoding="utf-8",
                                       where=f"roslina = '{nazwa}'")
            if len(g) < 5:
                print(f"{nazwa[:20]:22s}{rok:>6}   za malo dzialek ({len(g)})")
                continue
            naj = g.assign(_a=g.geometry.area).nlargest(ILE_DZIALEK, "_a")
            wnetrza = [q for q in naj.geometry.buffer(MARGINES_M)
                       if not q.is_empty]
            if not wnetrza:
                print(f"{nazwa[:20]:22s}{rok:>6}   dzialki za male po wcieciu")
                continue
            pkt = losuj_punkty(wnetrza, ILE_PUNKTOW, rng)
            if len(pkt) < 20:
                print(f"{nazwa[:20]:22s}{rok:>6}   za malo punktow ({len(pkt)})")
                continue
            import geopandas as gpd
            gs = gpd.GeoSeries(pkt, crs=naj.crs).to_crs(4326)
            geom = ee.Geometry.MultiPoint([[q.x, q.y] for q in gs])
            tlo_geom = geom.bounds().buffer(5000)   # okoliczne grunty orne
            try:
                w = krzywa(rok, geom, indeks, od, do, tlo_geom)
                d_zm, wart, n = szczyt(w)
            except Exception as e:
                print(f"{nazwa[:20]:22s}{rok:>6}   blad GEE: {str(e)[:44]}")
                continue
            d_mod = fen.get(nazwa, {}).get("daty", {}).get(str(rok))
            if d_zm is None:
                print(f"{nazwa[:20]:22s}{rok:>6}{n:>6}   za malo scen")
                continue
            roz = (d_zm - d_mod) if d_mod else None
            wyniki[nazwa]["lata"][rok] = {
                "zmierzone_doy": d_zm, "model_doy": d_mod,
                "roznica_d": roz, "scen": n, "dzialek": len(naj)}
            print(f"{nazwa[:20]:22s}{rok:>6}{n:>6}{dz(d_zm):>11}"
                  f"{(dz(d_mod) if d_mod else '—'):>9}"
                  f"{(f'{roz:+.0f} d' if roz is not None else '—'):>10}")

    # podsumowanie: gdzie kotwica trafia, a gdzie nie
    print("\nPODSUMOWANIE")
    for nazwa, v in wyniki.items():
        r = [x["roznica_d"] for x in v["lata"].values()
             if x["roznica_d"] is not None]
        if not r:
            print(f"  {nazwa[:22]:24s} brak pomiaru "
                  f"({v['indeks']}, {v['kwiat']})")
            continue
        sr = float(np.mean(np.abs(r)))
        ocena = "zgodne" if sr <= 7 else ("rozbieznosc" if sr <= 15 else "ZLE")
        print(f"  {nazwa[:22]:24s} sredni blad bezwzgledny {sr:5.1f} d  "
              f"({len(r)} sezon(y))  {ocena}")

    (WYNIKI / "json" / "kwitnienie_gatunki.json").write_text(json.dumps({
        "cel": "walidacja kotwiczonych modeli fenologicznych pomiarem "
               "z Sentinel-2 na dzialkach deklarowanych",
        "ograniczenie": "deklaracje tylko 2025 i 2026, wiec to walidacja "
                        "punktowa, nie kalibracja modelu GDD",
        "indeksy": {"NDYI": "(zielony-niebieski)/(zielony+niebieski) - zolc",
                    "JASN": "zielony + czerwony - jasnosc, dla bialych kwiatow"},
        "gatunki": wyniki,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/kwitnienie_gatunki.json")
