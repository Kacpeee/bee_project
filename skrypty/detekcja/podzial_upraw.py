"""
Podzial pozytkow na WEDRUJACE i NIEWEDRUJACE - i wynikajacy z niego wybor
zrodla dla kazdej warstwy mapy.

ZASADA
Nie kazda uprawa wymaga detekcji satelitarnej, i nie kazda sie jej poddaje.
Rozstrzyga jedno pytanie: czy roslina zmienia miejsce z roku na rok?

  WEDRUJACE (plodozmian)     - konkretne pola zmieniaja sie co sezon, wiec
                               deklaracje sprzed roku sa bezuzyteczne.
                               Detekcja z satelity jest JEDYNYM zrodlem.
  NIEWEDRUJACE (trwale)      - malinnik posadzony w 2019 stoi tam w 2025.
                               Deklaracje z dowolnego roku sa poprawne,
                               a detekcja nic nie wnosi.

DOWOD, NIE ZALOZENIE
Kazdy przydzial oparty jest na tescie przenoszenia (transfer_s1s2.json):
model uczony na 2025 sprawdzany na 2026, porownany z odniesieniem "roslo tam,
gdzie rok temu". Detekcja trafia do warstwy satelitarnej tylko wtedy, gdy to
odniesienie POBIJA - inaczej jest gorsza od zwyklego przepisania deklaracji.

DLACZEGO TRWALE SIE NIE PODDAJA
Metoda opiera sie na szeregu czasowym: rozpoznaje rosline po tym, JAK zmienia
sie przez sezon. Malina, porzeczka i sad przez caly rok wygladaja tak samo -
zielone, bez golej gleby, bez wyraznego momentu. Szereg nie ma czego
rozrozniac. Odrozniloby je dopiero rozroznienie STRUKTURY (rzedy pedow co 3 m
kontra zwarte krzaki), a to jest ponizej 10 m piksela Sentinela - informacja
fizycznie nie dociera do modelu i zadna architektura jej nie wydobedzie.

Symetria warta zapamietania:
  uprawy roczne  - potrzebuja SZEREGU CZASOWEGO, rozdzielczosc mniej wazna
  uprawy trwale  - potrzebuja ROZDZIELCZOSCI, szereg nic nie daje
Nasza metoda jest zbudowana pod pierwsze, wiec na drugich zawodzi z definicji.
"""

from __future__ import annotations

# gatunek -> (r modelu, r odniesienia "gdzie rok temu", uzasadnienie)
WEDRUJACE = {
    "rzepak ozimy":    (0.958, 0.338, "plodozmian; model bije pamiec 3x NA POZIOMIE DZIALEK - dla mapy "
                        "regionalnej pamiec daje 0.795, model 0.991"),
    "gryka zwyczajna": (0.859, 0.750, "siana pozno, kwitnie w VII"),
    "słonecznik":      (0.850, 0.814, "rusza i schnie najpozniej"),
}

