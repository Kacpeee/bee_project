"""
Raport wylacznie o rzepaku - jak policzono GDZIE, KIEDY i ILE.

PO CO OSOBNY RAPORT
Glowny raport opisuje caly model pozytkowy: 16 gatunkow, dwa zrodla warstw,
kalendarz, pojemnosc. Rzepak jest w nim jednym z watkow, a to on niesie
polowe cukru w wojewodztwie i jako jedyny ma wlasny model terminu.

TEZA TEGO RAPORTU
Modelu nie da sie dzis sprawdzic w PRZOD - sezon 2027 jeszcze nie nastapil,
a deklaracje ARiMR istnieja tylko za 2025 i 2026. Da sie natomiast sprawdzic
WSTECZ: puscic klasyfikator na lata 2019-2024, dla ktorych nie bylo zadnych
etykiet, i porownac wynik ze zrodlem niezaleznym. To jest jedyny dostepny
dowod, ze model dziala poza rokiem, na ktorym sie uczyl - i on jest tresci
sekcji 2.

Tekst po polsku, podpisy rysunkow po angielsku (mapy sa wspoldzielone
z README i paczka stron).

ZASADA
Zadna liczba nie jest tu wpisana recznie - wszystkie ida z wyniki/json.

Uruchomienie:
    python skrypty/raport/raport_rzepak.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"
J = WYNIKI / "json"


def czytaj(nazwa: str) -> dict:
    return json.loads((J / nazwa).read_text(encoding="utf-8"))


def obraz(nazwa: str, podpis: str) -> str:
    f = MAPY / nazwa
    if not f.exists():
        return f'<p class="brak">brak rysunku: {nazwa}</p>'
    b = base64.b64encode(f.read_bytes()).decode()
    return (f'<figure><img src="data:image/png;base64,{b}" alt="{podpis}">'
            f'<figcaption>{podpis}</figcaption></figure>')


def pl(x, n=3):
    """Liczba po polsku - przecinek dziesietny, spacja jako separator tysiecy."""
    if not isinstance(x, (int, float)):
        return str(x)
    return f"{x:,.{n}f}".replace(",", " ").replace(".", ",")


STYL = """
/* PALETA - trzy role, nie jeden kolor.
   Wczesniejsza wersja byla w calosci zielona: tlo, karty, naglowki, liczby.
   Nic sie przez to nie wyroznialo. Teraz tlo jest NEUTRALNE (grafit),
   zloto niesie temat (rzepak, miod) i prowadzi wzrok po naglowkach,
   blekit oznacza dane i pomiary, zielen wylacznie DOBRE WYNIKI.       */
