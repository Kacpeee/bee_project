"""
MIKROSERWIS FAZY FENOLOGICZNEJ - punkt 4 zalozen projektu.

CO ROBI
Wystawia model fenologiczny jako uslruge HTTP: pytasz o wspolrzedne,
dostajesz przewidywana date kwitnienia rzepaku z przedzialem niepewnosci.
Liczy na biezacej pogodzie z Open-Meteo, wiec odpowiedz zmienia sie
w trakcie sezonu - im blizej kwitnienia, tym dokladniejsza.

ENDPOINTY
    GET /                       prognoza + lista najlepszych miejsc
    GET /kalendarz              pelny kalendarz pozytkowy z prognoza
    GET /raport                 szczegolowy raport metodyczny
    GET /mechanika              jak model dziala, krok po kroku
    GET /prognoza?lat=&lon=     JSON z prognoza
    GET /miejsca                12 najlepszych lokalizacji z mapy
    GET /mapa/<nr>              mapa lokalna miejsca: heatmapa na dzialkach
    GET /warstwa/rzepak.json    siatka geo tej warstwy
    POST /prognoza_obszar       prognoza dla obszaru zaznaczonego lassem
    GET /model                  parametry i zmierzone bledy
    GET /kontrola               reanaliza wobec biezacego pomiaru IMGW
    GET /zdrowie                kontrola zycia

DLACZEGO RDZEN JEST W OSOBNYM MODULE
model_fenologiczny.py liczy to samo dla konsoli i dla API. Gdyby serwis
mial wlasna kopie, po pierwszej poprawce modelu obie sciezki zaczelyby
dawac rozne wyniki - a ciche rozbieznosci tego typu kosztowaly juz ten
projekt kilka godzin.

Uruchomienie:
    python skrypty/serwis/serwis.py
    -> http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_file

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_fenologiczny import parametry, prognozuj      # noqa: E402

WYNIKI = ROOT / "wyniki"
app = Flask(__name__)

# granice wojewodztwa lubelskiego z zapasem - poza nimi model nie byl
# walidowany i nie wolno udawac, ze dziala
GRANICE = {"lat": (49.9, 52.5), "lon": (21.2, 24.4)}

STYL = """
 :root{--tlo:#f4f6f5;--atr:#16201c;--mut:#5f6b66;--akc:#1d6f42;
       --akc2:#b3801a;--ram:#dbe3df;--kar:#fff;--cien:0 1px 3px rgba(0,0,0,.05)}
 *{box-sizing:border-box}
 body{margin:0;background:var(--tlo);color:var(--atr);
      font:16px/1.6 "Segoe UI",system-ui,sans-serif}
 a{color:var(--akc)}
 nav{background:var(--kar);border-bottom:1px solid var(--ram);
     position:sticky;top:0;z-index:20}
 nav .in{max-width:940px;margin:0 auto;padding:0 20px;display:flex;
         align-items:center;gap:4px;height:56px}
 nav .logo{font-weight:600;margin-right:auto;font-size:15px;
           display:flex;align-items:center;gap:9px}
 nav .kropka{width:9px;height:9px;border-radius:50%;background:var(--akc2)}
 nav a{padding:7px 13px;border-radius:7px;text-decoration:none;
       color:var(--mut);font-size:14.5px}
 nav a:hover{background:var(--tlo);color:var(--atr)}
 nav a.akt{background:var(--akc);color:#fff}
 .w{max-width:940px;margin:0 auto;padding:38px 20px 70px}
 h1{font-size:27px;margin:0 0 4px;letter-spacing:-.3px}
 h1::after{content:"";display:block;width:46px;height:3px;
           background:var(--akc2);margin-top:11px;border-radius:2px}
 .pod{color:var(--mut);margin:0 0 26px;font-size:15px}
 .karta{background:var(--kar);border:1px solid var(--ram);box-shadow:var(--cien);
        border-radius:12px;padding:20px 22px;margin:0 0 16px}
 .siatka{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
 @media(max-width:760px){.siatka{grid-template-columns:1fr}}
 label{display:block;font-size:12.5px;color:var(--mut);margin:0 0 4px;
       text-transform:uppercase;letter-spacing:.5px}
 input{width:100%;padding:9px 11px;border:1px solid var(--ram);border-radius:7px;
       font:inherit;background:var(--kar);color:var(--atr)}
 .rzad{display:flex;gap:12px}.rzad>div{flex:1}
 button{margin-top:14px;width:100%;padding:11px;border:0;border-radius:7px;
        background:var(--akc);color:#fff;font:inherit;font-weight:600;cursor:pointer}
 button:hover{filter:brightness(1.08)}
 .duza{font-size:34px;font-weight:600;margin:2px 0;letter-spacing:-.5px}
 .pm{font-size:15px;font-weight:400;color:var(--mut)}
 .mniej{color:var(--mut);font-size:13.5px}
 table{border-collapse:collapse;width:100%;margin:14px 0 0;font-size:14.5px}
 td{padding:7px 0;border-bottom:1px solid var(--ram)}
 td:last-child{text-align:right;font-variant-numeric:tabular-nums}
 .zle{color:#a8442a}
 .pasek{margin:14px 0 4px}
 .pasek-tor{height:9px;background:var(--ram);border-radius:5px;overflow:hidden}
 .pasek-wyp{height:100%;background:var(--akc);border-radius:5px;
   transition:width .3s}
 .pasek-txt{display:flex;justify-content:space-between;font-size:13px;
   color:var(--mut);margin-top:6px}
 .ostrzez{background:rgba(179,128,26,.13);border-left:3px solid var(--akc2);
   padding:10px 13px;margin:10px 0 0;font-size:13.5px;border-radius:0 7px 7px 0;
   color:var(--atr)}
 .lista{max-height:320px;overflow:auto;margin:6px -6px 0}
 .poz{display:flex;align-items:center;gap:10px;padding:8px 10px;
      border-radius:8px;cursor:pointer;font-size:14.5px}
 .poz:hover{background:var(--tlo)}
 .poz.akt{background:var(--akc);color:#fff}
 .poz .nr{width:22px;height:22px;border-radius:50%;background:var(--tlo);
          color:var(--mut);font-size:12px;display:grid;place-items:center;
          flex:0 0 auto;font-weight:600}
 .poz.akt .nr{background:rgba(255,255,255,.25);color:#fff}
 .poz .rodz{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:600}
 #mapa img{width:100%;height:auto;display:block;border-radius:9px;
   border:1px solid var(--ram);margin:10px 0 8px;background:#fff}
 .krok{display:flex;gap:12px;align-items:flex-start;margin:0 0 12px}
 .krok .ik{width:26px;height:26px;border-radius:50%;background:var(--akc);
           color:#fff;display:grid;place-items:center;font-size:13px;
           font-weight:600;flex:0 0 auto}
 @media(prefers-color-scheme:dark){
  :root{--tlo:#101613;--atr:#e3eae6;--mut:#8d9a94;--ram:#27332d;
        --kar:#18211d;--akc:#54b37c;--akc2:#d6a53f;--cien:none}}
"""


# Styl paska nawigacji ZAWEZONY do .appnav.
#
# Pierwsza wersja wstrzykiwala do kalendarza caly arkusz STYL, ktory ma
# reguly globalne (body, button, table, a). Nadpisaly one wlasne style
# kalendarza i rozwalily uklad zakladek. Strony generowane osobno maja
# swoja typografie i nie wolno w nia wchodzic - pasek musi byc samowystarczalny.
STYL_NAW = """
 .appnav{background:#fff;border-bottom:1px solid #dbe3df;position:sticky;
   top:0;z-index:9999;font:15px/1.4 "Segoe UI",system-ui,sans-serif;
   color:#16201c}
 .appnav .in{max-width:1100px;margin:0 auto;padding:0 20px;display:flex;
   align-items:center;gap:4px;height:54px}
 .appnav .logo{font-weight:600;margin-right:auto;font-size:15px;
   display:flex;align-items:center;gap:9px;color:#16201c}
 .appnav .kropka{width:9px;height:9px;border-radius:50%;background:#b3801a;
   display:inline-block}
 .appnav a{padding:7px 13px;border-radius:7px;text-decoration:none;
   color:#5f6b66;font-size:14.5px;background:transparent;border:0}
 .appnav a:hover{background:#f4f6f5;color:#16201c}
 .appnav a.akt{background:#1d6f42;color:#fff}
 @media(prefers-color-scheme:dark){
  .appnav{background:#18211d;border-bottom-color:#27332d;color:#e3eae6}
  .appnav .logo{color:#e3eae6}
  .appnav a{color:#8d9a94}
  .appnav a:hover{background:#101613;color:#e3eae6}
  .appnav a.akt{background:#54b37c;color:#0d1512}}
"""


def NAW(akt: str) -> str:
    poz = [("/", "Prognoza"), ("/kalendarz", "Kalendarz"),
           ("/raport", "Raport"), ("/mechanika", "Jak to działa")]
    linki = "".join(
        f'<a href="{u}"{" class=\'akt\'" if u == akt else ""}>{n}</a>'
        for u, n in poz)
    return (f'<nav class="appnav"><div class="in"><span class="logo">'
            f'<span class="kropka"></span>Model pożytkowy · Lubelskie</span>'
            f'{linki}</div></nav>')


STRONA = """<!doctype html><meta charset="utf-8">
<title>Prognoza kwitnienia rzepaku</title>
<style>""" + STYL + STYL_NAW + """
 .mapa-box{background:var(--kar);border:1px solid var(--ram);
   border-radius:12px;padding:14px;box-shadow:var(--cien)}
 .plotno{position:relative;width:100%;aspect-ratio:150/186;margin:0 auto}
 .plotno canvas{position:absolute;inset:0;width:100%;height:100%;
   border-radius:8px}
 #lasso{cursor:crosshair}
 .legenda{display:flex;flex-direction:column;gap:3px;margin:12px 0 0;
   font-size:12.5px;color:var(--mut)}
 .legenda div{display:flex;align-items:center;gap:8px}
 .legenda i{width:14px;height:11px;border-radius:2px;flex:0 0 auto}
 .lata2{display:flex;flex-wrap:wrap;gap:5px;margin:12px 0 0}
 .lata2 button{margin:0;flex:0 0 auto;width:auto;padding:5px 11px;font-size:13px;
   font-weight:500;background:var(--kar);color:var(--atr);
   border:1px solid var(--ram);border-radius:6px}
 .lata2 button.akt{background:var(--akc);color:#fff;border-color:var(--akc)}
 .chipy{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 0}
 .chip{margin:0;width:auto;flex:0 0 auto;padding:5px 11px;font-size:12.5px;
   font-weight:500;background:transparent;color:var(--mut);
   border:1px solid var(--ram);border-radius:20px}
 .chip:hover{background:var(--tlo);color:var(--atr);filter:none}
 .chip.akt{background:var(--akc);color:#fff;border-color:var(--akc)}
 .grupa{font-size:11.5px;color:var(--mut);text-transform:uppercase;
   letter-spacing:.5px;margin:12px 0 5px}
 .wsk{display:flex;gap:12px;align-items:center;justify-content:space-between;
   font-size:13px;color:var(--mut);margin-top:10px;flex-wrap:wrap}
 .przyciski{display:flex;gap:8px;margin-top:10px}
 .przyciski button{margin:0;flex:1}
 button.pom{background:transparent;color:var(--mut);border:1px solid var(--ram)}
 button.pom:hover{background:var(--tlo);color:var(--atr);filter:none}
</style>
""" + NAW("/") + """
<div class="w">
<h1>Kiedy zakwitnie rzepak</h1>
<p class="pod">Kliknij miejsce na mapie — model policzy termin kwitnienia
z bieżącej pogody. <b>Mapa pokazuje sam rzepak</b>, bo prognoza dotyczy
właśnie jego.</p>

<div class="siatka">
  <div class="mapa-box">
    <div class="plotno">
      <canvas id="raster"></canvas>
      <canvas id="lasso"></canvas>
    </div>

    <div class="grupa">Detekcja satelitarna</div>
    <div class="lata2" id="lata-sat"></div>
    <div class="grupa">Deklaracje ARiMR</div>
    <div class="lata2" id="lata-gsa"></div>

    <div class="legenda" id="legenda"></div>
    <div class="wsk">
      <span id="opis-warstwy"></span>
      <span id="stan-zazn">kliknij miejsce na mapie</span>
    </div>
  </div>
  <div id="wynik"><div class="karta mniej">zaznacz obszar na mapie</div></div>
</div>

<div class="karta" style="margin-top:22px">
  <div class="krok"><span class="ik">1</span><div>
    <b>Gdzie</b> — mapa pokazuje, ile rzepaku pszczoła dosięgnie z danego
    punktu. Rok typowy to średnia z siedmiu sezonów; pojedyncze lata
    pokazują, jak rzepak wędruje w płodozmianie. Pełne zestawienie pożytków
    jest w <a href="/kalendarz">kalendarzu</a>, najlepsze miejsca
    w <a href="/raport">raporcie</a>.</div></div>
  <div class="krok"><span class="ik">2</span><div>
    <b>Kiedy</b> — suma temperatur od 15 marca; kwitnienie, gdy przekroczy
    430. Pogoda z Open-Meteo.</div></div>
  <div class="krok"><span class="ik">3</span><div>
    <b>Z jaką pewnością</b> — przedział ze zmierzonego błędu dla stanu
    wiedzy w dniu pytania. Przed połową kwietnia model nie ma danych sezonu
    i mówi o tym wprost.</div></div>
</div>
</div>

<script>
let D = null, wybrany = null, wybor = {zrodlo: "detekcja", rok: "sr"};
const cvR = document.getElementById("raster"), cvL = document.getElementById("lasso");
let off = null, octx = null, img = null, geoBox = null;

const RGB = h => [1,3,5].map(i => parseInt(h.slice(i, i+2), 16));

fetch("/warstwa/rzepak.json").then(r => r.json()).then(d => {
  D = d;
  off = document.createElement("canvas");
  off.width = D.nx; off.height = D.ny;
  octx = off.getContext("2d");
  img = octx.createImageData(D.nx, D.ny);
  D.maskaB = b64(D.maska);
  przyciskiLat();
  rysuj();
});

function b64(s) {
  const bin = atob(s), a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  return a;
}
function warstwa(s, skala) {
  const a = b64(s), o = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) o[i] = a[i] / 255 * skala;
  return o;
}

function przyciskiLat() {
  const zrob = (el, zrodlo, lata, sr) => {
    el.innerHTML = "";
    const poz = (sr ? [["sr", "typowy"]] : []).concat(lata.map(y => [String(y), String(y)]));
    poz.forEach(([k, et]) => {
      const b = document.createElement("button");
      b.textContent = et;
      b.onclick = () => { wybor = {zrodlo, rok: k}; przyciskiLat(); rysuj(); };
      if (wybor.zrodlo === zrodlo && wybor.rok === k) b.className = "akt";
      el.appendChild(b);
    });
  };
  zrob(document.getElementById("lata-sat"), "detekcja", D.detekcja.lata, true);
  zrob(document.getElementById("lata-gsa"), "deklaracje", D.deklaracje.lata, false);
}

function progi(a) {
  // DOKLADNIE ta sama regula, co w kalendarzu (eksport_interaktywny.progi):
  // percentyle 60, 80, 92, 98 po WSZYSTKICH pikselach w masce, takze zerowych.
  // Pierwsza wersja brala 20/45/68/86 i tylko piksele niezerowe - progi
  // wychodzily duzo nizsze i ta sama mapa byla znacznie czerwienisza niz
  // w kalendarzu. Dwie strony musza kolorowac tak samo, inaczej porownanie
  // miedzy nimi wprowadza w blad.
  const v = [];
  for (let i = 0; i < a.length; i++) if (D.maskaB[i]) v.push(a[i]);
  v.sort((x, y) => x - y);
  if (!v.length) return [0, 1, 2, 3, 4, 5];
  const q = p => v[Math.min(v.length - 1, Math.floor(p / 100 * v.length))];
  return [0, q(60), q(80), q(92), q(98), v[v.length - 1]];
}

function rysuj() {
  if (!D) return;
  const z = wybor.zrodlo === "detekcja" ? D.detekcja : D.deklaracje;
  const a = warstwa(z.warstwy[wybor.rok], z.skala);
  const br = progi(a), pal = D.paleta.klasy.map(RGB);
  const d = img.data;
  for (let i = 0; i < D.nx * D.ny; i++) {
    const p = i * 4;
    if (!D.maskaB[i]) { d[p]=246; d[p+1]=248; d[p+2]=247; d[p+3]=255; continue; }
    let k = 0;
    while (k < 4 && a[i] > br[k + 1]) k++;
    const c = a[i] <= 0 ? [248, 249, 248] : pal[k];
    d[p]=c[0]; d[p+1]=c[1]; d[p+2]=c[2]; d[p+3]=255;
  }
  octx.putImageData(img, 0, 0);

  const r = cvR.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  [cvR, cvL].forEach(c => { c.width = r.width * dpr; c.height = r.height * dpr; });
  const ctx = cvR.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, r.width, r.height);
  const pad = 10;
  const sc = Math.min((r.width - 2*pad) / D.nx, (r.height - 2*pad) / D.ny);
  const dw = D.nx * sc, dh = D.ny * sc;
  const ox = (r.width - dw) / 2, oy = (r.height - dh) / 2;
  geoBox = {ox, oy, sc};
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, ox, oy, dw, dh);

  ctx.beginPath();
  D.granica.forEach((pt, i) => {
    const x = ox + pt[0]*sc, y = oy + pt[1]*sc;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.closePath();
  ctx.strokeStyle = D.paleta.atrament; ctx.globalAlpha = .5;
  ctx.lineWidth = 1.2; ctx.stroke(); ctx.globalAlpha = 1;

  ctx.font = "600 11px Segoe UI, sans-serif"; ctx.textAlign = "center";
  for (const m of D.miasta) {
    const x = ox + m.x*sc, y = oy + m.y*sc;
    ctx.beginPath(); ctx.arc(x, y, 3, 0, 7);
    ctx.fillStyle = "#fff"; ctx.fill();
    ctx.lineWidth = 1.2; ctx.strokeStyle = D.paleta.atrament; ctx.stroke();
    ctx.lineWidth = 3; ctx.strokeStyle = "#fff";
    ctx.strokeText(m.n, x, y - 7);
    ctx.fillStyle = D.paleta.atrament; ctx.fillText(m.n, x, y - 7);
  }
  rysujLegende(br);
  document.getElementById("opis-warstwy").textContent =
    wybor.zrodlo === "detekcja"
      ? (wybor.rok === "sr" ? "detekcja, średnia 2019–2025" : "detekcja " + wybor.rok)
      : "deklaracje ARiMR " + wybor.rok;
  przerysujLasso();
}
function rysujLegende(br) {
  // te same progi, co uzyte do pokolorowania mapy - legenda nie moze
  // pokazywac innych liczb niz raster, wiec bierze je z tego samego miejsca
  const el = document.getElementById("legenda");
  const kg = D.rzepak_kg / 1000;              // udzial -> tony cukrow
  const fm = v => (v * kg).toFixed(v * kg < 1 ? 2 : 1).replace(".", ",");
  // apostrofy, nie cudzyslowy - cala strona siedzi w potrojnym cudzyslowie
  // Pythona, wiec \" traci ukosnik i zamyka lancuch JS przedwczesnie
  el.innerHTML = '<div style="margin-bottom:2px">tony cukrów z rzepaku w zasięgu lotu</div>' +
    D.paleta.klasy.map((c, i) =>
      `<div><i style="background:${c}"></i>${fm(br[i])} – ${fm(br[i+1])}</div>`
    ).join("");
}
window.addEventListener("resize", () => rysuj());

// ekran -> piksel rastra -> wspolrzedne (siatka 9x9 z eksportu kalendarza)
function naGeo(x, y) {
  if (!D || !geoBox || !D.geo || !D.geo.lat) return null;
  const px = (x - geoBox.ox) / geoBox.sc, py = (y - geoBox.oy) / geoBox.sc;
  const K = D.geo.n;
  const u = Math.max(0, Math.min(D.nx, px)) / D.nx * (K - 1);
  const v = Math.max(0, Math.min(D.ny, py)) / D.ny * (K - 1);
  const j0 = Math.min(K-2, Math.floor(u)), i0 = Math.min(K-2, Math.floor(v));
  const fu = u - j0, fv = v - i0;
  const w = m => (1-fu)*(1-fv)*m[i0][j0] + fu*(1-fv)*m[i0][j0+1]
               + (1-fu)*fv*m[i0+1][j0] + fu*fv*m[i0+1][j0+1];
  return [w(D.geo.lat), w(D.geo.lon)];
}

function poz(ev) {
  const r = cvL.getBoundingClientRect(), e = ev.touches ? ev.touches[0] : ev;
  return [e.clientX - r.left, e.clientY - r.top];
}
cvL.addEventListener("click", ev => {
  const p = poz(ev);
  const g = naGeo(p[0], p[1]);
  if (!g) return;
  wybrany = p;
  przerysujLasso();
  liczPunkt(g);
});

function przerysujLasso() {
  const dpr = window.devicePixelRatio || 1;
  const ctx = cvL.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cvL.width, cvL.height);
  if (!wybrany) return;
  const [x, y] = wybrany;
  ctx.beginPath(); ctx.arc(x, y, 8, 0, 7);
  ctx.strokeStyle = "#fff"; ctx.lineWidth = 4; ctx.stroke();
  ctx.strokeStyle = "#1d6f42"; ctx.lineWidth = 2; ctx.stroke();
  ctx.beginPath(); ctx.arc(x, y, 2.5, 0, 7);
  ctx.fillStyle = "#1d6f42"; ctx.fill();
}

// SEZONY: nadchodzacy + trzy minione.
// Poza sezonem model nie zna zadnej pogody nadchodzacego kwitnienia
// i zwraca srednia wieloletnia (blad 6,8 d). Sezony minione maja komplet
// pogody, wiec pokazuja, co model potrafi naprawde (3,2 d).
let OSTATNI_G = null, SEZON_DOM = null;

function chipy(akt) {
  if (!SEZON_DOM) return '';
  const lata = [SEZON_DOM, SEZON_DOM-1, SEZON_DOM-2, SEZON_DOM-3];
  return '<div class="chipy">' + lata.map(r =>
    '<button class="chip' + (r === akt ? ' akt' : '') +
    '" onclick="przelaczSezon(' + r + ')">' +
    (r === SEZON_DOM ? r + ' (nadchodzący)' : r) + '</button>').join('') + '</div>';
}
function przelaczSezon(rok) { if (OSTATNI_G) liczPunkt(OSTATNI_G, rok); }

function liczPunkt(g, rok) {
  OSTATNI_G = g;
  document.getElementById("stan-zazn").textContent =
    `${g[0].toFixed(3)} N  ${g[1].toFixed(3)} E`;
  const punkty = [g, g, g];
  const w = document.getElementById("wynik");
  w.innerHTML = '<div class="karta mniej">liczę…</div>';
  fetch("/prognoza_obszar", {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({punkty, rok: rok || null})})
   .then(r => r.json()).then(d => {
    if (d.blad) { w.innerHTML = '<div class="karta zle">' + d.blad + '</div>'; return; }
    if (!rok) SEZON_DOM = d.sezon;
    w.innerHTML = `<div class="karta">
      <div class="mniej">${d.naglowek} · pełnia kwitnienia</div>
      <div class="duza">${d.pelnia.opis} ${d.sezon} <span class="pm">±${d.niepewnosc_dni} dnia</span></div>
      ${d.rodzaj === "srednia_wieloletnia" ? '<p class="ostrzez">'+d.uwaga+'</p>' : ''}
      ${chipy(d.sezon)}
      <div class="pasek">
        <div class="pasek-tor"><div class="pasek-wyp" style="width:${d.postep.procent}%"></div></div>
        <div class="pasek-txt"><span>${d.postep.gdd_teraz} z ${d.postep.prog} GDD</span>
          <span>${d.postep.procent}%</span></div></div>
      <table>
        <tr><td>przedział</td><td>${d.przedzial.od} – ${d.przedzial.do}</td></tr>
        <tr><td>początek kwitnienia</td><td>${d.poczatek.opis}</td></tr>
        <tr><td><b>ustaw ul około</b></td><td><b>${d.ustaw_ul.opis}</b></td></tr>
        <tr><td>środek zaznaczenia</td><td>${d.srodek.lat} N ${d.srodek.lon} E</td></tr>
        ${d.rozrzut_w_obszarze_d > 0
          ? `<tr><td>rozrzut w obszarze</td><td>${d.rozrzut_w_obszarze_d} dni</td></tr>` : ""}
        <tr><td>pogoda realna</td><td>${d.pogoda_realna_pct}%</td></tr>
      </table>
      <p class="mniej" style="margin-top:14px">${d.zastrzezenie}</p>
      <p class="mniej">model: baza ${d.model.baza_C}°C, próg ${d.model.prog_gdd},
        start ${d.model.start} · błąd ${d.model.rmse_walidacji_d} d
        (walidacja krzyżowa, n=${d.model.n_obserwacji})</p>
    </div>`;
  }).catch(e => { w.innerHTML = '<div class="karta zle">błąd: ' + e + '</div>'; });
}
</script>"""


@app.get("/")
def strona():
    return STRONA


def _z_nawigacja(plik: Path, akt: str, brak: str):
    """Strona wygenerowana osobno, podana przez serwis z doklejona nawigacja.

    Pliki dzialaja tak samo otwarte z dysku - nawigacja jest dodawana tylko
    tutaj, wiec wersja do wyslania mailem pozostaje samodzielna.
    """
    if not plik.exists():
        return jsonify({"blad": brak}), 404
    h = plik.read_text(encoding="utf-8")
    wstawka = f"<style>{STYL_NAW}</style>{NAW(akt)}"
    i = h.lower().find("<body")
    if i >= 0:
        j = h.index(">", i) + 1
        return h[:j] + wstawka + h[j:]
    return wstawka + h


@app.get("/raport")
def raport():
    return _z_nawigacja(ROOT / "raport.html", "/raport",
                        "brak raport.html - uruchom skrypty/raport/raport_buduj.py")


@app.get("/mechanika")
def mechanika():
    return _z_nawigacja(ROOT / "mechanika.html", "/mechanika",
                        "brak mechanika.html - uruchom skrypty/raport/mechanika.py")


@app.get("/kalendarz")
def kalendarz():
    """Ten sam plik, ktory dziala z dysku - ale podany przez serwis,
    dzieki czemu jego panel prognozy ma do kogo zapytac. Otwarty
    lokalnie kalendarz po prostu tej sekcji nie pokazuje."""
    return _z_nawigacja(ROOT / "kalendarz.html", "/kalendarz",
                        "brak kalendarz.html - uruchom "
                        "skrypty/kalendarz/eksport_interaktywny.py")


@app.get("/zdrowie")
def zdrowie():
    return jsonify({"stan": "ok", "model": parametry()["rmse_modelu"]})


@app.get("/model")
def model():
    p = parametry()
    return jsonify({
        "baza_C": p["baza"], "prog_gdd": p["prog"],
        "start_doy": p["start_doy"],
        "rmse_walidacji_krzyzowej_d": round(p["rmse_modelu"], 2),
        "n_obserwacji": p["n_obserwacji"],
        "bledy_prognozy_wg_dnia_decyzji": p["bledy_prognozy"],
        "metoda": "suma temperatur efektywnych od wznowienia wegetacji; "
                  "parametry dobrane na krzywych NDYI Sentinel-2, blad "
                  "z walidacji leave-one-out",
    })


@app.get("/kontrola")
def kontrola():
    """Biezaca kontrola reanalizy wobec stacji IMGW.

    Model stoi na ERA5, zwalidowanej historycznie (962 dni, RMSE 1.13 K).
    Ten endpoint sprawdza, czy w BIEZACYM sezonie nie odjezdza - ale
    porownuje pojedynczy odczyt godzinowy, wiec jest sygnalem, nie dowodem.
    """
    import kontrola_meteo as KM
    try:
        st = KM.imgw()
        w, r = [], []
        for n, (lat, lon) in KM.STACJE.items():
            if n not in st:
                continue
            s = st[n]
            om = KM.openmeteo(lat, lon, s["data"], s["godz"])
            if om is None:
                continue
            r.append(om - s["T"])
            w.append({"stacja": n, "data": s["data"], "godzina": s["godz"],
                      "imgw_C": s["T"], "openmeteo_C": om,
                      "roznica_K": round(om - s["T"], 2)})
        return jsonify({
            "stacje": w,
            "obciazenie_srednie_K": round(sum(r) / len(r), 2) if r else None,
            "odniesienie_historyczne": {"stacja": "Zamosc 595", "n_dni": 962,
                                        "rmse_K": 1.126, "r": 0.986},
            "zastrzezenie": "pojedynczy odczyt godzinowy; model GDD uzywa "
                            "dobowych Tmax i Tmin, wiec obciazenie o tej "
                            "godzinie nie przenosi sie wprost na sume "
                            "temperatur",
        })
    except Exception as e:
        return jsonify({"blad": str(e)}), 502


@app.get("/miejsca")
def miejsca():
    d = json.loads((WYNIKI / "json" / "najlepsze_punkty.json")
                   .read_text(encoding="utf-8"))
    return jsonify({"miejsca": [
        {"nr": m["nr"], "lat": round(m["lat"], 4), "lon": round(m["lon"], 4),
         "rodzin": round(m["rodzin"]), "promien_95_m": m["promien_95_m"]}
        for m in d["miejsca"]]})


@app.get("/mapa/<int:nr>")
def mapa_miejsca(nr: int):
    """Wycinek 3 km wokol miejsca: heatmapa potencjalu na granicach dzialek
    ARiMR, z okregami rownowaznosci. Generowane przez
    skrypty/potencjal/mapa_dzialki.py."""
    f = ROOT / "mapy" / f"mapa_dzialki_{nr}.png"
    if not f.exists():
        return jsonify({"blad": f"brak mapy dla miejsca {nr} - uruchom "
                                f"skrypty/potencjal/mapa_dzialki.py {nr}"}), 404
    return send_file(f, mimetype="image/png")


@app.get("/warstwa/rzepak.json")
def warstwa_json():
    """Warstwy rzepaku prosto z danych kalendarza.

    Wlasny renderer PNG dawal ziarnista, nieczytelna mape. Kalendarz rysuje
    to samo lepiej i ma juz gotowe warstwy: deklaracje ARiMR (2025, 2026),
    detekcje satelitarna (2019-2025) oraz rok typowy. Zamiast robic drugi
    renderer, podajemy te same dane - dzieki czemu obie strony pokazuja
    dokladnie to samo, tym samym kluczem kolorow.
    """
    f = WYNIKI / "cache" / "kalendarz_dane.json"
    if not f.exists():
        return jsonify({"blad": "brak kalendarz_dane.json - uruchom "
                                "skrypty/kalendarz/eksport_interaktywny.py"}), 404
    d = json.loads(f.read_text(encoding="utf-8"))
    return jsonify({
        "nx": d["nx"], "ny": d["ny"], "px_km": d["px_km"],
        "maska": d["maska"], "granica": d["granica"], "miasta": d["miasta"],
        "geo": d["geo"], "paleta": d["paleta"],
        "rzepak_kg": d["rzepak_kg"],
        "deklaracje": {"lata": d["rolnicy"]["lata"],
                       "warstwy": d["rolnicy"]["rzepak"],
                       "skala": d["rolnicy"]["rzepak_skala"]},
        "detekcja": {"lata": d["satelita"]["lata"],
                     "warstwy": d["satelita"]["rzepak"],
                     "skala": d["satelita"]["rzepak_skala"]},
    })


@app.post("/prognoza_obszar")
def prognoza_obszar():
    """Prognoza dla obszaru zaznaczonego na mapie.

    Termin kwitnienia zmienia sie w wojewodztwie o ok. 8 dni z poludnia na
    polnoc, wiec dla zaznaczenia nie wystarczy jeden punkt - probkujemy
    kilka i podajemy zakres. Liczba punktow jest ograniczona, bo kazdy to
    zapytanie do Open-Meteo (cache w module lagodzi powtorki).
    """
    d = request.get_json(silent=True) or {}
    pkt = d.get("punkty") or []
    if len(pkt) < 3:
        return jsonify({"blad": "podaj co najmniej 3 punkty obrysu"}), 400

    lats = [p[0] for p in pkt]
    lons = [p[1] for p in pkt]
    # srodek ciezkosci obrysu + kilka punktow w jego zasiegu
    clat, clon = sum(lats) / len(lats), sum(lons) / len(lons)
    if not (GRANICE["lat"][0] <= clat <= GRANICE["lat"][1]
            and GRANICE["lon"][0] <= clon <= GRANICE["lon"][1]):
        return jsonify({"blad": "obszar poza województwem lubelskim"}), 400

    probki = [(clat, clon)]
    rozp_lat, rozp_lon = max(lats) - min(lats), max(lons) - min(lons)
    if rozp_lat > 0.15 or rozp_lon > 0.25:
        # zaznaczenie duze - dokladamy skrajne rogi, zeby pokazac zakres
        probki += [(min(lats), clon), (max(lats), clon)]

    # ROK OPCJONALNY - strona pozwala obejrzec sezony minione.
    # Poza sezonem (od czerwca do marca) model dla najblizszego kwitnienia
    # nie ma zadnej pogody i zwraca srednia wieloletnia. Bez mozliwosci
    # cofniecia sie do lat minionych strona przez wiekszosc roku nie
    # pokazywalaby niczego poza klimatologia.
    rok = d.get("rok")
    rok = int(rok) if rok else None

    wyniki, bledy = [], []
    for la, lo in probki:
        try:
            wyniki.append(prognozuj(la, lo, rok))
        except Exception as e:
            bledy.append(str(e))
    if not wyniki:
        return jsonify({"blad": "; ".join(bledy) or "brak wyniku"}), 500

    doy = [w["pelnia"]["doy"] for w in wyniki]
    g = dict(wyniki[0])
    g["srodek"] = {"lat": round(clat, 4), "lon": round(clon, 4)}
    g["probek"] = len(wyniki)
    g["rozrzut_w_obszarze_d"] = round(max(doy) - min(doy))
    g["obrys_punktow"] = len(pkt)
    return jsonify(g)


@app.get("/prognoza")
def prognoza():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({"blad": "podaj lat i lon, np. /prognoza?lat=51.06&lon=22.10"}), 400
    if not (GRANICE["lat"][0] <= lat <= GRANICE["lat"][1]
            and GRANICE["lon"][0] <= lon <= GRANICE["lon"][1]):
        return jsonify({"blad": "punkt poza województwem lubelskim — model "
                                "nie był tam walidowany"}), 400
    rok = request.args.get("rok", type=int)
    try:
        return jsonify(prognozuj(lat, lon, rok))
    except Exception as e:
        return jsonify({"blad": str(e)}), 500


if __name__ == "__main__":
    # DOMYSLNIE TYLKO TEN KOMPUTER.
    # 127.0.0.1 znaczy, ze nikt z zewnatrz sie nie polaczy - nawet z tego
    # samego Wi-Fi. To celowe: serwer deweloperski Flaska nie jest
    # przeznaczony do wystawiania w siec. Przelacznik --siec otwiera go
    # na siec lokalna, zeby dalo sie pokazac projekt na obronie albo
    # na telefonie; do internetu to nadal NIE wystarczy.
    import socket

    siec = "--siec" in sys.argv
    host = "0.0.0.0" if siec else "127.0.0.1"

    p = parametry()
    print("MIKROSERWIS FAZY FENOLOGICZNEJ")
    print(f"  model: baza {p['baza']} °C, prog {p['prog']:.0f}, "
          f"blad {p['rmse_modelu']:.2f} d (walidacja krzyzowa, "
          f"n={p['n_obserwacji']})")
    print("  http://127.0.0.1:8000")
    if siec:
        try:
            g = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            g.connect(("8.8.8.8", 80))
            ip = g.getsockname()[0]
            g.close()
            print(f"  http://{ip}:8000   <- z innych urzadzen w tej sieci")
        except OSError:
            print("  (nie udalo sie ustalic adresu w sieci lokalnej)")
        print("  UWAGA: zapora Windows moze poprosic o zgode przy pierwszym raz")
    else:
        print("  (widoczny tylko na tym komputerze - dodaj --siec, "
              "zeby udostepnic w sieci lokalnej)")
    print()
    app.run(host=host, port=8000, debug=False)
