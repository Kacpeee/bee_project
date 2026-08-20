"""
Rdzen modelu fenologicznego - jedna funkcja, z ktorej korzysta i narzedzie
konsolowe, i mikroserwis.

DLACZEGO OSOBNY MODUL
Gdyby serwis mial wlasna kopie obliczen, po pierwszej poprawce modelu
konsola i API zaczelyby dawac rozne odpowiedzi - a tego typu cicha
rozbieznosc kosztowala juz ten projekt kilka godzin (zaszyta stala
w sprawdzianie GUS, stary model w mapie). Rdzen jest wiec jeden.

MODEL
Suma temperatur efektywnych od 15 III, baza 1.5 C, prog 430 GDD.
Parametry dobrane pomiarowo na 145 obserwacjach z 19 obszarow (krzywe NDYI
Sentinel-2); blad 3.2 dnia w walidacji krzyzowej leave-one-out. Pierwotna
proba (45 obserwacji, 7 obszarow) dala te same parametry i ten sam blad -
wynik nie byl wiec artefaktem doboru miejsc.

NIEPEWNOSC
Nie jest zgadywana - brana ze zmierzonej tabeli hindcastu, wg tego ILE
REALNEJ POGODY mamy do dnia kwitnienia (a nie ktory dzis jest w kalendarzu).
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
LAT_KLIM = 8
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII",
        "IX", "X", "XI", "XII"]

# LIMITY OPEN-METEO.
# Kazde zapytanie o prognoze to dwa wywolania API (klimatologia + sezon
# biezacy), a lasso probkuje do trzech punktow - czyli szesc wywolan na
# klikniecie. Przy dowolnych wspolrzednych z mapy cache nigdy nie trafial
# i serwis dostawal 429 Too Many Requests.
#
# Rozwiazanie: wspolrzedne PRZYCINANE DO SIATKI przed zapytaniem. Termin
# kwitnienia zmienia sie o ok. 8 dni na 230 km, czyli 0.035 dnia na
# kilometr - przy siatce 0.1 stopnia (ok. 11 km) blad z tego tytulu to
# nieco ponad 0.3 dnia, dziesiec razy mniej niz blad modelu. Za to liczba
# roznych zapytan spada z nieskonczonej do kilkuset na wojewodztwo.
#
# Cache trzymany takze NA DYSKU, zeby restart serwisu nie zaczynal od zera.
SIATKA_ST = 0.1
_CACHE: dict[tuple, tuple[float, pd.DataFrame]] = {}
_TTL = 3600
_DYSK = WYNIKI / "cache" / "meteo_serwis"


def _przytnij(lat: float, lon: float) -> tuple[float, float]:
    return (round(round(lat / SIATKA_ST) * SIATKA_ST, 3),
            round(round(lon / SIATKA_ST) * SIATKA_ST, 3))


def dz(doy: float, rok: int) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def iso(doy: float, rok: int) -> str:
    return (date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)).isoformat()


def parametry() -> dict:
    """Parametry modelu i zmierzone bledy - czytane, nie wpisane."""
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json")
                     .read_text(encoding="utf-8"))["model"]
    hind = json.loads((WYNIKI / "json" / "prognoza_w_sezonie.json")
                      .read_text(encoding="utf-8"))
    return {
        "baza": fin["baza"], "prog": fin["prog"],
        "start_doy": fin.get("start_doy", 74),
        "rmse_modelu": fin["rmse"],
        "n_obserwacji": fin.get("n"),
        "bledy_prognozy": {int(k): v["rmse"] for k, v in hind["statystyki"].items()},
        "sredni_termin": hind["sredni_termin_kwitnienia"],
    }


def _pobierz(lat: float, lon: float, od: date, do: date) -> pd.DataFrame:
    lat, lon = _przytnij(lat, lon)
    klucz = (lat, lon, od, do)
    teraz = time.time()
    if klucz in _CACHE and teraz - _CACHE[klucz][0] < _TTL:
        return _CACHE[klucz][1]

    # cache dyskowy: archiwum sie nie zmienia, wiec moze lezec dowolnie dlugo
    _DYSK.mkdir(parents=True, exist_ok=True)
    plik = _DYSK / f"{lat}_{lon}_{od}_{do}.csv"
    swiezy = do < date.today() - timedelta(days=7)
    if plik.exists() and (swiezy or teraz - plik.stat().st_mtime < _TTL):
        df = pd.read_csv(plik, parse_dates=["data"])
        _CACHE[klucz] = (teraz, df)
        return df

    def _get(url, params, prob=4):
        """Ponawianie z odczekaniem - Open-Meteo zwraca 429 przy nadmiarze."""
        for i in range(prob):
            r = requests.get(url, params=params, timeout=120)
            if r.status_code != 429:
                r.raise_for_status()
                return r
            time.sleep(1.5 * (i + 1))
        raise RuntimeError("Open-Meteo: limit zapytan (429) mimo ponowien")

    czesci, dzis = [], date.today()
    if od < dzis:
        r = _get("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": lat, "longitude": lon, "start_date": od.isoformat(),
            "end_date": min(do, dzis - timedelta(days=6)).isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Warsaw"})
        d = r.json()["daily"]
        czesci.append(pd.DataFrame({"data": pd.to_datetime(d["time"]),
                                    "Tmax": d["temperature_2m_max"],
                                    "Tmin": d["temperature_2m_min"]}))
    if do >= dzis - timedelta(days=6):
        try:
            r = _get("https://api.open-meteo.com/v1/forecast", {
                "latitude": lat, "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "past_days": 10, "forecast_days": 16,
                "timezone": "Europe/Warsaw"})
            d = r.json()["daily"]
            czesci.append(pd.DataFrame({"data": pd.to_datetime(d["time"]),
                                        "Tmax": d["temperature_2m_max"],
                                        "Tmin": d["temperature_2m_min"]}))
        except Exception:
            pass
    if not czesci:
        return pd.DataFrame(columns=["data", "Tmax", "Tmin"])
    df = pd.concat(czesci).drop_duplicates("data").sort_values("data").dropna()
    # FILTR DO ZADANEGO ZAKRESU - konieczny, nie kosmetyczny.
    # Endpoint prognozy Open-Meteo zwraca dni wokol DZISIAJ niezaleznie od
    # tego, o jaki okres pytamy. Bez tego filtra dni z sierpnia 2026 wpadaly
    # do sezonu 2027 jako "pogoda realna", serwis raportowal "cala pogoda
    # znana" i podawal niepewnosc 3.2 dnia zamiast 7.8 - czyli zanizal ja
    # dwukrotnie dla sezonu, o ktorym nie wiedzial nic.
    df = df[(df["data"].dt.date >= od) & (df["data"].dt.date <= do)]
    df = df.reset_index(drop=True)
    _CACHE[klucz] = (teraz, df)
    try:
        df.to_csv(plik, index=False)
    except Exception:
        pass
    return df


def prognozuj(lat: float, lon: float, rok: int | None = None) -> dict:
    """Przewidywana data kwitnienia rzepaku w podanym punkcie."""
    p = parametry()
    dzis = date.today()
    if rok is None:
        rok = dzis.year
        if dzis.timetuple().tm_yday > p["sredni_termin"] + 20:
            rok += 1

    hist = _pobierz(lat, lon, date(rok - LAT_KLIM, 1, 1), date(rok - 1, 12, 31))
    if hist.empty:
        raise ValueError("brak danych historycznych dla tego punktu")
    hist = hist.assign(doy=hist["data"].dt.dayofyear,
                       gdd=np.maximum((hist.Tmax + hist.Tmin) / 2 - p["baza"], 0))
    klim = hist.groupby("doy")["gdd"].mean()

    biez = _pobierz(lat, lon, date(rok, 1, 1), date(rok, 7, 15))
    realne = {}
    if not biez.empty:
        biez = biez.assign(doy=biez["data"].dt.dayofyear,
                           gdd=np.maximum((biez.Tmax + biez.Tmin) / 2 - p["baza"], 0))
        realne = dict(zip(biez["doy"].astype(int), biez["gdd"]))

    doy = np.arange(1, 200)
    gdd = np.array([realne.get(int(t), float(klim.get(int(t), 0))) for t in doy])
    gdd[doy < p["start_doy"]] = 0
    i = int(np.searchsorted(np.cumsum(gdd), p["prog"]))
    if i >= len(doy):
        raise ValueError("prog nieosiagniety do 19 VII")
    pelnia = float(doy[i])

    # niepewnosc wg stanu WIEDZY, nie wg daty w kalendarzu
    ostatni = max((int(t) for t in realne), default=0)
    wiedza = min(ostatni, int(pelnia))
    dost = sorted(p["bledy_prognozy"])
    if wiedza >= int(pelnia):
        blad, opis = p["rmse_modelu"], "cała pogoda sezonu znana"
    elif wiedza < dost[0]:
        blad, opis = p["bledy_prognozy"][dost[0]], "przed sezonem (klimatologia)"
    else:
        k = max(d for d in dost if d <= wiedza)
        blad, opis = p["bledy_prognozy"][k], f"pogoda znana do {dz(wiedza, rok)}"

    okres = max(1, int(pelnia - p["start_doy"] + 1))
    pokrycie = sum(1 for t in doy
                   if p["start_doy"] <= t <= pelnia and int(t) in realne)

    # POSTEP AKUMULACJI - ile ciepla juz sie uzbieralo i ile brakuje.
    # Sama data nie pokazuje, na jakim etapie jest sezon; suma GDD pokazuje.
    kum = np.cumsum(gdd)
    # Do ktorego dnia liczymy postep:
    #   sezon biezacy  - do dzisiaj
    #   sezon miniony  - do kwitnienia (dalej suma rosnie, ale juz nieistotna;
    #                    bez tego wychodzilo 1417 GDD zamiast progu 430)
    #   sezon przyszly - brak akumulacji
    if rok == dzis.year:
        dzis_doy = dzis.timetuple().tm_yday
    elif rok < dzis.year:
        dzis_doy = int(pelnia)
    else:
        dzis_doy = 0
    dzis_doy = min(dzis_doy, int(pelnia))
    if dzis_doy >= p["start_doy"]:
        gdd_teraz = float(kum[min(dzis_doy - 1, len(kum) - 1)])
    else:
        gdd_teraz = 0.0
    # tempo z ostatnich dwoch tygodni realnej pogody
    ost = sorted(t for t in realne if t <= dzis_doy)[-14:]
    tempo = (sum(realne[t] for t in ost) / len(ost)) if ost else None
    brak = max(0.0, p["prog"] - gdd_teraz)
    postep = {
        "gdd_teraz": round(gdd_teraz),
        "prog": p["prog"],
        "do_dnia": dz(dzis_doy, rok) if dzis_doy >= p["start_doy"] else None,
        "procent": round(min(100, gdd_teraz / p["prog"] * 100)),
        "brakuje_gdd": round(brak),
        "tempo_gdd_dzien": round(tempo, 1) if tempo else None,
        "dni_w_tym_tempie": round(brak / tempo) if tempo and tempo > 0 else None,
    }

    # CZY TO W OGOLE JEST PROGNOZA.
    #
    # Przy zerowym pokryciu realna pogoda model zwraca czysta klimatologie,
    # czyli srednia wieloletnia. Odniesienie "zawsze podawaj srednia" ma blad
    # 7.3 dnia, nasz model w tym trybie 7.8 - jest wiec MINIMALNIE GORSZY
    # od zwyklej sredniej. Nazywanie tego prognoza wprowadzaloby w blad,
    # bo liczba wyglada na przewidywanie, a nie niesie zadnej informacji
    # o konkretnym sezonie.
    pct = round(pokrycie / okres * 100)
    if pct == 0:
        rodzaj, naglowek = "srednia_wieloletnia", "termin typowy"
        uwaga = ("To NIE jest prognoza — model nie ma jeszcze żadnej pogody "
                 "tego sezonu, więc zwraca średnią wieloletnią. Realna "
                 "prognoza ma sens od połowy kwietnia (błąd 5,0 d), "
                 "a najlepsza jest 1 maja (3,4 d).")
    elif pct < 60:
        rodzaj, naglowek = "prognoza_wczesna", "prognoza wstępna"
        uwaga = ("Część okresu akumulacji to jeszcze klimatologia. "
                 "Zapytaj ponownie bliżej kwitnienia — błąd spadnie.")
    else:
        rodzaj, naglowek = "prognoza", "prognoza"
        uwaga = "Model ma większość pogody okresu akumulacji."

    return {
        "lat": lat, "lon": lon, "sezon": rok,
        "rodzaj": rodzaj, "naglowek": naglowek, "uwaga": uwaga,
        "pelnia": {"doy": pelnia, "data": iso(pelnia, rok),
                   "opis": dz(pelnia, rok)},
        "poczatek": {"data": iso(pelnia - 10, rok), "opis": dz(pelnia - 10, rok)},
        "koniec": {"data": iso(pelnia + 12, rok), "opis": dz(pelnia + 12, rok)},
        "ustaw_ul": {"data": iso(pelnia - 12, rok), "opis": dz(pelnia - 12, rok)},
        "niepewnosc_dni": round(blad, 1),
        "przedzial": {"od": iso(pelnia - blad, rok), "do": iso(pelnia + blad, rok)},
        "podstawa_bledu": opis,
        "pogoda_realna_pct": pct,
        "postep": postep,
        "model": {"baza_C": p["baza"], "prog_gdd": p["prog"],
                  "start": dz(p["start_doy"], rok),
                  "rmse_walidacji_d": round(p["rmse_modelu"], 2),
                  "n_obserwacji": p["n_obserwacji"]},
        "zastrzezenie": ("model przewiduje termin, nie lokalizację upraw; "
                         "przed połową kwietnia prognoza jest niewiele lepsza "
                         "od średniej wieloletniej"),
    }