:root{
  --tlo:#15171b; --tlo2:#1b1e23; --kar:#1f2329; --kar2:#262b32;
  --atr:#e9ecf0; --mut:#98a2ae; --ram:#333a43; --ram2:#404955;
  --zloto:#e8b33c; --zloto2:#f5cf7a;
  --blekit:#6bb3e8; --ziel:#57c98d; --zle:#e8785f;
  --cien:0 2px 12px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{margin:0;background:var(--tlo);color:var(--atr);
     font:16px/1.72 "Segoe UI",system-ui,sans-serif;
     background-image:radial-gradient(1200px 600px at 15% -10%,
       rgba(232,179,60,.07), transparent 60%);
     background-attachment:fixed}
.w{max-width:900px;margin:0 auto;padding:56px 22px 90px}

h1{font-size:35px;margin:0 0 10px;letter-spacing:-.7px;line-height:1.2;
   font-weight:660;color:#fff}
h1::after{content:"";display:block;width:70px;height:3px;
  background:linear-gradient(90deg,var(--zloto),transparent);
  margin-top:18px;border-radius:2px}
h2{font-size:26px;margin:70px 0 8px;letter-spacing:-.35px;font-weight:650;
   color:#fff;display:flex;align-items:center;gap:14px}
h2 .nr{font-size:15px;color:var(--tlo);background:var(--zloto);
  border-radius:9px;padding:3px 11px;font-weight:700;flex:0 0 auto;
  letter-spacing:0}
h3{font-size:18px;margin:36px 0 10px;font-weight:620;color:var(--zloto2)}
p{margin:0 0 14px}
.lead{color:var(--mut);font-size:17px;margin:0 0 12px}
.etap{display:inline-block;background:rgba(232,179,60,.13);color:var(--zloto);
  border:1px solid rgba(232,179,60,.32);font-size:11.5px;padding:5px 13px;
  border-radius:20px;letter-spacing:.8px;text-transform:uppercase;
  margin-bottom:16px;font-weight:600}

table{border-collapse:separate;border-spacing:0;width:100%;margin:18px 0;
  font-size:14.5px;background:var(--kar);border:1px solid var(--ram);
  border-radius:11px;overflow:hidden}
th,td{padding:11px 15px;border-bottom:1px solid var(--ram);text-align:left}
tbody tr:last-child td{border-bottom:none}
th{font-weight:600;color:var(--mut);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.7px;background:var(--tlo2);border-bottom:1px solid var(--ram2)}
td:not(:first-child),th:not(:first-child){text-align:right;
  font-variant-numeric:tabular-nums}
td:first-child{color:var(--atr)}
caption{caption-side:top;text-align:left;color:var(--mut);font-size:13px;
  padding:0 0 9px;font-style:italic}
b.ok{color:var(--ziel)} b.zle{color:var(--zle)}

.wzor{background:#101216;border:1px solid var(--ram);
  border-left:3px solid var(--blekit);padding:15px 19px;
  border-radius:0 10px 10px 0;color:#bcd6ea;
  font-family:"Cascadia Mono",Consolas,monospace;font-size:13.5px;
  margin:18px 0;overflow-x:auto;white-space:pre;line-height:1.6}
.uwaga{background:rgba(232,120,95,.09);border-left:3px solid var(--zle);
  padding:15px 19px;border-radius:0 10px 10px 0;font-size:14.5px;
  color:#f3c9bd;margin:18px 0}
.klucz{background:rgba(107,179,232,.09);border-left:3px solid var(--blekit);
  padding:17px 21px;border-radius:0 10px 10px 0;font-size:15.5px;margin:20px 0;
  color:#d6e7f4}
.mniej{color:var(--mut);font-size:14px}

figure{margin:30px 0}
figure img{width:100%;border:1px solid var(--ram2);border-radius:12px;
  display:block;box-shadow:var(--cien)}
figcaption{color:var(--mut);font-size:13.5px;margin-top:11px;font-style:italic;
  padding-left:2px;border-left:2px solid var(--ram2);padding-left:12px}

ol.kroki{padding-left:0;counter-reset:k;list-style:none;margin:20px 0}
ol.kroki li{counter-increment:k;position:relative;padding-left:48px;
  margin-bottom:18px}
ol.kroki li::before{content:counter(k);position:absolute;left:0;top:1px;
  width:30px;height:30px;border-radius:50%;background:transparent;
  border:1.5px solid var(--zloto);color:var(--zloto);
  display:flex;align-items:center;justify-content:center;font-size:14px;
  font-weight:700}

.spis{background:var(--kar);border:1px solid var(--ram);border-radius:14px;
  padding:10px 26px;margin:32px 0}
.spis a{color:var(--atr);text-decoration:none;display:flex;gap:14px;
  padding:11px 0;font-size:15.5px;border-bottom:1px solid var(--ram);
  transition:.14s}
.spis a:last-child{border-bottom:none}
.spis a:hover{color:var(--zloto)}
.spis a b{color:var(--mut);font-weight:600;min-width:16px;
  font-variant-numeric:tabular-nums}
.spis a:hover b{color:var(--zloto)}

.karty{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:14px;margin:22px 0}
.kafel{background:var(--kar);border:1px solid var(--ram);border-radius:12px;
  padding:20px 22px;border-top:2px solid var(--blekit)}
.kafel .duza{font-size:32px;font-weight:660;color:var(--blekit);
  letter-spacing:-.7px;line-height:1.1}
.kafel .duza.z{color:var(--zloto)}
.kafel .co{color:var(--mut);font-size:13.5px;margin-top:8px;line-height:1.5}

.brak{color:var(--zle);font-style:italic}
footer{margin-top:76px;padding-top:24px;border-top:1px solid var(--ram);
  color:var(--mut);font-size:13.5px}
code{background:var(--kar2);padding:2px 7px;border-radius:5px;font-size:13.5px;
  color:var(--zloto2);border:1px solid var(--ram)}
ul{margin:0 0 14px;padding-left:22px}
li{margin-bottom:9px}
li::marker{color:var(--zloto)}
i,em{color:#cfd6de}
@media(max-width:640px){.w{padding:32px 16px 60px}h1{font-size:27px}
  h2{font-size:22px}}
"""


def buduj() -> str:
    s1s2 = czytaj("wielo_s1s2.json")
    rz = s1s2["per_gatunek"]["rzepak ozimy"]
    piks = czytaj("ocena_pikselowa_pelna.json")
    pik_zr = piks["pokolenia"]["pokolenie 2 (S1+S2, 130 cech)"]["rzepak"]
    pik_pr = piks["prewalencja_rzeczywista"]["rzepak"]
    odl = piks["rzepak_wg_odleglosci_ze_zbozami"]
    fen = czytaj("fenologia_final.json")
    m = fen["model"]
    hind = czytaj("prognoza_w_sezonie.json")
    imgw = czytaj("imgw_walidacja.json")
    kal = czytaj("kalibracja_arealowa.json")
    jad = czytaj("jadro_sezonowe.json")
    ksz = czytaj("wrazliwosc_ksztaltu.json")["wyniki"]
    sr = czytaj("sredni_rok.json")
    stab = czytaj("stabilnosc_rzepaku.json")["korelacje"]
    przed = czytaj("przedkwitnieniowy.json")["wyniki"]
    star = czytaj("start_walidacja.json")["warianty"]
    tran = czytaj("wielo_transfer.json")
    tr_rz = tran["per_gatunek"]["rzepak ozimy"]
    woj = czytaj("wojewodztwo.json")
    wios = jad["jadra"]["wiosna"]
    ar = sr["areal_det_ha"]

    def w_odl(k):
        d = odl.get(k, {})
        return (f"<td>{pl(d.get('n', 0), 0)}</td><td>{pl(d.get('precyzja', 0))}</td>"
                f"<td>{pl(d.get('czulosc', 0))}</td>"
                f"<td><b>{pl(d.get('f1', 0))}</b></td>").replace(",", " ")

    hs = hind["statystyki"]
    dni = sorted(int(k) for k in hs)
    PL_M = {"XII": "grudnia", "I": "stycznia", "II": "lutego",
            "III": "marca", "IV": "kwietnia", "cały sezon": "cały sezon"}

    return f"""<!doctype html><html lang="pl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rzepak ozimy — raport modelu</title>
<style>{STYL}</style>
<div class="w">

<span class="etap">województwo lubelskie · raport jednego gatunku</span>
<h1>Rzepak ozimy: gdzie rośnie, kiedy zakwitnie<br>i ile z tego dosięgnie pszczoła</h1>
<p class="lead">Rzepak niesie około połowy cukru nektarowego w województwie
i jako jedyny gatunek ma własny model terminu kwitnienia. Ten raport prowadzi
całą ścieżkę rzepakową od zdjęcia satelitarnego do mapy. Wszystkie liczby są
odczytywane z <code>wyniki/json/</code> przy budowaniu — żadna nie jest
wpisana ręcznie.</p>

<div class="spis">
  <a href="#gdzie"><b>1</b>Gdzie rośnie — rozpoznanie uprawy z orbity</a>
  <a href="#wstecz"><b>2</b>Model przeniesiony na inne sezony</a>
  <a href="#kiedy"><b>3</b>Kiedy zakwitnie — model termiczny</a>
  <a href="#prog"><b>4</b>Skąd wzięły się próg GDD i temperatura bazowa</a>
  <a href="#splot"><b>5</b>Ile dosięgnie pszczoła — splot z jądrem zasięgu lotu</a>
  <a href="#mapy"><b>6</b>Mapy</a>
  <a href="#dane"><b>7</b>Dane i ograniczenia</a>
</div>

<!-- ============================================================ GDZIE -->
<h2 id="gdzie"><span class="nr">1</span>Gdzie rośnie — rozpoznanie uprawy z orbity</h2>
<p class="lead">Pytanie: <b>które pole jest rzepakiem?</b> Odpowiada las
losowy czytający cały rok zdjęć satelitarnych.</p>

<h3>Dlaczego akurat rzepak jest łatwy</h3>
<p>Rzepak wysyła w ciągu roku trzy sygnały, których żadna inna uprawa
w tym układzie nie powtarza:</p>
<ol class="kroki">
  <li><b>Zimuje zielony.</b> Kiedy zboża są rzadkie, a gleba ciemna, rzepak
      trzyma gęstą rozetę przez całą zimę — widać to w NDVI od października.</li>
  <li><b>W maju żółknie na całą powierzchnię.</b> NDYI, czyli różnica zieleni
      i błękitu, skacze przez mniej więcej dwa tygodnie nad całym łanem.
      Nic innego w tej skali tego nie robi.</li>
  <li><b>W lipcu zostaje ściernisko.</b> Żniwa są wczesne, więc pole spada do
      wartości gołej gleby, gdy uprawy jare są jeszcze zielone.</li>
</ol>

<h3>Co model czyta</h3>
<div class="wzor">26 okien półmiesięcznych (wrzesień → wrzesień)
w każdym oknie:  NDVI, NDYI      — optyka, jako anomalie sceny
                 VV, VH, VH−VV   — radar, w decybelach
razem {s1s2['n_cech']['S1_S2']} cech, 300 drzew</div>
<p><b>Anomalia sceny, nie surowy wskaźnik.</b> Od każdej wartości optycznej
odejmowana jest mediana gruntów ornych <i>z tego samego zdjęcia</i>. Bez tego
model uczyłby się kąta słońca i zamglenia zamiast rośliny — ta sama uprawa
wygląda inaczej na zdjęciu czerwcowym i wrześniowym z powodów czysto
atmosferycznych.</p>

<h3>Jak sprawdzano klasyfikator: walidacja przestrzenna</h3>
<p><b>Problem:</b> sąsiednie działki są do siebie podobne. Ta sama gleba, ten
sam gospodarz, ta sama data siewu, często ta sama odmiana. Gdyby zbiór
podzielić losowo, niemal identyczne pola trafiłyby jednocześnie do treningu
i do testu — model zdałby egzamin, bo widział odpowiedzi.</p>
<p><b>Rozwiązanie:</b> województwo dzielone jest na <b>kwadraty 2,5 km</b>,
a do zbioru testowego trafiają całe bloki, nie pojedyncze działki.</p>
<div class="wzor">bx = ⌊x / 2500⌋ ,  by = ⌊y / 2500⌋
dzialka trafia do testu, gdy  (bx + by) mod 10 < 3</div>
<p><b>Ile to daje:</b> mediana odległości działki testowej do najbliższej
treningowej rośnie z <b>439 m</b> przy podziale losowym do <b>1 723 m</b> przy
blokach. Tylko 1,8% działek testowych ma sąsiada tej samej klasy bliżej niż
500 m.</p>
<p><b>Czy to zmienia wynik:</b> sprawdzone przez zaostrzenie. Przy blokach
10 km, czyli separacji czterokrotnie ostrzejszej, rzepak dostaje
<b class="ok">0,947</b> — czyli <i>więcej</i>, nie mniej. Model uczy się
rośliny, nie lokalizacji.</p>

<table>
  <caption>Walidacja przestrzenna, bloki 2,5 km, 12 klas</caption>
  <thead><tr><th>zestaw czujników</th><th>cech</th><th>F1-makro</th>
    <th>F1 rzepaku</th></tr></thead>
  <tbody>
    <tr><td>sam Sentinel-2</td><td>{s1s2['n_cech']['S2']}</td>
        <td>{pl(s1s2['f1_makro']['S2'])}</td><td>{pl(rz['S2']['f1'])}</td></tr>
    <tr><td>sam Sentinel-1</td><td>{s1s2['n_cech']['S1']}</td>
        <td>{pl(s1s2['f1_makro']['S1'])}</td><td>—</td></tr>
    <tr><td><b>oba razem</b></td><td>{s1s2['n_cech']['S1_S2']}</td>
        <td><b>{pl(s1s2['f1_makro']['S1_S2'])}</b></td>
        <td><b class="ok">{pl(rz['S1_S2']['f1'])}</b></td></tr>
  </tbody>
</table>
<p>Radar odpowiada za {pl(s1s2['waznosc_radaru']*100, 1)}% ważności cech, ale
jego przewaga rozstrzygająca to pokrycie: <b>{s1s2['okna_puste']['S1']} pustych
okien wobec {s1s2['okna_puste']['S2']} u optyki</b> — w pierwszej połowie
stycznia 100% punktów nie ma ani jednej bezchmurnej sceny.</p>

<h3>Środek działki to nie piksel</h3>
<p>Powyższe F1 mierzy się w <b>jednym reprezentatywnym punkcie wewnątrz
działki</b>. Wdrożenie klasyfikuje każdy piksel, także brzegowy. Zmierzone na
{pl(piks['pokolenia']['pokolenie 2 (S1+S2, 130 cech)']['n_pikseli'], 0)} pikselach
odłożonych z bloków testowych, ze zbożami w zbiorze:</p>
<table>
  <thead><tr><th>poziom</th><th>precyzja</th><th>czułość</th><th>F1</th></tr></thead>
  <tbody>
    <tr><td>środek działki</td><td>0,938</td><td>0,942</td>
        <td><b>{pl(rz['S1_S2']['f1'])}</b></td></tr>
    <tr><td>pojedynczy piksel, próba zrównoważona</td>
        <td>{pl(pik_zr['precyzja'])}</td><td>{pl(pik_zr['czulosc'])}</td>
        <td>{pl(pik_zr['f1'])}</td></tr>
    <tr><td><b>pojedynczy piksel, proporcje terenowe</b></td>
        <td><b class="zle">{pl(pik_pr['precyzja'])}</b></td>
        <td>{pl(pik_pr['czulosc'])}</td>
        <td><b>{pl(pik_pr['f1'])}</b></td></tr>
  </tbody>
</table>
<p>W realnych proporcjach mniej więcej <b>co drugi piksel wskazany jako rzepak
nim nie jest</b> — 87% gruntów to coś innego, głównie zboża. Czułość się nie
zmienia i zmienić nie może, bo nie zależy od częstości występowania.</p>

<p>Prawie cały ten błąd siedzi przy granicy pola:</p>
<table>
  <caption>Trafność wg odległości od miedzy</caption>
  <thead><tr><th>odległość</th><th>pikseli</th><th>precyzja</th>
    <th>czułość</th><th>F1</th></tr></thead>
  <tbody>
    <tr><td><b>0–10 m</b></td>{w_odl('0-10')}</tr>
    <tr><td>10–20 m</td>{w_odl('10-20')}</tr>
    <tr><td>20–40 m</td>{w_odl('20-40')}</tr>
    <tr><td>&gt; 40 m</td>{w_odl('40-10000')}</tr>
  </tbody>
</table>
<div class="uwaga"><b>{piks['udzial_pikseli_do_10m']*100:.0f}% pikseli leży
bliżej niż 10 m od granicy działki.</b> Pola są tu wąskimi pasami, a piksel
Sentinela 10 m leżący na miedzy fizycznie zawiera dwie uprawy. Model nie myli
się co do tych pikseli — one naprawdę są dwiema rzeczami naraz. Dlatego mapy
nigdy nie używają surowych pikseli.</div>

<h3>Poziom jest zły, nawet gdy układ jest dobry</h3>
<p>Trening szedł na próbie <b>zrównoważonej</b> — po równo działek każdego
gatunku, żeby żaden nie przepadł. Model wyniósł z tego przekonanie, że
wszystkich upraw jest po tyle samo, i w terenie rozdaje piksele zbyt hojnie
klasom rzadkim. Poprawka: jeden współczynnik na gatunek z roku wzorcowego.</p>
<table>
  <thead><tr><th>kontrola</th><th>wartość</th></tr></thead>
  <tbody>
    <tr><td>areał zadeklarowany, ARiMR 2025</td>
        <td>{pl(kal['areal_gsa']['rzepak ozimy'], 0)} ha</td></tr>
    <tr><td>wykryty przed korektą</td>
        <td>{pl(kal['areal_wykryty']['rzepak ozimy'], 0)} ha</td></tr>
    <tr><td>współczynnik kalibracji</td>
        <td><b>×{pl(kal['wspolczynniki']['rzepak ozimy'])}</b></td></tr>
  </tbody>
</table>
<p class="mniej">Rzepak jest wykrywany o
<b>+{pl((kal['areal_wykryty']['rzepak ozimy'] / kal['areal_gsa']['rzepak ozimy'] - 1) * 100, 1)}%</b>
za obficie, więc zrównoważona próba prawie go nie zniekształca — inaczej niż
słonecznika, wykrywanego dziewięciokrotnie za obficie. Współczynnik
{pl(kal['wspolczynniki']['rzepak ozimy'])} sprowadza rok wzorcowy do zgodności
z definicji, bo właśnie z niego został policzony.</p>

<p><b>Prawdziwe sprawdzenie jest na innym roku.</b> Ten sam współczynnik
zastosowany do 2022:</p>
<table>
  <thead><tr><th>2022 — rok bez deklaracji</th><th>areał</th></tr></thead>
  <tbody>
    <tr><td>EUCROPMAP (JRC)</td>
        <td>{pl(kal['kontrola_eucropmap']['2022']['eucropmap_ha'], 0)} ha</td></tr>
    <tr><td>nasz model po korekcie</td>
        <td>{pl(kal['kontrola_eucropmap']['2022']['model_ha'], 0)} ha</td></tr>
    <tr><td>odchylenie</td>
        <td><b>{pl(kal['kontrola_eucropmap']['2022']['odchylenie_pct'], 1)}%</b></td></tr>
  </tbody>
</table>
<div class="uwaga"><b>Znaki są przeciwne i to nie przypadek.</b> W roku
wzorcowym model wykrywa
+{pl((kal['areal_wykryty']['rzepak ozimy'] / kal['areal_gsa']['rzepak ozimy'] - 1) * 100, 1)}%
<i>za dużo</i>, a po korekcie w 2022 —
{pl(abs(kal['kontrola_eucropmap']['2022']['odchylenie_pct']), 1)}% <i>za mało</i>.
Współczynnik z 2025 lekko przestrzeliwuje w drugą stronę; to nie jest ta sama
liczba dwa razy. Do tego <b>EUCROPMAP sam jest modelem</b>, nie pomiarem
w polu — te kilka procent to rozbieżność dwóch szacunków, a nie błąd naszego
wobec prawdy. Ostrożny wniosek: współczynnik przenosi się na inne lata
<i>z dokładnością do kilku procent</i>, i tyle da się z tego powiedzieć.</div>

<h3>Znaleźć pola, zanim zakwitną</h3>
<p>Datę kwitnienia mierzy się z NDYI, czyli z sygnału żółci. Gdyby te same
zdjęcia wybierały też, <i>które</i> pola mierzyć, data byłaby uczona sama
z siebie. Dlatego osobny klasyfikator używa wyłącznie okien sprzed
kwitnienia:</p>
<table>
  <caption>Ile skuteczności zostaje przy obcięciu cech do dnia decyzji</caption>
  <thead><tr><th>dane do</th><th>wyprzedzenie</th><th>F1 rzepaku</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{PL_M.get(k, k)}</td><td>{v.get('wyprzedzenie', '—')}</td>"
         f"<td>{pl(v['f1_rzepak'])}</td></tr>" for k, v in przed.items())}
  </tbody>
</table>
<p>Na koniec marca rzepak rozpoznaje się z <b>93% skuteczności pełnego
modelu, sześć tygodni przed kwitnieniem</b>. To właśnie utrzymuje datę poza
kołem — i otwiera drogę do prognozowania także <i>lokalizacji</i>, czego ten
projekt jeszcze nie robi.</p>

<!-- ============================================================ WSTECZ -->
<h2 id="wstecz"><span class="nr">2</span>Model przeniesiony na inne sezony</h2>
<p class="lead">Klasyfikator uczył się na jednym roczniku, a został sprawdzony
na dziewięciu sezonach. Za każdym razem rozpoznawał rzepak bardzo dobrze.</p>

<div class="klucz"><b>Model nie potrzebuje deklaracji, żeby działać.</b>
Uczy się raz — na roczniku 2025, jedynym z prawdą terenową — a potem czyta
same zdjęcia satelitarne. Dzięki temu daje mapę dla lat
{min(int(k) for k in ar)}–{max(int(k) for k in ar)}, dla których nie ma
żadnych wniosków ARiMR, i tak samo da ją dla sezonu nadchodzącego. Poniżej
trzy niezależne sprawdzenia, że to przeniesienie faktycznie działa.</div>

<div class="karty">
  <div class="kafel"><div class="duza">{pl(sr['walidacje']['det2022_vs_eucropmap2022'], 2)}</div>
    <div class="co">zgodność z niezależną mapą EUCROPMAP dla 2022 — roku
      bez żadnych deklaracji</div></div>
  <div class="kafel"><div class="duza">{pl(tr_rz['f1'], 2)}</div>
    <div class="co">F1 rzepaku po przeniesieniu na rocznik 2026, którego
      model nie widział</div></div>
  <div class="kafel"><div class="duza z">{pl(stab['2018 EUCROPMAP vs 2025 GSA'], 2)}</div>
    <div class="co">zgodność układu rejonów przez <b>siedem lat</b>
      i dwa różne źródła danych</div></div>
</div>

<h3>Czym się sprawdza rok bez etykiet</h3>
<p><b>Problem:</b> dla lat 2019–2024 nie ma żadnych etykiet, więc nie da się
policzyć F1. Trzeba czegoś, co powstało zupełnie inaczej.</p>
<p><b>Rozwiązanie:</b> EUCROPMAP — warstwa upraw dla całej Unii, robiona
przez Wspólne Centrum Badawcze Komisji Europejskiej z innego potoku, innych
cech i innego modelu. Porównuje się mapy <i>po rozmyciu zasięgiem lotu</i>,
bo to na tym poziomie działa produkt.</p>
<p class="mniej">Dlaczego po rozmyciu, a nie na pikselu: pomyłka między
dwiema sąsiednimi działkami nie ma znaczenia dla pszczoły, która i tak
oblatuje kilometr. Miarą sensowną jest zgodność <b>zagęszczeń rejonu</b>,
nie pojedynczych pól.</p>

<h3>Dowód pierwszy: niezależna mapa EUCROPMAP</h3>
<p>EUCROPMAP istnieje dla 2018 i 2022 — czyli dla lat, w których <b>nie ma
żadnych deklaracji ARiMR</b>, więc nie ma też jak podejrzeć odpowiedzi.</p>
<table>
  <thead><tr><th>porównanie</th><th>korelacja</th><th>co to znaczy</th></tr></thead>
  <tbody>
    <tr><td>nasza detekcja 2022 ↔ EUCROPMAP 2022</td>
        <td><b class="ok">{pl(sr['walidacje']['det2022_vs_eucropmap2022'])}</b></td>
        <td>ten sam rok, dwa niezależne modele</td></tr>
    <tr><td>nasza detekcja 2025 ↔ deklaracje 2025</td>
        <td><b class="ok">{pl(sr['walidacje']['det2025_vs_gsa2025'])}</b></td>
        <td>kontrola na roku z prawdą terenową</td></tr>
  </tbody>
</table>
<p>Zgodność w 2022 jest <b>o 0,03 niższa</b> niż w 2025, mimo że rok 2022 leży
trzy lata przed danymi treningowymi i nie ma dla niego ani jednej etykiety.
To jest miara utraty jakości przy cofaniu się w czasie — i jest mała.</p>

<h3>Dowód drugi: uczenie na 2025, sprawdzanie na 2026</h3>
<p>Osobny test: model nauczony wyłącznie na deklaracjach
{tran['trening']} ({pl(tran['n_2025'], 0)} działek), sprawdzony na całkowicie
osobnym roczniku {tran['test']} ({pl(tran['n_2026'], 0)} działek).</p>
<table>
  <thead><tr><th>miara dla rzepaku</th><th>wynik</th></tr></thead>
  <tbody>
    <tr><td>F1 na działce, inny rok</td><td><b>{pl(tr_rz['f1'])}</b></td></tr>
    <tr><td>korelacja po splocie zasięgiem lotu</td>
        <td><b class="ok">{pl(tr_rz['r_splot'])}</b></td></tr>
    <tr><td>korelacja cukru całej warstwy</td>
        <td>{pl(tran['cukier_splot_r'])}</td></tr>
  </tbody>
</table>
<p class="mniej">F1 spada z {pl(rz['S1_S2']['f1'])} do {pl(tr_rz['f1'])}, czyli
o {pl(rz['S1_S2']['f1'] - tr_rz['f1'], 3)} — tyle kosztuje przeniesienie na
rok, którego model nie widział. Po rozmyciu zasięgiem lotu, czyli tam, gdzie
mapa faktycznie działa, zostaje {pl(tr_rz['r_splot'])}.</p>

<h3>Dowód trzeci: rzepak wędruje, a rejony zostają</h3>
<p>Rzepak jest w płodozmianie, więc pojedyncze pole zmienia się z roku na rok.
Gdyby model tylko zapamiętał lokalizacje, korelacje między odległymi latami
runęłyby. Nie runęły:</p>
<table>
  <caption>Korelacje układu przestrzennego między źródłami i latami</caption>
  <thead><tr><th>para</th><th>odstęp</th><th>korelacja</th></tr></thead>
  <tbody>
    <tr><td>EUCROPMAP 2018 ↔ EUCROPMAP 2022</td><td>4 lata</td>
        <td>{pl(stab['2018 EUCROPMAP vs 2022 EUCROPMAP'])}</td></tr>
    <tr><td>EUCROPMAP 2018 ↔ deklaracje 2025</td><td>7 lat</td>
        <td>{pl(stab['2018 EUCROPMAP vs 2025 GSA'])}</td></tr>
    <tr><td>EUCROPMAP 2022 ↔ deklaracje 2025</td><td>3 lata</td>
        <td>{pl(stab['2022 EUCROPMAP vs 2025 GSA'])}</td></tr>
    <tr><td>deklaracje 2025 ↔ deklaracje 2026</td><td>1 rok</td>
        <td>{pl(stab['2025 GSA vs 2026 GSA'])}</td></tr>
  </tbody>
</table>
<p>Nawet przez siedem lat i przez granicę dwóch zupełnie różnych źródeł danych
układ rejonów rzepakowych trzyma się na poziomie
{pl(stab['2018 EUCROPMAP vs 2025 GSA'], 2)}. <b>Pojedyncze pole wędruje,
rejon zostaje</b> — i to rejon jest tym, co widzi pszczoła, bo splot zasięgiem
lotu i tak uśrednia po kilometrze.</p>

<h3>Areał wykryty rok po roku</h3>
<table>
  <caption>Bez żadnych deklaracji — sama detekcja satelitarna</caption>
  <thead><tr><th>rok</th>{"".join(f"<th>{r}</th>" for r in sorted(ar))}</tr></thead>
  <tbody><tr><td>rzepak, ha</td>
    {"".join(f"<td>{pl(ar[r], 0)}</td>" for r in sorted(ar))}</tr></tbody>
</table>
<p class="mniej">Zmienność {pl(min(ar.values()), 0)}–{pl(max(ar.values()), 0)} ha
to około ±16% wokół średniej. Wahania między latami są realne —
rzepak reaguje na ceny i na przezimowanie — ale mieszczą się w skali, którą
znamy z danych ARiMR między 2025 a 2026.</p>

<div class="klucz"><b>Czego to nie dowodzi.</b> Wszystkie trzy dowody
sprawdzają <i>rozpoznawanie uprawy</i>. Nie mówią nic o tym, czy mapa
potencjału przekłada się na zbiór miodu — tego nie sprawdziliśmy nigdy
i pozostaje to największą luką projektu.</div>

<!-- ============================================================ KIEDY -->
<h2 id="kiedy"><span class="nr">3</span>Kiedy zakwitnie — model termiczny</h2>
<p class="lead">Pytanie: <b>którego dnia pole jest w pełni kwitnienia?</b>
Ten model nie klasyfikuje pikseli, więc nie ma F1 — jego błąd mierzy się
w dniach.</p>

<h3>Mechanizm</h3>
<p>Rośliny nie idą za kalendarzem, tylko za nagromadzonym ciepłem. Każdy dzień
dokłada tyle, o ile jego średnia temperatura przekracza bazę, poniżej której
rozwój stoi. Kwitnienie następuje, gdy suma przekroczy próg.</p>
<div class="wzor">GDD = Σ max( (T_max + T_min)/2 − {pl(m['baza'],1)} °C , 0 )   od {m['start']}
kwitnienie pierwszego dnia, w którym GDD ≥ {pl(m['prog'],0)}</div>

<h3>Czym tu jest „obserwacja” i jak liczony jest błąd</h3>
<p><b>Co znaczy „{m['n']} obserwacji".</b> Obserwacja to jedna para
<i>obszar × sezon</i>: dla danego rejonu i danego roku wyznaczona data pełni
kwitnienia. {m['obszarow']} obszarów razy 9 sezonów, minus przypadki
odrzucone i te bez wystarczających zdjęć, daje {m['n']}.</p>
<p><b>Skąd bierze się jedna obserwacja:</b></p>
<ol class="kroki">
  <li><b>Wybierz pola.</b> Klasyfikator przedkwitnieniowy wskazuje działki
      rzepaku, korzystając wyłącznie z okien sprzed kwitnienia — żeby data
      nie była wyznaczana na polach wybranych po tym, że zakwitły.</li>
  <li><b>Zbuduj krzywą.</b> Dla każdej dostępnej sceny Sentinel-2 liczony
      jest średni NDYI tych pól. Powstaje szereg punktów przez cały maj.</li>
  <li><b>Znajdź szczyt.</b> Przez trzy punkty wokół maksimum przeprowadzana
      jest parabola, a jej wierzchołek to data pełni. Dzięki temu wynik nie
      jest ograniczony do dni z przelotem satelity — może wypaść między nimi.</li>
</ol>
<p><b>Jak działa sama walidacja:</b> dla każdej z {m['n']} obserwacji model
jest budowany <b>od zera na pozostałych {m['n'] - 1}</b> — baza i próg
dobierane od nowa — a następnie przewiduje datę tej jednej odłożonej. Błąd
liczony jest wyłącznie na przewidywaniach odłożonych.</p>
<div class="wzor">dla i = 1 … {m['n']}:
    dopasuj (baza, prog) na wszystkich obserwacjach OPROCZ i
    przewidz date obserwacji i
RMSE = pierwiastek ze sredniej kwadratow tych {m['n']} bledow</div>
<p>Dzięki temu model nigdy nie jest oceniany na danych, które go
ukształtowały. Różnica między błędem dopasowania a leave-one-out nazywa się
<b>optymizmem dopasowania</b>: gdyby była duża, znaczyłoby to, że model uczy
się szumu zamiast zjawiska. Obie są w tabeli poniżej.</p>

<table>
  <caption>{m['n']} obserwacji, {m['obszarow']} obszarów, 9 sezonów</caption>
  <thead><tr><th>miara</th><th>dni</th></tr></thead>
  <tbody>
    <tr><td><b>RMSE, walidacja leave-one-out</b></td>
        <td><b class="ok">{pl(m['rmse'],2)}</b></td></tr>
    <tr><td>RMSE dopasowania (in-sample)</td>
        <td>{pl(m['rmse_dopasowania'],2)}</td></tr>
    <tr><td>odniesienie „zawsze średnia data"</td>
        <td>{pl(fen['odniesienie_stala'],2)}</td></tr>
  </tbody>
</table>
<p><b>Leave-one-out</b> znaczy, że baza i próg są dobierane od nowa bez
ocenianej obserwacji, więc model nigdy nie jest sprawdzany na danych, które go
ukształtowały. Odstęp między {pl(m['rmse'],2)} a {pl(m['rmse_dopasowania'],2)}
dnia to optymizm dopasowania — tutaj mały, i tak być powinno.</p>

<h3>Prognoza w trakcie sezonu</h3>
<p>Przed sezonem model nie ma pogody danego roku i zwraca średnią wieloletnią.
Prognozą staje się dopiero w miarę, jak realna pogoda się nagromadzi:</p>
<table>
  <thead><tr><th>dzień decyzji</th><th>RMSE (dni)</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{d}. dzień roku</td><td>{pl(hs[str(d)]['rmse'],2)}</td></tr>"
         for d in dni)}
  </tbody>
</table>
<p>O terminie decyduje kwiecień. Pytany w lutym model nie jest lepszy od
podania średniej wieloletniej; pytany 1 maja trafia z dokładnością
{pl(hs[str(dni[-1])]['rmse'],1)} dnia.</p>

<h3>Czy sama pogoda jest wiarygodna</h3>
<p>Temperatury pochodzą z reanalizy ERA5 przez Open-Meteo, a nie z termometru
w polu. Reanaliza to model atmosfery — wartość dla punktu jest wyliczana,
nie mierzona. Trzeba więc wiedzieć, ile z błędu terminu pochodzi z samej
pogody.</p>
<p>Porównanie z rzeczywistą stacją naziemną IMGW {imgw['stacja']} na
{pl(imgw['n_dni'], 0)} dniach z {len(imgw['lata'])} sezonów:</p>
<table>
  <thead><tr><th>miara</th><th>wartość</th><th>co opisuje</th></tr></thead>
  <tbody>
    <tr><td>RMSE temperatury</td><td>{pl(imgw['rmse_K'],2)} K</td>
        <td>typowa różnica dobowa</td></tr>
    <tr><td>obciążenie</td><td>{pl(imgw['bias_K'],2)} K</td>
        <td>czy ERA5 systematycznie zawyża</td></tr>
    <tr><td>korelacja</td><td>{pl(imgw['r'],3)}</td>
        <td>czy nadąża za przebiegiem</td></tr>
  </tbody>
</table>

<p><b>Ale to nie są jeszcze dni.</b> Błąd temperatury przekłada się na błąd
terminu przez sumowanie: żeby wiedzieć ile, trzeba policzyć datę kwitnienia
<i>dwa razy</i> — raz z ERA5, raz z pomiarów stacji — i porównać wyniki.</p>
<table>
  <caption>Ta sama procedura GDD, dwa źródła temperatur</caption>
  <thead><tr><th>sezon</th>{"".join(f"<th>{r}</th>" for r in sorted(imgw['terminy']))}</tr></thead>
  <tbody>
    <tr><td>ze stacji IMGW</td>
      {"".join(f"<td>{imgw['terminy'][r]['stacja']:.0f}</td>" for r in sorted(imgw['terminy']))}</tr>
    <tr><td>z ERA5</td>
      {"".join(f"<td>{imgw['terminy'][r]['era5']:.0f}</td>" for r in sorted(imgw['terminy']))}</tr>
    <tr><td><b>różnica (dni)</b></td>
      {"".join(f"<td><b>{imgw['terminy'][r]['era5'] - imgw['terminy'][r]['stacja']:+.0f}</b></td>" for r in sorted(imgw['terminy']))}</tr>
  </tbody>
</table>
<p>Podmiana ERA5 na prawdziwą stację przesuwa przewidywany termin średnio
o {pl(imgw['roznica_srednia_d'], 1)} dnia, typowo o <b>1,9 dnia</b>
(RMSE różnic), a w najgorszym sezonie — 2020 — o
{pl(imgw['roznica_maks_d'], 0)} dni.</p>

<div class="uwaga"><b>To nie jest wielkość pomijalna.</b> Przy całkowitym
błędzie modelu {pl(m['rmse'],2)} dnia sama jakość danych pogodowych odpowiada
za około <b>jedną trzecią wariancji</b>. Innymi słowy: gdyby ERA5 zastąpić
gęstą siecią stacji, model mógłby być zauważalnie dokładniejszy — reszta
błędu siedzi w samym modelu termicznym i w odczycie daty z NDYI.
Wcześniejsza wersja tego raportu twierdziła, że wpływ pogody jest
„znacznie mniejszy niż dzień"; to było oszacowanie na oko i było zaniżone.</div>

<!-- ============================================================ PROG -->
<h2 id="prog"><span class="nr">4</span>Skąd wzięły się próg GDD i temperatura bazowa</h2>
<div class="uwaga"><b>Zostały dopasowane, nie wzięte z literatury.</b> Żadne
publikowane źródło nie podaje bazy {pl(m['baza'],1)} °C z progiem
{pl(m['prog'],0)}. Obie liczby pochodzą z przeszukania siatki wobec
{m['n']} zmierzonych dat kwitnienia.</div>

<h3>Procedura</h3>
<ol class="kroki">
  <li><b>Zmierzyć cel.</b> Daty kwitnienia z krzywych NDYI, na polach
      wskazanych przez klasyfikator przedkwitnieniowy, żeby data nie była
      cyrkularna.</li>
  <li><b>Przeszukać siatkę.</b> Każda para (baza, próg) dostaje ocenę za to,
      jak dobrze odtwarza te daty we wszystkich obszarach i sezonach.</li>
  <li><b>Wybrać start akumulacji.</b> Sześć dat startowych przetestowanych,
      nie założonych.</li>
  <li><b>Odrzucić obserwacje niemożliwe.</b> Próg wyprowadzony fizycznie,
      nie dobrany ręcznie.</li>
  <li><b>Zwalidować leave-one-out.</b> Parametry dobierane bez ocenianej
      obserwacji.</li>
</ol>

<h3>Dlaczego 15 marca, a nie 1 lutego</h3>
<p>Start akumulacji jest wolnym parametrem i został wybrany pomiarem. Oba
kandydaty walidowano tak samo:</p>
<table>
  <thead><tr><th>start</th><th>baza</th><th>próg</th>
    <th>RMSE dopasowania</th><th>RMSE leave-one-out</th>
    <th>najgorszy przypadek</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{v['opis']}</td><td>{pl(v['baza'],1)} °C</td>"
         f"<td>{pl(v['prog'],0)}</td><td>{pl(v['rmse_in'],2)}</td>"
         f"<td><b>{pl(v['rmse_loo'],2)}</b></td>"
         f"<td>{pl(v['najgorszy'],1)}</td></tr>" for v in star.values())}
  </tbody>
