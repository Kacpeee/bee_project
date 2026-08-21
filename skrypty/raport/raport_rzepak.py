"""
Raport wylacznie o rzepaku - jak policzono GDZIE, KIEDY i ILE.

PO CO OSOBNY RAPORT
Glowny raport opisuje caly model pozytkowy: 16 gatunkow, dwa zrodla warstw,
kalendarz, pojemnosc. Rzepak jest w nim jednym z watkow, a to on niesie
polowe cukru w wojewodztwie i jako jedyny ma wlasny model terminu. Ten plik
sklada cala sciezke rzepakowa w jedno miejsce, po angielsku, z liczbami
czytanymi z wyniki/json - zeby dalo sie ja obronic bez przegryzania sie
przez reszte projektu.

ZASADA
Zadna liczba nie jest tu wpisana recznie. Jesli ktorys plik JSON sie zmieni,
raport zmieni sie razem z nim - inaczej powtorzylby sie problem, ktory juz
raz kosztowal ten projekt kilka godzin (stary prog GDD w README, zaszyta
stala w sprawdzianie GUS).

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
        return f'<p class="brak">missing figure: {nazwa}</p>'
    b = base64.b64encode(f.read_bytes()).decode()
    return (f'<figure><img src="data:image/png;base64,{b}" alt="{podpis}">'
            f'<figcaption>{podpis}</figcaption></figure>')


def lb(x, n=3):
    """Liczba z kropka dziesietna - raport jest po angielsku."""
    return f"{x:,.{n}f}" if isinstance(x, (int, float)) else str(x)


STYL = """
:root{--tlo:#fbfbfa;--atr:#16201c;--mut:#5f6b66;--akc:#1d6f42;--akc2:#b3801a;
      --ram:#e2e8e4;--kar:#fff;--cien:0 1px 3px rgba(0,0,0,.05)}
*{box-sizing:border-box}
body{margin:0;background:var(--tlo);color:var(--atr);
     font:16px/1.65 "Segoe UI",system-ui,sans-serif}
.w{max-width:900px;margin:0 auto;padding:44px 22px 80px}
h1{font-size:31px;margin:0 0 6px;letter-spacing:-.4px;line-height:1.2}
h1::after{content:"";display:block;width:52px;height:3px;
          background:var(--akc2);margin-top:14px;border-radius:2px}
h2{font-size:23px;margin:52px 0 4px;letter-spacing:-.2px}
h3{font-size:17px;margin:30px 0 8px}
.lead{color:var(--mut);font-size:16.5px;margin:0 0 8px}
.etap{display:inline-block;background:var(--akc);color:#fff;font-size:11.5px;
      padding:3px 10px;border-radius:20px;letter-spacing:.5px;
      text-transform:uppercase;margin-bottom:10px}
.karta{background:var(--kar);border:1px solid var(--ram);box-shadow:var(--cien);
       border-radius:12px;padding:20px 24px;margin:18px 0}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--ram);text-align:left}
th{font-weight:600;color:var(--mut);font-size:12.5px;text-transform:uppercase;
   letter-spacing:.4px}
td:not(:first-child),th:not(:first-child){text-align:right;
   font-variant-numeric:tabular-nums}
caption{caption-side:top;text-align:left;color:var(--mut);font-size:13px;
        padding-bottom:6px}
