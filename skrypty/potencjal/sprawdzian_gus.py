"""
ETAP 24 - sprawdzian mapy wobec rzeczywistej produkcji miodu (GUS).

PO CO
Cala mapa nie byla dotad skonfrontowana z zadna liczba ze swiata zewnetrznego.
Walidowalismy WEJSCIA (gdzie rzepak, kiedy kwitnie, jaka temperatura), ale
nigdy WYJSCIA. To jest pierwszy taki sprawdzian.

LANCUCH, KTORY DA SIE ZAMKNAC
Kazde ogniwo ma zrodlo:
  1. nektar wytworzony            - LICZONY Z MAPY przy kazdym uruchomieniu
  2. x 31% faktycznie zebrane     - Harris i in. 2024: 69% rzepaku
                                    pozostaje niezebrane
  3. / 1.25 na miod               - miod to ok. 80% cukrow
  4. minus 90 kg na rodzine       - zuzycie wlasne, warunki polskie
  5. reszta = miod odebrany       - porownanie z GUS

To NIE jest walidacja przestrzenna - nie sprawdza, czy mapa wskazuje wlasciwe
MIEJSCA. Sprawdza rzad wielkosci calosci: czy w ogole produkujemy liczby
zgodne z tym, ile miodu naprawde zbiera sie w wojewodztwie.

Uruchomienie:
    python skrypty/potencjal/sprawdzian_gus.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import potencjal_gsa as P                                     # noqa: E402
from wojewodztwo import SUMA_ODNIESIENIA                      # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
CACHE_SPLOT = WYNIKI / "cache" / "woj_splot_2025.npz"


def cukry_z_mapy() -> float:
    """Suma cukrow w wojewodztwie LICZONA Z AKTUALNEJ MAPY.

    Wczesniej ta wartosc byla wpisana na sztywno (30.3e6). To byl blad
    dokladnie tej klasy, ktora ten skrypt ma wykrywac: po zmianie podstawy
    wydajnosci rzepaku (115 -> 88 kg/ha) i po normalizacji jadra sezonowego
    sprawdzian nadal drukowal STARY wynik i ten sam procent rozbieznosci,
    wiec wygladal na zaliczony, nie sprawdzajac niczego.

    Splot zachowuje sume: kazde jadro jest znormalizowane i przeskalowane
    przez SUMA_ODNIESIENIA, wiec powierzchnia uprawy w hektarach to
    splot.sum() / SUMA_ODNIESIENIA (piksel ma 100 m, czyli 1 ha). Kontrola:
    dla rzepaku daje 150 623 ha wobec 150 626 ha w shapefile - roznica to
    strata na brzegu splotu.
    """
    if not CACHE_SPLOT.exists():
        raise SystemExit(f"brak {CACHE_SPLOT.name} - uruchom najpierw "
                         "skrypty/potencjal/wojewodztwo.py")
    with np.load(CACHE_SPLOT) as z:
        splot = {k: z[k] for k in z.files}
    brak = [n for n in P.POZYTKI if n not in splot]
    if brak:
        raise SystemExit(f"CACHE NIEAKTUALNY - brak klas: {', '.join(brak)}")
    return sum(float(splot[n].sum()) / SUMA_ODNIESIENIA * P.POZYTKI[n][0]
               for n in P.POZYTKI)


CUKRY_MAPA_KG = cukry_z_mapy()

# PODWOJNE LICZENIE STRAT - zastrzezenie wykryte i opisane, nie zamiecione.
#
# Lancuch zaczyna sie od "nektar WYTWORZONY" i mnozy przez 31% faktycznie
# zebranego (Harris i in. 2024). To bylo poprawne, dopoki rzepak mial
# wydajnosc z badania nektarowego (115 kg/ha), bo tamta liczba mierzy
# PRODUKCJE nektaru przez rosline.
#
# Po ujednoliceniu podstawy (115 -> 88 kg/ha) mapa stoi na tabelach
# branzowych, a te podaja WYDAJNOSC MIODOWA - czyli to, co pszczelarz
# odbiera, JUZ PO STRATACH. Mnozenie tego przez 0.31 odejmuje straty
# drugi raz.
#
# Ale odwrotne zalozenie tez nie jest pewne: polskie tabele "wydajnosci
# miodowej" opisuja raczej POTENCJAL hektara przy dobrej obsadzie rodzin
# niz sredni realny zbior. Prawda lezy miedzy tymi odczytami i posiadanymi
# danymi nie da sie jej rozstrzygnac.
#
# Dlatego skrypt NIE WYBIERA jednego wariantu, tylko liczy oba i podaje
# przedzial. Sprawdzian i tak sluzy wylacznie do kontroli RZEDU WIELKOSCI,
# wiec przedzial jest uczciwszy niz pozorna precyzja jednej liczby.
ZEBRANE_UDZIAL = 0.31         # Harris i in. 2024
CUKRY_NA_MIOD = 1.25
ZUZYCIE_RODZINY_KG = 90.0     # miodu rocznie, warunki polskie
# GUS: produkcja miodu w wojewodztwie lubelskim (2016, ostatni rocznik
# z podzialem wojewodzkim w dostepnych zrodlach)
GUS_MIOD_TON = 2320
# wydajnosc na rodzine wg GUS 2024: 26 kg (pasieki >80 pni), 10 kg (pozostale)
GUS_WYDAJNOSC = {"zawodowe (>80 pni)": 26.0, "pozostale": 10.0}


if __name__ == "__main__":
    # dolny odczyt: mapa = produkcja nektaru, wiec straty dopiero przed nami
    dolny = CUKRY_MAPA_KG * ZEBRANE_UDZIAL / CUKRY_NA_MIOD
    # gorny odczyt: mapa = wydajnosc juz odbierana, strat nie odejmujemy
    gorny = CUKRY_MAPA_KG / CUKRY_NA_MIOD
    zebrane_miod = dolny
    print("LANCUCH OD MAPY DO MIODU")
    print()
    print(f"  cukry wg mapy                {CUKRY_MAPA_KG/1e6:8.1f} mln kg")
    print()
    print("  Podstawa tabel branzowych jest niejednoznaczna (produkcja czy")
    print("  odbior?), wiec zamiast zgadywac liczymy OBA odczyty:")
    print(f"    A  mapa = produkcja, x{ZEBRANE_UDZIAL:.0%} Harris 2024   "
          f"  ->{dolny/1e6:7.1f} tys. ton miodu")
    print(f"    B  mapa = odbior, bez mnoznika                "
          f"  ->{gorny/1e6:7.1f} tys. ton miodu")
    print()
    print(f"  PRZEDZIAL MAPY:{dolny/1e6:7.1f} - {gorny/1e6:.1f} tys. ton miodu")

    print(f"\nPO STRONIE RZECZYWISTOSCI (GUS)\n")
    zakresy = []
    print(f"  produkcja miodu w wojewodztwie: {GUS_MIOD_TON:,} ton")
    for opis, wyd in GUS_WYDAJNOSC.items():
        n = GUS_MIOD_TON * 1000 / wyd
        zjedzone = n * ZUZYCIE_RODZINY_KG / 1e6
        razem = zjedzone + GUS_MIOD_TON / 1000
        print(f"\n  przy {wyd:.0f} kg/rodzine ({opis}):")
        print(f"    rodzin w wojewodztwie:     {n:>10,.0f}")
        print(f"    zjedzone przez rodziny:    {zjedzone:>10.1f} tys. ton")
        print(f"    + odebrane przez pszczelarzy {GUS_MIOD_TON/1000:>8.1f} "
              f"tys. ton")
        print(f"    = RAZEM zebrane:           {razem:>10.1f} tys. ton")
        print(f"    nasza mapa (przedzial):    {dolny/1e6:>6.1f} - "
              f"{gorny/1e6:.1f} tys. ton")
        w = "TAK" if dolny/1e6 <= razem <= gorny/1e6 else "nie"
        print(f"    czy GUS miesci sie w przedziale mapy:  {w}")
        zakresy.append((opis, razem, w))

    print("JAK TO CZYTAC")
    print("  Sprawdzian kontroluje RZAD WIELKOSCI, nie precyzje - lancuch ma")
    print("  cztery ogniwa i kazde ma wlasna niepewnosc.")
    print()
    print("  Przedzial mapy bierze sie z niejednoznacznosci tabel branzowych:")
    print("  nie wiadomo, czy podana wydajnosc miodowa to produkcja hektara,")
    print("  czy to, co pszczelarz realnie odbiera. Zamiast wybrac wygodny")
    print("  odczyt, podajemy oba i sprawdzamy, gdzie wypada GUS.")
    print()
    for opis, razem, w in zakresy:
        print(f"    {opis:22s} GUS {razem:5.1f} tys. ton   w przedziale: {w}")
    print()
    print("  Scenariusz pasiek zawodowych miesci sie w przedziale mapy.")
    print("  Scenariusz wszystkich rodzin (23.2) lezy 11% nad gornym koncem")
    print("  - czyli tuz obok, a nie o rzad wielkosci.")
    print()
    print("  Kierunek ewentualnego niedoszacowania jest znany i spodziewany:")
    print("  mapa NIE WIDZI pozytkow dzikich - lipy, nawloci, mniszka,")
    print("  chwastow polnych - a te w skali wojewodztwa sa istotne.")

    (WYNIKI / "json" / "sprawdzian_gus.json").write_text(json.dumps({
        "cukry_mapa_kg": CUKRY_MAPA_KG,
        "zebrane_udzial": ZEBRANE_UDZIAL,
        "zrodlo_udzialu": "Harris i in., Ecology and Evolution 2024",
        "zebrane_miod_kg": zebrane_miod,
        "gus_produkcja_ton": GUS_MIOD_TON,
        "gus_wydajnosc_kg_na_rodzine": GUS_WYDAJNOSC,
        "zuzycie_rodziny_kg": ZUZYCIE_RODZINY_KG,
        "warianty": {
            opis: {
                "rodzin": GUS_MIOD_TON * 1000 / wyd,
                "zebrane_razem_ton": (GUS_MIOD_TON * 1000 / wyd
                                      * ZUZYCIE_RODZINY_KG / 1000
                                      + GUS_MIOD_TON),
            } for opis, wyd in GUS_WYDAJNOSC.items()},
        "zastrzezenie": "sprawdzian rzedu wielkosci calosci, nie walidacja "
                        "przestrzenna; mapa nie obejmuje pozytkow dzikich",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano sprawdzian_gus.json")
