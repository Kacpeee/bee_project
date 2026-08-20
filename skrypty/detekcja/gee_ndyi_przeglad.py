"""
ETAP 0 - czy rzepak w ogole widac? Przeglad amplitudy NDYI z Sentinel-2 przez GEE.

Nie potrzebuje danych ARiMR ani zadnych etykiet. Odpowiada na trzy pytania,
od ktorych zalezy sens calego projektu:

  1. Czy pola rzepaku odcinaja sie od tla?
     -> ogladasz miniatury, ktore skrypt wypisze w konsoli
  2. Ile bezchmurnych obserwacji przypada na piksel w oknie kwitnienia?
     -> jesli mediana < 4, ekstrakcja daty kwitnienia per pole jest zagrozona
  3. Jak bardzo termin kwitnienia rozjezdza sie miedzy latami?
     -> jesli rozrzut < tygodnia, model fenologiczny nie ma czego przewidywac

WAZNE - dlaczego amplituda, a nie samo NDYI:
    NDYI = (zielony - niebieski) / (zielony + niebieski). Chlorofil pochlania
    niebieski duzo silniej niz zielony, wiec KAZDA zielona roslinnosc ma NDYI
    rzedu 0.2-0.3. Prog na wartosci bezwzglednej zaznacza cale wojewodztwo
    (sprawdzone: 99.5% powierzchni). Sygnatura rzepaku to przejsciowy SKOK
    ponad wlasna linie bazowa piksela, zbiezny ze spadkiem NDVI - platki
    przeslaniaja lisce. Dlatego liczymy:
        AMPL = NDYI_p90 - NDYI_p25   (w obrebie sezonu, per piksel)
        DIP  = NDVI_med - NDVI w momencie szczytu zoltosci
    p90 zamiast maksimum, bo maksimum z kilkunastu obserwacji lapie gorny
    ogon szumu, zwlaszcza w pasmie niebieskim.

Przygotowanie (jednorazowo):
    pip install earthengine-api
    earthengine authenticate
    ... oraz projekt z https://code.earthengine.google.com/register

Uruchomienie:
    python gee_ndyi_przeglad.py
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- konfiguracja
# ID projektu Google Cloud z zarejestrowanym Earth Engine. Kolejnosc szukania:
# zmienna srodowiskowa EE_PROJECT -> plik .ee_projekt obok skryptu -> stala ponizej.
PROJEKT_GEE = ""            # np. "pszczoly-505208"

# Obszar pilotazowy: trojkat Zamosc-Hrubieszow-Tomaszow, okolice Werbkowic.
# Lessy i czarnoziemy, duze zwarte pola, jeden kafelek S2.
SRODEK_LAT = 50.755
SRODEK_LON = 23.600
PROMIEN_M = 15_000          # 15 km -> obszar ok. 30x30 km

LATA = range(2019, 2027)    # S2A+S2B daja pelne pokrycie od ~2018

# Okno szersze niz samo kwitnienie - termin przesuwa sie miedzy latami o 2-3 tyg.
OKNO_OD = "04-01"
OKNO_DO = "06-05"

MAX_CHMUR = 60              # odrzuc sceny beznadziejne, reszte maskuj per piksel

# Prog amplitudy dobierany kalibracyjnie, nie z sufitu. Skrypt wypisuje udzial
# powierzchni dla kilku wartosci - wybierz te, ktora daje areal zblizony do
# statystyki GUS/BDL dla powiatu (rzepak to ok. 10-15% gruntow ornych).
PROGI_AMPL = [0.06, 0.08, 0.10, 0.12, 0.15]
PROG_ROBOCZY = 0.10         # uzywany do statystyk fenologicznych i maski

ROK_EKSPORTU = None         # np. 2025; None = tylko statystyki, bez eksportu
FOLDER_DRIVE = "pszczoly_gee"

# Bez tej maski amplitude NDYI jest zdominowana przez rozwoj lisci lasu
# lisciastego (kwiecien-maj to najwiekszy skok zieleni w calym roku).
# ESA WorldCover 10 m, klasa 40 = grunty orne. Tymczasowo, do czasu GSA.
MASKA_GRUNTOW = True


def pobierz_png(url: str, nazwa: str) -> str:
    """Zapisuje miniature GEE do wyniki/ i zwraca sciezke.

    Adresy z getThumbURL wygasaja po kilkudziesieciu minutach, wiec raport
    nie moze ich trzymac w JSON-ie i pobierac pozniej - trzeba sciagnac
    plik w momencie liczenia."""
    wyj = ROOT / "wyniki" / "podglady"
    wyj.mkdir(parents=True, exist_ok=True)
    sciezka = wyj / nazwa
    urllib.request.urlretrieve(url, sciezka)
    return str(sciezka.relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------- inicjalizacja
def id_projektu() -> str:
    plik = ROOT / ".ee_projekt"
    return (os.environ.get("EE_PROJECT")
            or (plik.read_text(encoding="utf-8").strip() if plik.exists() else "")
            or PROJEKT_GEE)


def start() -> None:
    projekt = id_projektu()
    if not projekt:
        raise SystemExit(
            "Brak ID projektu Earth Engine.\n"
            "  1. Zarejestruj projekt: https://code.earthengine.google.com/register\n"
            "     (wybierz uzytek niekomercyjny / akademicki - jest darmowy)\n"
            "  2. Zapisz jego ID w pliku .ee_projekt obok tego skryptu,\n"
            "     albo ustaw zmienna EE_PROJECT."
        )
    try:
        ee.Initialize(project=projekt)
    except Exception:
        print("Brak waznego tokenu - otwieram logowanie w przegladarce...")
        ee.Authenticate()
        ee.Initialize(project=projekt)
    print(f"Earth Engine: projekt {projekt}")


AOI = None  # ustawiane w main, po ee.Initialize


# ---------------------------------------------------------------- dane
def przygotuj(img: ee.Image) -> ee.Image:
    """Maska chmur z SCL + wskazniki + numer dnia roku jako pasmo."""
    scl = img.select("SCL")
    # 4 = wegetacja, 5 = gleba odkryta. Reszta to chmury, cienie, snieg, woda.
    czyste = scl.eq(4).Or(scl.eq(5))

    opt = img.select(["B2", "B3", "B4", "B8"])
    ndyi = opt.normalizedDifference(["B3", "B2"]).rename("NDYI")
    ndvi = opt.normalizedDifference(["B8", "B4"]).rename("NDVI")
    doy = ee.Image.constant(
        img.date().getRelative("day", "year").add(1)
    ).int16().rename("DOY")

    return (ee.Image.cat([ndyi, ndvi, doy])
            .updateMask(czyste)
            .copyProperties(img, ["system:time_start"]))


def kolekcja(rok: int) -> ee.ImageCollection:
    # S2_SR_HARMONIZED, nie S2_SR: od baseline 04.00 (styczen 2022) Copernicus
    # dodal offset -1000 do reflektancji. Przy roznicy znormalizowanej offset sie
    # NIE skraca, wiec na surowym S2_SR szereg czasowy pekaby w 2022 roku.
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(AOI)
            .filterDate(f"{rok}-{OKNO_OD}", f"{rok}-{OKNO_DO}")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
            .map(przygotuj))


def wskazniki(rok: int) -> tuple[ee.ImageCollection, ee.Image]:
    """Zwraca kolekcje i obraz z pasmami AMPL, DIP, DOY, N_OBS."""
    col = kolekcja(rok)

    kwantyle = col.select("NDYI").reduce(ee.Reducer.percentile([25, 90]))
    ampl = (kwantyle.select("NDYI_p90")
            .subtract(kwantyle.select("NDYI_p25")).rename("AMPL"))

    # qualityMosaic bierze piksel o najwyzszym NDYI wraz z towarzyszacymi
    # pasmami - dostajemy NDVI i date DOKLADNIE z momentu szczytu zoltosci.
    szczyt = col.qualityMosaic("NDYI")
    dip = (col.select("NDVI").median()
           .subtract(szczyt.select("NDVI")).rename("DIP"))

    n_obs = col.select("NDYI").count().rename("N_OBS")
    obr = ee.Image.cat([ampl, dip, szczyt.select("DOY"), n_obs])

    if MASKA_GRUNTOW:
        orne = ee.Image("ESA/WorldCover/v200/2021").select("Map").eq(40)
        obr = obr.updateMask(orne)

    return col, obr


# ---------------------------------------------------------------- analiza roku
def przeanalizuj(rok: int, ha_aoi: float) -> dict | None:
    col, obr = wskazniki(rok)
    n_scen = col.size().getInfo()
    if n_scen == 0:
        print(f"{rok}: brak scen spelniajacych filtr")
        return None

    wspolne = dict(geometry=AOI, scale=100, maxPixels=1e9, bestEffort=True)

    # rozklad amplitudy + dostepnosc obserwacji (jedno zapytanie na oba pasma;
    # przy pojedynczym percentylu GEE nie doklada sufiksu _pNN, stad kilka naraz)
    p = obr.select(["AMPL", "N_OBS"]).reduceRegion(
        reducer=ee.Reducer.percentile([10, 50, 90, 99]), **wspolne).getInfo()

    # udzial powierzchni dla kilku progow naraz - jedno zapytanie
    maski = ee.Image.cat([obr.select("AMPL").gte(t).rename(f"t{int(t * 100):02d}")
                          for t in PROGI_AMPL])
    udzialy = maski.reduceRegion(reducer=ee.Reducer.mean(), **wspolne).getInfo()

    # fenologia liczona TYLKO w masce kandydatow na rzepak - mediana po calym
    # obszarze jest bez sensu, bo dominuja ja piksele bez kwitnienia
    kand = obr.select("AMPL").gte(PROG_ROBOCZY)
    fen = (obr.select(["DOY", "DIP"]).updateMask(kand)
           .reduceRegion(reducer=ee.Reducer.percentile([25, 50, 75]),
                         **wspolne).getInfo())

    areale = "  ".join(
        f"{t:.2f}:{udzialy[f't{int(t * 100):02d}'] * ha_aoi / 1000:.1f}k"
        for t in PROGI_AMPL)

    print(f"{rok}: scen={n_scen:3d}  obs/px med={p['N_OBS_p50']:.0f} "
          f"p10={p['N_OBS_p10']:.0f}")
    print(f"      AMPL p50={p['AMPL_p50']:.3f} p90={p['AMPL_p90']:.3f} "
          f"p99={p['AMPL_p99']:.3f}   ha wg progu [{areale}]")
    if fen.get("DOY_p50") is not None:
        print(f"      w masce AMPL>={PROG_ROBOCZY}: DOY szczytu "
              f"{fen['DOY_p25']:.0f}/{fen['DOY_p50']:.0f}/{fen['DOY_p75']:.0f} "
              f"(p25/med/p75), spadek NDVI med={fen['DIP_p50']:.3f}")

    return {"rok": rok, "obraz": obr, "doy": fen.get("DOY_p50"),
            "dip": fen.get("DIP_p50"), "n_obs_med": p["N_OBS_p50"]}


def miniatura(obr: ee.Image) -> str:
    """Link do PNG - otwierasz w przegladarce, bez czekania na eksport."""
    return obr.select("AMPL").getThumbURL({
        "region": AOI, "dimensions": 1200,
        "min": 0.0, "max": 0.20,
        # ciemne = brak skoku zoltosci, zolte = kandydat na rzepak
        "palette": ["#101820", "#2c4a52", "#5d8a3a", "#c2c93f", "#ffe600"],
        "format": "png",
    })


def eksportuj(obr: ee.Image, rok: int) -> None:
    zadanie = ee.batch.Export.image.toDrive(
        image=obr.toFloat().clip(AOI),
        description=f"ndyi_ampl_{rok}", folder=FOLDER_DRIVE,
        fileNamePrefix=f"ndyi_ampl_{rok}",
        region=AOI, scale=10, crs="EPSG:2180", maxPixels=1e10,
    )
    zadanie.start()
    print(f"\nEksport {rok} wystartowal -> Google Drive / {FOLDER_DRIVE}")
    print("Postep: https://code.earthengine.google.com/tasks")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    start()
    AOI = ee.Geometry.Point([SRODEK_LON, SRODEK_LAT]).buffer(PROMIEN_M).bounds()
    ha_aoi = AOI.area(maxError=100).getInfo() / 10_000

    print(f"Obszar: {PROMIEN_M / 1000:.0f} km wokol {SRODEK_LAT}, {SRODEK_LON} "
          f"({ha_aoi / 1000:.0f} tys. ha)")
    print(f"Okno: {OKNO_OD} .. {OKNO_DO}")

    # areale licz wzgledem powierzchni odniesienia, nie calego AOI
    ha_baza = ha_aoi
    if MASKA_GRUNTOW:
        udzial_ornych = ee.Image("ESA/WorldCover/v200/2021").select("Map").eq(40) \
            .reduceRegion(ee.Reducer.mean(), AOI, 100, maxPixels=1e9,
                          bestEffort=True).get("Map").getInfo()
        ha_baza = ha_aoi * udzial_ornych
        print(f"Maska: grunty orne WorldCover = {ha_baza / 1000:.0f} tys. ha "
              f"({udzial_ornych:.0%} AOI)")
    print()

    wyniki = [w for rok in LATA if (w := przeanalizuj(rok, ha_baza))]
    if not wyniki:
        raise SystemExit("Nic nie policzono - sprawdz AOI i uprawnienia GEE.")

    print("\nMiniatury (zolte = wysoka amplituda NDYI, czyli kandydaci na rzepak):")
    for w in wyniki[-3:]:
        print(f"  {w['rok']}: {miniatura(w['obraz'])}")

    najgorszy = min(w["n_obs_med"] for w in wyniki)
    print(f"\nChmury: najgorszy rok ma mediane {najgorszy:.0f} obserwacji na piksel.")
    print("  -> " + ("ZA MALO na date kwitnienia per pole, doloz Sentinel-1."
                     if najgorszy < 4 else
                     "Wystarczy na dopasowanie krzywej NDYI per pole."))

    # Kontrola sygnatury: kwitnienie ma dawac DODATNI spadek NDVI (platki
    # przeslaniaja lisce). Jesli DIP <= 0, maska lapie zazielenienie, nie kwiaty.
    dip = [w["dip"] for w in wyniki if w["dip"] is not None]
    if dip:
        print(f"Kontrola NDVI: mediana spadku {min(dip):+.3f}..{max(dip):+.3f}")
        if max(dip) < 0.02:
            print("  -> BRAK spadku NDVI w masce. Prog na amplitudzie NDYI lapie")
            print("     zazielenienie zboz, a nie kwitnienie rzepaku.")
            print("     Wniosek: prog bezobiektowy nie wystarcza - potrzebny")
            print("     poziom dzialki (usrednienie po poligonie GSA) i klasyfikator.")

    doy = [w["doy"] for w in wyniki if w["doy"] is not None]
    if len(doy) >= 3:
        print(f"DOY szczytu w latach: {min(doy):.0f}..{max(doy):.0f} "
              f"(rozrzut {max(doy) - min(doy):.0f} dni)")
        print("  UWAGA: to argmax po kilkunastu scenach, wiec wartosci kwantuja sie")
        print("  do dat przelotow satelity - czesc rozrzutu to artefakt, nie biologia.")
        print("  Wiarygodna data kwitnienia wymaga dopasowania krzywej do szeregu")
        print("  usrednionego po dzialce. Nie wyciagaj stad wnioskow o Etapie 4.")

    if ROK_EKSPORTU:
        if w := next((w for w in wyniki if w["rok"] == ROK_EKSPORTU), None):
            eksportuj(w["obraz"], ROK_EKSPORTU)