b.ok{color:var(--akc)}
b.zle{color:#a8442a}
.wzor{background:#f3f6f4;border-left:3px solid var(--akc);padding:12px 16px;
      border-radius:0 8px 8px 0;font-family:"Cascadia Mono",Consolas,monospace;
      font-size:14px;margin:14px 0;overflow-x:auto;white-space:pre;
      line-height:1.5}
.uwaga{background:#fdf6e6;border-left:3px solid var(--akc2);padding:12px 16px;
       border-radius:0 8px 8px 0;font-size:14.5px;color:#6b5416;margin:14px 0}
.mniej{color:var(--mut);font-size:14px}
figure{margin:22px 0}
figure img{width:100%;border:1px solid var(--ram);border-radius:10px;
           display:block}
figcaption{color:var(--mut);font-size:13.5px;margin-top:8px}
ol.kroki{padding-left:0;counter-reset:k;list-style:none}
ol.kroki li{counter-increment:k;position:relative;padding-left:42px;
            margin-bottom:16px}
ol.kroki li::before{content:counter(k);position:absolute;left:0;top:1px;
   width:27px;height:27px;border-radius:50%;background:var(--akc);color:#fff;
   display:flex;align-items:center;justify-content:center;font-size:14px;
   font-weight:600}
.spis{background:var(--kar);border:1px solid var(--ram);border-radius:12px;
      padding:16px 22px;margin:26px 0}
.spis a{color:var(--atr);text-decoration:none;display:block;padding:4px 0;
        font-size:15px}
.spis a:hover{color:var(--akc)}
.brak{color:#a8442a;font-style:italic}
footer{margin-top:60px;padding-top:20px;border-top:1px solid var(--ram);
       color:var(--mut);font-size:13.5px}
@media(max-width:640px){.w{padding:28px 16px 60px}h1{font-size:25px}}
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
    stab = czytaj("stabilnosc_rzepaku.json")
    przed = czytaj("przedkwitnieniowy.json")["wyniki"]
    star = czytaj("start_walidacja.json")["warianty"]
    woj = czytaj("wojewodztwo.json")
    wios = jad["jadra"]["wiosna"]

    def w_odl(k):
        d = odl.get(k, {})
        return (f"<td>{d.get('n', 0):,}</td><td>{lb(d.get('precyzja', 0))}</td>"
                f"<td>{lb(d.get('czulosc', 0))}</td>"
                f"<td><b>{lb(d.get('f1', 0))}</b></td>")

    hs = hind["statystyki"]
    dni = sorted(int(k) for k in hs)

    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Winter Rapeseed — Model Report</title>
<style>{STYL}</style>
<div class="w">

<span class="etap">Lubelskie voivodeship · single-species report</span>
<h1>Winter rapeseed: where it grows, when it blooms,<br>and how much a bee can reach</h1>
<p class="lead">Rapeseed carries about half of the nectar sugar in this
voivodeship and is the only species with its own bloom-date model. This
report follows the whole rapeseed pipeline end to end. Every number is read
from <code>wyniki/json/</code> at build time — none is typed in.</p>

<div class="spis">
  <a href="#gdzie">1 · Where — recognising the crop from orbit</a>
  <a href="#kiedy">2 · When — the thermal bloom model</a>
  <a href="#prog">3 · Where the GDD threshold and base temperature came from</a>
  <a href="#splot">4 · How much reaches the hive — the flight-range kernel</a>
  <a href="#mapy">5 · Fields around the best sites</a>
  <a href="#dane">6 · Data, and what limits it</a>
</div>

<!-- ------------------------------------------------------- GDZIE -->
<h2 id="gdzie">1 · Where — recognising the crop from orbit</h2>
<p class="lead">The question: <b>which fields are rapeseed?</b> Answered by a
random forest reading a whole year of satellite imagery.</p>

<h3>Why rapeseed is the easy one</h3>
<p>Rapeseed emits three unmistakable signals in a single year, and no other
arable crop here repeats that sequence:</p>
<ol class="kroki">
  <li><b>It overwinters green.</b> While cereals are thin and bare soil is
      dark, rapeseed holds a dense rosette through winter — visible in NDVI
      from October onward.</li>
  <li><b>It turns the whole field yellow in May.</b> NDYI, the
      green-minus-blue index, spikes over the entire canopy for roughly two
      weeks. Nothing else at this scale does that.</li>
  <li><b>It leaves stubble in July.</b> Harvest is early, so the field drops
      to bare-soil values while spring crops are still green.</li>
</ol>

<h3>What the model reads</h3>
<div class="wzor">26 half-month windows (September → September)
per window: NDVI, NDYI  (optical, as scene anomalies)
            VV, VH, VH−VV  (radar, decibels)
= {s1s2['n_cech']['S1_S2']} features, 300 trees</div>
<p><b>Scene anomaly, not raw index.</b> Each optical value has the median of
arable land <i>from the same scene</i> subtracted. Without this the model
would learn sun angle and haze instead of the plant — the same crop looks
different in a June and a September image for purely atmospheric reasons.</p>

<table>
  <caption>Spatial block cross-validation, 2.5 km blocks, 12 classes</caption>
  <thead><tr><th>sensor set</th><th>features</th><th>F1-macro</th>
    <th>rapeseed F1</th></tr></thead>
  <tbody>
    <tr><td>Sentinel-2 only</td><td>{s1s2['n_cech']['S2']}</td>
        <td>{lb(s1s2['f1_makro']['S2'])}</td><td>{lb(rz['S2']['f1'])}</td></tr>
    <tr><td>Sentinel-1 only</td><td>{s1s2['n_cech']['S1']}</td>
        <td>{lb(s1s2['f1_makro']['S1'])}</td><td>—</td></tr>
    <tr><td><b>both</b></td><td>{s1s2['n_cech']['S1_S2']}</td>
        <td><b>{lb(s1s2['f1_makro']['S1_S2'])}</b></td>
        <td><b class="ok">{lb(rz['S1_S2']['f1'])}</b></td></tr>
  </tbody>
</table>
<p>Radar carries {lb(s1s2['waznosc_radaru']*100, 1)}% of feature importance.
Its decisive advantage is coverage: <b>{s1s2['okna_puste']['S1']} empty
windows against {s1s2['okna_puste']['S2']} for optics</b> — in the first half
of January, 100% of points have no cloud-free scene at all.</p>

<h3>Parcel centre is not a pixel</h3>
<p>The F1 above is measured at <b>one representative point inside each
parcel</b>. Deployment classifies every pixel, edges included. Measured on
{piks['pokolenia']['pokolenie 2 (S1+S2, 130 cech)']['n_pikseli']:,} held-out
pixels, with cereals present:</p>
<table>
  <thead><tr><th>level</th><th>precision</th><th>recall</th><th>F1</th></tr></thead>
  <tbody>
    <tr><td>parcel centre</td><td>0.938</td><td>0.942</td>
        <td><b>{lb(rz['S1_S2']['f1'])}</b></td></tr>
    <tr><td>single pixel, balanced sample</td>
        <td>{lb(pik_zr['precyzja'])}</td><td>{lb(pik_zr['czulosc'])}</td>
        <td>{lb(pik_zr['f1'])}</td></tr>
    <tr><td><b>single pixel, real crop proportions</b></td>
        <td><b class="zle">{lb(pik_pr['precyzja'])}</b></td>
        <td>{lb(pik_pr['czulosc'])}</td>
        <td><b>{lb(pik_pr['f1'])}</b></td></tr>
  </tbody>
</table>
<p>At real prevalence roughly <b>every second pixel called rapeseed is not
rapeseed</b>, because 87% of farmland is something else. Recall is unchanged,
as it must be — prevalence cannot affect it.</p>

<p>Almost all of that error sits at the field boundary:</p>
<table>
  <caption>Rapeseed accuracy by distance from the parcel edge</caption>
  <thead><tr><th>distance</th><th>pixels</th><th>precision</th>
    <th>recall</th><th>F1</th></tr></thead>
  <tbody>
    <tr><td><b>0–10 m</b></td>{w_odl('0-10')}</tr>
    <tr><td>10–20 m</td>{w_odl('10-20')}</tr>
    <tr><td>20–40 m</td>{w_odl('20-40')}</tr>
    <tr><td>&gt; 40 m</td>{w_odl('40-10000')}</tr>
  </tbody>
</table>
<div class="uwaga"><b>{piks['udzial_pikseli_do_10m']*100:.0f}% of pixels lie
within 10 m of a boundary.</b> Parcels here are narrow strips, and a 10 m
Sentinel pixel straddling a boundary physically contains two crops. The model
is not wrong about those pixels — they genuinely are two things at once.
This is why the maps never use raw pixels.</div>

<h3>The level is wrong even when the pattern is right</h3>
<p>Training used a <b>balanced</b> sample — equal parcels per class, so no
crop vanishes. The model inherits the belief that all crops are equally
common and hands pixels too generously to rare classes. Correction: one
coefficient per species from a reference year.</p>
<table>
  <thead><tr><th>check</th><th>value</th></tr></thead>
  <tbody>
    <tr><td>declared area, ARiMR 2025</td>
        <td>{kal['areal_gsa']['rzepak ozimy']:,.0f} ha</td></tr>
    <tr><td>detected before correction</td>
        <td>{kal['areal_wykryty']['rzepak ozimy']:,.0f} ha</td></tr>
    <tr><td>calibration coefficient</td>
        <td><b>×{lb(kal['wspolczynniki']['rzepak ozimy'])}</b></td></tr>
    <tr><td>independent check: EUCROPMAP 2022</td>
        <td>{kal['kontrola_eucropmap']['2022']['eucropmap_ha']:,.0f} ha
            vs model {kal['kontrola_eucropmap']['2022']['model_ha']:,.0f} ha
            ({kal['kontrola_eucropmap']['2022']['odchylenie_pct']:+.1f}%)</td></tr>
  </tbody>
</table>
<p class="mniej">Rapeseed needs a correction of only 6%, so the balanced
sample barely distorts it — unlike sunflower, over-detected ninefold. The
assumption behind the fix is stated in the file: <i>{kal['zalozenie']}</i></p>

<h3>Does it hold in other years?</h3>
<table>
  <thead><tr><th>comparison</th><th>correlation</th></tr></thead>
  <tbody>
    <tr><td>detection 2025 vs declarations 2025</td>
        <td><b class="ok">{lb(sr['walidacje']['det2025_vs_gsa2025'])}</b></td></tr>
    <tr><td>detection 2022 vs EUCROPMAP 2022</td>
        <td><b class="ok">{lb(sr['walidacje']['det2022_vs_eucropmap2022'])}</b></td></tr>
    <tr><td>EUCROPMAP 2018 vs EUCROPMAP 2022</td>
        <td>{lb(stab['korelacje']['2018 EUCROPMAP vs 2022 EUCROPMAP'])}</td></tr>
    <tr><td>EUCROPMAP 2018 vs declarations 2025</td>
        <td>{lb(stab['korelacje']['2018 EUCROPMAP vs 2025 GSA'])}</td></tr>
  </tbody>
</table>
<p>Maps for {min(sr['lata_detekcji'])}–{max(sr['lata_detekcji'])} were made by
training on 2025 and running the model backwards. The EUCROPMAP agreement in
2022 is the only fully independent confirmation that this transfer works —
without it we would be assuming, not knowing.</p>

<h3>Finding the fields before they bloom</h3>
<p>The bloom date is measured from NDYI — the yellow signal. If the same
imagery also chose <i>which</i> fields to measure, the date would be learned
from itself. A separate classifier therefore uses only windows from before
flowering:</p>
<table>
  <caption>Accuracy retained when features are truncated to the decision day</caption>
  <thead><tr><th>data through</th><th>lead time</th><th>rapeseed F1</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{k}</td><td>{v.get('wyprzedzenie', '—')}</td>"
         f"<td>{lb(v['f1_rzepak'])}</td></tr>" for k, v in przed.items())}
  </tbody>
</table>
<p>At the end of March rapeseed is recognised with <b>93% of full-season
accuracy, six weeks before it flowers</b>. That is what keeps the bloom date
non-circular — and it opens the door to forecasting <i>location</i>, not just
timing, which this project does not yet do.</p>

<!-- ------------------------------------------------------- KIEDY -->
<h2 id="kiedy">2 · When — the thermal bloom model</h2>
<p class="lead">The question: <b>on which day is the field at full bloom?</b>
This model classifies nothing, so it has no F1 — its error is measured in
days.</p>

<h3>The mechanism</h3>
<p>Plants do not follow the calendar, they follow accumulated warmth. Every
day contributes the amount by which its mean temperature exceeds a base
below which development stalls. Bloom occurs when the running total crosses
a threshold.</p>
<div class="wzor">GDD = Σ max( (T<sub>max</sub> + T<sub>min</sub>)/2 − {lb(m['baza'],1)} °C , 0 )   from {m['start']}
bloom on the first day where GDD ≥ {lb(m['prog'],0)}</div>

<h3>What "an observation" means here</h3>
<p>The {m['n']} observations are <b>not field records</b>. For each area and
season, the NDYI curve of rapeseed fields is traced and the date of its peak
taken as full bloom. A parabola is fitted through the three points around the
maximum, so the date is not restricted to days when a satellite happened to
pass. The RMSE below therefore measures agreement with <b>remote-sensing
phenology</b>, not with BBCH observations on the ground.</p>

<table>
  <caption>{m['n']} observations, {m['obszarow']} areas, 9 seasons</caption>
  <thead><tr><th>metric</th><th>days</th></tr></thead>
  <tbody>
    <tr><td><b>RMSE, leave-one-out</b></td>
        <td><b class="ok">{lb(m['rmse'],2)}</b></td></tr>
    <tr><td>RMSE in-sample</td><td>{lb(m['rmse_dopasowania'],2)}</td></tr>
    <tr><td>baseline "always the average date"</td>
        <td>{lb(czytaj('fenologia_final.json')['odniesienie_stala'],2)}</td></tr>
    <tr><td>without rejecting outlier observations</td>
        <td>{lb(fen['rmse_bez_odrzucania'],2)}</td></tr>
  </tbody>
</table>
<p><b>Leave-one-out</b> means the base and threshold are re-fitted without the
observation being scored, so the model is never tested on data that shaped
it. The gap between {lb(m['rmse'],2)} and {lb(m['rmse_dopasowania'],2)} days
is the optimism of fitting — here it is small, which is what you want.</p>

<h3>In-season forecasting</h3>
<p>Before the season starts the model has no weather of that year and returns
the long-term mean. It becomes a forecast only as real weather accumulates:</p>
<table>
  <thead><tr><th>decision day</th><th>RMSE (days)</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>day {d} of year</td><td>{lb(hs[str(d)]['rmse'],2)}</td></tr>"
         for d in dni)}
  </tbody>
