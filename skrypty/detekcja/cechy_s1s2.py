"""
ETAP 18 - polaczone cechy Sentinel-1 + Sentinel-2 (wymog tematu pracy).

DLACZEGO RADAR
Sentinel-2 jest optyczny, wiec nie widzi przez chmury. Nad Lubelszczyzna
kosztuje to konkretnie: w I polowie stycznia 100% punktow mialo zero (ani
jednej sceny bezchmurnej), w II polowie lutego 59%, w grudniu 47%. W tescie
przenoszenia na 2026 wypadlo 16 z 52 okien - i uderzylo to w rosliny pozne,
czyli w gryke i slonecznik.

Sentinel-1 to radar C-band: przelot co ok. 6 dni, chmury bez znaczenia.
Wypelnia dokladnie te dziury. EUCROPMAP (mapa upraw calej UE) jest zreszta
zbudowana na samym S1, wiec to nie jest proteza tylko sprawdzone narzedzie
do rozpoznawania upraw.

CO WNOSI POZA CIAGLOSCIA
Radar mierzy strukture i wilgotnosc, nie kolor. Rozroznia rzeczy, ktore
optycznie sa podobne:
  - lucerna vs koniczyna: pokosy widac jako naglе spadki VH
  - malina vs porzeczka: inna struktura pedow (rzedy vs krzaki)
  - gola gleba po zbiorze: bardzo niskie VH niezaleznie od pogody

CECHY
  S2: NDVI_A, NDYI_A - anomalie wzgledem mediany pol z tej samej sceny
  S1: VV, VH i roznica VH-VV w dB (roznica dB = iloraz mocy, standardowa
      miara struktury), mediana w oknie. Tylko orbita zstepujaca - mieszanie
      orbit wprowadza sztuczna zmiennosc kata padania.

Uruchomienie: importowany przez wielo_s1s2.py
"""

from __future__ import annotations

import ee

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import gee_klasyfikator_rzepaku as K
from klasyfikator_wielo import kolekcja


def okna_polmiesieczne(rok: int) -> list[tuple[str, str]]:
    okna = []
    for m in range(9, 22):
        r, mm = (rok - 1, m) if m <= 12 else (rok, m - 12)
        okna += [(f"{r}-{mm:02d}-01", f"{r}-{mm:02d}-16"),
                 (f"{r}-{mm:02d}-16",
                  f"{r + (mm == 12)}-{(mm % 12) + 1:02d}-01")]
    return okna


def kolekcja_s1(rok: int) -> ee.ImageCollection:
    """Sentinel-1 GRD, IW, orbita zstepujaca, VV i VH w dB."""
    return (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(K.AOI)
            .filterDate(f"{rok - 1}-09-01", f"{rok}-09-30")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation",
                                           "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation",
                                           "VH"))
            .select(["VV", "VH"]))


def cechy(rok: int, z_radarem: bool = True,
          tylko: list[str] | None = None) -> tuple[ee.Image, list[str]]:
    """Kompozyty polmiesieczne: S2 (anomalie) + opcjonalnie S1 (dB).

    tylko: lista nazw cech do policzenia. Model koncowy uzywa 40 z 130
    dostepnych, a te 40 dotyka 12 okien optycznych i 14 radarowych z 26.
    Bez tego filtra kazdy kafel liczyl wszystkie 52 kompozyty, czyli
    dwukrotnie wiecej niz potrzeba - przy 252 kaflach to polowa rachunku.
    """
    chce = set(tylko) if tylko else None
    okna = okna_polmiesieczne(rok)
    s2 = kolekcja(rok)
    s1 = kolekcja_s1(rok) if z_radarem else None
    pasma, nazwy = [], []
    for i, (od, do) in enumerate(okna):
        if chce is not None and not any(
                f"{p}_{i:02d}" in chce
                for p in ("ndvi", "ndyi", "vv", "vh", "rat")):
            continue
        o2 = s2.filterDate(od, do)
        for ind, pre in (("NDVI_A", "ndvi"), ("NDYI_A", "ndyi")):
            n = f"{pre}_{i:02d}"
            if chce is not None and n not in chce:
                continue
            # to samo zabezpieczenie co przy radarze: okno bez ani jednej
            # sceny daje obraz bez pasm, na ktorym unmask() sie wywala
            pasma.append(ee.Image(ee.Algorithms.If(
                o2.size().gt(0),
                o2.select(ind).mean().unmask(0),
                ee.Image.constant(0))).rename(n).toFloat())
            nazwy.append(n)
        if not z_radarem:
            continue
        o1 = s1.filterDate(od, do)
        # median() na pustej kolekcji zwraca obraz BEZ PASM i select() sie
        # wywala. Puste okno moze byc zwyczajne (wrzesien sezonu, ktory
        # jeszcze trwa), wiec podstawiamy -99 = "brak sceny".
        pusty = ee.Image.constant([-99, -99]).rename(["VV", "VH"]).toFloat()
        med = ee.Image(ee.Algorithms.If(o1.size().gt(0), o1.median(), pusty))
        for pas, pre in (("VV", "vv"), ("VH", "vh")):
            n = f"{pre}_{i:02d}"
            if chce is not None and n not in chce:
                continue
            pasma.append(med.select(pas).unmask(-99).rename(n).toFloat())
            nazwy.append(n)
        # roznica w dB = iloraz mocy VH/VV: miara struktury rosliny
        n = f"rat_{i:02d}"
        if chce is not None and n not in chce:
            continue
        pasma.append(med.select("VH").subtract(med.select("VV"))
                     .unmask(-99).rename(n).toFloat())
        nazwy.append(n)
    return ee.Image.cat(pasma), nazwy
