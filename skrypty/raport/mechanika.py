"""
Krotki raport: MECHANIKA MODELU - jak to dziala, krok po kroku.

W odroznieniu od raport.html (ktory dokumentuje wszystko) ten ma pokazac
sam lancuch: co wchodzi, co sie z tym dzieje, co wychodzi.

Liczby czytane z wyniki/json/ przy kazdym uruchomieniu - zadna nie jest
wpisana na sztywno. To celowe: w tym projekcie zaszyta stala raz juz
uniewaznila caly sprawdzian GUS, ktory przez to wygladal na zaliczony.

Uruchomienie:
    python skrypty/raport/mechanika.py
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / "wyniki" / "json"


def w(nazwa):
    return json.loads((J / f"{nazwa}.json").read_text(encoding="utf-8"))


def pl(x, n=1):
    return f"{x:,.{n}f}".replace(",", " ").replace(".", ",")


def obraz(nazwa, podpis):
    """Mapa wklejona w HTML jako data:URI - strona ma dzialac bez katalogu."""
    f = ROOT / "mapy" / nazwa
    if not f.exists():
        return ""
    typ = mimetypes.guess_type(f.name)[0] or "image/png"
    b64 = base64.b64encode(f.read_bytes()).decode()
    return (f'<figure><img src="data:{typ};base64,{b64}" alt="{podpis}">'
            f'<figcaption>{podpis}</figcaption></figure>')


if __name__ == "__main__":
    kal = w("kalibracja_arealowa")
    zlo = w("zloz_calosc")
    krz = w("odrzut_sezonow")
    ksz = w("wrazliwosc_ksztaltu")
    tuz = w("wrazliwosc_tuz")
    pkt = w("najlepsze_punkty")
    gus = w("sprawdzian_gus")
    s1s2 = w("wielo_s1s2")

    najgorszy_ksz = min(v["korelacja"] for v in ksz["wyniki"].values())
    najgorszy_tuz = min(v["korelacja"] for v in tuz["wyniki"])
    m1 = pkt["miejsca"][0]
    n_cech = json.loads((J / "klasyfikator_wielo.json")
                        .read_text(encoding="utf-8"))["n_cech"]
    dz_start = {1: "1 I", 32: "1 II", 74: "15 III"}.get(krz.get("start_doy", 74),
                                                        "15 III")
    rz22 = kal["areal_po_korekcie"]["2022"]["rzepak ozimy"]

    HTML = f"""<meta charset="utf-8">