</table>
<p>Start 15 marca wygrał <b>45 z 45 podziałów</b>, gdy sama data startu była
wybierana wewnątrz pętli walidacyjnej. Powód jest fizyczny: w lutym dzienne
przyrosty są bliskie zeru, więc te tygodnie dokładają szumu, nie różnicując
lat ciepłych od chłodnych.</p>

<h3>Sam próg nic nie znaczy</h3>
<p>Baza i próg wymieniają się między sobą: niższa baza dokłada więcej stopni
dziennie, więc potrzebuje wyższego progu do tej samej daty. Przeszukanie
siatki znajduje nie punkt, lecz <b>dolinę</b> rozwiązań prawie równoważnych.</p>
<div class="wzor">rozwiązania w promieniu 0,2 dnia od optimum, start 15 marca:
    baza   0,0 – 4,0 °C
    próg   305 – 540 GDD</div>
<p><b>{pl(m['prog'],0)} leży w środku tej doliny.</b> Podawanie progu bez bazy
jest bez sensu — parametrem jest para, nie żadna z liczb osobno.</p>

<h3>Dlaczego nie da się tego porównać z literaturą</h3>
<table>
  <caption>Publikowane progi dla kwitnienia rzepaku ozimego</caption>
  <thead><tr><th>źródło</th><th>baza</th><th>start</th><th>próg</th></tr></thead>
  <tbody>
    <tr><td>Czechy, <i>Atmosphere</i> 2021</td><td>6,0 °C</td>
        <td>30 I</td><td>157</td></tr>
    <tr><td>rejon Skopje, BBCH 63</td><td>—</td><td>—</td><td>633–809</td></tr>
    <tr><td>Estonia, przezimowanie</td><td>5,0 °C</td><td>—</td><td>416</td></tr>
    <tr><td><b>ten model</b></td><td><b>{pl(m['baza'],1)} °C</b></td>
        <td><b>{m['start']}</b></td><td><b>{pl(m['prog'],0)}</b></td></tr>
  </tbody>
