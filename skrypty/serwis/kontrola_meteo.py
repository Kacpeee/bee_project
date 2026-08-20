"""
KONTROLA DANYCH METEO - czy reanaliza zgadza sie z pomiarem ze stacji.

PO CO
Model fenologiczny stoi na reanalizie ERA5 (Open-Meteo), nie na pomiarach
z polskich stacji. Zwalidowalismy ja historycznie - 962 dni wobec stacji
Zamosc 595, RMSE 1.13 K, r = 0.986. Ale to walidacja SPRZED lat; nic nie
mowi, czy reanaliza nie odjezdza w BIEZACYM sezonie.

IMGW udostepnia darmowe API z pomiarem godzinowym, bez klucza:
    https://danepubliczne.imgw.pl/api/data/synop

W wojewodztwie lubelskim sa cztery stacje synoptyczne. Ten skrypt porownuje
ich biezacy odczyt z tym, co dla tych samych wspolrzednych i tej samej
godziny podaje Open-Meteo.

CZEGO TO NIE ZASTAPI
Endpoint IMGW zwraca WYLACZNIE biezacy odczyt - nie ma historii. Nie da sie
z niego zbudowac sumy temperatur od 15 marca, wiec nie zastapi reanalizy
jako zrodla. Sluzy do kontroli, nie do liczenia.

Uruchomienie:
    python skrypty/serwis/kontrola_meteo.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

# stacje synoptyczne IMGW w wojewodztwie lubelskim i okolicy
STACJE = {
    "Lublin":    (51.216, 22.394),
    "Zamość":    (50.700, 23.250),
    "Włodawa":   (51.550, 23.530),
    "Terespol":  (52.070, 23.620),
}
PROG_OSTRZEZENIA_K = 2.0     # powyzej tego roznica warta uwagi


def imgw() -> dict[str, dict]:
    r = requests.get("https://danepubliczne.imgw.pl/api/data/synop", timeout=60)
    r.raise_for_status()
    out = {}
    for x in r.json():
        n = x["stacja"]
        if n in STACJE and x.get("temperatura") is not None:
            out[n] = {"T": float(x["temperatura"]),
                      "data": x["data_pomiaru"],
                      "godz": int(x["godzina_pomiaru"]),
                      "id": x["id_stacji"]}
    return out


def openmeteo(lat: float, lon: float, dzien: str, godz: int) -> float | None:
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "hourly": "temperature_2m",
        "past_days": 3, "forecast_days": 2,
        "timezone": "Europe/Warsaw"}, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    cel = f"{dzien}T{godz:02d}:00"
    for t, v in zip(h["time"], h["temperature_2m"]):
        if t == cel:
            return None if v is None else float(v)
    return None


if __name__ == "__main__":
    print("KONTROLA: reanaliza Open-Meteo wobec pomiaru IMGW\n")
    st = imgw()
    if not st:
        raise SystemExit("IMGW nie zwrocilo danych dla stacji lubelskich")

    print(f"{'stacja':12s}{'godzina':>18}{'IMGW':>8}{'Open-Meteo':>12}"
          f"{'roznica':>10}")
    wiersze, roznice = [], []
    for n, (lat, lon) in STACJE.items():
        if n not in st:
            print(f"{n:12s}{'brak odczytu':>18}")
            continue
        s = st[n]
        om = openmeteo(lat, lon, s["data"], s["godz"])
        if om is None:
            print(f"{n:12s}{s['data'] + ' ' + str(s['godz']) + ':00':>18}"
                  f"{s['T']:>8.1f}{'brak':>12}")
            continue
        d = om - s["T"]
        roznice.append(d)
        wiersze.append({"stacja": n, "id_imgw": s["id"],
                        "data": s["data"], "godzina": s["godz"],
                        "imgw_C": s["T"], "openmeteo_C": om,
                        "roznica_K": round(d, 2)})
        flaga = "  <-- sprawdz" if abs(d) > PROG_OSTRZEZENIA_K else ""
        print(f"{n:12s}{s['data'] + ' ' + str(s['godz']) + ':00':>18}"
              f"{s['T']:>8.1f}{om:>12.1f}{d:>+9.1f} K{flaga}")

    if roznice:
        sr = sum(roznice) / len(roznice)
        maks = max(abs(x) for x in roznice)
        print(f"\n  obciazenie srednie: {sr:+.2f} K")
        print(f"  najwieksza roznica: {maks:.2f} K")
        print(f"  odniesienie historyczne (962 dni, Zamosc): RMSE 1.13 K")
        if maks > PROG_OSTRZEZENIA_K:
            print(f"\n  UWAGA: roznica powyzej {PROG_OSTRZEZENIA_K} K na "
                  f"co najmniej jednej stacji.")
            print("  Pojedynczy odczyt godzinowy bywa rozbiezny (chmury, "
                  "inwersja), wiec")
            print("  to jeszcze nie jest blad reanalizy - ale warto sprawdzic "
                  "ponownie.")
        else:
            print("\n  Reanaliza zgadza sie z pomiarem w granicach bledu "
                  "historycznego.")

    (WYNIKI / "json" / "kontrola_meteo.json").write_text(json.dumps({
        "cel": "biezaca kontrola reanalizy ERA5 wobec pomiaru stacji IMGW",
        "zrodlo_imgw": "https://danepubliczne.imgw.pl/api/data/synop",
        "ograniczenie": "IMGW zwraca tylko biezacy odczyt godzinowy, bez "
                        "historii - nie zastapi reanalizy jako zrodla",
        "odniesienie_historyczne": {"stacja": "Zamosc 595", "n_dni": 962,
                                    "rmse_K": 1.126, "r": 0.986},
        "sprawdzono": date.today().isoformat(),
        "stacje": wiersze,
        "obciazenie_srednie_K": round(sum(roznice) / len(roznice), 2)
        if roznice else None,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/kontrola_meteo.json")
