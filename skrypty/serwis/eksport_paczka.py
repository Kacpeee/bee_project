"""
Paczka stron dzialajacych z dysku - bez Pythona, bez serwera, bez danych.

PROBLEM
Mikroserwis wymaga Pythona, Flaska i ~4,6 GB danych, ktorych NIE MA
w repozytorium (dane/, wyniki/cache/, wyniki/rastry/ sa w .gitignore).
Kto pobierze projekt, nie uruchomi serwisu - zabraknie mu kalendarz_dane.json
i rastrow. Do tego raport, mechanika i kalendarz nie linkowaly do siebie
nawzajem: nawigacje dorabial serwer przy wysylaniu strony.

CO ROBI TEN SKRYPT
  1. buduje prognoza.html (obliczenia w przegladarce, pogoda z Open-Meteo)
  2. wstawia do wszystkich stron te sama nawigacje, ale na NAZWY PLIKOW
     zamiast tras serwera, wiec dziala takze przez file://
  3. pisze index.html - punkt wejscia dla kogos, kto dostal katalog

Wstawka jest oznaczona znacznikiem i usuwana przed ponownym wstawieniem,
wiec skrypt mozna uruchamiac wielokrotnie bez mnozenia paskow nawigacji.

Uruchomienie:
    python skrypty/serwis/eksport_paczka.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

import serwis  # noqa: E402
from eksport_statyczny import buduj  # noqa: E402

ZNACZNIK = "<!--paczka-nawigacja-->"

STRONY = [
    ("prognoza.html", "Prognoza", "kiedy zakwitnie rzepak w wybranym miejscu"),
    ("kalendarz.html", "Kalendarz", "co i kiedy kwitnie w każdym powiecie"),
    ("raport.html", "Raport", "pełne wyniki, walidacje i zastrzeżenia"),
    ("mechanika.html", "Jak to działa", "krok po kroku, skąd biorą się liczby"),
]


def styl_nawigacji() -> str:
    """Arkusz paska nawigacji prosto z serwis.py - jedno zrodlo wygladu.

    Zakres ograniczony do .appnav, bo bez tego reguly globalne (body,
    button, table) nadpisywaly wlasny styl kalendarza i strona sie sypala.
    """
    return serwis.STYL_NAW


def pasek(akt: str) -> str:
    linki = "".join(
        f'<a href="{p}"{" class=\'akt\'" if p == akt else ""}>{n}</a>'
        for p, n, _ in STRONY)
    return (f'{ZNACZNIK}<nav class="appnav"><div class="in"><span class="logo">'
            f'<span class="kropka"></span>Model pożytkowy · Lubelskie</span>'
            f'{linki}</div></nav>')


def wstaw(plik: Path, akt: str) -> bool:
    if not plik.exists():
        return False
    h = plik.read_text(encoding="utf-8")
    # usun poprzednia wstawke, zeby paski sie nie mnozyly przy kolejnym uruchomieniu
    h = re.sub(re.escape(ZNACZNIK) + r"<nav class=\"appnav\">.*?</nav>", "",
               h, flags=re.S)
    h = h.replace(f'<style>{styl_nawigacji()}</style>', "")

    wstawka = f"<style>{styl_nawigacji()}</style>{pasek(akt)}"
    i = h.lower().find("<body")
    if i >= 0:
        j = h.index(">", i) + 1
        h = h[:j] + wstawka + h[j:]
    else:
        # strony bez <body> - wstawiamy po bloku <style> naglowka,
        # zeby pasek nie wyladowal przed <meta charset>
        m = re.search(r"</style>", h)
        h = (h[:m.end()] + wstawka + h[m.end():]) if m else wstawka + h
    plik.write_text(h, encoding="utf-8")
    return True


def index() -> str:
    kafle = "".join(
        f'<a class="kafel" href="{p}"><b>{n}</b><span>{o}</span></a>'
        for p, n, o in STRONY)
    return f"""<!doctype html><html lang="pl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Model pożytkowy — Lubelskie</title>
<style>{serwis.STYL}
 .kafel{{display:block;background:var(--kar);border:1px solid var(--ram);
   box-shadow:var(--cien);border-radius:12px;padding:18px 20px;margin:0 0 12px;
   text-decoration:none;color:var(--atr)}}
 .kafel:hover{{border-color:var(--akc)}}
 .kafel b{{display:block;font-size:17px;margin-bottom:3px}}
 .kafel span{{color:var(--mut);font-size:14px}}
 .uwaga{{background:#fdf6e6;border-left:3px solid var(--akc2);padding:12px 15px;
   border-radius:0 7px 7px 0;font-size:14px;color:#6b5416;margin:22px 0 0}}
</style>
<div class="w">
<h1>Model pożytkowy — województwo lubelskie</h1>
<p class="pod">Gdzie postawić ul i kiedy zakwitnie rzepak. Wszystkie strony
otwierają się z dysku — nie trzeba niczego instalować.</p>
{kafle}
<p class="uwaga"><b>Prognoza</b> pobiera aktualną pogodę z Open-Meteo, więc
potrzebuje internetu. Pozostałe trzy strony działają całkowicie bez sieci.</p>
</div>
"""


if __name__ == "__main__":
    (ROOT / "prognoza.html").write_text(buduj(), encoding="utf-8")
    print("zbudowano prognoza.html")

    brak = []
    for p, n, _ in STRONY:
        if wstaw(ROOT / p, p):
            print(f"  nawigacja -> {p}")
        else:
            brak.append(p)

    (ROOT / "index.html").write_text(index(), encoding="utf-8")
    print("zapisano index.html")

    razem = sum((ROOT / p).stat().st_size
                for p, _, _ in STRONY if (ROOT / p).exists())
    razem += (ROOT / "index.html").stat().st_size
    print(f"\npaczka: {razem / 1e6:.1f} MB, punkt wejscia index.html")
    if brak:
        print(f"BRAKUJE: {', '.join(brak)} - uruchom generatory tych stron")
        sys.exit(1)