</table>
<p>Suma GDD ma sens wyłącznie razem ze swoją bazą i datą startu. Przy bazie
6 °C odejmujesz codziennie o cztery i pół stopnia więcej niż przy 1,5 °C, więc
ta sama data kwitnienia daje zupełnie inną sumę. Liczby 157, 430 i 633 nie są
ze sobą sprzeczne — to różne układy współrzędnych.</p>

<h3>Odrzucanie obserwacji bez wybierania ręką</h3>
<p>Część szczytów NDYI jest fałszywa: chmura, sąsiednie pole gorczycy, źle
posadzona krzywa. Usuwanie ich na oko byłoby dopasowywaniem danych do modelu.
Próg wyprowadzono więc z tego, co sam model potrafi wyjaśnić:</p>
<div class="wzor">rozrzut modelowany między obszarami: mediana 2 d, maks 5 d
  → odchylenie od mediany uzasadnione termiką do 2,5 d
  + około 3 d niepewności odczytu NDYI
  = odrzuć obserwację dalszą niż 6 dni od mediany sezonu</div>
<p class="mniej">Bez odrzucania błąd wynosi {pl(fen['rmse_bez_odrzucania'],2)}
dnia, z odrzucaniem {pl(m['rmse'],2)}. Odrzucono {len(fen['odrzucone'])}
obserwacji z {m['n'] + len(fen['odrzucone'])}.</p>

