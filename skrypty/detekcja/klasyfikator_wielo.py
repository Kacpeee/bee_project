"""
ETAP 16 - klasyfikator WIELOKLASOWY: ktore pozytki da sie wykryc z orbity.

PYTANIE, NA KTORE TO ODPOWIADA
Model rzepakowy dziala (F1 0.90), fasola padla (F1 0.69). Nie wiadomo, czy
reszta pozytkow jest wykrywalna - a od tego zalezy, czy mapa teledetekcyjna
moze byc czyms wiecej niz rzepakiem plus lakami (75% cukru).

Zamiast zgadywac: jeden model na wszystkie klasy naraz i MACIERZ POMYLEK.
Wynikiem jest F1 osobno dla kazdego gatunku oraz informacja, z czym
konkretnie sie myli. Wynik negatywny jest tu tak samo wartosciowy jak
pozytywny - dokumentuje granice metody zamiast jej zakladac.

DWIE ZMIANY WZGLEDEM MODELU RZEPAKOWEGO

1. SZEREG ZAMIAST OKIEN POD RZEPAK.
   Osiem okien (jesien / marzec / kwitnienie / czerwiec) bylo zaprojektowane
   pod fenologie rzepaku. Dla fasoli sadzonej w maju jesienne i marcowe okno
   to gola gleba, czyli polowa cech byla szumem - to wspolwina tamtej porazki.
   Tu: regularne kompozyty polmiesieczne przez caly sezon (IX -> IX), po
   NDVI i NDYI. Model sam znajduje, co odroznia gatunki:
     rzepak    - zielony jesienia, zolty w maju, schnie w czerwcu
     gryka     - gola gleba do VI, zieleń i kwitnienie w VII
     lucerna   - pila: 3-4 pokosy w sezonie
     sad/malina- NIGDY nie ma golej gleby, zielone jesienia i wiosna
     slonecznik- rusza najpozniej i najpozniej schnie

2. BEZ MASKI GRUNTOW ORNYCH.
   orne_maska() to WorldCover kl. 40; sady, maliny i laki w niej nie leza,
   wiec maskowanie wycielo by wlasnie te klasy, ktore chcemy zbadac. Mediana
   sceny (odniesienie anomalii) nadal liczona jest po gruntach ornych - to
   tylko punkt odniesienia atmosferycznego, nie filtr.

WALIDACJA
Bloki przestrzenne 2.5 km rozlaczne miedzy treningiem a testem. Podzial
losowy po pikselach dalby falszywie wysokie wyniki, bo sasiednie piksele tej
samej dzialki trafialyby po obu stronach.

Uruchomienie:
    python skrypty/detekcja/klasyfikator_wielo.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import ee
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import gee_klasyfikator_rzepaku as K
import potencjal_gsa as P

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

ROK = 2025
BUFOR_UJEMNY = -10
BLOK_M = 2500
UDZIAL_TESTU = 0.3
NA_KLASE = 1400          # limit: proba idzie do GEE inline (limit 10 MB)
NA_KLASE_INNE = 2500     # klasa "inne" szersza - to ona ma lapac falszywki
LICZBA_DRZEW = 300
ZIARNO = 42
CACHE = WYNIKI / "cache" / "wielo_punkty.csv"
CACHE_CECH = WYNIKI / "cache" / "wielo_cechy.csv"

# gatunki pozytkowe (te same co w modelu potencjalu) + klasa zbiorcza "inne"
KLASY = [n for n in P.POZYTKI]
INNE = "inne"


def probka(shp: Path | None = None, cache: Path | None = None) -> pd.DataFrame:
    """Probka dzialek z CALEGO wojewodztwa, po rowno na klase."""
    shp = SHP if shp is None else shp
    cache = CACHE if cache is None else cache
    if cache.exists():
        df = pd.read_csv(cache)
        print(f"punkty z cache: {len(df):,}  ({cache.name})")
        return df

    # najczestsze uprawy NIEpozytkowe jako klasa "inne" - to one sa realnymi
    # zrodlami pomylek (zboza, kukurydza, okopowe)
    nazwy = pyogrio.read_dataframe(shp, columns=["roslina"],
                                   read_geometry=False, encoding="utf-8")
    licz = nazwy["roslina"].value_counts()
    inne_nazwy = [n for n in licz.index if n not in P.POZYTKI][:12]
    print(f"klasa 'inne' zlozona z: {', '.join(x[:18] for x in inne_nazwy[:6])}...")

    tr = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    czesci = []
    for kod, (etyk, lista, limit) in enumerate(
            [(n, [n], NA_KLASE) for n in KLASY] +
            [(INNE, inne_nazwy, NA_KLASE_INNE)]):
        lst = ", ".join("'" + n.replace("'", "''") + "'" for n in lista)
        g = pyogrio.read_dataframe(shp, encoding="utf-8",
                                   where=f"roslina IN ({lst})")
        if g.empty:
            print(f"  {etyk[:24]:26s} BRAK")
            continue
        # zwezenie o 10 m: piksel ma lezec we wnetrzu dzialki, nie na miedzy
        wn = g.geometry.buffer(BUFOR_UJEMNY)
        g = g.loc[~wn.is_empty].copy()
        g["geometry"] = wn[~wn.is_empty]
        if g.empty:
            print(f"  {etyk[:24]:26s} same waskie dzialki")
            continue
        sr = g.geometry.representative_point()
        g["x"], g["y"] = sr.x.values, sr.y.values
        # bloki przestrzenne wyznaczane PRZED losowaniem
        bx = np.floor(g["x"] / BLOK_M).astype(int)
        by = np.floor(g["y"] / BLOK_M).astype(int)
        g["test"] = (((bx + by) % 10) < UDZIAL_TESTU * 10).astype(int)
        wyb = g.sample(n=min(limit, len(g)), random_state=ZIARNO)
        wyb = wyb.assign(klasa=kod, etykieta=etyk)
        czesci.append(wyb[["x", "y", "klasa", "etykieta", "test"]])
        print(f"  {etyk[:24]:26s} {len(wyb):6,} z {len(g):8,} dzialek "
              f"(test {wyb['test'].sum():5,})")

    df = pd.concat(czesci, ignore_index=True)
    df["lon"], df["lat"] = tr.transform(df["x"].values, df["y"].values)
    df.to_csv(cache, index=False)
    return df


def kolekcja(rok: int) -> ee.ImageCollection:
    """Jak K.kolekcja_anomalii, ale sezon wydluzony do konca wrzesnia -
    slonecznik i gryka konczą sie duzo pozniej niz rzepak."""
    orne = K.orne_maska()
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(K.AOI)
           .filterDate(f"{rok - 1}-09-01", f"{rok}-09-30")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", K.MAX_CHMUR))
           .map(K.przygotuj))

    def anom(img: ee.Image) -> ee.Image:
        med = (img.select(["NDYI", "NDVI"]).updateMask(orne)
               .reduceRegion(ee.Reducer.median(), K.AOI, 500,
                             maxPixels=1e9, bestEffort=True))
        my = ee.Number(ee.Algorithms.If(med.get("NDYI"), med.get("NDYI"), 0))
        mv = ee.Number(ee.Algorithms.If(med.get("NDVI"), med.get("NDVI"), 0))
        return img.addBands([
            img.select("NDYI").subtract(my).rename("NDYI_A").toFloat(),
            img.select("NDVI").subtract(mv).rename("NDVI_A").toFloat(),
        ])

    return col.map(anom)


def cechy_szereg(rok: int) -> tuple[ee.Image, list[str]]:
    """Kompozyty polmiesieczne przez caly sezon, NDVI i NDYI."""
    col = kolekcja(rok)
    okna = []
    for m in range(9, 22):                       # IX poprz. roku -> IX biez.
        r, mm = (rok - 1, m) if m <= 12 else (rok, m - 12)
        okna += [(f"{r}-{mm:02d}-01", f"{r}-{mm:02d}-16"),
                 (f"{r}-{mm:02d}-16",
                  f"{r + (mm == 12)}-{(mm % 12) + 1:02d}-01")]
    pasma, nazwy = [], []
    for i, (od, do) in enumerate(okna):
        okno = col.filterDate(od, do)
        for ind in ("NDVI_A", "NDYI_A"):
            n = f"{ind[:4].lower()}_{i:02d}"
            # puste okno (zima / przyszlosc) nie ma pasm - unmask wtedy wali
            img = ee.Image(ee.Algorithms.If(
                okno.size().gt(0),
                okno.select(ind).mean().unmask(0).rename(n).toFloat(),
                ee.Image.constant(0).rename(n).toFloat()))
            pasma.append(img)
            nazwy.append(n)
    return ee.Image.cat(pasma), nazwy


def pobierz_cechy(obraz: ee.Image, nazwy: list[str], df: pd.DataFrame,
                  krok: int = 1200, cache: Path | None = None) -> pd.DataFrame:
    """Cechy w punktach, partiami - jedno zapytanie na wszystko przekracza
    limit czasu. Wynik cache'owany, bo to najdrozszy krok. Partie sa
    zapisywane po drodze, zeby zerwanie nie kasowalo godziny liczenia."""
    cache = CACHE_CECH if cache is None else cache
    if cache.exists():
        X = pd.read_csv(cache).set_index("i")
        print(f"cechy z cache: {X.shape}  ({cache.name})")
        return X
    czesci_dir = cache.parent / (cache.stem + "_czesci")
    czesci_dir.mkdir(parents=True, exist_ok=True)
    czesci = []
    for i in range(0, len(df), krok):
        part = czesci_dir / f"{i:06d}.csv"
        if part.exists():
            czesci.append(pd.read_csv(part))
            print(f"  cechy {min(i + krok, len(df)):6,}/{len(df):,}  (cache)")
            continue
        pod = df.iloc[i:i + krok]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"i": int(r.Index)})
            for r in pod.itertuples()])
        pr = obraz.sampleRegions(collection=fc, scale=10, geometries=False,
                                 tileScale=8)
        for prob in range(4):
            try:
                d = pr.getInfo()
                break
            except Exception as e:
                if prob == 3:
                    raise
                print(f"    ponawiam ({str(e)[:40]})")
                time.sleep(20 * (prob + 1))
        kawa = pd.DataFrame([f["properties"] for f in d["features"]])
        kawa.to_csv(part, index=False)
        czesci.append(kawa)
        print(f"  cechy {min(i + krok, len(df)):6,}/{len(df):,}")
    X = pd.concat(czesci, ignore_index=True).set_index("i").sort_index()
    X.to_csv(cache, index_label="i")
    return X


if __name__ == "__main__":
    K.start()
    print(f"Probka z calego wojewodztwa, {len(KLASY)} klas pozytkowych + inne:")
    df = probka()

    K.AOI = ee.Geometry.Rectangle(
        [pd.to_numeric(df.lon).min() - .1, pd.to_numeric(df.lat).min() - .1,
         pd.to_numeric(df.lon).max() + .1, pd.to_numeric(df.lat).max() + .1],
        "EPSG:4326", False)
    obraz, nazwy = cechy_szereg(ROK)
    print(f"\ncech: {len(nazwy)} (kompozyty polmiesieczne IX->IX, NDVI + NDYI)")

    # Cechy ciagniemy PARTIAMI i uczymy lokalnie. Trening po stronie GEE
    # (52 cechy x 20 tys. punktow x 300 drzew) przekracza limit czasu
    # zapytania interaktywnego; poza tym majac cechy na dysku mozna iterowac
    # po modelu bez ponownego liczenia w chmurze.
    X = pobierz_cechy(obraz, nazwy, df)
    dane = df.reset_index(drop=True).join(X)
    dane = dane.dropna(subset=nazwy)
    print(f"\npunktow z kompletnymi cechami: {len(dane):,}")

    tr = dane[dane["test"] == 0]
    te = dane[dane["test"] == 1]
    las = RandomForestClassifier(n_estimators=LICZBA_DRZEW, n_jobs=-1,
                                 random_state=ZIARNO, class_weight=None)
    las.fit(tr[nazwy], tr["klasa"])
    pred = las.predict(te[nazwy])
    etyk = (dane.drop_duplicates("klasa").sort_values("klasa")["etykieta"]
            .tolist())
    kody = sorted(dane["klasa"].unique())
    m = confusion_matrix(te["klasa"], pred, labels=kody).astype(float)

    print(f"\n{'gatunek':26s}{'n':>7}{'precyzja':>10}{'czulosc':>9}"
          f"{'F1':>7}  najczestsza pomylka")
    wynik = {}
    for i, nazwa in enumerate(etyk):
        if i >= m.shape[0]:
            break
        tp = m[i, i]
        n = m[i].sum()
        prec = tp / max(m[:, i].sum(), 1e-9)
        czul = tp / max(n, 1e-9)
        f1 = 2 * prec * czul / max(prec + czul, 1e-9)
        poza = [(m[i, j], etyk[j]) for j in range(m.shape[1])
                if j != i and j < len(etyk)]
        gl = max(poza)[1] if poza and max(poza)[0] > 0 else "-"
        udz = max(poza)[0] / max(n, 1) if poza else 0
        wynik[nazwa] = {"n": int(n), "precyzja": prec, "czulosc": czul,
                        "f1": f1, "mylona_z": gl, "udzial_pomylki": udz}
        print(f"{nazwa[:24]:26s}{int(n):>7,}{prec:>10.3f}{czul:>9.3f}"
              f"{f1:>7.3f}  {gl[:22]} ({udz:.0%})")

    dobre = [n for n, w in wynik.items() if w["f1"] >= .80 and n != INNE]
    print(f"\nF1 >= 0.80: {', '.join(dobre) if dobre else 'BRAK'}")
    cuk = {"rzepak ozimy": 57.2, "TUZ": 18.4, "malina": 6.3,
           "gryka zwyczajna": 6.1, "fasola wielokwiatowa": 5.1,
           "porzeczka": 2.5}
    pok = sum(v for n, v in cuk.items() if n in dobre)
    print(f"pokrycie cukru przez klasy wykrywalne: {pok:.1f}%")

    (WYNIKI / "json" / "klasyfikator_wielo.json").write_text(json.dumps({
        "rok": ROK, "n_cech": len(nazwy), "drzew": LICZBA_DRZEW,
        "walidacja": f"bloki przestrzenne {BLOK_M} m",
        "wyniki": wynik, "wykrywalne_f1_08": dobre,
        "pokrycie_cukru_pct": pok,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano klasyfikator_wielo.json")
