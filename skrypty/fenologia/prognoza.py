"""
NARZEDZIE PROGNOZY - kiedy zakwitnie rzepak w podanym miejscu.

CZYM SIE ROZNI OD RESZTY PROJEKTU
Pozostale skrypty licza na pogodzie HISTORYCZNEJ i pokazuja sezony, ktore
juz minely. Ten liczy W PRZOD: pobiera pogode do dzisiaj, reszte sezonu
uzupelnia klimatologia z lat poprzednich i podaje przewidywana date
kwitnienia wraz z przedzialem niepewnosci.

MODEL
Suma temperatur efektywnych od 15 III (wznowienie wegetacji), baza 1.5 C,
prog 430. Parametry dobrane pomiarowo na 45 obserwacjach z krzywych NDYI
Sentinel-2, blad 3.2 dnia w walidacji krzyzowej leave-one-out.

Prog 430 zgadza sie niezaleznie z literatura branzowa, ktora podaje
400-500 C od wznowienia wegetacji - a doszlismy do niego z satelity,
nie z agronomii.

SKAD NIEPEWNOSC
Nie jest zgadywana. Bierzemy zmierzony blad prognozy dla dnia, w ktorym
pytamy (hindcast na tych samych 45 obserwacjach):

    15 II  7.8 d      1 IV  8.2 d
    1 III  7.8 d     15 IV  5.0 d
    15 III 7.8 d      1 V   3.9 d      po sezonie 3.2 d

Widac, ze do polowy kwietnia prognoza jest niewiele lepsza od sredniej
wieloletniej - i tak trzeba ja przedstawiac. Uzyteczna staje sie dopiero
na przelomie kwietnia i maja.

Uruchomienie:
    python skrypty/fenologia/prognoza.py                    # Lublin, sezon biezacy
    python skrypty/fenologia/prognoza.py 51.06 22.10        # wspolrzedne
    python skrypty/fenologia/prognoza.py 51.06 22.10 2027   # wybrany sezon
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
LAT_KLIM = 8              # ile lat wstecz na klimatologie
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
        "IX", "X", "XI", "XII"]


def dz(doy: float, rok: int) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def pobierz(lat: float, lon: float, od: date, do: date) -> pd.DataFrame:
    """Pogoda z Open-Meteo: archiwum dla przeszlosci, prognoza dla przyszlosci."""
    czesci = []
    dzis = date.today()
    if od < dzis:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": od.isoformat(),
            "end_date": min(do, dzis - timedelta(days=6)).isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Warsaw"}, timeout=120)
        r.raise_for_status()
        d = r.json()["daily"]
        czesci.append(pd.DataFrame({"data": pd.to_datetime(d["time"]),
                                    "Tmax": d["temperature_2m_max"],
                                    "Tmin": d["temperature_2m_min"]}))
    if do >= dzis - timedelta(days=6):
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "past_days": 10, "forecast_days": 16,
                "timezone": "Europe/Warsaw"}, timeout=120)
            r.raise_for_status()
            d = r.json()["daily"]
            czesci.append(pd.DataFrame({"data": pd.to_datetime(d["time"]),
                                        "Tmax": d["temperature_2m_max"],
                                        "Tmin": d["temperature_2m_min"]}))
        except Exception:
            pass
    if not czesci:
        return pd.DataFrame(columns=["data", "Tmax", "Tmin"])
    df = pd.concat(czesci).drop_duplicates("data").sort_values("data")
    return df.dropna().reset_index(drop=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    lat = float(a[0]) if len(a) > 0 else 51.246
    lon = float(a[1]) if len(a) > 1 else 22.568
    dzis = date.today()

    fin = json.loads((WYNIKI / "json" / "fenologia_final.json")
                     .read_text(encoding="utf-8"))["model"]
    baza, prog = fin["baza"], fin["prog"]
    d0 = fin.get("start_doy", 74)
    hind = json.loads((WYNIKI / "json" / "prognoza_w_sezonie.json")
                      .read_text(encoding="utf-8"))
    bledy = {int(k): v["rmse"] for k, v in hind["statystyki"].items()}
    sredni_termin = hind["sredni_termin_kwitnienia"]

    # sezon: podany albo biezacy; jesli kwitnienie juz minelo - nastepny
    if len(a) > 2:
        rok = int(a[2])
    else:
        rok = dzis.year
        if dzis.timetuple().tm_yday > sredni_termin + 20:
            rok += 1

    print(f"PROGNOZA KWITNIENIA RZEPAKU OZIMEGO")
    print(f"  miejsce: {lat:.3f} N  {lon:.3f} E")
    print(f"  sezon:   {rok}")
    print(f"  model:   baza {baza} °C, prog {prog:.0f}, start {dz(d0, rok)}"
          f"  (blad 3,2 d w walidacji krzyzowej)\n")

    # --- klimatologia: srednie dobowe GDD z ostatnich lat
    print("pobieram pogode...", flush=True)
    hist = pobierz(lat, lon, date(rok - LAT_KLIM, 1, 1), date(rok - 1, 12, 31))
    if hist.empty:
        raise SystemExit("brak danych historycznych dla tego punktu")
    hist["doy"] = hist["data"].dt.dayofyear
    hist["gdd"] = np.maximum((hist.Tmax + hist.Tmin) / 2 - baza, 0)
    klim = hist.groupby("doy")["gdd"].mean()

    # --- pogoda biezacego sezonu, ile jej juz jest
    biez = pobierz(lat, lon, date(rok, 1, 1), date(rok, 7, 15))
    if not biez.empty:
        biez["doy"] = biez["data"].dt.dayofyear
        biez["gdd"] = np.maximum((biez.Tmax + biez.Tmin) / 2 - baza, 0)
        realne = dict(zip(biez["doy"], biez["gdd"]))
        ostatni = int(biez["doy"].max())
    else:
        realne, ostatni = {}, 0

    # --- akumulacja: realna pogoda, dalej klimatologia
    doy = np.arange(1, 200)
    gdd = np.array([realne.get(int(t), float(klim.get(int(t), 0)))
                    for t in doy])
    gdd[doy < d0] = 0
    kum = np.cumsum(gdd)
    i = int(np.searchsorted(kum, prog))
    if i >= len(doy):
        raise SystemExit("prog nieosiagniety do 19 VII - sprawdz dane")
    pelnia = float(doy[i])

    # --- niepewnosc: zmierzony blad dla stanu WIEDZY, nie dla daty w kalendarzu
    #
    # Pierwsza wersja brala dzien dzisiejszy i dla sezonu minionego ustawiala
    # 0, czyli blad "przed sezonem" (7.8 d) - mimo ze pogoda byla znana
    # w calosci i blad powinien wynosic 3.2 d. Liczy sie to, ILE REALNEJ
    # POGODY mamy do dnia kwitnienia, a nie ktory dzis jest.
    ostatni_realny = max((int(t) for t in realne), default=0)
    dzien_wiedzy = min(ostatni_realny, int(pelnia))
    dostepne = sorted(bledy)
    if dzien_wiedzy >= int(pelnia):
        blad = fin["rmse"]
        opis = "cala pogoda sezonu znana (blad modelu, nie prognozy)"
    elif dzien_wiedzy < dostepne[0]:
        blad, opis = bledy[dostepne[0]], "przed sezonem (sama klimatologia)"
    else:
        k = max(d for d in dostepne if d <= dzien_wiedzy)
        blad, opis = bledy[k], f"pogoda znana do {dz(dzien_wiedzy, rok)}"

    pokrycie = sum(1 for t in doy if d0 <= t <= pelnia and int(t) in realne)
    okres = max(1, int(pelnia - d0 + 1))

    print(f"\n{'='*54}")
    print(f"  PELNIA KWITNIENIA:  {dz(pelnia, rok)}  ±{blad:.1f} dnia")
    print(f"{'='*54}")
    print(f"  przedzial:        {dz(pelnia - blad, rok)} – {dz(pelnia + blad, rok)}")
    print(f"  podstawa bledu:   {opis}")
    print(f"  pogoda realna:    {pokrycie}/{okres} dni okresu akumulacji "
          f"({pokrycie/okres*100:.0f}%)")
    print(f"  reszta:           klimatologia z {LAT_KLIM} lat")

    print(f"\n  POCZATEK KWITNIENIA (okno -10 d):  {dz(pelnia - 10, rok)}")
    print(f"  KONIEC   (okno +12 d):             {dz(pelnia + 12, rok)}")
    print(f"\n  Ul warto ustawic okolo {dz(pelnia - 12, rok)}, zeby rodzina")
    print(f"  byla na miejscu, zanim ruszy pozytek.")

    if pokrycie / okres < 0.5:
        print(f"\n  UWAGA: mniej niz polowa okresu akumulacji to realna pogoda,")
        print(f"  wiec prognoza opiera sie glownie na klimatologii. Zapytaj")
        print(f"  ponownie po 15 IV - blad spada wtedy z {bledy[74]:.1f} na "
              f"{bledy[121]:.1f} dnia.")