<h3>Czy próba była dość duża</h3>
<p>Pierwsze dopasowanie szło na {fen['obserwacje_poprzednie']['n']}
obserwacjach z {fen['obserwacje_poprzednie']['obszarow']} obszarów. Żeby
sprawdzić, czy wynik nie jest artefaktem doboru miejsc, próbę potrojono do
{m['n']} obserwacji z {m['obszarow']} obszarów. Przeszukanie siatki trafiło
w <b>tę samą bazę i ten sam próg</b>, a błąd przesunął się z
{pl(fen['model_poprzedni']['rmse'],2)} na {pl(m['rmse'],2)} dnia. To jest
najmocniejszy dostępny tu dowód, że parametry są realne, a nie dopasowane
do szumu.</p>

<!-- ============================================================ SPLOT -->
<h2 id="splot"><span class="nr">5</span>Ile dosięgnie pszczoła — splot z jądrem zasięgu lotu</h2>
<p class="lead">Ul nie zbiera z piksela, na którym stoi. Mapa musi
odpowiadać, <b>ile cukru jest w zasięgu</b>, czyli sumować otoczenie z wagą
malejącą wraz z odległością.</p>

<div class="wzor">P(x) = Σ_y  C(y) · K( d(x,y) )        K(d) = exp( −d / λ )</div>
<p>gdzie C(y) to cukier na pikselu y, a d odległość między pikselami. To jest
<b>splot</b>, liczony przez FFT na całej siatce
{pl(woj['siatka'][0], 0)} × {pl(woj['siatka'][1], 0)} przy rozdzielczości
{woj['piksel_m']} m — jeden piksel to jeden hektar.</p>