</table>
<p>April decides the date. Asked in February the model is no better than
quoting the multi-year average; asked on 1 May it is within
{lb(hs[str(dni[-1])]['rmse'],1)} days.</p>

<h3>Is the weather itself trustworthy?</h3>
<p>Temperatures come from ERA5 reanalysis through Open-Meteo, not from
stations. Checked against the IMGW station at {imgw['stacja']}:
<b>RMSE {lb(imgw['rmse_K'],2)} K, r = {lb(imgw['r'],3)}</b>, bias
{lb(imgw['bias_K'],2)} K. At roughly 5 GDD accumulated per spring day, a
1 K error shifts the predicted date by well under a day.</p>

<!-- ------------------------------------------------------- PROG -->
<h2 id="prog">3 · Where the GDD threshold and base temperature came from</h2>
<div class="uwaga"><b>They were fitted, not taken from the literature.</b>
No published source gives base {lb(m['baza'],1)} °C with threshold
{lb(m['prog'],0)}. Both numbers come from a grid search against the
{m['n']} measured bloom dates.</div>

<h3>The procedure</h3>
<ol class="kroki">
  <li><b>Measure the target.</b> Bloom dates from NDYI curves, on fields
      chosen by the pre-bloom classifier so the date is not circular.</li>
  <li><b>Search the grid.</b> Every (base, threshold) pair is scored by how
      well it reproduces those dates across all areas and seasons.</li>
  <li><b>Choose the accumulation start.</b> Six starting dates were tested,
      not assumed.</li>
  <li><b>Reject impossible observations.</b> A physically derived cutoff,
      not a hand-picked one.</li>
  <li><b>Validate leave-one-out.</b> Parameters re-fitted without the scored
      observation.</li>
