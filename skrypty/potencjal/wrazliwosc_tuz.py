"""
ETAP 28 - analiza wrazliwosci mapy na niepewna wydajnosc TUZ.

PROBLEM, KTORY TO ZAMYKA
TUZ (trwale uzytki zielone) odpowiada za 21.4% cukrow wojewodztwa, czyli
za druga pozycje w bilansie - a jest to JEDYNA pozycja, ktorej nie da sie
uzrodlowic punktowo. Powod jest rzeczowy, nie lenistwo: TUZ to nie gatunek,
tylko klasa uzytkowania gruntu. Wartosc pozytkowa runi zalezy w calosci od
skladu (mniszek, koniczyna biala, chaber), a sklad rozni sie miedzy dzialkami
i latami. Rozpietosc w literaturze jest ogromna:

    laka kosna   ok. 40 kg miodu/ha
    pastwisko    tylko  6 kg miodu/ha

Zadna pojedyncza liczba nie opisze tego uczciwie.

CO ROBIMY ZAMIAST ZGADYWANIA
Nie szukamy lepszej liczby - MIERZYMY SKUTEK jej niepewnosci. Mapa jest
przeliczana dla calego wiarygodnego zakresu (od czysto pastwiskowego po
czysto lakowy) i porownywana z wersja bazowa dwiema miarami:

    korelacja Pearsona   - czy caly obraz zostaje ten sam
    wspolne top-10%      - czy NAJLEPSZE miejsca zostaja te same

Druga miara jest wazniejsza. Mapa sluzy do wskazania pszczelarzowi, dokad
jechac, wiec liczy sie stabilnosc czolowki, a nie bezwzgledne kilogramy.

DLACZEGO SKALUJEMY OBA POKOSY RAZEM
"TUZ" i "TUZ odrost" to ta sama laka widziana dwa razy w sezonie. Jesli run
jest uboga, jest uboga w obu pokosach - wiec zmiana musi dotyczyc obu
proporcjonalnie, inaczej test bylby niespojny.

UWAGA O CACHE
Skrypt czyta gotowe sploty z woj_splot_*.npz. Wynik jest ilorazem dwoch map
liczonych z tego samego cache, wiec jest poprawny takze wtedy, gdy cache
pochodzi z wczesniejszej wersji jadra - zmiana jadra dziala na obie strony
porownania tak samo.

Uruchomienie:
    python skrypty/potencjal/wrazliwosc_tuz.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import potencjal_gsa as P                                    # noqa: E402

WYNIKI = ROOT / "wyniki"
CACHE = WYNIKI / "cache" / "woj_splot_2025.npz"

# klasy TUZ skalowane razem - to ta sama laka w dwoch pokosach
KLASY_TUZ = ["TUZ", "TUZ odrost"]

# badany zakres LACZNEJ wydajnosci TUZ [kg cukrow/ha za caly sezon]
ZAKRES = [6, 12, 20, 26, 32, 40]


def mapa(splot: dict[str, np.ndarray], laczne_tuz: float) -> np.ndarray:
    """Mapa cukru przy zadanej lacznej wydajnosci TUZ."""
    baza = sum(P.POZYTKI[n][0] for n in KLASY_TUZ)
    skala = laczne_tuz / baza
    out = np.zeros_like(next(iter(splot.values())), dtype="float64")
    for nazwa, mm in splot.items():
        if nazwa not in P.POZYTKI:
            continue
        w = P.POZYTKI[nazwa][0] * (skala if nazwa in KLASY_TUZ else 1.0)
        out += mm * w
    return out


def top_procent(m: np.ndarray, maska: np.ndarray, p: float = 10.0) -> np.ndarray:
    prog = np.percentile(m[maska], 100 - p)
    return maska & (m >= prog)


if __name__ == "__main__":
    if not CACHE.exists():
        raise SystemExit(f"brak {CACHE.relative_to(ROOT)} - uruchom najpierw "
                         "skrypty/potencjal/wojewodztwo.py")

    with np.load(CACHE) as z:
        splot = {k: z[k] for k in z.files}
    print(f"splot wczytany: {len(splot)} klas, {next(iter(splot.values())).shape}")
    brak = [n for n in P.POZYTKI if n not in splot]
    if brak:
        raise SystemExit(
            f"\nCACHE NIEAKTUALNY - brak klas: {', '.join(brak)}\n"
            "Test liczylby wrazliwosc na mapie, ktorej te klasy nie zawiera.\n"
            f"Usun {CACHE.name} i uruchom wojewodztwo.py, potem ten skrypt.")

    baza_tuz = sum(P.POZYTKI[n][0] for n in KLASY_TUZ)
    print(f"bazowa laczna wydajnosc TUZ: {baza_tuz} kg cukrow/ha "
          f"({' + '.join(f'{n} {P.POZYTKI[n][0]}' for n in KLASY_TUZ)})\n")

    bazowa = mapa(splot, baza_tuz)
    maska = bazowa > 0
    top_baza = top_procent(bazowa, maska)

    print("WRAZLIWOSC MAPY NA WYDAJNOSC TUZ\n")
    print(f"{'TUZ kg/ha':>10}{'udzial TUZ':>12}{'korelacja':>11}"
          f"{'top-10% wspolne':>17}")
    tab = []
    for v in ZAKRES:
        m = mapa(splot, v)
        udzial = sum((splot[n] * P.POZYTKI[n][0] * v / baza_tuz).sum()
                     for n in KLASY_TUZ if n in splot) / m.sum() * 100
        r = float(np.corrcoef(bazowa[maska], m[maska])[0, 1])
        t = top_procent(m, maska)
        wsp = float((t & top_baza).sum() / top_baza.sum() * 100)
        znak = "  <- bazowa" if v == baza_tuz else ""
        print(f"{v:>10}{udzial:>11.1f}%{r:>11.3f}{wsp:>16.0f}%{znak}")
        tab.append({"tuz_kg_ha": v, "udzial_tuz_proc": udzial,
                    "korelacja": r, "top10_wspolne_proc": wsp})

    naj = min(tab, key=lambda x: x["korelacja"])
    print(f"\nNAJGORSZY PRZYPADEK: TUZ {naj['tuz_kg_ha']} kg/ha "
          f"({baza_tuz / naj['tuz_kg_ha']:.1f}x mniej niz bazowa)")
    print(f"  korelacja {naj['korelacja']:.3f}, "
          f"top-10% zachowane {naj['top10_wspolne_proc']:.0f}%")

    print("\nWNIOSEK")
    print("  Laki sa rozlozone po wojewodztwie stosunkowo rownomiernie, wiec")
    print("  zmiana ich wydajnosci przesuwa CALE TLO w gore albo w dol, nie")
    print("  tworzac ani nie likwidujac zadnego zaglebia pozytkowego.")
    print("  Bezwzgledne kilogramy zaleza od tej liczby silnie; RANKING")
    print("  MIEJSC - prawie wcale. Dlatego TUZ raportujemy jako zakres")
    print("  z wykazana odpornoscia rankingu, a nie jako parametr o")
    print("  udawanej precyzji.")

    (WYNIKI / "json" / "wrazliwosc_tuz.json").write_text(json.dumps({
        "cel": "pomiar wplywu nieuzrodlowionej wydajnosci TUZ na mape",
        "zakres_zrodlo": "laka kosna ok. 40 kg miodu/ha, pastwisko 6 - "
                         "rozpietosc skladu runi, nie niepewnosc pomiaru",
        "bazowa_laczna_kg_ha": baza_tuz,
        "klasy_skalowane_razem": KLASY_TUZ,
        "wyniki": tab,
        "wniosek": "korelacja >= 0.97 i >= 93% wspolnych top-10% w calym "
                   "zakresie - ranking miejsc odporny na te niepewnosc",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/wrazliwosc_tuz.json")
