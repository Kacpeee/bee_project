"""
Czy strony paczki otwieraja sie z dysku i nie sypia bledem JavaScriptu.

PO CO
Wiekszosc bledow w tym projekcie byla CICHA - nic nie rzucalo wyjatku,
a wynik wygladal sensownie. Na stronach bylo tak samo: znikajacy backslash
w JS wywalal cala prognoze, wstrzykniety arkusz nadpisywal styl kalendarza,
a ciemny motyw gasil przyciski. Za kazdym razem znajdowal to czlowiek
patrzacy na ekran, nie ja czytajacy kod. To jest proba zautomatyzowania
tego spojrzenia.

CO SPRAWDZA
  - strona otwiera sie przez file:// (tak jak po pobraniu projektu)
  - konsola nie zglasza bledu ("Uncaught", "SyntaxError")
  - w wyrenderowanym DOM sa znaczniki tresci, ktore MUSZA tam byc
  - pasek nawigacji jest dokladnie jeden i prowadzi do istniejacych plikow

Uruchomienie:
    python skrypty/serwis/test_strony.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# tresc, ktora musi sie pojawic w wyrenderowanej stronie
STRONY = {
    "index.html": ["Model pożytkowy", "Prognoza", "Kalendarz", "Raport"],
    # mapa jest RYSOWANA na canvas z warstw kalendarza, nie wtapiana
    # jako PNG - wczesniejsza wersja uzywala porzuconego renderera
    "prognoza.html": ["Kiedy zakwitnie rzepak", "Detekcja satelitarna",
                      "Deklaracje ARiMR", "id=\"raster\"", "id=\"lasso\"",
                      "lata-sat", "lata-gsa"],
    "kalendarz.html": ["Kalendarz", "kwitnien"],
    "raport.html": ["Co liczy", "Modele"],
    "mechanika.html": ["Jak to działa", "GDD"],
}


def renderuj(plik: Path) -> tuple[str, str]:
    """Zwraca (DOM po wykonaniu JS, log konsoli)."""
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [str(EDGE), "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={Path(tmp) / 'p'}",
             "--enable-logging=stderr", "--v=0",
             "--virtual-time-budget=8000", "--dump-dom", plik.as_uri()],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180)
    return r.stdout or "", r.stderr or ""


if __name__ == "__main__":
    if not EDGE.exists():
        raise SystemExit(f"brak przegladarki: {EDGE}")

    zle = 0
    for nazwa, wymagane in STRONY.items():
        plik = ROOT / nazwa
        if not plik.exists():
            print(f"{nazwa:16s} BRAK PLIKU")
            zle += 1
            continue

        dom, log = renderuj(plik)
        uwagi = []

        bledy = [w for w in ("Uncaught", "SyntaxError", "is not defined",
                             "is not a function")
                 if w in log or w in dom]
        if bledy:
            uwagi.append("blad JS: " + ", ".join(bledy))
            for lin in log.splitlines():
                if any(b in lin for b in bledy):
                    uwagi.append("   " + lin.strip()[:150])
                    break

        brak = [w for w in wymagane if w not in dom]
        if brak:
            uwagi.append(f"brak tresci: {brak}")

        n_nav = len(re.findall(r'class="appnav"', dom))
        if nazwa != "index.html" and n_nav != 1:
            uwagi.append(f"paskow nawigacji: {n_nav} (ma byc 1)")

        for cel in re.findall(r'<a[^>]*href="([a-z_]+\.html)"', dom):
            if not (ROOT / cel).exists():
                uwagi.append(f"link do nieistniejacego {cel}")

        stan = "OK" if not uwagi else "BLAD"
        print(f"{nazwa:16s} {stan:5s} {plik.stat().st_size / 1e6:5.1f} MB  "
              f"nav={n_nav}")
        for u in uwagi:
            print(f"   {u}")
        zle += bool(uwagi)

    print("\n" + "=" * 52)
    if zle:
        print(f"BLEDY na {zle} z {len(STRONY)} stron")
        sys.exit(1)
    print(f"WSZYSTKIE {len(STRONY)} STRON OTWIERAJA SIE POPRAWNIE Z DYSKU")