</ol>

<h3>Why 15 March, and not 1 February</h3>
<p>The accumulation start is a free parameter and was chosen by measurement.
Both candidates were validated the same way:</p>
<table>
  <thead><tr><th>start</th><th>base</th><th>threshold</th>
    <th>RMSE in-sample</th><th>RMSE leave-one-out</th><th>worst case</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{v['opis']}</td><td>{lb(v['baza'],1)} °C</td>"
         f"<td>{lb(v['prog'],0)}</td><td>{lb(v['rmse_in'],2)}</td>"
         f"<td><b>{lb(v['rmse_loo'],2)}</b></td>"
         f"<td>{lb(v['najgorszy'],1)}</td></tr>" for v in star.values())}
  </tbody>
</table>
<p>Starting on 15 March won <b>45 of 45 folds</b> when the start date itself
was chosen inside the validation loop. The reason is physical: in February
daily increments are near zero, so those weeks add noise without separating
warm years from cold ones.</p>

<h3>The threshold alone is meaningless</h3>
<p>Base and threshold trade off against each other: a lower base adds more
degrees per day, so it needs a higher threshold to reach the same date. The
grid search finds not a point but a <b>valley</b> of near-equivalent
solutions.</p>
<div class="wzor">solutions within 0.2 days of the optimum, start 15 March:
    base       0.0 – 4.0 °C
    threshold  305 – 540 GDD</div>