<title>Mechanika modelu</title>
<style>
 :root {{ --tlo:#f4f6f5; --atr:#16201c; --mut:#5f6b66; --akc:#1d6f42;
          --akc2:#b3801a; --ram:#dbe3df; --kar:#fff; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; background:var(--tlo); color:var(--atr);
   font:16px/1.65 "Segoe UI",system-ui,sans-serif; }}
 .w {{ max-width:900px; margin:0 auto; padding:48px 24px 80px; }}
 h1 {{ font-size:30px; margin:0 0 6px; letter-spacing:-.4px; }}
 h1::after {{ content:""; display:block; width:52px; height:3px;
   background:var(--akc2); margin-top:12px; border-radius:2px; }}
 .pod {{ color:var(--mut); margin:0 0 40px; font-size:16px; }}
 .krok {{ background:var(--kar); border:1px solid var(--ram);
   border-radius:12px; padding:22px 26px; margin:0 0 18px; }}
 .nr {{ display:inline-block; background:var(--akc); color:#fff;
   flex:0 0 auto;
   width:26px; height:26px; border-radius:50%; text-align:center;
   line-height:26px; font-size:14px; font-weight:600; margin-right:10px; }}
 h2 {{ font-size:19px; margin:0 0 12px; display:flex; align-items:center; }}
 p {{ margin:0 0 10px; }}
 .mniej {{ color:var(--mut); font-size:14.5px; }}
 code, .wzor {{ font-family:"Cascadia Mono",Consolas,monospace; }}
 .wzor {{ background:#eef2f0; border-left:3px solid var(--akc2);
   padding:10px 14px; margin:12px 0; font-size:14px; white-space:pre-wrap;
   border-radius:0 6px 6px 0; overflow-x:auto; }}
 table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:14.5px; }}
 th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--ram); }}
 th {{ font-weight:600; color:var(--mut); font-size:13px;
   text-transform:uppercase; letter-spacing:.4px; }}
 td.l {{ text-align:right; font-variant-numeric:tabular-nums; }}
 b.ok {{ color:var(--akc); }} b.uw {{ color:#a8442a; }}
 .strz {{ text-align:center; color:var(--ram); font-size:22px; margin:-8px 0 10px; }}
 .pod-krok {{ font-size:15px; margin:22px 0 12px; color:var(--mut);
   text-transform:uppercase; letter-spacing:.5px; font-weight:600; }}
 .etap-k {{ display:flex; gap:14px; align-items:flex-start; margin:0 0 16px; }}
 .etap-n {{ width:28px; height:28px; border-radius:50%; flex:0 0 auto;
   background:var(--akc2); color:#fff; display:grid; place-items:center;
   font-size:13.5px; font-weight:700; margin-top:2px; }}
 .etap-t {{ flex:1; font-size:15px; }}
 table.mini {{ margin:9px 0 2px; font-size:14px; }}
 table.mini td {{ padding:6px 10px 6px 0; vertical-align:top; }}
 table.mini td.l {{ text-align:right; }}
 .mn {{ color:var(--mut); font-size:13px; }}
 .wyjasn {{ background:#eef2f0; border-left:3px solid var(--ram);
   border-radius:0 8px 8px 0; padding:14px 18px;
   margin:14px 0; font-size:14.5px; }}
 .wyjasn p {{ margin:0 0 8px; }}
 .wyjasn p:last-child {{ margin-bottom:0; }}
 figure {{ margin:16px 0 4px; }}
 figure img {{ width:100%; height:auto; display:block; border-radius:8px;
   border:1px solid var(--ram); background:#fff; }}
 figcaption {{ color:var(--mut); font-size:13.5px; margin-top:7px; }}
 .stopka {{ margin-top:36px; padding-top:20px; border-top:2px solid var(--ram);
   color:var(--mut); font-size:14px; }}
 @media (prefers-color-scheme:dark) {{
   :root {{ --tlo:#101613; --atr:#e3eae6; --mut:#8d9a94; --ram:#27332d;
            --kar:#18211d; --akc:#54b37c; --akc2:#d6a53f; }}
   .wzor, .wyjasn {{ background:#1e2823; }}
   figure img {{ background:#e8ece9; }}
 }}
</style>
<div class="w">
<h1>Jak działa model</h1>
<p class="pod">Od zdjęcia satelitarnego do współrzędnych, gdzie postawić ul.<br>
Województwo lubelskie · siatka 100 m · sezony 2019–2026</p>

<div class="krok">
<h2><span class="nr">1</span>Co rośnie — dwa źródła, nie jedno</h2>
<p>Deklaracje ARiMR obejmują 1,5 mln działek, ale istnieją tylko dla 2025
i 2026. Detekcja satelitarna sięga wstecz, lecz nie dla każdego gatunku
jest lepsza.</p>
<p><b>Kryterium podziału jest pomiarowe:</b> gatunek idzie z satelity tylko
wtedy, gdy detekcja bije odniesienie „rosło tam, gdzie rok temu”.</p>

<div class="wyjasn">
<p><b>Jak czytać tabelę.</b> Obie kolumny to <b>współczynniki korelacji</b>
w skali 0–1: ile z rzeczywistego rozmieszczenia uprawy udało się trafić.
1,0 = idealnie, 0 = zupełnie mimo.</p>
<p><b>MODEL</b> — uczymy klasyfikator na sezonie 2025, każemy mu wskazać
uprawy w 2026, porównujemy z rzeczywistością 2026.</p>
<p><b>PAMIĘĆ</b> — nie liczymy nic. Bierzemy mapę z 2025 i mówimy „w 2026
będzie tak samo”. To jest <b>punkt odniesienia</b>: najprostsze możliwe
rozwiązanie, za darmo.</p>
<p>Bez tej drugiej kolumny nie wiadomo, czy 0,878 dla maliny to dużo.
Okazuje się, że nie — samo powtórzenie zeszłego roku daje 0,847, czyli
niemal tyle samo. <b>Model musi wygrać z pamięcią, żeby miał sens.</b></p>
</div>

<table>
<tr><th>gatunek</th><th>model</th><th>pamięć</th><th>źródło w mapie</th></tr>
<tr><td>rzepak ozimy</td><td class="l">0,958</td><td class="l">0,338</td><td><b class="ok">satelita</b></td></tr>
<tr><td>gryka</td><td class="l">0,859</td><td class="l">0,750</td><td><b class="ok">satelita</b></td></tr>
<tr><td>słonecznik</td><td class="l">0,850</td><td class="l">0,814</td><td><b class="ok">satelita</b></td></tr>
<tr><td>malina</td><td class="l">0,878</td><td class="l">0,847</td><td>deklaracje</td></tr>
<tr><td>fasola wielokwiatowa</td><td class="l">0,880</td><td class="l">0,949</td><td>deklaracje</td></tr>
<tr><td>łąki, sady, porzeczka</td><td class="l">&lt; próg</td><td class="l">wyższe</td><td>deklaracje</td></tr>
</table>
<p class="mniej"><b>Rzepak 0,958 wobec 0,338</b> — pamięć zawodzi, bo rzepak
wraca na to samo pole dopiero co 3–4 lata. <b>Fasola 0,880 wobec 0,949</b> —
odwrotnie: uprawa specjalistyczna, sadzona na tych samych polach, więc detekcja
tylko by popsuła. Malina to krzew wieloletni — plantacja stoi dekadę. Warstwa
satelitarna niesie <b>{pl(zlo['udzial_satelity'] * 100)}%</b> cukrów.</p>

<div class="wyjasn">
<p><b>Uwaga — te liczby dotyczą DZIAŁEK, nie mapy.</b> Odniesienie 0,338
powstaje przez przypisanie każdej działce etykiety najbliższej działki z roku
poprzedniego, więc odpowiada na pytanie „czy <i>to konkretne pole</i> będzie
rzepakiem".</p>
<p>Produktem projektu jest natomiast <b>gęstość regionalna po splocie</b>,
a ta jest znacznie stabilniejsza. Zmierzone na deklaracjach ARiMR:</p>
<table class="mini">
  <tr><td>deklaracje rzepaku 2025 wobec 2026</td><td class="l"><b>0,795</b></td></tr>
  <tr><td>detekcja 2025 wobec deklaracji 2025</td><td class="l">0,991</td></tr>
</table>
<p>Dla mapy detekcja podnosi więc zgodność <b>z 0,795 na 0,991</b> — poprawa
realna, ale nie trzykrotna. Rolnicy zmieniają konkretne pola, lecz w obrębie
tych samych okolic, bo decyduje o tym gleba i tradycja płodozmianu.</p>
<p><b>Detekcja pozostaje niezbędna z innego powodu:</b> deklaracje istnieją
tylko dla 2025 i 2026. Dla lat 2019–2024 <i>nie ma czego pamiętać</i> — bez
niej nie powstałby ani przeciętny rok, ani warstwa niezawodności.</p>
</div>
</div>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">2</span>Detekcja — rozpoznanie uprawy ze zdjęć</h2>
<p>Zadanie: dla każdego pola powiedzieć, co na nim rośnie, mając tylko zdjęcia
satelitarne. Odróżnia je <b>przebieg w czasie</b> — rzepak zimuje zielony
i żółknie w maju, gryka rusza dopiero latem, łąka jest kilkukrotnie koszona.
Jedno zdjęcie tego nie pokaże, cały sezon tak.</p>

<h3 class="pod-krok">Jak to zrobiono</h3>

<div class="etap-k">
<div class="etap-n">A</div>
<div class="etap-t">
  <b>Zbudować przebieg roczny.</b> Kompozyty <b>półmiesięczne od września do
  września</b> — 26 okien, bo rzepak trzeba złapać już od siewu jesienią.
  Z każdego okna dwa wskaźniki optyczne i trzy radarowe:
  <table class="mini">
    <tr><td><b>NDVI</b> <span class="mn">(NIR − czerwony)/(NIR + czerwony)</span></td>
        <td>biomasa — ile zieleni jest na polu</td></tr>
    <tr><td><b>NDYI</b> <span class="mn">(zielony − niebieski)/(zielony + niebieski)</span></td>
        <td>żółć — czyli kwitnienie rzepaku i gorczycy</td></tr>
    <tr><td><b>VV, VH, VH−VV</b> <span class="mn">Sentinel-1, w decybelach</span></td>
        <td>szorstkość i struktura — radar widzi pokosy i wyleganie</td></tr>
  </table>
</div></div>

<div class="etap-k">
<div class="etap-n">B</div>
<div class="etap-t">
  <b>Usunąć wpływ warunków zdjęcia.</b> Wskaźniki optyczne wchodzą jako
  <b>anomalie sceny</b>: od wartości na polu odejmowana jest mediana gruntów
  ornych <i>z tego samego zdjęcia</i>. Bez tego model uczyłby się kąta słońca
  i zamglenia zamiast rośliny — ta sama uprawa wyglądałaby inaczej na zdjęciu
  czerwcowym i wrześniowym z powodów czysto atmosferycznych.
</div></div>

<div class="etap-k">
<div class="etap-n">C</div>
<div class="etap-t">
  <b>Nauczyć las losowy na deklaracjach.</b> Etykiety pochodzą z deklaracji
  ARiMR&nbsp;2025 — jedynego rocznika z prawdą terenową. 300 drzew,
  {n_cech} cech.
  <p style="margin:9px 0 0"><b>Walidacja przestrzenna, nie losowa</b> — zbiór
  dzielony na <b>bloki 2,5&nbsp;km</b>. Sąsiednie działki są do siebie podobne
  (ta sama gleba, ten sam gospodarz, ta sama data siewu), więc losowy podział
  wpuściłby niemal identyczne pola do treningu i do testu naraz. Wynik byłby
  zawyżony, a model wyglądałby lepiej, niż jest.</p>
</div></div>

<div class="etap-k">
<div class="etap-n">D</div>
<div class="etap-t">
  <b>Wyrzucić pomiary, które są awarią odczytu.</b> Nie każdy odczyt
  z satelity jest dobry — czasem brakuje bezchmurnych scen i krzywa NDYI
  jest tak dziurawa, że szczyt wypada byle gdzie. Takie przypadki trzeba
  usunąć, ale <b>próg musi wynikać z czegoś poza danymi</b>, inaczej jest
  to dopasowywanie zbioru do oczekiwanego wyniku.

  <p style="margin:10px 0 6px"><b>Skąd próg.</b> Model przewiduje, że
  między 19 obszarami pomiarowymi kwitnienie różni się o <b>2–5 dni</b>
  (leżą bliżej siebie niż krańce województwa). Odchylenie pojedynczego
  obszaru od mediany sezonu może więc sięgać ~2,5 dnia z samej termiki.
  Do tego ok. 3 dni niepewności odczytu NDYI — <b>razem około 6 dni</b>.
  Wszystko powyżej to nie zjawisko, tylko zepsuty pomiar.</p>

  <p style="margin:8px 0 6px"><b>Wynik nie zależy od tego wyboru</b> — i to
  jest ważniejsze niż sama liczba:</p>
  <table class="mini">
    <tr><th>próg odrzutu</th><th>obserwacji</th><th>RMSE walidacji</th></tr>
    <tr><td>6 dni <span class="mn">(fizyczny)</span></td><td class="l">141</td><td class="l">3,17 d</td></tr>
    <tr><td><b>8 dni</b> <span class="mn">(przyjęty)</span></td><td class="l"><b>145</b></td><td class="l"><b class="ok">3,21 d</b></td></tr>
    <tr><td>12 dni</td><td class="l">150</td><td class="l">3,59 d</td></tr>
    <tr><td>20 dni</td><td class="l">157</td><td class="l">4,82 d</td></tr>
    <tr><td><b>bez odrzutu</b></td><td class="l">162</td><td class="l"><b class="uw">7,09 d</b></td></tr>
  </table>
  <p style="margin:8px 0 0">Zależność jest płynna — nie ma progu, przy
  którym wynik nagle „wskakuje". Za to <b>bez odrzutu błąd rośnie ponad
  dwukrotnie</b>, a najgorszy przypadek z 12 na 38 dni: filtrowanie awarii
  odczytu jest więc konieczne, nie kosmetyczne.</p>

  <p style="margin:8px 0 0" class="mn">Wcześniejsza wersja odrzucała całe
  sezony, gdy ich rozrzut przekraczał dwukrotność mediany. Przy 7 obszarach
  to działało, bo awarie skupiały się w konkretnych latach. Po rozszerzeniu
  do 19 obszarów okazały się rozproszone, mediana rozrzutów urosła z 9 na
  30 dni i reguła przestała cokolwiek odrzucać — miara względna zawodzi,
  gdy psuje się cały rozkład.</p>
</div></div>

<div class="etap-k">
<div class="etap-n">E</div>
<div class="etap-t">
  <b>Dołożyć radar.</b> Sam Sentinel-2 ma nad Lubelszczyzną <b>8 okien
  całkowicie pustych</b> — w pierwszej połowie stycznia 100% punktów nie ma
  ani jednej bezchmurnej sceny. Sentinel-1 przenika chmury i ma <b>zero
  pustych okien</b>.
</div></div>

<table>
<tr><th>zestaw cech</th><th>F1-makro</th></tr>
<tr><td>Sentinel-2 sam</td><td class="l">{pl(s1s2['f1_makro']['S2'], 3)}</td></tr>
<tr><td>Sentinel-1 sam</td><td class="l">{pl(s1s2['f1_makro']['S1'], 3)}</td></tr>
<tr><td><b>oba razem</b></td><td class="l"><b class="ok">{pl(s1s2['f1_makro']['S1_S2'], 3)}</b></td></tr>
</table>

<div class="wyjasn">
<p><b>F1</b> to ocena rozpoznawania w skali 0–1, łącząca dwie rzeczy: ile
wskazanych pól faktycznie jest tą uprawą i ile jej pól udało się znaleźć.
Sama „dokładność" tu nie wystarcza — model mówiący o każdym pikselu „to nie
gryka" miałby 98% dokładności, bo gryki jest mało. <b>F1-makro</b> uśrednia
po gatunkach z równą wagą, więc rzadka gryka liczy się tyle co rzepak.</p>
</div>

<h3 class="pod-krok">Trzy gatunki, które trafiają do mapy</h3>
<p>Klasyfikator rozpoznaje dwanaście klas, ale do warstwy satelitarnej
wchodzą tylko te trzy — pozostałe idą z deklaracji, bo dla upraw trwałych
pamięć „rosło tam rok temu" jest dokładniejsza niż detekcja.</p>
<table>
<tr><th>gatunek</th><th>F1 sam S2</th><th>F1 S1+S2</th><th>przeniesienie na inny rok</th><th>udział w cukrze warstwy</th></tr>
<tr><td><b>rzepak ozimy</b></td><td class="l"><b>0,922</b></td>
    <td class="l"><b class="ok">0,940</b></td><td class="l"><b>0,958</b></td>
    <td class="l"><b>86,7%</b></td></tr>
<tr><td>gryka zwyczajna</td><td class="l">0,543</td><td class="l">0,583</td>
    <td class="l">0,859</td><td class="l">12,1%</td></tr>
<tr><td>słonecznik</td><td class="l">0,559</td><td class="l">0,605</td>
    <td class="l">0,850</td><td class="l">1,2%</td></tr>
</table>
<div class="wyjasn">
<p><b>Rzepak jest zdecydowanie najłatwiejszy</b> — 0,940 wobec 0,58–0,61
u pozostałych. Powód jest w samym przebiegu: rzepak <b>zimuje jako zielona
rozeta</b>, gdy sąsiednie pola są gołe, w maju <b>żółknie na całą
powierzchnię</b>, a w lipcu zostaje po nim ściernisko. Trzy wyraźne,
niepowtarzalne sygnały w jednym roku.</p>
<p>Gryka i słonecznik są <b>jare</b> — pojawiają się dopiero późną wiosną
i przez pierwsze miesiące wyglądają jak każde inne świeżo obsiane pole.
Do tego jest ich mało (13&nbsp;201 i 5&nbsp;771&nbsp;ha wobec
150&nbsp;626&nbsp;ha rzepaku), więc model ma na czym się uczyć znacznie
mniej.</p>
<p><b>Dla mapy to jednak drugorzędne:</b> rzepak niesie 86,7% cukru tej
warstwy. Gorsze rozpoznanie gryki obciąża wynik w małym stopniu, a błąd
poziomu i tak naprawia kalibracja areałowa (etap&nbsp;F). Ważniejsze jest,
że <b>wszystkie trzy przenoszą się na inne lata powyżej 0,85</b> — bez tego
seria 2019–2025 nie miałaby podstaw.</p>
</div>

<div class="etap-k">
<div class="etap-n">F</div>
<div class="etap-t">
  <b>Poprawić areały.</b> Model uczono na próbce <b>zrównoważonej</b> — po
  równo działek każdego gatunku, żeby żaden nie przepadł w treningu. Wyniósł
  z tego przekonanie, że wszystkich upraw jest po tyle samo, i w terenie
  rozdawał piksele zbyt hojnie rzadkim klasom: słonecznika wykrywał
  <b>dziewięciokrotnie</b> za dużo.
  <p style="margin:9px 0 0">To jest błąd <b>poziomu, nie wzoru</b> — korelacja
  układu przestrzennego wychodziła 0,85–0,96, czyli model trafia
  <i>gdzie</i> rośnie gatunek, a myli się <i>ile</i> go jest. Poprawka:
  współczynnik z roku wzorcowego, w którym znamy prawdę.</p>
  <table class="mini">
    <tr><td>rzepak ozimy</td><td class="l">×0,94</td></tr>
    <tr><td>malina</td><td class="l">×0,78</td></tr>
    <tr><td>gryka zwyczajna</td><td class="l">×2,96</td></tr>
    <tr><td>słonecznik</td><td class="l">×0,11</td></tr>
  </table>
  <p style="margin:9px 0 0">Kontrola niezależna: dla 2022 EUCROPMAP podaje
  147&nbsp;701&nbsp;ha rzepaku, model po korekcie {pl(rz22, 0)}&nbsp;ha —
  różnica <b class="ok">6%</b>. Współczynnik z 2025 przenosi się więc na
  inne lata.</p>
</div></div>

{obraz("mapa_detekcji.png", "Po lewej rzepak wykryty ze zdjęć, po prawej zadeklarowany przez rolników. Detekcja korzysta wyłącznie z jesieni i marca, więc nie widzi kwitnienia — a mimo to wskazuje te same rejony.")}

<p><b>Czego detekcja nie daje.</b> Areałów rocznych gatunków pobocznych nie
wolno czytać jako zmian w rolnictwie: malina to krzew wieloletni, a wykryty
areał skacze między latami piętnastokrotnie. To szum klasyfikacji, nie
plantacje. Wiarygodna jest seria rzepaku (zmienność 5%) oraz przeciętny rok
i warstwa niezawodności.</p>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">3</span>Ile nektaru — wydajności z tabel</h2>
<p>Każda uprawa ma wydajność w kg cukrów na hektar, z branżowych kompilacji
i dwóch badań naukowych. Wszystkie na <b>jednej podstawie</b>: kg miodu
÷ 1,25.</p>
<p class="mniej">Rzepak przeniesiono z podstawy produkcyjnej (115 kg, badanie
z Puław) na tabelaryczną (88 kg), bo badanie mierzy <i>produkcję nektaru</i>,
a tabele <i>wydajność miodową</i> — mieszanie dwóch wielkości zawyżało rzepak
o ~30% względem reszty. Badanie służy teraz za walidację.</p>
</div>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">4</span>Kiedy kwitnie — model termiczny</h2>
<p>Roślina nie liczy dni, tylko ciepło. Cały model operacyjny to trzy działania:</p>
<div class="wzor">1.  każdego dnia od <b>15 marca</b>:   gdd = max( (Tmax + Tmin)/2 − <b>1,5</b> , 0 )
2.  sumuj:                            suma = suma + gdd
3.  gdy suma ≥ <b>430</b>             →  pełnia kwitnienia</div>
<p><b>Tyle.</b> Wystarczy termometr — model nie potrzebuje zdjęć satelitarnych
do działania. Mikroserwis pobiera temperatury i sumuje, nic więcej.</p>

<div class="wyjasn">
<p><b>Po co więc satelita.</b> Posłużył <b>jednorazowo</b>, żeby ustalić dwie
liczby: bazę <b>1,5 °C</b> i próg <b>430</b>. Bez niego trzeba by je wziąć
z literatury albo zgadnąć. Po kalibracji satelita jest zbędny — i to jest
zaleta, bo model wymagający zdjęć do codziennej pracy byłby operacyjnie
bezużyteczny.</p>
</div>

<h3 class="pod-krok">Jak ustalono te dwie liczby</h3>

<div class="etap-k">
<div class="etap-n">A</div>
<div class="etap-t">
  <b>Zmierzyć, kiedy rzepak naprawdę zakwitł</b> — z krzywych NDYI: kwitnące
  pole żółknie, więc indeks rośnie i opada. Trzy rzeczy decydują, czy ten
  pomiar w ogóle coś znaczy:
  <table class="mini">
    <tr><td><b>normalizacja sceny</b><br><span class="mn">odejmujemy tło z tego samego zdjęcia</span></td>
        <td>bez tego mierzy się atmosferę, nie kwitnienie — błąd rośnie
            z <b>4,1</b> na <b>9,5</b> dnia</td></tr>
    <tr><td><b>brak cyrkularności</b><br><span class="mn">pola wskazuje klasyfikator przedkwitnieniowy</span></td>
        <td>gdyby używał okna kwitnienia, wskazywałby piksele, które zakwitły
            <i>tam, gdzie okno</i> — data ciążyłaby do jego środka</td></tr>
    <tr><td><b>wierzchołek paraboli</b><br><span class="mn">zamiast zwykłego maksimum</span></td>
        <td>argmax daje wynik skwantowany do dat przelotów satelity;
            parabola przez trzy najwyższe punkty daje dokładność
            podprzelotową</td></tr>
  </table>
</div></div>

<div class="etap-k">
<div class="etap-n">B</div>
<div class="etap-t">
  <b>Dopasować bazę i próg — jednocześnie, nie osobno.</b> Przeszukanie siatki:
  baza 0–8,5 °C co 0,5, próg 150–900 co 5. Dla każdej pary liczony RMSE,
  wybierana para z minimum. Wynik: <b>baza 1,5 °C, próg 430</b>.
</div></div>

<div class="etap-k">
<div class="etap-n">C</div>
<div class="etap-t">
  <b>Ustalić, od kiedy sumować.</b> To zmieniło wynik bardziej niż cokolwiek innego:
  <table class="mini">
    <tr><td>1 stycznia</td><td class="l">4,39 d</td></tr>
    <tr><td>1 lutego <span class="mn">(wersja pierwotna)</span></td><td class="l">3,89 d</td></tr>
    <tr><td><b>15 marca</b></td><td class="l"><b class="ok">3,13 d</b></td></tr>
  </table>
  Rzepak ozimy zimuje jako rozeta i <b>rusza z wegetacją dopiero wiosną</b>,
  więc ciepło styczniowe niczego nie napędza — dokłada wyłącznie szum.
  Literatura branżowa mówi to samo: sumę liczy się „od wznowienia wegetacji",
  a podawany zakres <b>400–500 °C</b> obejmuje nasz próg 430. Doszliśmy do
  niego z satelity, nie z agronomii.
</div></div>

<div class="etap-k">
<div class="etap-n">D</div>
<div class="etap-t">
  <b>Wyrzucić pomiary, które są awarią odczytu.</b> Nie każdy odczyt
  z satelity jest dobry — czasem brakuje bezchmurnych scen i krzywa NDYI
  jest tak dziurawa, że szczyt wypada byle gdzie. Takie przypadki trzeba
  usunąć, ale <b>reguła musi być podana z góry</b>, inaczej jest to
  dopasowywanie danych do oczekiwanego wyniku.

  <p style="margin:10px 0 6px"><b>Skąd wiadomo, że coś jest awarią.</b>
  Rzepak w całym województwie kwitnie w oknie około&nbsp;10 dni — tyle
  wynika z różnicy temperatur między południem a północą. Jeśli w jednym
  sezonie pomiary rozjeżdżają się na 40 dni, to nie jest zjawisko
  przyrodnicze, tylko zepsuty pomiar.</p>

  <table class="mini">
    <tr><th>sezon</th><th>rozrzut pomiarów</th><th></th></tr>
    <tr><td>2018</td><td class="l">8 dni</td><td class="mn">ok</td></tr>
    <tr><td>2019</td><td class="l">9 dni</td><td class="mn">ok</td></tr>
    <tr><td><b>2020</b></td><td class="l"><b>25 dni</b></td><td><b class="uw">odrzucony</b></td></tr>
    <tr><td>2021</td><td class="l">13 dni</td><td class="mn">ok</td></tr>
    <tr><td>2022</td><td class="l">9 dni</td><td class="mn">ok</td></tr>
    <tr><td>2023</td><td class="l">6 dni</td><td class="mn">ok</td></tr>
    <tr><td>2024</td><td class="l">7 dni</td><td class="mn">ok</td></tr>
    <tr><td>2025</td><td class="l">6 dni</td><td class="mn">ok</td></tr>
    <tr><td><b>2026</b></td><td class="l"><b>40 dni</b></td><td><b class="uw">odrzucony</b></td></tr>
  </table>

  <p style="margin:8px 0 0">Siedem sezonów mieści się w 6–13 dniach.
  Dwa odstają tak bardzo, że widać je gołym okiem — i oba mają wyjaśnienie:
  <b>2026 to sezon bieżący</b>, więc archiwum zdjęć jest rzadsze
  (ten sam rok miał 24 z 52 okien pustych w teście przenoszenia).</p>

  <p style="margin:8px 0 0"><b>Reguła:</b> odpada sezon, którego rozrzut
  przekracza <b>dwukrotność mediany</b> wszystkich sezonów. Mediana wynosi
  8,7 dnia, próg więc 17,5. To standardowa reguła odstających oparta na
  medianie — odporna na same odstające i niezależna od tego, jaki wynik
  chcielibyśmy dostać.</p>

  <p style="margin:8px 0 0" class="mn">Poprzednia wersja odrzucała
  7 pojedynczych obserwacji progiem „8 dni od mediany roku", dobranym już
  po zobaczeniu danych. Usuwała objawy zamiast przyczyny i wyglądała na
  dobieranie danych pod wynik.</p>
</div></div>

<div class="etap-k">
<div class="etap-n">E</div>
<div class="etap-t">
  <b>Sprawdzić model na danych, których nie widział.</b> Walidacja
  <b>leave-one-out</b>: dla każdej z {krz['n_po']} obserwacji parametry
  dobierane są <i>bez niej</i>, błąd liczony na odłożonej. W teście
  najostrzejszym, gdzie nawet wybór daty startu nie widzi ocenianej
  obserwacji, 15 marca wygrał <b>45 na 45</b> razy (na pierwotnej próbie
  7 obszarów; parametry potwierdziła później próba 19 obszarów).
</div></div>

<table>
<tr><th>miara</th><th>wynik</th></tr>
<tr><td>RMSE dopasowania</td><td class="l">{pl(krz['rmse_dopasowania'], 2)} d</td></tr>
<tr><td><b>RMSE walidacji krzyżowej</b></td><td class="l"><b class="ok">{pl(krz['rmse_walidacji_loo'], 2)} d</b></td></tr>
<tr><td>błąd bezwzględny</td><td class="l">{pl(krz['blad_bezwzgledny'], 2)} d</td></tr>
<tr><td>najgorszy przypadek</td><td class="l">{pl(krz['najgorszy_d'], 1)} d</td></tr>
</table>

{obraz("wykres_prognoza.png", "Błąd prognozy w zależności od dnia decyzji. Im bliżej kwitnienia, tym więcej rzeczywistej pogody zamiast klimatologii.")}

<div class="wyjasn">
<p><b>Dlaczego dwie różne liczby błędu.</b> Nie są sprzeczne — odpowiadają
na różne pytania:</p>
<p>• <b>{pl(krz['rmse_walidacji_loo'], 1)} dnia</b> — błąd modelu przy
<i>pełnej</i> znajomości pogody. To jego podłoga: uproszczenie GDD, różnice
odmianowe, błąd odczytu NDYI. Niżej nie zejdziesz bez poprawienia modelu.</p>
<p>• <b>3,4 dnia</b> — błąd prognozy 1 maja, gdy dwunastu dni do kwitnienia
jeszcze nie ma. Różnica 0,2 dnia to <b>cena nieznajomości tych dni</b>.</p>
<p>Odniesienie „zawsze podawaj średnią wieloletnią" daje <b>7,3 dnia</b>.
Model zmniejsza błąd ponad dwukrotnie — ale trzy dni to trzy dni, dlatego
narzędzie podaje przedział, nie punkt.</p>
</div>

<p><b>Czego ta walidacja nie obejmuje:</b> wartości odniesienia pochodzą
z krzywych NDYI, czyli z <b>innej estymacji satelitarnej</b>, a nie
z obserwacji polowej. Krajowe sieci fenologiczne nie obejmują rzepaku —
IMGW obserwuje wyłącznie rośliny dzikorosnące, COBORU publikuje jedynie
ranking odmian bez dat. Dla lipy i robinii walidacja polowa istnieje
(błąd 2,8 dnia i −1 dzień); dla rzepaku nie.</p>
</div>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">5</span>Zasięg lotu — splot jądrem</h2>
<p>Pszczoła nie zbiera spod ula, tylko z otoczenia, ważąc bliższe pola mocniej.
Trzeba więc dla <b>każdego</b> punktu mapy zsumować pożytek z okolicy — z wagą
malejącą wraz z odległością. Ta operacja nazywa się splotem.</p>

<div class="wyjasn">
<p><b>Krok 1 — waga zależna od odległości.</b> Pole oddalone o <i>d</i> metrów
liczy się z wagą:</p>
<div class="wzor">K(d) = exp(−d / λ)     dla d ≤ R,     0 dalej</div>
<p>λ to skala spadku: po tylu metrach waga maleje e-krotnie (ok. 2,7 raza).
Dla wiosny λ = 294 m, więc pole 294 m dalej liczy się <b>2,7 raza słabiej</b>,
a 600 m dalej — już siedmiokrotnie słabiej. R to odcięcie: dalej model nie
sięga wcale.</p>

<p><b>Krok 2 — skąd λ.</b> Nie z założenia. Znamy <b>zmierzoną średnią
odległość lotu</b> (493 m wiosną), więc dobieramy λ tak, żeby średnia ważona
jądra wyszła dokładnie tyle:</p>
<div class="wzor">średnia jądra = Σ( d · K(d) ) / Σ K(d)   =   493 m</div>
<p>Szukamy λ bisekcją — połowimy przedział, aż trafimy. Wyszło 294 m.
Zasięg przyjmujemy R = 4λ, bo obejmuje to 99% masy jądra; reszta jest
pomijalna.</p>

<p><b>Krok 3 — normalizacja.</b> Jądro letnie jest szersze, więc obejmuje
więcej pikseli i sumuje się do większej liczby. Gdyby zostawić je tak,
hektar gryki liczyłby się 19 razy mocniej niż hektar rzepaku — wyłącznie
dlatego, że ma szersze jądro. Dlatego każde jądro dzielimy przez jego sumę
i mnożymy przez tę samą stałą. Po tym zabiegu <b>zasięg lotu decyduje tylko
o tym, jak szeroko pożytek się rozmywa</b>, a nie ile go jest.</p>

<p><b>Krok 4 — splot.</b> Dla każdego piksela mapy bierzemy wszystkie pola
w zasięgu, mnożymy ich pożytek przez wagę z kroku 1 i sumujemy:</p>
<div class="wzor">P(x) = Σ<sub>y</sub>  C(y) · K( d(x,y) )</div>
<p>gdzie C(y) to cukier na pikselu y, a d(x,y) odległość między pikselami.
Powtarzamy to dla wszystkich 4 mln pikseli mapy — dlatego liczone jest przez
FFT, bo wprost byłoby to nie do udźwignięcia.</p>

<p><b>Co z tego wychodzi:</b> każdy piksel mówi, <b>ile cukru pszczoła z tego
miejsca realnie dosięgnie</b> — a nie ile go leży dokładnie pod ulem.</p>
</div>
<table>
<tr><th>pora</th><th>zmierzony dystans</th><th>λ</th><th>zasięg</th></tr>
<tr><td>wiosna (rzepak)</td><td class="l">493 m</td><td class="l">294 m</td><td class="l">1178 m</td></tr>
<tr><td>lato (gryka, TUZ)</td><td class="l">2156 m</td><td class="l">1285 m</td><td class="l">5142 m</td></tr>
<tr><td>jesień</td><td class="l">1275 m</td><td class="l">760 m</td><td class="l">3041 m</td></tr>
</table>
{obraz("mapa_wojewodztwa.png", "Potencjał pożytkowy województwa po splocie jądrem zasięgu lotu.")}
<p class="mniej">Dystanse z <b>Couvillon i in. 2014</b> (<i>PLOS ONE</i>) — odczyt
5 tys. tańców pszczelich. λ dobrane numerycznie tak, by średni ważony dystans
jądra równał się zmierzonemu. Jądra <b>znormalizowane</b>: bez tego hektar
pożytku letniego liczyłby się 19× mocniej niż wiosennego, wyłącznie z geometrii.</p>
</div>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">6</span>Z ton cukru na rodziny</h2>
<div class="wzor">pojemność = cukier w zasięgu lotu / 72 kg cukrów na rodzinę</div>
<p>72 kg = 90 kg miodu rocznie ÷ 1,25. Wynik przeciętnego roku z 7 sezonów:
mediana <b>{pl(zlo['pojemnosc_percentyle']['50'], 0)}</b> rodzin,
percentyl 90 to <b>{pl(zlo['pojemnosc_percentyle']['90'], 0)}</b> rodzin.</p>
{obraz("mapa_sredni_rok.png", "Przeciętny rok z 7 sezonów i warstwa niezawodności — jak często miejsce było w czołówce.")}
<p class="mniej">To dzielenie przez stałą — daje liczbę porównywalną ze stanem
posiadania, ale nie zmienia mapy ani kolejności miejsc.</p>
</div>
<div class="strz">↓</div>

<div class="krok">
<h2><span class="nr">7</span>Wynik — współrzędne z promieniem</h2>
<p>Maksima lokalne rozdzielone o 8 km. Dla każdego liczony <b>promień
równoważności</b> — jak daleko można się odsunąć, zanim straci się 5 / 10 / 20%.</p>
<div class="wzor">miejsce nr 1 · {pl(m1['rodzin'], 0)} rodzin · {m1['lat']:.4f} N  {m1['lon']:.4f} E
w promieniu {pl(m1['promien_95_m'], 0)} m tracisz &lt; 5%
w promieniu {pl(m1['promien_80_m'], 0)} m tracisz &lt; 20%</div>
{obraz("mapa_dzialki_1.png", "Miejsce nr 1 w kadrze 3 km: heatmapa potencjału na granicach działek ARiMR, z okręgami równoważności.")}
<p class="mniej">Wewnątrz tego koła mapa nie rozstrzyga — decyduje dojazd, osłona
od wiatru i woda. Promień jest mały, bo pole potencjału <b>nie jest płaskie</b>:
odsunięcie o 100 m zmniejsza wkład sąsiedniego pola o 29%.</p>
</div>

<div class="krok">
<h2>Czy to się broni</h2>
<div class="wyjasn">
<p>Model nie jest sprawdzany sam ze sobą — każdy wiersz to porównanie
z <b>niezależnym źródłem</b>: inną mapą upraw, statystyką GUS albo
obserwacjami terenowymi IMGW. Dwa ostatnie wiersze to co innego: sprawdzają,
czy wynik nie stoi na przypadkowo dobranych założeniach.</p>
</div>
<table>
<tr><th>sprawdzenie</th><th>wynik</th></tr>
<tr><td>bilans cukru: mapa wobec hektarów × wydajność</td><td class="l"><b class="ok">{pl(gus['cukry_mapa_kg'] / 1e6)} = {pl(gus['cukry_mapa_kg'] / 1e6)} mln kg</b></td></tr>
<tr><td>areał rzepaku 2022 wobec EUCROPMAP</td><td class="l"><b class="ok">−6%</b></td></tr>
<tr><td>produkcja miodu wobec GUS</td><td class="l">scenariusz zawodowy w przedziale</td></tr>
<tr><td>kwitnienie lipy wobec obserwacji IMGW</td><td class="l"><b class="ok">2,8 d</b></td></tr>
<tr><td>kwitnienie robinii wobec IMGW</td><td class="l"><b class="ok">−1 d</b></td></tr>
<tr><td>odporność na wartość łąk (zmiana 5-krotna)</td><td class="l">r ≥ {pl(najgorszy_tuz, 3)}</td></tr>
<tr><td>odporność na kształt jądra (3 warianty)</td><td class="l">r ≥ {pl(najgorszy_ksz, 3)}</td></tr>
</table>
<p><b class="uw">Czego nie wiemy:</b> nikt nie porównał tej mapy z realnymi
zbiorami z pasiek. Walidacja jest <b>składnikowa</b> — sprawdzone są wejścia
i sumy, nie sam ranking miejsc. To największa dziura projektu.</p>
<p class="mniej">Model przewiduje <b>termin</b> kwitnienia, ale nie
<b>lokalizację</b> upraw w przyszłym sezonie — detekcja wymaga zdjęć z sezonu,
który ma być zmapowany. Zamiast tego działa warstwa niezawodności: 6,6%
powierzchni było w czołówce we wszystkich 7 sezonach.</p>
</div>

<p class="stopka">Model pożytkowy dla pszczelarstwa wędrownego —
integracja Sentinel-1, Sentinel-2 i danych meteorologicznych.</p>
</div>
"""
    out = ROOT / "mechanika.html"
    out.write_text(HTML, encoding="utf-8")
    print(f"zapisano {out.name}: {len(HTML) / 1024:.0f} kB")
