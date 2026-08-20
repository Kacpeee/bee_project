"""
Czy JS w prognoza.html liczy TO SAMO, co model_fenologiczny.py.

PO CO
Naglowek model_fenologiczny.py mowi wprost: gdyby serwis mial wlasna kopie
obliczen, po pierwszej poprawce konsola i API zaczelyby dawac rozne
odpowiedzi. Strona statyczna lamie te zasade z koniecznosci - bez Pythona
model musi istniec takze w JS. Skoro nie da sie tego uniknac, trzeba to
MIERZYC, a nie zakladac.

JAK
Ten sam zestaw punktow przechodzi przez Pythona i przez JS wykonany
w przegladarce (Edge w trybie headless). Porownywane sa pola, ktore widzi
uzytkownik: data pelni, niepewnosc, procent realnej pogody, stan akumulacji.
Rozbieznosc w KTORYMKOLWIEK z nich to blad - test konczy sie kodem 1.

Uruchomienie:
    python skrypty/serwis/test_rownowaznosc.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

from model_fenologiczny import prognozuj  # noqa: E402

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# punkty rozrzucone po wojewodztwie - rozne dlugosci i szerokosci,
# zeby zlapac ewentualny blad przycinania do siatki
PUNKTY = [
    (51.25, 22.57),   # okolice Lublina - lat dokladnie na polowce siatki
    (50.70, 23.25),   # poludniowy wschod - lon na polowce
    (51.80, 22.10),   # polnocny zachod
    (51.05, 23.40),   # wschod
    (52.10, 22.90),   # polnoc
    # PUNKTY PULAPKOWE: obie wspolrzedne koncza sie na .x5, czyli dokladnie
    # w polowie komorki siatki 0,1 stopnia. Tam Python (polowka do parzystej)
    # i JS (polowka w gore) zaokraglaly w rozne strony. Bez tych punktow
    # blad wychodzil tylko przypadkiem.
    (51.15, 22.25),
    (50.85, 23.15),
    (51.35, 22.45),
    (51.45, 22.35),
]

# SEZONY MINIONE - osobna sciezka kodu.
# Strona pozwala przelaczyc rok, a wtedy model dostaje komplet pogody
# i inaczej liczy postep akumulacji (do dnia kwitnienia, nie do dzisiaj).
# Bez tych przypadkow przelacznik bylby niesprawdzony.
PUNKTY_LATA = [
    (51.25, 22.57, 2026),
    (51.25, 22.57, 2025),
    (50.70, 23.25, 2024),
    (51.80, 22.10, 2023),
]

# pola, ktore uzytkownik widzi na ekranie
POLA = [
    ("pelnia.opis", lambda d: d["pelnia"]["opis"]),
    ("pelnia.doy", lambda d: d["pelnia"]["doy"]),
    ("niepewnosc_dni", lambda d: d["niepewnosc_dni"]),
    ("pogoda_realna_pct", lambda d: d["pogoda_realna_pct"]),
    ("rodzaj", lambda d: d["rodzaj"]),
    ("podstawa_bledu", lambda d: d["podstawa_bledu"]),
    ("ustaw_ul.opis", lambda d: d["ustaw_ul"]["opis"]),
    ("postep.gdd_teraz", lambda d: d["postep"]["gdd_teraz"]),
    ("postep.procent", lambda d: d["postep"]["procent"]),
    ("przedzial.od", lambda d: d["przedzial"]["od"]),
    ("przedzial.do", lambda d: d["przedzial"]["do"]),
]


def js_wyniki(punkty: list[tuple[float, float]]) -> list[dict]:
    """Uruchamia funkcje z prognoza.html w przegladarce i zbiera wyniki."""
    # PIERWSZY blok <script> to wstawka eksportu: dane warstwy + model.
    # Drugi to interfejs strony, ktory wymaga DOM-u mapy i w tescie jest
    # zbedny. Czytamy z gotowego pliku, a nie z model_prognozy.js, zeby
    # sprawdzac to, co naprawde trafia do uzytkownika - razem z podstawionymi
    # parametrami.
    strona = (ROOT / "prognoza.html").read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", strona, re.S)
    if not m or "async function prognozuj" not in m.group(1):
        raise SystemExit("nie znaleziono bloku modelu w prognoza.html")
    kod = m.group(1)

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "t.html").write_text(
            "<!doctype html><meta charset=\"utf-8\"><body><pre id=\"o\"></pre>"
            "<script>\n" + kod + "\n"
            "const PUNKTY = " + json.dumps(punkty) + ";\n"
            "(async () => {\n"
            "  const wyn = [];\n"
            "  for (const p of PUNKTY) {\n"
            "    try { wyn.push(await prognozuj(p[0], p[1], p[2] || null)); }\n"
            "    catch (e) { wyn.push({blad: String(e)}); }\n"
            # ODSTEP MIEDZY PUNKTAMI - bez niego test sam wywolywal 429
            # u Open-Meteo i zglaszal blad strony zamiast rozbieznosci modeli.
            "    await new Promise(s => setTimeout(s, 900));\n"
            "  }\n"
            "  document.getElementById('o').textContent =\n"
            "    'WYNIK_START' + JSON.stringify(wyn) + 'WYNIK_KONIEC';\n"
            "})();\n</script>", encoding="utf-8")

        r = subprocess.run(
            [str(EDGE), "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={t / 'profil'}",
             "--virtual-time-budget=120000", "--dump-dom",
             (t / "t.html").as_uri()],
            capture_output=True, text=True, encoding="utf-8", timeout=300)

    dom = r.stdout or ""
    m = re.search(r"WYNIK_START(.*?)WYNIK_KONIEC", dom, re.S)
    if not m:
        raise SystemExit(
            "przegladarka nie zwrocila wyniku - sprawdz polaczenie z sieci\n"
            + dom[-600:])
    tekst = m.group(1)
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        tekst = tekst.replace(a, b)
    return json.loads(tekst)


if __name__ == "__main__":
    if not EDGE.exists():
        raise SystemExit(f"brak przegladarki: {EDGE}")
    if not (ROOT / "prognoza.html").exists():
        raise SystemExit("brak prognoza.html - uruchom eksport_statyczny.py")

    # sezon domyslny: (lat, lon); sezon wybrany: (lat, lon, rok)
    wszystkie = [(la, lo, None) for la, lo in PUNKTY] + PUNKTY_LATA
    print(f"punktow: {len(wszystkie)} "
          f"({len(PUNKTY)} sezon domyslny, {len(PUNKTY_LATA)} sezony wybrane)\n")
    print("liczenie w JS (przegladarka)...")
    js = js_wyniki([[la, lo] if r is None else [la, lo, r]
                    for la, lo, r in wszystkie])
    print("liczenie w Pythonie...")
    py = [prognozuj(la, lo, r) for la, lo, r in wszystkie]

    rozne = 0
    for (lat, lon, _r), a, b in zip(wszystkie, py, js):
        if "blad" in b:
            print(f"\n{lat} {lon}  JS BLAD: {b['blad']}")
            rozne += 1
            continue
        zle = []
        for nazwa, f in POLA:
            wa, wb = f(a), f(b)
            if isinstance(wa, float) or isinstance(wb, float):
                zgoda = abs(float(wa) - float(wb)) < 1e-6
            else:
                zgoda = wa == wb
            if not zgoda:
                zle.append(f"{nazwa}: python={wa!r} js={wb!r}")
        stan = "ZGODNE" if not zle else "ROZNICA"
        print(f"\n{lat} {lon}  {stan}   "
              f"pelnia {a['pelnia']['opis']} ±{a['niepewnosc_dni']} d, "
              f"pogoda realna {a['pogoda_realna_pct']}%")
        for z in zle:
            print(f"    {z}")
        rozne += bool(zle)

    print("\n" + "=" * 58)
    if rozne:
        print(f"NIEZGODNOSC w {rozne} z {len(wszystkie)} punktow")
        sys.exit(1)
    print(f"WSZYSTKIE {len(wszystkie)} PUNKTOW ZGODNE "
          f"({len(POLA)} pol kazdy) - JS liczy to samo, co Python")
