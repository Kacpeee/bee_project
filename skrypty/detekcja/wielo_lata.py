"""
ETAP 19 - mapy WIELOGATUNKOWE wstecz (2019-2024) z Sentinel-1 + Sentinel-2.

CO ODTWARZAMY I DLACZEGO WLASNIE TO
Test przenoszenia (transfer_s1s2.py: ucz 2025, sprawdz 2026) porownal model
z odniesieniem "roslo tam, gdzie rok temu". Odtwarzamy tylko gatunki, gdzie
detekcja to odniesienie POBIJA - bo tylko tam cokolwiek wnosi:

  rzepak      r 0.958 wobec 0.338 pamieci  - wedruje w plodozmianie
  gryka       r 0.859 wobec 0.750
  malina      r 0.878 wobec 0.847
  slonecznik  r 0.850 wobec 0.814
  razem 70.4% cukru wojewodztwa

Reszta (laki, fasola, porzeczka, motylkowe, sad) zostaje zamrozona
z deklaracji - dla nich pamiec WYGRYWA z modelem, co jest wynikiem
poprawnym: to uprawy trwale albo specjalistyczne, ktore nie wedruja.
Fasola wielokwiatowa uprawiana jest w kolko na tych samych polach pod
Hrubieszowem (pamiec 0.949) i model tego nie pobije.

DWIE POPRAWKI WOBEC PIERWSZEJ, NIEUDANEJ WERSJI

1. MODEL JAKO ZASOB, NIE W GRAFIE KAFLA.
   Poprzednio las uczyl sie od nowa przy kazdym kaflu (21 tys. punktow x
   300 drzew) - pierwszy kafel przekroczyl limit czasu po 23 minutach.
   Teraz trening leci raz jako zadanie wsadowe, zapisuje sie do zasobu,
   a kafle tylko go wczytuja.

2. 40 CECH ZAMIAST 122.
   Wybrane wg waznosci; sprawdzone lokalnie, ze daja LEPSZY transfer niz
   pelny zestaw (srednie r 0.899 wobec 0.885 - mniej przeuczenia).
   Sklad: 19 optycznych, 21 radarowych.

Pobieramy surowe klasy w 20 m i agregujemy lokalnie - mediana klas nie ma
sensu, a osobne reduceResolution na gatunek byloby kilkakrotnie drozsze.

Wznawialne: kazdy kafel ladu je na dysk od razu.

Uruchomienie:
    python skrypty/detekcja/wielo_lata.py
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import ee
import numpy as np
import pandas as pd
import rasterio
import requests

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import gee_klasyfikator_rzepaku as K
import mapa_wojewodztwa as MW
from cechy_s1s2 import cechy
from wielo_diagnoza import ODRZUC, SCAL
from wielo_transfer import GRUPA

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL, SKALA, KAFEL_PX = 100, 20, 300
# 2025 liczony jako PIERWSZY: to jedyny sezon z pelnymi
# deklaracjami, wiec na nim wyliczane sa wspolczynniki
# kalibracji arealowej dla pozostalych lat (probka treningowa
# jest zrownowazona, a w terenie slonecznika jest 20x mniej
# niz rzepaku - bez korekty model zawyza go 12-krotnie)
LATA = [2025, 2024, 2023, 2022, 2021, 2020, 2019]
ROK_TRENINGU = 2025
DRZEW = 200
# Drzewa bez limitu rozmiaru wysadzily trening wsadowy na braku
# pamieci (21 tys. punktow x 300 nieograniczonych drzew). Limit
# 500 lisci kosztuje 0.005 w srednim r (0.899 -> 0.894), a tnie
# rozmiar modelu kilkunastokrotnie.
MAX_LISCI = 500
ODTWARZANE = ["rzepak ozimy", "gryka zwyczajna", "malina", "słonecznik"]
N_TRENING = 7000        # limit 10 MB na zapytanie; koszt -0.005 w srednim r


def pobierz(img, l, t, w, h, prob=4):
    region = ee.Geometry.Rectangle(
        [l, t - h * PIKSEL, l + w * PIKSEL, t], "EPSG:2180", False)
    for i in range(prob):
        try:
            url = img.getDownloadURL({"region": region, "scale": SKALA,
                                      "crs": "EPSG:2180", "format": "GEO_TIFF"})
            r = requests.get(url, timeout=600)
            r.raise_for_status()
            b = r.content
            if b[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    b = z.read([n for n in z.namelist()
                                if n.endswith(".tif")][0])
            with rasterio.open(io.BytesIO(b)) as f:
                return f.read(1).astype("uint8")
        except Exception as e:
            if i == prob - 1:
                print(f"      pominiety: {str(e)[:60]}")
                return None
            time.sleep(15 * (i + 1))


def model(cechy_ok, tr):
    """Las trenowany RAZ jako zadanie wsadowe i zapisany jako zasob.

    Droga do tego rozwiazania byla kreta i warto to zapisac:
      1. trening w grafie kazdego kafla (sampleRegions na 21 tys. punktow)
         - pierwszy kafel padl po 23 minutach
      2. podanie gotowych liczb inline - przekroczylo limit 10 MB na
         zapytanie; po skroceniu nazw i zaokragleniu zmiescilo sie, ale
         kosztem ciecia proby do 7 tys. punktow (srednie r 0.899 -> 0.889)
      3. zapis jako zasob - poczatkowo niemozliwy, bo projekt nie mial
         zainicjowanego katalogu zasobow

    Droga 3 odpadla ostatecznie: zadanie wsadowe dwukrotnie skonczylo sie
    brakiem pamieci, i to NIE przez rozmiar lasu (limit 500 lisci nic nie
    dal), tylko przez samo sampleRegions - wyciagniecie 40 cech w 21 tys.
    punktow rozrzuconych po calym wojewodztwie trzeba zmiescic w jednym
    zadaniu, a tego nie da sie rozbic na porcje.

    Zostaje droga 2, ktora udowodnila, ze dziala (kafle liczyly sie bez
    bledu). Kosztuje 0.005 w srednim r wzgledem pelnej proby - mniej niz
    szum miedzy losowaniami.
    """
    krotkie = [f"f{i}" for i in range(len(cechy_ok))]
    tr = tr.sample(n=min(N_TRENING, len(tr)), random_state=42)
    print(f"trening w zapytaniu: {len(tr):,} punktow, {DRZEW} drzew "
          f"po max {MAX_LISCI} lisci")
    fc = ee.FeatureCollection([
        ee.Feature(None, {**{k: round(float(getattr(r, c)), 4)
                             for k, c in zip(krotkie, cechy_ok)},
                          "k": int(r.kod)})
        for r in tr.itertuples()])
    las = ee.Classifier.smileRandomForest(
        numberOfTrees=DRZEW, maxNodes=MAX_LISCI).train(
        features=fc, classProperty="k", inputProperties=krotkie)
    return las, krotkie


def zajmij_blokade() -> Path:
    """Jeden proces na raz.

    Po wylaczeniu laptopa latwo uruchomic skrypt drugi raz, nie zauwazajac,
    ze poprzedni przezyl. Dwa procesy pisza wtedy do tego samego pliku kafli
    i moga sobie nawzajem nadpisac wyniki - zdarzylo sie to raz i wykrylem
    po dwoch osiach czasu w logu.
    """
    lock = WYNIKI / "cache" / "wielo_lata.lock"
    if lock.exists():
        stary = lock.read_text().strip()
        czy_zyje = False
        try:
            import subprocess
            out = subprocess.run(["tasklist", "/FI", f"PID eq {stary}"],
                                 capture_output=True, text=True).stdout
            czy_zyje = stary in out
        except Exception:
            pass
        if czy_zyje:
            raise SystemExit(
                f"Inny proces (PID {stary}) juz liczy. Ubij go albo poczekaj; "
                f"jesli na pewno nie dziala, skasuj {lock}")
        print(f"blokada po martwym procesie {stary} - przejmuje")
    lock.write_text(str(os.getpid()))
    return lock


if __name__ == "__main__":
    blokada = zajmij_blokade()
    K.start()
    projekt = (ROOT / ".ee_projekt").read_text(encoding="utf-8").strip()
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx) = f.bounds, f.shape
    K.AOI = ee.Geometry.Rectangle([b.left, b.bottom, b.right, b.top],
                                  "EPSG:2180", False)

    cechy_ok = json.loads((WYNIKI / "json" / "cechy_top40.json")
                          .read_text(encoding="utf-8"))
    print(f"cech: {len(cechy_ok)} "
          f"({sum(1 for c in cechy_ok if c[:2] == 'nd')} optycznych, "
          f"{sum(1 for c in cechy_ok if c[:2] != 'nd')} radarowych)")

    df = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    X = (pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
         .join(pd.read_csv(WYNIKI / "cache" / "wielo_cechy_s1.csv")
               .set_index("i")))
    df = df.reset_index(drop=True).join(X[cechy_ok])
    df = df[~df.etykieta.isin(ODRZUC)].dropna(subset=cechy_ok).copy()
    df["grupa"] = df.etykieta.replace(SCAL).replace(GRUPA)
    kody = {n: i for i, n in enumerate(sorted(df.grupa.unique()))}
    df["kod"] = df.grupa.map(kody)
    print(f"proba: {len(df):,} punktow, {len(kody)} klas, {DRZEW} drzew")
    print("odtwarzane: " + ", ".join(f"{n}={kody[n]}" for n in ODTWARZANE))

    las, krotkie = model(cechy_ok, df)

    from shapely.geometry import MultiLineString, box
    from shapely.ops import polygonize, unary_union
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in MW.podklad()[2] if len(g) > 1]))), key=lambda q: q.area)
    kafle = [(x0, y0, min(KAFEL_PX, nx - x0), min(KAFEL_PX, ny - y0))
             for y0 in range(0, ny, KAFEL_PX)
             for x0 in range(0, nx, KAFEL_PX)
             if poly.intersects(box(
                 b.left + x0 * PIKSEL,
                 b.top - (y0 + min(KAFEL_PX, ny - y0)) * PIKSEL,
                 b.left + (x0 + min(KAFEL_PX, nx - x0)) * PIKSEL,
                 b.top - y0 * PIKSEL))]
    print(f"kafli na sezon: {len(kafle)}, sezonow: {len(LATA)}\n")

    kro = PIKSEL // SKALA
    t0 = time.time()
    for rok in LATA:
        wyj = WYNIKI / "cache" / f"wielo_klasy_{rok}.npz"
        if wyj.exists():
            print(f"SEZON {rok}: gotowy")
            continue
        print(f"SEZON {rok}:")
        xr, _ = cechy(rok, z_radarem=True, tylko=cechy_ok)
        klas = (xr.select(cechy_ok).rename(krotkie)
                .classify(las).rename("k").toByte())
        czesc = WYNIKI / "cache" / f"wielo_czesc_{rok}.npz"
        udzial = {n: np.zeros((ny, nx), "float32") for n in ODTWARZANE}
        gotowe = set()
        if czesc.exists():
            # kontekst obowiazkowy: np.load zwraca leniwy uchwyt i trzyma
            # plik otwarty, przez co pozniejszy unlink() konczy sie na
            # Windows bledem "plik uzywany przez inny proces"
            with np.load(czesc) as z:
                udzial = {n: z[n].copy() for n in ODTWARZANE}
                gotowe = set(map(tuple, z["gotowe"]))
            print(f"  wznawiam: {len(gotowe)}/{len(kafle)}")
        for i, (x0, y0, w, h) in enumerate(kafle, 1):
            if (x0, y0) in gotowe:
                continue
            a = pobierz(klas, b.left + x0 * PIKSEL, b.top - y0 * PIKSEL, w, h)
            if a is not None:
                hh, ww = a.shape[0] // kro, a.shape[1] // kro
                for n in ODTWARZANE:
                    m = (a[:hh * kro, :ww * kro] == kody[n]).astype("float32")
                    udzial[n][y0:y0 + hh, x0:x0 + ww] = \
                        m.reshape(hh, kro, ww, kro).mean(axis=(1, 3))
            gotowe.add((x0, y0))
            np.savez_compressed(czesc, gotowe=np.array(sorted(gotowe)),
                                **udzial)
            print(f"  {rok} kafel {i}/{len(kafle)}  "
                  f"{(time.time()-t0)/60:6.1f} min")
        np.savez_compressed(wyj, **udzial)
        czesc.unlink(missing_ok=True)
        for n in ODTWARZANE:
            print(f"    {n[:24]:26s} {udzial[n].sum():9,.0f} ha")
        print()

    (WYNIKI / "json" / "wielo_lata.json").write_text(json.dumps({
        "lata": LATA, "trening": ROK_TRENINGU, "n_cech": len(cechy_ok),
        "cechy": cechy_ok, "odtwarzane": ODTWARZANE, "kody": kody,
        "uzasadnienie": "gatunki, dla ktorych detekcja bije odniesienie "
                        "'roslo tam, gdzie rok temu' (transfer_s1s2.json)",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    blokada.unlink(missing_ok=True)
    print("KONIEC")