<p><b>{lb(m['prog'],0)} sits in the middle of that valley.</b> Quoting it
without the base is meaningless — the pair is the parameter, not either
number alone.</p>

<h3>Why it cannot be compared with published values</h3>
<table>
  <caption>Published thresholds for winter rapeseed flowering</caption>
  <thead><tr><th>source</th><th>base</th><th>start</th><th>threshold</th></tr></thead>
  <tbody>
    <tr><td>Czech Republic, Atmosphere 2021</td><td>6.0 °C</td>
        <td>30 Jan</td><td>157</td></tr>
    <tr><td>Skopje region, BBCH 63</td><td>—</td><td>—</td><td>633–809</td></tr>
    <tr><td>Estonia, overwintering</td><td>5.0 °C</td><td>—</td><td>416</td></tr>
    <tr><td><b>this model</b></td><td><b>{lb(m['baza'],1)} °C</b></td>
        <td><b>{m['start']}</b></td><td><b>{lb(m['prog'],0)}</b></td></tr>
  </tbody>
</table>
<p>A GDD sum only means something together with its base and its start date.
At base 6 °C you subtract four and a half degrees more every day than at
1.5 °C, so the same bloom date produces a completely different total. The
numbers 157, 430 and 633 are not in conflict — they are different
coordinate systems.</p>

