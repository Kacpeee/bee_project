"""
ETAP 0b - jak naprawde wyglada sygnatura rzepaku? Profil czasowy NDYI i NDVI.

Przeglad amplitudowy (gee_ndyi_przeglad.py) pokazal, ze prog na pojedynczej
liczbie nie oddziela rzepaku. Zanim zbudujemy klasyfikator, trzeba zobaczyc
KSZTALT krzywej dla znanego rzepaku i porownac go z innymi uprawami.

Etykiety: EUCROPMAP (JRC), 10 m, klasa 232 = rzepak. Dokladnosc calej mapy to
ok. 70%, wiec do trenowania per pole jest za slaba - ale do wyznaczenia
usrednionego profilu setek tysiecy pikseli w zupelnosci wystarczy.
Docelowo zastapimy to poligonami GSA z ARiMR.

Uruchomienie:
    python gee_profil_rzepaku.py
"""

from __future__ import annotations

import json
from pathlib import Path

import ee

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

from gee_ndyi_przeglad import (MAX_CHMUR, PROMIEN_M, SRODEK_LAT, SRODEK_LON,
                               przygotuj, start)

# ---------------------------------------------------------------- konfiguracja
ROK = 2022                  # EUCROPMAP ma 2018 i 2022
OKNO_OD, OKNO_DO = "03-01", "07-15"   # szerzej niz samo kwitnienie

# Kody wg wlasciwosci 'classification_class_values' zasobu, NIE ze zgadywania.
# Pomylka, ktora to kosztowala: 300 to "Woodland and Shrubland", nie rzepak.
# Rzepak ma kod 232. Profil policzony na 300 byl profilem lasu - stad falszywy
# "sygnal marcowy" (iglaste maja wysokie NDVI w marcu) i falszywy skok NDYI
# w maju (rozwoj lisci drzew lisciastych).
KLASY = {
    232: "rzepak",
    211: "pszenica",
    213: "jeczmien",
    214: "zyto",
    216: "kukurydza",
    500: "uzytki zielone",
    300: "LAS(kontrola)",
}

SKALA = 100                 # 100 m wystarczy do sredniej po tysiacach ha


# ---------------------------------------------------------------- profil
def profile(aoi: ee.Geometry, rok: int) -> list[dict]:
    klasy = (ee.ImageCollection("JRC/D5/EUCROPMAP/V1")
             .filter(ee.Filter.eq("system:index", "EU27_2022"))
             .first().select("classification"))

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi)
           .filterDate(f"{rok}-{OKNO_OD}", f"{rok}-{OKNO_DO}")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
           .map(przygotuj))

    def jedna(img: ee.Image) -> ee.Feature:
        wl = {"doy": img.select("DOY").reduceRegion(
            ee.Reducer.first(), aoi, 1000, maxPixels=1e9, bestEffort=True).get("DOY")}
        for kod, nazwa in KLASY.items():
            s = (img.select(["NDYI", "NDVI"]).updateMask(klasy.eq(kod))
                 .reduceRegion(ee.Reducer.mean(), aoi, SKALA,
                               maxPixels=1e9, bestEffort=True))
            wl[f"{nazwa}_NDYI"] = s.get("NDYI")
            wl[f"{nazwa}_NDVI"] = s.get("NDVI")
        return ee.Feature(None, wl)

    fc = ee.FeatureCollection(col.map(jedna))
    return [f["properties"] for f in fc.getInfo()["features"]]


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    start()
    aoi = ee.Geometry.Point([SRODEK_LON, SRODEK_LAT]).buffer(PROMIEN_M).bounds()

    print(f"Profil {ROK}, okno {OKNO_OD}..{OKNO_DO}, AOI {PROMIEN_M / 1000:.0f} km\n")
    wiersze = sorted((w for w in profile(aoi, ROK) if w.get("doy")),
                     key=lambda w: w["doy"])

    wyj = Path(__file__).resolve().parents[2] / "wyniki"
    wyj.mkdir(exist_ok=True)
    (wyj / "json" / f"profil_{ROK}.json").write_text(
        json.dumps({"rok": ROK, "klasy": list(KLASY.values()), "wiersze": wiersze},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"zapisano wyniki/profil_{ROK}.json\n")

    naglowek = "DOY " + " ".join(f"{n[:8]:>9}" for n in KLASY.values())
    print("NDYI (zoltosc - kwitnienie podbija zielony, tlumi niebieski)")
    print(naglowek)
    for w in wiersze:
        kom = " ".join(
            f"{w[f'{n}_NDYI']:9.3f}" if w.get(f"{n}_NDYI") is not None else f"{'-':>9}"
            for n in KLASY.values())
        print(f"{w['doy']:>3.0f} {kom}")

    print("\nNDVI (kwitnienie ma dawac LOKALNY SPADEK - platki przeslaniaja lisce)")
    print(naglowek)
    for w in wiersze:
        kom = " ".join(
            f"{w[f'{n}_NDVI']:9.3f}" if w.get(f"{n}_NDVI") is not None else f"{'-':>9}"
            for n in KLASY.values())
        print(f"{w['doy']:>3.0f} {kom}")

    # rozdzielczosc sygnalu: o ile rzepak odstaje od najblizszej innej uprawy
    print("\nPrzewaga rzepaku nad najwyzsza inna uprawa (NDYI):")
    inne = [n for n in KLASY.values() if n != "rzepak"]
    for w in wiersze:
        r = w.get("rzepak_NDYI")
        poz = [w[f"{n}_NDYI"] for n in inne if w.get(f"{n}_NDYI") is not None]
        if r is None or not poz:
            continue
        d = r - max(poz)
        print(f"{w['doy']:>3.0f}  rzepak={r:.3f}  max(inne)={max(poz):.3f}  "
              f"roznica={d:+.3f}  {'<<< SEPARACJA' if d > 0.03 else ''}")