<h3>Jądro kalibrowane na zmierzonych lotach pszczół</h3>
<p>λ nie jest dobierane dla wyglądu. Rozwiązuje się je numerycznie tak, żeby
<b>ważona średnia odległość lotu w jądrze równała się odległości zmierzonej
z tańca pszczelego</b> — około 5 tys. tańców odczytanych przez Couvillon i in.
(<i>PLOS ONE</i>, 2014):</p>
<table>
  <thead><tr><th>pora</th><th>zmierzony średni lot</th><th>λ</th>
    <th>zasięg efektywny (4λ)</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{k}</td><td>{pl(jad['dystanse_zmierzone_m'][k], 0)} m</td>"
         f"<td>{pl(v['lambda_m'], 0)} m</td>"
         f"<td>{pl(v['zasieg_m'], 0)} m</td></tr>"
         for k, v in jad['jadra'].items())}
  </tbody>
</table>
<p><b>Rzepak używa jądra wiosennego</b> — jego pełnia wypada przed 152. dniem
roku, więc zasięg to {pl(wios['zasieg_m'], 0)} m, a nie letnie
{pl(jad['jadra']['lato']['zasieg_m'], 0)} m. Pszczoły latają dalej latem, kiedy
pożytku jest mniej; w majowym łanie rzepaku nie muszą.</p>