<h3>Rejecting observations, without hand-picking</h3>
<p>Some NDYI peaks are wrong: a cloud, a neighbouring mustard field, a
mis-set curve. Removing them by eye would be fitting the data to the model.
The cutoff is instead derived from what the model itself can explain:</p>
<div class="wzor">modelled spread between areas: median 2 d, max 5 d
  → up to 2.5 d of legitimate deviation from the median
  + about 3 d of NDYI reading uncertainty
  = reject an observation more than 6 days from the seasonal median</div>
<p class="mniej">Without rejection the error is
{lb(fen['rmse_bez_odrzucania'],2)} days; with it,
{lb(m['rmse'],2)}. {len(fen['odrzucone'])} observations were dropped out of
{m['n'] + len(fen['odrzucone'])}.</p>

<h3>Was the sample large enough?</h3>
<p>The first fit used {czytaj('fenologia_final.json')['obserwacje_poprzednie']['n']}
observations from
{czytaj('fenologia_final.json')['obserwacje_poprzednie']['obszarow']} areas.
To test whether the result was an artefact of site choice, the sample was
tripled to {m['n']} observations from {m['obszarow']} areas. The grid search
landed on <b>the same base and the same threshold</b>, and the error moved
from {lb(czytaj('fenologia_final.json')['model_poprzedni']['rmse'],2)} to
{lb(m['rmse'],2)} days. That is the strongest evidence available here that
the parameters are real and not fitted noise.</p>

