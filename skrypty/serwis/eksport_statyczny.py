"""
Eksport strony prognozy do POJEDYNCZEGO PLIKU HTML, ktory dziala z dysku.

PO CO
Mikroserwis wymaga Pythona, Flaska i ~4,6 GB danych, ktorych nie ma
w repozytorium (dane/, wyniki/cache/, wyniki/rastry/ sa w .gitignore).
Kto pobierze projekt, NIE URUCHOMI wiec serwisu. Raport, mechanika
i kalendarz sa samowystarczalnymi plikami HTML; prognoza byla jedyna
czescia, ktora tego nie potrafila.

JEDNO ZRODLO STRONY
Ta wersja NIE ma wlasnego interfejsu. Bierze doslownie STRONA z serwis.py
i podmienia w niej dwie rzeczy, ktorych nie ma bez serwera:

    fetch("/warstwa/rzepak.json")  ->  dane wtopione w plik
    fetch("/prognoza_obszar")      ->  model policzony w przegladarce

Pierwsza wersja tego eksportu miala wlasny szablon z mapa PNG
(warstwa_rzepak.py) i lassem. Byl to renderer JUZ PORZUCONY - docstring
trasy /warstwa/rzepak.json mowi wprost, ze dawal "ziarnista, nieczytelna
mape" i zostal zastapiony warstwami kalendarza. Statyczna strona pokazywala
wiec stara mape bez przelacznikow lat, podczas gdy serwis mial nowa.
Stad ta zasada: interfejs jest jeden, tak jak model jest jeden.

RYZYKO
Model istnieje w dwoch jezykach - przed tym ostrzega naglowek
model_fenologiczny.py. Dlatego zaden parametr nie jest tu wpisany na
sztywno (ida z wyniki/json/), a zgodnosc sprawdza test_rownowaznosc.py.

Uruchomienie:
    python skrypty/serwis/eksport_statyczny.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
sys.path.insert(0, str(Path(__file__).parent))

import serwis  # noqa: E402
from model_fenologiczny import dz, parametry  # noqa: E402

# ta sama tresc, ktora zwraca trasa /warstwa/rzepak.json
KALENDARZ = WYNIKI / "cache" / "kalendarz_dane.json"


def warstwa() -> dict:
    """Warstwy rzepaku z kalendarza - te same, ktore podaje serwis."""
    if not KALENDARZ.exists():
        raise SystemExit(
            "brak wyniki/cache/kalendarz_dane.json - uruchom najpierw "
            "python skrypty/kalendarz/eksport_interaktywny.py")
    d = json.loads(KALENDARZ.read_text(encoding="utf-8"))
    return {
        "nx": d["nx"], "ny": d["ny"], "px_km": d["px_km"],
        "maska": d["maska"], "granica": d["granica"], "miasta": d["miasta"],
        "geo": d["geo"], "paleta": d["paleta"], "rzepak_kg": d["rzepak_kg"],
        "deklaracje": {"lata": d["rolnicy"]["lata"],
                       "warstwy": d["rolnicy"]["rzepak"],
                       "skala": d["rolnicy"]["rzepak_skala"]},
        "detekcja": {"lata": d["satelita"]["lata"],
                     "warstwy": d["satelita"]["rzepak"],
                     "skala": d["satelita"]["rzepak_skala"]},
    }


def model_js() -> str:
    """Model fenologiczny w JS - odpowiednik model_fenologiczny.prognozuj.

    Zwraca obiekt o TYM SAMYM ksztalcie, co /prognoza_obszar, zeby kod
    rysujacy wynik w STRONA nie wymagal ani jednej zmiany.
    """
    p = parametry()
    m = json.dumps({
        "baza": p["baza"], "prog": p["prog"], "start_doy": p["start_doy"],
        "rmse_modelu": round(p["rmse_modelu"], 2),
        "n_obserwacji": p["n_obserwacji"],
        "bledy_prognozy": p["bledy_prognozy"],
        "sredni_termin": p["sredni_termin"],
        "przed_pelnia": p["przed_pelnia"], "po_pelni": p["po_pelni"],
    }, ensure_ascii=False)
    js = (Path(__file__).parent / "model_prognozy.js").read_text(encoding="utf-8")
    return js.replace("__MODEL__", m).replace("__START__", dz(p["start_doy"], 2026))


def buduj() -> str:
    h = serwis.STRONA

    # 1. warstwa mapy - zamiast pobierania z serwera
    stare = 'fetch("/warstwa/rzepak.json").then(r => r.json())'
    if stare not in h:
        raise SystemExit("nie znaleziono pobrania warstwy w STRONA")
    h = h.replace(stare, "Promise.resolve(WARSTWA)")

    # 2. prognoza - zamiast POST do serwera
    stare = ('fetch("/prognoza_obszar", {method: "POST",\n'
             '    headers: {"Content-Type": "application/json"},\n'
             '    body: JSON.stringify({punkty, rok: rok || null})})\n'
             '   .then(r => r.json())')
    if stare not in h:
        raise SystemExit("nie znaleziono wywolania prognozy w STRONA")
    h = h.replace(stare, "prognozaLokalna(punkty, rok || null)")

    # 3. wlasny pasek nawigacji STRONA (NAW("/")) - do usuniecia.
    # Paczka wstawia swoj, na nazwy plikow zamiast tras serwera. Gdyby
    # zostawic oba, prognoza mialaby dwa paski, a ten z serwisu prowadzilby
    # pod adresy, ktorych bez serwera nie ma.
    h = re.sub(r'<nav class="appnav">.*?</nav>', "", h, count=1, flags=re.S)

    # 4. odnosniki serwera -> nazwy plikow (strona dziala przez file://)
    for a, b in (('href="/kalendarz"', 'href="kalendarz.html"'),
                 ('href="/raport"', 'href="raport.html"'),
                 ('href="/mechanika"', 'href="mechanika.html"'),
                 ('href="/"', 'href="prognoza.html"')):
        h = h.replace(a, b)

    # 5. dane i model wstrzykniete przed skryptem strony
    wstawka = ("<script>\nconst WARSTWA = "
               + json.dumps(warstwa(), ensure_ascii=False, separators=(",", ":"))
               + ";\n" + model_js() + "\n</script>\n")
    h = h.replace("<script>", wstawka + "<script>", 1)

    if "fetch(" in h.split("</script>")[-2]:
        pass  # dopuszczalne: pozostale fetch to tylko Open-Meteo
    zostalo = re.findall(r'fetch\("/', h)
    if zostalo:
        raise SystemExit(f"w stronie zostalo {len(zostalo)} odwolan do serwera")
    return h


if __name__ == "__main__":
    html = buduj()
    wyj = ROOT / "prognoza.html"
    wyj.write_text(html, encoding="utf-8")
    print(f"zapisano {wyj.name}: {len(html.encode()) / 1e6:.1f} MB")
    print("  interfejs wziety z serwis.py STRONA - jeden zrodlowy uklad")