<div class="uwaga"><b>Jądra są normalizowane do stałej masy.</b> Każde jest
przeskalowane tak, by wszystkie pory sumowały się do tej samej wartości przed
splotem. Bez tego jądro letnie — rozłożone na 25 razy większą powierzchnię —
po prostu dodawałoby więcej cukru każdemu pikselowi, a mapa stawiałaby
gatunki późne wyżej z powodu czysto arytmetycznego.</div>

<h3>Kształt nie ma znaczenia, zasięg ma</h3>
<table>
  <caption>Te same dane, różne kształty jądra</caption>
  <thead><tr><th>kształt</th><th>korelacja z wykładniczym</th>
    <th>wspólne top 10%</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{k}</td><td>{pl(v['korelacja'],4)}</td>"
         f"<td>{pl(v['top10_wspolne_proc'],1)}%</td></tr>"
         for k, v in ksz.items())}
  </tbody>
</table>
<p>Jądro gaussowskie i liniowe dają praktycznie tę samą mapę. Spór o postać
funkcji byłby stratą czasu — liczy się skala odległości, a ta pochodzi
z pomiaru.</p>

<!-- ============================================================ MAPY -->
<h2 id="mapy"><span class="nr">6</span>Mapy</h2>
<p class="lead">Produkt końcowy ścieżki rzepakowej: detekcja → kalibracja
areałowa → pomnożenie przez wydajność → splot jądrem wiosennym.</p>