NIEWEDRUJACE = {
    "malina":              (0.878, 0.847, "przewaga pozorna: po kalibracji "
                                          "areal skacze 7x miedzy latami"),
    "porzeczka":           (0.798, 0.845, "pamiec lepsza"),
    "Sad":                 (0.788, 0.460, "model lepszy, ale ponizej progu"),
    "TUZ":                 (0.627, 0.432, "ponizej progu"),
    "motylkowe pastewne":  (0.780, 0.829, "pamiec lepsza"),
    "fasola wielokwiatowa": (0.880, 0.949, "uprawa specjalistyczna, te same "
                                           "pola pod Hrubieszowem"),
    "bobik":               (0.810, 0.817, "pamiec nieznacznie lepsza"),
    "gorczyca":            (0.610, 0.625, "pamiec lepsza"),

    # --- gatunki BEZ WLASNEGO TESTU PRZENOSZENIA ---------------------------
    # Ponizsze nie maja szeregu satelitarnego, bo klasyfikator wielogatunkowy
    # albo ich nie wyroznia, albo maja za malo dzialek na wiarygodny test.
    # Z braku pomiaru NIE WOLNO ich wrzucic do warstwy satelitarnej - ida
    # z deklaracji, gdzie sa prawda ewidencyjna.
    #
    # DLACZEGO TO TU DOPISANO: gatunek nieobecny w ZADNEJ z dwoch list
    # wypadal z produktu koncowego bez sladu, bo zloz_calosc.py iteruje
    # po WEDRUJACE i NIEWEDRUJACE. Tak gubilo sie 12.4% cukrow, w tym
    # drugi pokos TUZ (9.4%). Straznik ponizej pilnuje, zeby sie nie
    # powtorzylo.
    "TUZ odrost":          (None, None, "drugi pokos tej samej laki co TUZ; "
                                        "dzieli z nia geometrie i warstwe"),
    "koniczyna czerwona":  (None, None, "roslina wieloletnia, malo dzialek"),
    "lucerna mieszańcowa": (None, None, "roslina wieloletnia, malo dzialek"),
    "gorczyca biała":      (None, None, "wchodzi w klase zbiorcza 'gorczyca'"),
    "słonecznik oleisty":  (None, None, "wchodzi w klase zbiorcza 'slonecznik'"),
    "rzepak jary":         (None, None, "odrzucony z klasyfikatora - mylil sie "
                                        "z rzepakiem ozimym"),
}


def sprawdz_kompletnosc(pozytki) -> None:
    """Kazdy pozytek musi nalezec do dokladnie jednej warstwy.

    Bez tego gatunek dodany do POZYTKI, a niedopisany tutaj, znikalby
    z mapy koncowej po cichu - suma policzylaby sie bez bledu.
    """
    brak = [n for n in pozytki if n not in WEDRUJACE and n not in NIEWEDRUJACE]
    obie = [n for n in WEDRUJACE if n in NIEWEDRUJACE]
    if brak or obie:
        raise SystemExit(
            "PODZIAL WARSTW NIEKOMPLETNY"
            + (" | bez warstwy: " + ", ".join(brak) if brak else "")
            + (" | w obu naraz: " + ", ".join(obie) if obie else ""))

# udzial w cukrach wojewodztwa (%)
CUKIER = {
    "rzepak ozimy": 57.2, "gryka zwyczajna": 6.1, "słonecznik": 0.8,
    "TUZ": 18.4, "malina": 6.3, "fasola wielokwiatowa": 5.1,
    "porzeczka": 2.5, "motylkowe pastewne": 1.7, "Sad": 0.3,
    "gorczyca": 0.3, "bobik": 0.1,
}


def podsumowanie() -> str:
    w = sum(CUKIER.get(n, 0) for n in WEDRUJACE)
    n_ = sum(CUKIER.get(n, 0) for n in NIEWEDRUJACE)
    return (f"z satelity: {w:.1f}% cukru ({len(WEDRUJACE)} gatunki)\n"
            f"z deklaracji: {n_:.1f}% cukru ({len(NIEWEDRUJACE)} gatunkow)")


if __name__ == "__main__":
    print(podsumowanie(), "\n")
    for tytul, grupa in (("WEDRUJACE - warstwa satelitarna", WEDRUJACE),
                         ("NIEWEDRUJACE - warstwa deklaracyjna", NIEWEDRUJACE)):
        print(f"{tytul}\n{'gatunek':24s}{'model':>8}{'pamiec':>8}"
              f"{'cukier':>8}  uzasadnienie")
        for n, (rm, rp, opis) in sorted(
                grupa.items(), key=lambda x: -CUKIER.get(x[0], 0)):
            print(f"{n[:22]:24s}{rm:>8.3f}{rp:>8.3f}"
                  f"{CUKIER.get(n, 0):>7.1f}%  {opis}")
        print()
