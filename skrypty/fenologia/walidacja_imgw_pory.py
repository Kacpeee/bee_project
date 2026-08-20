"""
ETAP 26 - walidacja modeli fenologicznych na obserwacjach polowych IMGW.

DZIURA, KTORA TO ZAMYKA
Czternascie z pietnastu modeli fenologicznych bylo KOTWICZONYCH: baze brano
z literatury, prog dobierano tak, by mediana trafila w tabelaryczna date.
Mediana byla wiec poprawna z definicji, ale AMPLITUDA wahan miedzyrocznych
pozostawala czystym zalozeniem - nie mielismy czym jej sprawdzic, bo
kwitnienia maliny czy lipy nie widac z satelity.

ZRODLO
IMGW-PIB prowadzi od 2007 roku obserwacje fitofenologiczne na 51 stacjach
synoptycznych i publikuje mapy dat poczatku fenologicznych por roku. Kazda
pora ma gatunek wskaznikowy:

    pelnia wiosny  - lilak pospolity (Syringa vulgaris) i kasztanowiec
    lato           - LIPA DROBNOLISTNA (Tilia cordata Mill.)

Lipa jest dokladnie tym gatunkiem, ktory chcemy dolozyc jako warstwe lesna,
wiec walidacja jest bezposrednia - bez podmiany gatunku.

JAK POBIERAMY
Mapy nie sa opublikowane jako dane, ale strona doczytuje je zapytaniem:

    POST /fenologia/<pora>/pokazrok  {rok: RRRR}

ktore zwraca adresy trzech obrazow (rok, srednia, odchylenie). Skrypt
pobiera je dla wszystkich dostepnych lat do lokalnego katalogu, zeby dalo
sie je odczytac i porownac z modelem.

ODCZYT JEST RECZNY I TAK MUSI BYC
Mapy to rastry z legenda dziesieciodniowa, bez warstwy danych. Daty dla
Lubelszczyzny odczytuje sie z koloru. Wpisy w ODCZYTANE ponizej pochodza
z takiego odczytu i sa oznaczone jako klasa B - to jest ograniczenie
zrodla, nie metody.

Uruchomienie:
    python skrypty/fenologia/walidacja_imgw_pory.py
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "dane" / "imgw_fenologia"
BAZA_URL = "https://agrometeo.imgw.pl"
LATA = range(2007, 2026)
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

# pora fenologiczna -> (gatunek wskaznikowy, nasz odpowiednik w modelu)
PORY = {
    "lato": ("lipa drobnolistna (Tilia cordata)", "lipa"),
    "pelnia_wiosny": ("lilak pospolity i kasztanowiec", "Sad"),
    "wczesne_lato": ("robinia akacjowa (Robinia pseudoacacia)",
                     "robinia (akacja)"),
}

# Daty odczytane z map dla Lubelszczyzny (srodek pasma legendy, DOY).
# Uzupelniac w miare odczytywania kolejnych rocznikow.
# WNIOSEK Z ODCZYTOW DLA PELNI WIOSNY (lilak, kasztanowiec):
# model wyprzedza obserwacje o 14-15 dni w OBU odczytanych rocznikach, a oba
# to lata bardzo ciepłe (2024, 2025). Srednia wieloletnia jest przy tym
# poprawna (-1 d). To nie jest stale przesuniecie jak przy lipie, tylko
# ZA DUZA AMPLITUDA: w cieplych latach model przyspiesza kwitnienie mocniej,
# niz dzieje sie naprawde.
#
# HIPOTEZA 1 (SPRAWDZONA, ODRZUCONA): brak fazy chlodowej. Przetestowano
# wymagania 20, 40, 60 i 80 dni chlodu (dni ze srednia 0-7.2 C). Blad
# pozostal -15 d przy 20 i 40 dniach, a przy 60+ model przestaje ruszac.
# Powod ten sam co przy rzepaku: zimy w Lubelskiem spelniaja wymaganie
# chlodowe juz w grudniu, wiec faza chlodowa niczego nie opoznia.
#
# HIPOTEZA 2 (NIEROZSTRZYGALNA POSIADANYMI DANYMI): niedopasowanie gatunkow.
# Modelujemy JABLON (literatura: pelnia 5 V), a IMGW obserwuje LILAKA
# i KASZTANOWCA, ktore w Polsce kwitna zwykle 10-15 dni pozniej. Model moze
# byc poprawny dla jabloni, tylko mierzony przeciwko pozniejszej roslinie.
# Rozstrzygniecie wymagaloby obserwacji kwitnienia samej jabloni - IMGW ich
# nie prowadzi, bo celowo obserwuje wylacznie rosliny dzikorosnace.
#
# Wniosek dla pracy: rozbieznosci NIE wolno przypisac modelowi, dopoki nie
# ma obserwacji tego samego gatunku. Przy lipie i robinii gatunek sie zgadza
# i tam walidacja jest rozstrzygajaca (2.8 d i -1 d).
ODCZYTANE = {
    "lato": {
        2010: 176,      # 21-30 VI
        2018: 166,      # 11-20 VI
        2019: 176,      # 21-30 VI, ciemniejsza plama wokol Lublina
        2021: 186,      # 1-10 VII, wyrazna plama wokol Lublina
        2024: 166,      # 11-20 VI
    },
    "pelnia_wiosny": {
        2024: 116,      # 21-30 IV
        2025: 126,      # 1-10 V, odchylenie bliskie zeru
    },
    "wczesne_lato": {},   # do odczytania z pobranych map

}
# Srednie IMGW odczytane ze zbiorczych map "srednia_<pora>_<rok>.jpg".
#   lato          176 = 21-30 VI   ODCZYTANE z mapy
#   pelnia_wiosny 126 = 1-10 V     ODCZYTANE z mapy
#   wczesne_lato  146 = 26 V       ODCZYTANE z mapy (pasmo 21-31 V)
#
# UWAGA - przestroga zapisana celowo. Pierwotnie wpisano tu 151 (31 V) "na
# oko", bez odczytu mapy. Porownanie dawalo wtedy blad -6 d i kusilo, zeby
# przesunac kotwice robinii. Po odczytaniu mapy okazalo sie, ze prawdziwa
# srednia to 146, a model (145) trafia w nia z bledem -1 d. Zgadnieta liczba
# doprowadzilaby do zepsucia poprawnego modelu.
SREDNIE_IMGW = {"lato": 176, "pelnia_wiosny": 126, "wczesne_lato": 146}
NIEZWERYFIKOWANE = set()   # 21-30 VI / 1-10 V


def dz(doy: float) -> str:
    x = date(2025, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def pobierz_mapy(pora: str) -> dict[int, list[str]]:
    """Adresy map z endpointu AJAX; pliki lokalnie w dane/imgw_fenologia/."""
    kat = MAPY / pora
    kat.mkdir(parents=True, exist_ok=True)
    zebrane = {}
    for rok in LATA:
        cel = kat / f"{rok}.jpg"
        if cel.exists() and cel.stat().st_size > 50_000:
            zebrane[rok] = [str(cel)]
            continue
        try:
            r = requests.post(f"{BAZA_URL}/fenologia/{pora}/pokazrok",
                              data={"rok": rok}, timeout=40,
                              headers={"X-Requested-With": "XMLHttpRequest"})
            adresy = re.findall(r'/uploads/fenologia[^"]*', r.text)
            poczatek = [a for a in adresy if "srednia" not in a and "roznic" not in a and "odchyl" not in a]
            if not poczatek:
                continue
            img = requests.get(BAZA_URL + poczatek[0], timeout=60)
            if img.status_code == 200 and len(img.content) > 50_000:
                cel.write_bytes(img.content)
                zebrane[rok] = [str(cel)]
        except Exception as e:
            print(f"    {rok}: {str(e)[:40]}")
        time.sleep(0.5)
    return zebrane


if __name__ == "__main__":
    fen = json.loads((WYNIKI / "json" / "fenologia_wszystkie.json")
                     .read_text(encoding="utf-8"))["gatunki"]

    wyniki = {}
    for pora, (gatunek, nasz) in PORY.items():
        print(f"\n=== {pora.upper()} — wskaznik: {gatunek} ===")
        mapy = pobierz_mapy(pora)
        print(f"  map pobranych: {len(mapy)} ({min(mapy)}–{max(mapy)})"
              if mapy else "  brak map")

        if nasz not in fen:
            print(f"  brak modelu dla '{nasz}' — pomijam porownanie")
            continue
        daty = {int(k): v for k, v in fen[nasz]["daty"].items()}
        okres = [daty[r] for r in range(2007, 2022) if r in daty]
        sr_model = float(np.mean(okres))
        sr_imgw = SREDNIE_IMGW[pora]
        print(f"\n  srednia 2007–2021:  model {dz(sr_model)}   "
              f"IMGW {dz(sr_imgw)}   roznica {sr_model - sr_imgw:+.0f} d")

        odcz = ODCZYTANE.get(pora, {})
        if odcz:
            print(f"\n  {'rok':>6}{'model':>9}{'IMGW':>9}{'roznica':>9}")
            bl = []
            for rok, imgw in sorted(odcz.items()):
                if rok not in daty:
                    continue
                r = daty[rok] - imgw
                bl.append(r)
                print(f"  {rok:>6}{dz(daty[rok]):>9}{dz(imgw):>9}{r:>+8.0f} d")
            if bl:
                print(f"\n  blad sredni {np.mean(bl):+.1f} d, "
                      f"bezwzgledny {np.mean(np.abs(bl)):.1f} d, n={len(bl)}")
        wyniki[pora] = {
            "gatunek_wskaznikowy": gatunek, "nasz_model": nasz,
            "map_pobranych": len(mapy),
            "srednia_model": sr_model, "srednia_imgw": sr_imgw,
            "roznica_srednich_d": sr_model - sr_imgw,
            "odczytane": {str(k): {"imgw": v, "model": daty.get(k)}
                          for k, v in odcz.items() if k in daty},
        }

    (WYNIKI / "json" / "walidacja_imgw_pory.json").write_text(json.dumps({
        "zrodlo": "IMGW-PIB, obserwacje fitofenologiczne 51 stacji "
                  "synoptycznych od 2007; mapy z agrometeo.imgw.pl",
        "uwaga": "daty odczytane wzrokowo z map rastrowych, dokladnosc "
                 "do dekady - to ograniczenie zrodla, nie modelu",
        "pory": wyniki,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nmapy w {MAPY.relative_to(ROOT)}, wynik w "
          f"json/walidacja_imgw_pory.json")