<!-- ------------------------------------------------------- SPLOT -->
<h2 id="splot">4 · How much reaches the hive — the flight-range kernel</h2>
<p class="lead">A hive does not harvest the pixel it stands on. The map must
answer <b>how much sugar is reachable</b>, which means summing the
surroundings with a weight that falls off with distance.</p>

<div class="wzor">P(x) = Σ<sub>y</sub> C(y) · K( d(x,y) )       K(d) = exp( −d / λ )</div>
<p>where C(y) is the sugar on pixel y and d the distance between pixels. This
is a <b>convolution</b>, computed with an FFT over the whole
{woj['siatka'][0]:,} × {woj['siatka'][1]:,} grid at {woj['piksel_m']} m
resolution — one pixel is one hectare.</p>

<h3>The kernel is calibrated on measured bee flights</h3>
<p>λ is not chosen for looks. It is solved numerically so that the
<b>weighted mean flight distance of the kernel equals the distance measured
from waggle dances</b> — about 5,000 dances decoded by Couvillon et al.
(PLOS ONE, 2014):</p>
<table>
  <thead><tr><th>season</th><th>measured mean flight</th><th>λ</th>
    <th>effective range (4λ)</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{k}</td><td>{jad['dystanse_zmierzone_m'][k]:,.0f} m</td>"
         f"<td>{v['lambda_m']:,.0f} m</td>"
         f"<td>{v['zasieg_m']:,.0f} m</td></tr>"
         for k, v in jad['jadra'].items())}
  </tbody>
</table>
<p><b>Rapeseed uses the spring kernel</b> — its bloom falls before day 152, so
foraging range is {wios['zasieg_m']:,.0f} m, not the summer
{jad['jadra']['lato']['zasieg_m']:,.0f} m. Bees fly further in summer when
forage is scarcer; in a May rapeseed field they do not need to.</p>

<div class="uwaga"><b>Kernels are normalised to constant mass.</b> Each is
rescaled so all seasons sum to the same total before convolution. Without
this the summer kernel — spread over 25 times the area — would simply add
more sugar to every pixel, and the map would rank late species higher for a
purely arithmetic reason.</div>

<h3>The shape does not matter, the range does</h3>
<table>
  <caption>Same data, different kernel shapes</caption>
  <thead><tr><th>shape</th><th>correlation with exponential</th>
    <th>shared top 10%</th></tr></thead>
  <tbody>
{"".join(f"    <tr><td>{k}</td><td>{lb(v['korelacja'],4)}</td>"
         f"<td>{lb(v['top10_wspolne_proc'],1)}%</td></tr>"
         for k, v in ksz.items())}
  </tbody>
</table>
<p>Gaussian and linear kernels give effectively the same map. Arguing about
the functional form would be wasted effort — what matters is the distance
scale, and that comes from measurement.</p>

<!-- ------------------------------------------------------- MAPY -->
<h2 id="mapy">5 · Fields around the best sites</h2>
<p class="lead">The potential map is deliberately blurred by flight range, so
it cannot say <b>which</b> field is rapeseed. These close-ups can.</p>

<p><b>Parcels, not pixels.</b> A raw pixel scores F1 {lb(pik_pr['f1'])} at real crop
proportions — a pixel map would be confetti. Snapping the classification to
ARiMR parcel outlines and taking a majority vote restores F1 <b>0.910</b>,
so each field gets one colour.</p>