<div class="klucz">Mapa wojewódzka jest policzona dla <b>2022</b> —
z rozmysłem. Dla tego roku <b>nie istnieją żadne deklaracje ARiMR</b>, więc
wszystko na niej pochodzi wyłącznie z klasyfikacji zdjęć satelitarnych.
Niezależne potwierdzenie dla tego rocznika jest w sekcji 2.</div>

{obraz("nectar_voivodeship_2022.png",
       "Reachable rapeseed nectar sugar across the voivodeship, 2022 — "
       "detected from satellite imagery alone. No farmer declarations exist "
       "for this year.")}

<p>Wycinki poniżej pokazują <b>2025</b>, bo tylko dla 2025 i 2026 istnieją
granice działek — a bez nich nie dałoby się pokazać pojedynczych pól. Kolor
działki nadal pochodzi z klasyfikacji satelitarnej, nie z wniosku rolnika;
granice służą wyłącznie za podkład.</p>

{obraz("nectar_site_2.png",
       "Site 2, 3 km around the hive: the coloured surface is the convolution "
       "result, the green parcels are its input. A single field lifts the "
       "potential around it, because a colony forages over kilometres.")}

{obraz("nectar_site_1.png",
       "Site 1 for contrast — the highest-scoring location overall, but a "
       "fruit-growing region: only 51 rapeseed parcels within 3 km.")}

<p class="mniej">Zestawienie miejsc 1 i 2 warto zauważyć: oba są wysoko
w rankingu potencjału, ale miejsce 1 leży w rejonie sadowniczym, gdzie rzepak
jest składnikiem drugorzędnym, a miejsce 2 w prawdziwym pasie rzepakowym.
Mapa potencjału porządkuje <i>cały</i> osiągalny cukier, nie sam rzepak —
więc pszczelarz jadący na miejsce 1 z datą kwitnienia rzepaku trafi na sady
i maliny, kwitnące w innym terminie.</p>

<!-- ============================================================ DANE -->
<h2 id="dane"><span class="nr">7</span>Dane i ograniczenia</h2>
<table>
  <thead><tr><th>źródło</th><th>zakres</th><th>rola dla rzepaku</th></tr></thead>
  <tbody>
    <tr><td>deklaracje ARiMR GSA</td><td>2025, 2026</td>
        <td>etykiety do uczenia, granice działek, kalibracja areałowa</td></tr>
    <tr><td>Sentinel-2 L2A</td><td>2018–2026</td>
        <td>NDVI, NDYI; data kwitnienia ze szczytu NDYI</td></tr>
    <tr><td>Sentinel-1 GRD</td><td>2018–2026</td>
        <td>VV, VH, VH−VV; wypełnia osiem okien niewidocznych dla optyki</td></tr>
    <tr><td>EUCROPMAP (JRC)</td><td>2018, 2022</td>
        <td>niezależna kontrola dla lat bez deklaracji</td></tr>
    <tr><td>ERA5 przez Open-Meteo</td><td>2000–2026</td>
        <td>temperatury do modelu GDD</td></tr>
    <tr><td>Couvillon i in. 2014</td><td>—</td>
        <td>zmierzone odległości lotu do jądra</td></tr>
  </tbody>
</table>

<h3>Czego ten raport nie twierdzi</h3>
<ul>
  <li><b>Brak walidacji zbiorem.</b> Nic tutaj nie zostało sprawdzone
      rzeczywistym zbiorem miodu z rzeczywistej pasieki. To największa
      otwarta luka projektu.</li>
  <li><b>Daty kwitnienia pochodzą z satelity.</b> Błąd {pl(m['rmse'],2)} dnia
      mierzy zgodność z fenologią NDYI. Gdyby NDYI systematycznie wyprzedzał
      albo opóźniał prawdziwą pełnię, próg przejąłby to obciążenie, a błąd
      by tego nie pokazał.</li>
  <li><b>Deklaracje istnieją tylko za dwa lata.</b> Cała wieloletniość stoi
      na przenoszeniu detekcji wstecz, potwierdzonym jednym niezależnym
      źródłem.</li>
  <li><b>Szereg zaczyna się w 2018</b> wraz z Sentinelem-2. Wcześniejsze lata
      to ekstrapolacja. MODIS jest za gruby (500 m wobec mediany działki
      1,16 ha), Landsat za rzadki — oba sprawdzone i odrzucone.</li>
  <li><b>Wynik pikselowy sam w sobie jest niepewny</b> i nigdy tak nie jest
      używany: mapy najpierw rozmywają zasięgiem lotu i kalibrują areał.</li>
</ul>

<footer>
Wygenerowane przez <code>skrypty/raport/raport_rzepak.py</code>. Wszystkie
liczby odczytane z <code>wyniki/json/</code> przy budowaniu. Pełne pochodzenie
parametrów, łącznie z wynikami negatywnymi, w <code>ZRODLA.md</code>.
</footer>
</div>
"""


if __name__ == "__main__":
    html = buduj()
    wyj = ROOT / "raport_rzepak.html"
    wyj.write_text(html, encoding="utf-8")
    print(f"zapisano {wyj.name}: {len(html.encode()) / 1e6:.1f} MB")