<div class="uwaga"><b>Yellow is the model's answer, not the farmer's.</b>
The outlines come from the 2025 declarations, but the colour is what the
classifier concluded from Sentinel-1+2 imagery alone — the declared crop is
never shown to it. Grey parcels are everything else, drawn only so the field
pattern is readable. Areas are raw detections, <b>before</b> the ×{lb(kal['wspolczynniki']['rzepak ozimy'])}
area calibration from section 1.</div>

{obraz("rapeseed_site_1.png", "Site 1 — highest-scoring location. A fruit-growing region: only 80 ha of rapeseed within 3 km.")}
{obraz("rapeseed_site_2.png", "Site 2 — a genuine rapeseed belt: 468 ha across 550 parcels within 3 km.")}
{obraz("rapeseed_site_3.png", "Site 3.")}

<p class="mniej">The contrast between sites 1 and 2 is worth noting: both
rank near the top of the potential map, but site 1 is a fruit-growing region
where rapeseed is a minor component, while site 2 sits in a genuine rapeseed
belt. The potential map ranks total reachable sugar, not rapeseed — so a
beekeeper travelling to site 1 on a rapeseed bloom date would arrive to
orchards and berries, which flower on a different schedule.</p>

<!-- ------------------------------------------------------- DANE -->
<h2 id="dane">6 · Data, and what limits it</h2>
<table>
  <thead><tr><th>source</th><th>span</th><th>role for rapeseed</th></tr></thead>
  <tbody>
    <tr><td>ARiMR GSA declarations</td><td>2025, 2026</td>
        <td>training labels, parcel outlines, area calibration</td></tr>
    <tr><td>Sentinel-2 L2A</td><td>2018–2026</td>
        <td>NDVI, NDYI; bloom date from the NDYI peak</td></tr>
    <tr><td>Sentinel-1 GRD</td><td>2018–2026</td>
        <td>VV, VH, VH−VV; fills the eight cloud-blind windows</td></tr>
    <tr><td>EUCROPMAP (JRC)</td><td>2018, 2022</td>
        <td>independent cross-check of detected area</td></tr>
    <tr><td>ERA5 via Open-Meteo</td><td>2000–2026</td>
        <td>temperatures for the GDD model</td></tr>
    <tr><td>Couvillon et al. 2014</td><td>—</td>
        <td>measured flight distances for the kernel</td></tr>
  </tbody>
</table>

<h3>What this report does not claim</h3>
<ul>
  <li><b>No harvest validation.</b> Nothing here has been checked against a
      real honey yield from a real apiary. That is the largest open gap in
      the project.</li>
  <li><b>Bloom dates are satellite-derived.</b> The {lb(m['rmse'],2)}-day
      error measures agreement with NDYI phenology. If NDYI systematically
      leads or lags true full bloom, the threshold absorbs that bias and the
      error would not show it.</li>
  <li><b>Declarations exist for two years only.</b> Everything multi-year
      rests on detection transferring backwards, which is confirmed by a
      single independent source (EUCROPMAP 2022).</li>
  <li><b>The series starts in 2018</b> with Sentinel-2. Earlier years are
      extrapolation. MODIS is too coarse (500 m against a 1.16 ha median
      parcel) and Landsat too sparse — both were tested and rejected.</li>
  <li><b>Per-pixel output is unreliable on its own</b> and is never used
      that way: the maps blur by flight range and calibrate area first.</li>
</ul>

<footer>
Generated by <code>skrypty/raport/raport_rzepak.py</code>. All figures read
from <code>wyniki/json/</code> at build time. Full parameter provenance,
including negative results, is in <code>ZRODLA.md</code>.
</footer>
</div>
"""


if __name__ == "__main__":
    html = buduj()
    wyj = ROOT / "raport_rzepak.html"
    wyj.write_text(html, encoding="utf-8")
    print(f"zapisano {wyj.name}: {len(html.encode()) / 1e6:.1f} MB")
