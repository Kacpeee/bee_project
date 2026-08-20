"""
Buduje raport.html z wynikow zapisanych w wyniki/json i mapy/.

Strona jest samowystarczalna: mapy jako data URI, wykresy jako inline SVG.

    python skrypty/raport/raport_buduj.py
"""

from __future__ import annotations

import base64
import json
import math
from datetime import date, timedelta
from pathlib import Path

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import potencjal_gsa as P

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
MAPY = ROOT / "mapy"

S1, S1D = "#2a78d6", "#3987e5"
S2, S2D = "#eb6834", "#d95926"
S3, S3D = "#1baf7a", "#199e70"
KONTEKST = "#898781"

MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
KLASA = {"A": "badanie", "B": "tabela branżowa", "C": "założenie"}
ZERO_POZYTEK = ("soja zwyczajna", "groch siewny", "fasola zwykła")


def pl(x: float, n: int = 3) -> str:
    return f"{x:,.{n}f}".replace(",", "\u202f").replace(".", ",")


def dz(doy: float, rok: int = 2022) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def skala(v, lo, hi, a, b):
    return a + (v - lo) / (hi - lo) * (b - a)


def png_b64(sciezka: Path) -> str:
    return ("data:image/png;base64,"
            + base64.b64encode(sciezka.read_bytes()).decode())


def f1(p: float, c: float) -> float:
    return 2 * p * c / max(p + c, 1e-9)


def czytaj(n: str):
    return json.loads((WYNIKI / "json" / n).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- wykresy
def wykres_profil(wiersze, pasmo, lo, hi, rok, kwit, tytul, os_y, adnotacja):
    W, H = 760, 318
    ML, MR, MT, MB = 58, 128, 44, 52
    x0, x1, y0, y1 = ML, W - MR, MT, H - MB
    doye = [int(w["doy"]) for w in wiersze]
    dmin, dmax = min(doye), max(doye)
    px = lambda d: skala(d, dmin, dmax, x0, x1)
    py = lambda v: skala(v, lo, hi, y1, y0)

    def sciezka(n):
        p = [(px(int(w["doy"])), py(w[f"{n}_{pasmo}"])) for w in wiersze
             if w.get(f"{n}_{pasmo}") is not None]
        return "M " + " L ".join(f"{a:.1f} {b:.1f}" for a, b in p)

    s = [f'<svg viewBox="0 0 {W} {H}" class="wykres" role="img" '
         f'aria-label="{tytul}">']
    s.append(f'<text x="{x0}" y="18" class="w-tytul">{tytul}</text>')
    s.append(f'<rect x="{px(kwit[0]):.1f}" y="{y0}" '
             f'width="{px(kwit[1])-px(kwit[0]):.1f}" height="{y1-y0}" class="pas"/>')
    s.append(f'<text x="{(px(kwit[0])+px(kwit[1]))/2:.1f}" y="{y0+13}" '
             f'class="pas-txt" text-anchor="middle">kwitnienie rzepaku</text>')
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        s.append(f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" class="siatka"/>')
        s.append(f'<text x="{x0-8}" y="{py(v)+3.5:.1f}" class="os" text-anchor="end">{pl(v,2)}</text>')
    for d in range(((dmin + 19) // 20) * 20, dmax + 1, 20):
        s.append(f'<text x="{px(d):.1f}" y="{y1+18}" class="os" text-anchor="middle">{dz(d,rok)}</text>')
    s.append(f'<text x="{(x0+x1)/2:.1f}" y="{H-8}" class="os-os" text-anchor="middle">'
             f'data · Sentinel-2, sezon {rok}</text>')
    s.append(f'<text transform="rotate(-90 16 {(y0+y1)/2:.1f})" x="16" '
             f'y="{(y0+y1)/2:.1f}" class="os-os" text-anchor="middle">{os_y}</text>')
    for n in ("pszenica", "jeczmien", "zyto", "kukurydza", "uzytki zielone"):
        s.append(f'<path d="{sciezka(n)}" class="linia-kontekst"/>')
    s.append(f'<path d="{sciezka("LAS(kontrola)")}" class="linia-las"/>')
    s.append(f'<path d="{sciezka("rzepak")}" class="linia-rzepak"/>')
    for w in wiersze:
        v = w.get(f"rzepak_{pasmo}")
        if v is not None:
            s.append(f'<circle cx="{px(int(w["doy"])):.1f}" cy="{py(v):.1f}" r="4" '
                     f'class="punkt-rzepak"><title>{dz(int(w["doy"]),rok)}: {pl(v)}</title></circle>')
    pkt = [(int(w["doy"]), w[f"rzepak_{pasmo}"]) for w in wiersze
           if w.get(f"rzepak_{pasmo}") is not None
           and kwit[0] <= int(w["doy"]) <= kwit[1]]
    if pkt:
        znacznik = (max if pasmo == "NDYI" else min)(pkt, key=lambda t: t[1])
        sx, sy = px(znacznik[0]), py(znacznik[1])
        dy = -22 if pasmo == "NDYI" else 28
        s.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{sx:.1f}" y2="{sy+dy:.1f}" class="blad"/>')
        s.append(f'<text x="{sx:.1f}" y="{sy+dy+(-4 if dy < 0 else 12):.1f}" '
                 f'class="adnotacja" text-anchor="middle">{adnotacja}</text>')
    ost = wiersze[-1]
    et = []
    for n, k, t in (("rzepak", "et-rzepak", "rzepak"),
                    ("LAS(kontrola)", "et-las", "las — nie uprawa"),
                    ("pszenica", "et-kontekst", "inne uprawy")):
        if ost.get(f"{n}_{pasmo}") is not None:
            et.append([py(ost[f"{n}_{pasmo}"]), k, t])
    et.sort()
    for i in range(1, len(et)):
        if et[i][0] - et[i-1][0] < 16:
            et[i][0] = et[i-1][0] + 16
    for y, k, t in et:
        s.append(f'<text x="{x1+8}" y="{y+4:.1f}" class="{k}">{t}</text>')
    s.append("</svg>")
    return "\n".join(s)


def wykres_fenologia(f):
    W, H = 760, 348
    ML, MR, MT, MB = 58, 148, 40, 52
    x0, x1, y0, y1 = ML, W - MR, MT, H - MB
    obs = {int(k): v for k, v in f["obserwacje"].items()}
    pre = {int(k): v for k, v in f["przewidywania"].items()}
    lata = sorted(obs)
    lo, hi = 108, 152
    px = lambda r: skala(r, min(lata), max(lata), x0, x1)
    py = lambda v: skala(v, lo, hi, y1, y0)
    sr = sum(obs.values()) / len(obs)

    s = [f'<svg viewBox="0 0 {W} {H}" class="wykres" role="img" '
         'aria-label="Termin kwitnienia: obserwacja z satelity wobec modelu GDD">']
    s.append('<text x="56" y="16" class="w-tytul">Data pełni rzepaku: satelita vs GDD</text>')
    for v in range(110, 151, 10):
        s.append(f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" class="siatka"/>')
        s.append(f'<text x="{x0-8}" y="{py(v)+3.5:.1f}" class="os" text-anchor="end">{dz(v)}</text>')
    s.append(f'<line x1="{x0}" y1="{py(sr):.1f}" x2="{x1}" y2="{py(sr):.1f}" class="odniesienie"/>')
    s.append(f'<text x="{x1+8}" y="{py(sr)+4:.1f}" class="et-kontekst">gdyby zawsze średnia</text>')
    for r in lata:
        s.append(f'<text x="{px(r):.1f}" y="{y1+20}" class="os" text-anchor="middle">{r}</text>')
        if r in pre:
            s.append(f'<line x1="{px(r):.1f}" y1="{py(obs[r]):.1f}" x2="{px(r):.1f}" '
                     f'y2="{py(pre[r]):.1f}" class="blad"/>')
    s.append('<path d="M ' + " L ".join(f"{px(r):.1f} {py(pre[r]):.1f}"
             for r in lata if r in pre) + '" class="linia-model"/>')
    for r in lata:
        if r in pre:
            s.append(f'<circle cx="{px(r):.1f}" cy="{py(pre[r]):.1f}" r="4" class="punkt-model">'
                     f'<title>model {r}: {dz(pre[r], r)}</title></circle>')
        s.append(f'<circle cx="{px(r):.1f}" cy="{py(obs[r]):.1f}" r="5" class="punkt-obs">'
                 f'<title>obserwacja {r}: {dz(obs[r], r)}</title></circle>')
    s.append(f'<text x="{x1+8}" y="{py(obs[lata[-1]])+4:.1f}" class="et-rzepak">satelita (prawda)</text>')
    s.append(f'<text x="{x1+8}" y="{py(pre[lata[-1]])+18:.1f}" class="et-las">GDD (model)</text>')
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="baza"/>')
    s.append(f'<text x="{(x0+x1)/2:.1f}" y="{H-6}" class="os-os" text-anchor="middle">rok</text>')
    s.append(f'<text transform="rotate(-90 14 {(y0+y1)/2:.1f})" x="14" '
             f'y="{(y0+y1)/2:.1f}" class="os-os" text-anchor="middle">data pełni</text>')
    s.append("</svg>")
    return "\n".join(s)


def wykres_kalendarz(p):
    W, H = 760, 300
    ML, MR, MT, MB = 52, 120, 18, 44
    x0, x1, y0, y1 = ML, W - MR, MT, H - MB
    dek = p["dekady"]
    serie = [("caly sezon", "kal-1", "cały sezon"), ("sam rzepak", "kal-2", "sam rzepak"),
             ("po rzepaku", "kal-3", "po rzepaku")]
    hi = math.ceil(max(v for n, _, _ in serie
                       for v in p["kalendarze"][n].values()) / 1000)
    px = lambda d: skala(d, min(dek), max(dek), x0, x1)
    py = lambda v: skala(v, 0, hi, y1, y0)

    s = [f'<svg viewBox="0 0 {W} {H}" class="wykres" role="img" '
         'aria-label="Potencjal pozytkowy w dekadach sezonu">']
    for i in range(5):
        v = hi * i / 4
        s.append(f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" class="siatka"/>')
        s.append(f'<text x="{x0-8}" y="{py(v)+3.5:.1f}" class="os" text-anchor="end">{pl(v,1)}</text>')
    for d in dek[::3]:
        s.append(f'<text x="{px(d):.1f}" y="{y1+20}" class="os" text-anchor="middle">{p["daty"][str(d)]}</text>')
    s.append(f'<text x="{(x0+x1)/2:.1f}" y="{y1+38}" class="os" text-anchor="middle">'
             'tony cukrów w nektarze w zasięgu lotu (oś pionowa)</text>')
    for n, kls, _ in serie:
        pk = [(px(d), py(p["kalendarze"][n][str(d)] / 1000)) for d in dek]
        s.append(f'<path d="M {" L ".join(f"{a:.1f} {b:.1f}" for a, b in pk)}" class="{kls}"/>')
        for (a, b), d in zip(pk, dek):
            s.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.5" class="{kls}-p">'
                     f'<title>{n}, {p["daty"][str(d)]}: {pl(p["kalendarze"][n][str(d)]/1000,2)} t</title></circle>')
    et = sorted((py(p["kalendarze"][n][str(dek[7])] / 1000), f"et-{kls}", t)
                for n, kls, t in serie)
    for i in range(1, len(et)):
        if et[i][0] - et[i-1][0] < 14:
            et[i] = (et[i-1][0] + 14, et[i][1], et[i][2])
    for y, kls, t in et:
        s.append(f'<text x="{x1+8}" y="{y+4:.1f}" class="{kls}">{t}</text>')
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="baza"/>')
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- strona
def strona(prof, kl, fen, pot, mapy) -> str:
    # najlepsze miejsca - wynik koncowy, przeniesiony tu ze strony prognozy
    pkt_m = czytaj("najlepsze_punkty.json")["miejsca"]
    zlo_m = czytaj("zloz_calosc.json")
    mediana_rodzin = f"{zlo_m['pojemnosc_percentyle']['50']:.0f}"
    wiersze_miejsc = "".join(
        f'<tr><th scope="row">{q["nr"]}</th>'
        f'<td class="mocne">{q["rodzin"]:.0f}</td>'
        f'<td>{q["promien_95_m"]:.0f} m</td>'
        f'<td>{q["promien_90_m"]:.0f} m</td>'
        f'<td>{q["promien_80_m"]:.0f} m</td>'
        f'<td>{q["lat"]:.4f} N</td><td>{q["lon"]:.4f} E</td></tr>'
        for q in pkt_m)
    mapy_miejsce1 = mapy.get("miejsce1", "")
    rok = prof["rok"]
    obs = {int(k): v for k, v in fen["obserwacje"].items()}
    pre = {int(k): v for k, v in fen["przewidywania"].items()}
    m, odn = fen["model"], fen["odniesienia"]
    fin_ = fen["final"]
    gl_nazwa = fin_["glowny"]

    fas = czytaj("klasyfikator_fasoli.json")
    sr = czytaj("sredni_rok.json")
    imgw = czytaj("imgw_walidacja.json")
    stab = czytaj("stabilnosc_rzepaku.json")
    sez = czytaj("sezony_porownanie.json")
    tel = czytaj("teledetekcja_mapy.json")
    prog = czytaj("prognoza_w_sezonie.json")
    det_lat = czytaj("detekcja_lata.json")
    det_woj = czytaj("detekcja_wojewodztwo.json")
    sad = czytaj("fenologia_sadu.json")
    woj = czytaj("wojewodztwo.json")
    s1s2 = czytaj("wielo_s1s2.json")
    m_fen = czytaj("fenologia_final.json")["model"]
    n_cech_wielo = czytaj("klasyfikator_wielo.json")["n_cech"]

    kp = fen["klasyfikator_przed"]
    f1_przed = f1(kp["precyzja"], kp["czulosc"])
    f1_lata = f1(det_lat["walidacja"]["precyzja"], det_lat["walidacja"]["czulosc"])
    wp = det_woj["walidacja_punktowa"]
    oa = lambda d, k="oa": pl(d[k]) if k in d else "—"
    nn = lambda d: str(d["n"]) if "n" in d else "—"
    sr_kwit = prog["sredni_termin_kwitnienia"]
    et_dec = {46: "15 II", 60: "1 III", 74: "15 III", 91: "1 IV", 105: "15 IV", 121: "1 V"}

    tab_obszary = "\n".join(
        f"<tr><th scope='row'>{n}</th><td>{pl(v['lat'],2)}</td><td>{v['n']}</td>"
        f"<td class='mocne'>{pl(v['rmse'],1)}</td><td>{v['bias']:+.1f}</td></tr>"
        for n, v in sorted(fin_["per_obszar"].items(), key=lambda kv: kv[1]["lat"]))

    tab_fen = "\n".join(
        f"<tr><th scope='row'>{r}</th><td>{dz(obs[r], r)}</td>"
        f"<td>{dz(pre[r], r) if r in pre else '–'}</td>"
        f"<td class='{'blad-duzy' if r in pre and abs(pre[r]-obs[r]) >= 5 else ''}'>"
        f"{pre[r]-obs[r]:+.0f}</td></tr>"
        for r in sorted(obs) if r in pre)

    tab_prog = "\n".join(
        f"<tr><th scope='row'>{et_dec[int(d)]}</th>"
        f"<td>{pl(sr_kwit - int(d), 0)}</td>"
        f"<td class='{'mocne' if v['rmse'] < 5 else ''}'>{pl(v['rmse'],1)}</td></tr>"
        for d, v in prog["statystyki"].items())

    ha = {n: v["ha_2025"] for n, v in sez["gatunki"].items()}
    wiersze_rosl = []
    for n, (kg, s0, p0, k0, zrod, klasa) in P.POZYTKI.items():
        okno = ("z GDD, −10 / +12 dni wokół pełni"
                if n == "rzepak ozimy"
                else f"{dz(s0)} – {dz(k0)}")
        wiersze_rosl.append(
            f"<tr><th scope='row'>{n}</th>"
            f"<td>{pl(ha.get(n, 0)/1000, 1)}</td>"
            f"<td class='mocne'>{kg}</td>"
            f"<td>{okno}</td>"
            f"<td class='zr-{klasa}'>{KLASA[klasa]}</td>"
            f"<td style='white-space:normal;text-align:left'>{zrod}</td></tr>")
    for n in ZERO_POZYTEK:
        wiersze_rosl.append(
            f"<tr><th scope='row'>{n}</th><td>—</td><td>0</td><td>—</td>"
            f"<td class='zr-A'>badanie (brak)</td>"
            f"<td style='white-space:normal;text-align:left'>"
            f"nieobecne w krajowych tabelach miododajności; samopylne</td></tr>")
    tab_rosl = "\n".join(wiersze_rosl)

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gdzie postawić ul — wyniki</title>
<style>
:root {{
  color-scheme: light dark;
  /* PALETA WSPOLNA dla wszystkich stron projektu (serwis, kalendarz,
     raport, mechanika). --s1..--s3 to kolory danych na wykresach
     i zostaja bez zmian - koduja wartosc, nie wyglad. */
  --tlo:#f4f6f5; --plyta:#ffffff; --plyta-2:#eef2f0;
  --atrament:#16201c; --atrament-2:#42504a; --muted:#5f6b66;
  --linia:#dbe3df; --siatka:#e3e9e5; --baza:#b8c4be;
  --akcent:#1d6f42; --akcent2:#b3801a;
  --s1:{S1}; --s2:{S2}; --s3:{S3}; --kontekst:{KONTEKST};
  --pas:rgba(179,128,26,.10); --ok:#1d6f42;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --tlo:#101613; --plyta:#18211d; --plyta-2:#1e2823;
    --atrament:#e3eae6; --atrament-2:#b6c2bc; --muted:#8d9a94;
    --linia:#27332d; --siatka:#242f29; --baza:#3a4a42;
    --akcent:#54b37c; --akcent2:#d6a53f;
    --pas:rgba(214,165,63,.12); --ok:#54b37c;
  }}
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--tlo); color:var(--atrament);
  font:400 17px/1.62 Charter,"Bitstream Charter","Iowan Old Style",Georgia,serif;
  -webkit-text-size-adjust:100%; }}
.strona {{ max-width:1160px; margin:0 auto; padding:56px 24px 96px; }}
.kolumna {{ max-width:66ch; }}
h1,h2,h3,.etap,.os,table,.liczba,.pas-txt,
.et-rzepak,.et-las,.et-kontekst,.et-kal-1,.et-kal-2,.et-kal-3,figcaption b {{
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
h1 {{ font-size:clamp(30px,4.4vw,46px); font-weight:700; letter-spacing:-.022em;
  line-height:1.08; margin:0 0 14px; text-wrap:balance; max-width:22ch; }}
h2 {{ font-size:25px; font-weight:700; letter-spacing:-.018em; line-height:1.2;
  margin:0 0 14px; text-wrap:balance; }}
p {{ margin:0 0 16px; }}
.lid {{ font-size:19px; color:var(--atrament-2); max-width:62ch; }}
.meta {{ font:400 13px/1.6 ui-monospace,"Cascadia Mono",Consolas,monospace;
  color:var(--muted); margin-top:22px; }}
section {{ margin-top:60px; padding-top:30px; border-top:1px solid var(--linia); }}
.karta.zastapiony {{ opacity:.72; }}
.etap {{ display:inline-block; font-size:11.5px; font-weight:650; letter-spacing:.1em;
  text-transform:uppercase; color:var(--akcent2); margin-bottom:10px; }}
.tiles {{ display:grid; gap:2px; grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  margin:26px 0 8px; }}
.tile {{ background:var(--plyta); padding:16px 18px; }}
.liczba {{ font-size:30px; font-weight:700; letter-spacing:-.02em; line-height:1.05;
  display:block; }}
.tile span.opis {{ display:block; font-size:13px; color:var(--atrament-2);
  margin-top:5px; line-height:1.35; }}
figure {{ margin:26px 0 0; }}
figure.plansza {{ background:var(--plyta); padding:20px 18px 14px; }}
.wykres {{ display:block; width:100%; height:auto; }}
figcaption {{ font-size:13.5px; color:var(--atrament-2); line-height:1.45; margin-top:10px; }}
figcaption b {{ color:var(--atrament); font-weight:650; }}
.legenda {{ display:flex; flex-wrap:wrap; gap:18px; font-size:13px;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--atrament-2); margin:2px 0 12px; }}
.legenda i {{ display:inline-block; width:16px; height:3px; border-radius:2px;
  vertical-align:middle; margin-right:7px; }}
.siatka {{ stroke:var(--siatka); stroke-width:1; }}
.baza {{ stroke:var(--baza); stroke-width:1; }}
.odniesienie {{ stroke:var(--muted); stroke-width:1.5; stroke-dasharray:2 4; }}
.blad {{ stroke:var(--muted); stroke-width:1.5; opacity:.55; }}
.pas {{ fill:var(--pas); }}
.pas-txt {{ font-size:10.5px; fill:var(--muted); letter-spacing:.06em; text-transform:uppercase; }}
.os {{ font-size:11px; fill:var(--muted); font-variant-numeric:tabular-nums; }}
.os-os {{ font-size:11px; fill:var(--muted); }}
.w-tytul {{ font-size:13.5px; font-weight:650; fill:var(--atrament); }}
.adnotacja {{ font-size:11.5px; font-weight:650; fill:var(--s2); }}
.linia-kontekst {{ fill:none; stroke:var(--kontekst); stroke-width:1.25; opacity:.5; }}
.linia-las {{ fill:none; stroke:var(--s1); stroke-width:2; stroke-dasharray:5 4; }}
.linia-rzepak {{ fill:none; stroke:var(--s2); stroke-width:2.5; }}
.linia-model {{ fill:none; stroke:var(--s1); stroke-width:2; stroke-dasharray:5 4; }}
.punkt-rzepak {{ fill:var(--s2); stroke:var(--plyta); stroke-width:2; }}
.punkt-obs {{ fill:var(--s2); stroke:var(--plyta); stroke-width:2; }}
.punkt-model {{ fill:var(--s1); stroke:var(--plyta); stroke-width:2; }}
.et-rzepak,.et-kal-2 {{ font-size:12.5px; font-weight:650; fill:var(--s2); }}
.et-las,.et-kal-1 {{ font-size:12.5px; font-weight:650; fill:var(--s1); }}
.et-kal-3 {{ font-size:12.5px; font-weight:650; fill:var(--s3); }}
.et-kontekst {{ font-size:12.5px; fill:var(--muted); }}
.kal-1 {{ fill:none; stroke:var(--s1); stroke-width:2.5; }}
.kal-2 {{ fill:none; stroke:var(--s2); stroke-width:2; stroke-dasharray:5 4; }}
.kal-3 {{ fill:none; stroke:var(--s3); stroke-width:2; }}
.kal-1-p {{ fill:var(--s1); stroke:var(--plyta); stroke-width:1.5; }}
.kal-2-p {{ fill:var(--s2); stroke:var(--plyta); stroke-width:1.5; }}
.kal-3-p {{ fill:var(--s3); stroke:var(--plyta); stroke-width:1.5; }}
.przewijak {{ overflow-x:auto; margin-top:22px; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px;
  font-variant-numeric:tabular-nums; }}
caption {{ text-align:left; font-size:13px; color:var(--atrament-2); padding-bottom:8px; }}
th,td {{ padding:8px 12px; text-align:right; white-space:nowrap;
  border-bottom:1px solid var(--linia); }}
thead th {{ font-size:11.5px; letter-spacing:.05em; text-transform:uppercase;
  color:var(--muted); font-weight:650; }}
tbody th {{ text-align:left; font-weight:650; }}
td.mocne {{ font-weight:700; }}
td.blad-duzy {{ color:var(--s2); font-weight:700; }}
td.zr-A {{ color:var(--ok); font-weight:650; }}
td.zr-B {{ color:var(--atrament-2); }}
td.zr-C {{ color:var(--muted); font-style:italic; }}
.wzor {{ background:var(--plyta); padding:16px 18px; font:400 14px/1.55 ui-monospace,
  "Cascadia Mono",Consolas,monospace; overflow-x:auto; margin:18px 0; }}
figure.mapa-hero {{ margin:26px 0 0; background:#fcfcfb; padding:0; }}
figure.mapa-hero img {{ display:block; width:100%; height:auto; }}
figure.mapa-hero figcaption {{ padding:14px 18px 16px; margin:0; }}
ul {{ margin:0 0 16px; padding-left:1.15em; }}
li {{ margin-bottom:9px; }}
.uwaga {{ background:var(--plyta-2); border-left:3px solid var(--s2);
  padding:15px 18px; margin:22px 0; font-size:15.5px; }}
.uwaga p:last-child {{ margin-bottom:0; }}
code {{ font:400 .88em ui-monospace,"Cascadia Mono",Consolas,monospace;
  background:var(--plyta-2); padding:.1em .35em; border-radius:3px; }}
h3 {{ font-size:16px; font-weight:700; letter-spacing:-.01em; margin:22px 0 10px; }}
ol {{ margin:0 0 16px; padding-left:1.2em; }}
ol li {{ margin-bottom:8px; }}
a {{ color:var(--s2); }}
.spis {{ display:flex; flex-wrap:wrap; gap:8px 18px; font:650 13px/1.4 system-ui,sans-serif;
  margin:18px 0 0; }}
.spis a {{ color:var(--atrament-2); text-decoration:none; border-bottom:1px solid var(--linia); }}
.karta {{ background:var(--plyta); padding:18px 20px 8px; margin-top:16px; }}
.karta h3 {{ margin:0 0 6px; font-size:17px; }}
.karta .do-czego {{ color:var(--atrament-2); margin:0 0 12px; font-size:15px; }}
.karta .status-ok {{ font-size:12.5px; font-weight:650; color:var(--ok); margin:0 0 10px; }}
.karta .status-no {{ font-size:12.5px; font-weight:650; color:var(--s2); margin:0 0 10px; }}
.karta table {{ margin-top:0; }}
.karta .przewijak {{ margin-top:4px; max-width:min(100%, 46rem); }}
.karta table {{ font-size:13px; }}
.karta th, .karta td {{ padding:7px 10px; }}
.karta .dopisek {{ font-size:13px; color:var(--muted); margin:8px 0 12px; }}
</style>
</head>
<body>
<div class="strona">
<header class="kolumna">
  <h1>Gdzie postawić ul</h1>
  <p class="lid">Raport z modelu lokalizacji pasiek na Lubelszczyźnie.
  Mapa pokazuje <b>potencjał</b>: ile cukrów w nektarze pszczoła dosięgnie
  z danego punktu. To nie jest prognoza plonu miodu.</p>
  <p class="meta">województwo lubelskie · siatka 100&nbsp;m
  ({woj['siatka'][0]}×{woj['siatka'][1]} px) · sezony 2019–2026</p>
  <nav class="spis" aria-label="Spis">
    <a href="#liczy">Co liczy</a>
    <a href="#jakosc">Modele</a>
    <a href="#dane">Skąd dane</a>
    <a href="#mapa">Jak liczona mapa</a>
    <a href="#rosliny">Rośliny i źródła</a>
    <a href="#satelita">Jak widać rzepak</a>
    <a href="#gdd">GDD i mapy</a>
    <a href="#metoda">Jak to policzono</a>
    <a href="#miejsca">Najlepsze miejsca</a>
    <a href="#produkty">Co powstało</a>
    <a href="#uwaga">Na co uważać</a>
  </nav>
</header>

<section id="liczy" style="border-top:0">
  <span class="etap">1 · zakres</span>
  <div class="kolumna"><h2>Co model liczy, a czego nie</h2>
  <p>Dla każdego hektara: suma cukrów z pól w zasięgu lotu pszczoły, ważona
  odległością. Jednostka: tony cukrów w nektarze, nie kilogramy miodu.
  Nie ma tu siły rodziny, konkurencji innych pasiek ani pozwolenia na ul.</p></div>
  <div class="tiles">
    <div class="tile"><span class="liczba">{pl(kl['przestrzenna']['f1'],2)}</span>
      <span class="opis">F1 detekcji rzepaku (czy satelita trafia w działki ARiMR)</span></div>
    <div class="tile"><span class="liczba">{pl(m['rmse_dni'],1)} dnia</span>
      <span class="opis">błąd daty pełni rzepaku z temperatur vs zdjęcie, {fin_['model']['n']} obs.</span></div>
    <div class="tile"><span class="liczba">{pl(sr['walidacje']['det2025_vs_gsa2025'],2)}</span>
      <span class="opis">zgodność mapy satelitarnej z deklaracjami po splocie</span></div>
    <div class="tile"><span class="liczba">{pl(sez['korelacja'],2)}</span>
      <span class="opis">stabilność mapy potencjału 2025 ↔ 2026</span></div>
  </div>
</section>

<section id="jakosc">
  <span class="etap">2 · jakość modeli</span>
  <div class="kolumna"><h2>Każdy model osobno</h2>
  <p>W projekcie pracują <b>dwa modele</b>: klasyfikator mówiący, co rośnie
  na polu, i model termiczny mówiący, kiedy to zakwitnie. Poniżej każdy
  osobno, z miarą właściwą dla swojego zadania — plus dwa modele
  z wcześniejszych etapów, które <b>zostały zastąpione</b> i są tu wyłącznie
  dla porządku.</p>
  <p class="dopisek"><b>F1</b> = ocena rozpoznawania w skali 0–1, łącząca
  precyzję (ile wskazań trafionych) i czułość (ile znalezionych).
  <b>RMSE</b> = typowy błąd daty w dniach.</p></div>

  <article class="karta">
    <h3>1. Klasyfikator wielogatunkowy — Sentinel-1 + Sentinel-2</h3>
    <p class="status-ok">W użyciu · warstwa satelitarna mapy, sezony 2019–2025</p>
    <p class="do-czego">Pytanie: <b>co rośnie na tym polu?</b> Las losowy,
    {n_cech_wielo} cech z kompozytów półmiesięcznych (wrzesień → wrzesień):
    NDVI i NDYI jako anomalie sceny oraz VV, VH i VH−VV z radaru.
    Etykiety: deklaracje ARiMR&nbsp;2025.</p>
    <div class="przewijak"><table>
      <caption>Walidacja przestrzenna, bloki 2,5&nbsp;km · 12 klas</caption>
      <thead><tr><th scope="col">zestaw cech</th><th scope="col">F1-makro</th></tr></thead>
      <tbody>
        <tr><th scope="row">Sentinel-2 sam</th><td>{pl(s1s2['f1_makro']['S2'], 3)}</td></tr>
        <tr><th scope="row">Sentinel-1 sam</th><td>{pl(s1s2['f1_makro']['S1'], 3)}</td></tr>
        <tr><th scope="row">oba razem</th><td class="mocne">{pl(s1s2['f1_makro']['S1_S2'], 3)}</td></tr>
      </tbody>
    </table></div>
    <div class="przewijak"><table>
      <caption>Trzy gatunki, które trafiają do mapy</caption>
      <thead><tr><th scope="col">gatunek</th><th scope="col">F1</th>
        <th scope="col">przeniesienie na inny rok</th>
        <th scope="col">udział w cukrze warstwy</th></tr></thead>
      <tbody>
        <tr><th scope="row">rzepak ozimy</th><td class="mocne">0,940</td><td>0,958</td><td>86,7%</td></tr>
        <tr><th scope="row">gryka zwyczajna</th><td>0,583</td><td>0,859</td><td>12,1%</td></tr>
        <tr><th scope="row">słonecznik</th><td>0,605</td><td>0,850</td><td>1,2%</td></tr>
      </tbody>
    </table></div>
    <p class="dopisek"><b>Rzepak jest zdecydowanie najłatwiejszy</b>, bo daje
    trzy niepowtarzalne sygnały w roku: zimuje jako zielona rozeta, w maju
    żółknie na całą powierzchnię, w lipcu zostaje ściernisko. Gryka
    i słonecznik są jare i przez pierwsze miesiące wyglądają jak każde
    świeżo obsiane pole. Dla mapy to drugorzędne — rzepak niesie 86,7% cukru
    tej warstwy, a błąd poziomu naprawia kalibracja areałowa.</p>
    <p class="dopisek">Radar odpowiada za {pl(s1s2['waznosc_radaru'] * 100, 0)}% ważności cech.
    Jego przewaga to <b>zero pustych okien</b> wobec ośmiu u optyki —
    w pierwszej połowie stycznia 100% punktów nad Lubelszczyzną nie ma ani
    jednej bezchmurnej sceny.</p>
  </article>

  <article class="karta">
    <h3>2. Model termiczny GDD — kiedy pełnia kwitnienia</h3>
    <p class="status-ok">W użyciu · kalendarz, prognoza, mikroserwis</p>
    <p class="do-czego">Pytanie: <b>którego dnia pole jest najżółtsze?</b>
    Nie klasyfikuje pikseli, więc nie ma F1. Suma temperatur efektywnych
    <b>od 15 marca</b> (baza {pl(m_fen['baza'], 1)}&nbsp;°C) do progu
    {pl(m_fen['prog'], 0)}. Pola do pomiaru NDYI wskazał klasyfikator
    przedkwitnieniowy, żeby data nie była cyrkularna.</p>
    <div class="przewijak"><table>
      <caption>{m_fen['n']} obserwacji z {m_fen['obszarow']} obszarów i 9 sezonów</caption>
      <thead><tr><th scope="col">metryka</th><th scope="col">wynik</th></tr></thead>
      <tbody>
        <tr><th scope="row">RMSE (walidacja krzyżowa)</th><td class="mocne">{pl(m_fen['rmse'], 2)} dnia</td></tr>
        <tr><th scope="row">RMSE dopasowania</th><td>{pl(m_fen['rmse_dopasowania'], 2)} dnia</td></tr>
        <tr><th scope="row">zawsze średnia data (odniesienie)</th><td>{pl(odn['stala'],1)} dnia</td></tr>
        <tr><th scope="row">jak rok temu (odniesienie)</th><td>{pl(odn['persystencja'],1)} dnia</td></tr>
      </tbody>
    </table></div>
    <p class="dopisek">Walidacja <b>leave-one-out</b>: parametry dobierane bez
    ocenianej obserwacji, więc model nie jest sprawdzany na danych, które go
    stworzyły. Wynik <b>{pl(m_fen['rmse'], 1)}&nbsp;dnia</b> zmniejsza błąd
    ponad dwukrotnie wobec odniesienia „zawsze średnia data”
    ({pl(odn['stala'],1)}).</p>
    <p class="dopisek"><b>Próbę rozszerzono z 7 na 19 obszarów</b> właśnie po
    to, żeby sprawdzić, czy wynik nie jest artefaktem doboru miejsc. Nie jest:
    na trzykrotnie większym zbiorze błąd wyszedł ten sam, a przeszukanie
    siatki wskazało <b>te same parametry</b>. Temperatury z ERA5; wobec stacji
    IMGW Zamość RMSE {pl(imgw['rmse_K'],2)}&nbsp;K, r = {pl(imgw['r'],3)}.</p>
  </article>

  <article class="karta">
    <h3>3. Klasyfikator przedkwitnieniowy — tylko jesień i marzec</h3>
    <p class="status-ok">W użyciu · kalibracja GDD, bez ryzyka cyrkularności</p>
    <p class="do-czego">Pytanie: <b>gdzie będzie rzepak, zanim zakwitnie?</b>
    Te same etykiety, ale okna wyłącznie sprzed kwitnienia. Dzięki temu data
    pełni nie jest uczona na tym, co sama mierzy.</p>
    <div class="przewijak"><table>
      <caption>Ile skuteczności zostaje przy obcięciu cech do dnia decyzji</caption>
      <thead><tr><th scope="col">dane do</th><th scope="col">wyprzedzenie</th>
        <th scope="col">F1 rzepaku</th></tr></thead>
      <tbody>
        <tr><th scope="row">grudnia</th><td>~5 miesięcy</td><td>0,826</td></tr>
        <tr><th scope="row">lutego</th><td>~10 tygodni</td><td>0,840</td></tr>
        <tr><th scope="row">marca</th><td>~6 tygodni</td><td class="mocne">0,869</td></tr>
        <tr><th scope="row">cały sezon</th><td>po fakcie</td><td>0,939</td></tr>
      </tbody>
    </table></div>
    <p class="dopisek">Wynik uboczny, ale istotny: na koniec marca rzepak
    rozpoznaje się z <b>93% skuteczności pełnego modelu, sześć tygodni przed
    kwitnieniem</b>. Otwiera to drogę do prognozowania także <em>lokalizacji</em>,
    a nie tylko terminu — dziś projekt tego nie robi.</p>
  </article>

  <article class="karta zastapiony">
    <h3>4. Wcześniejsze modele — zastąpione</h3>
    <p class="status-no">Poza użyciem · zostawione dla porządku</p>
    <p class="do-czego"><b>Klasyfikator rzepaku na 8 cechach Sentinel-2</b>
    (F1 {pl(kl['przestrzenna']['f1'])}) rysował pierwotną mapę satelitarną.
    Zastąpił go klasyfikator wielogatunkowy, który rozpoznaje trzy gatunki
    zamiast jednego i korzysta także z radaru.</p>
    <p class="do-czego"><b>Osobny klasyfikator fasoli</b> — F1
    {pl(fas['przestrzenna']['f1'])}, odrzucony. Późniejszy model
    wielogatunkowy rozpoznaje fasolę z F1&nbsp;0,922, więc problemem był
    <em>sposób postawienia zadania</em> (binarny model na rzadkiej klasie),
    a nie sam gatunek. Do mapy fasola i tak wchodzi z deklaracji, bo dla niej
    pamięć „rosło tam rok temu” (0,949) bije detekcję (0,880).</p>
    <p class="dopisek">Oba zostawiono w dokumentacji, bo pokazują, <b>skąd
    wzięła się obecna konstrukcja</b> — a wynik negatywny bywa równie
    informatywny co dodatni.</p>
  </article>
</section>

<section id="dane">
  <span class="etap">2 · skąd liczby</span>
  <div class="kolumna"><h2>Jakie źródła weszły do modelu</h2>
  <p>Każda liczba ma klasę: <b>A</b> pomiar / rejestr, <b>B</b> kompilacja
  branżowa albo mapa referencyjna, <b>C</b> założenie własne. Nie po to,
  by ukryć luki — żeby było widać, co jest daną, a co konstrukcją.</p></div>
  <div class="przewijak"><table>
    <caption>Dane wejściowe. To nie są wyniki — to surowiec.</caption>
    <thead><tr><th scope="col">źródło</th><th scope="col">co z niego bierzemy</th>
    <th scope="col">zakres</th><th scope="col">klasa</th></tr></thead>
    <tbody>
      <tr><th scope="row">ARiMR GSA</th>
        <td style="text-align:left;white-space:normal">działki i gatunki (rolnik zgłasza, co posiał). Etykiety treningu i pełna mapa 13 pożytków.</td>
        <td>2025, 2026 — tylko te dwa roczniki są publikowane</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">Sentinel-2</th>
        <td style="text-align:left;white-space:normal">zdjęcia: NDYI (żółtość) i NDVI (zieloność). Klasyfikator rzepaku i daty pełni.</td>
        <td>2018–2026</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">ERA5 / Open-Meteo</th>
        <td style="text-align:left;white-space:normal">Tmax, Tmin dobowe → GDD. Województwo: 63 punkty co 25&nbsp;km.</td>
        <td>2000–2026</td>
        <td class="zr-B">B</td></tr>
      <tr><th scope="row">IMGW Zamość 595</th>
        <td style="text-align:left;white-space:normal">kontrola, czy ERA5 wystarcza. Nie wchodzi do mapy, tylko do walidacji.</td>
        <td>2018–2025, II–V</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">ESA WorldCover 2021</th>
        <td style="text-align:left;white-space:normal">maska gruntów ornych (klasa 40) przy klasyfikatorze. Łąk (klasa 30) nie ma na kalendarzu satelitarnym.</td>
        <td>jeden rok, ~76% dokładności globalnie</td>
        <td class="zr-B">B</td></tr>
      <tr><th scope="row">EUCROPMAP (JRC)</th>
        <td style="text-align:left;white-space:normal">niezależna mapa rzepaku (klasa 232) do sprawdzenia, czy detekcja trzyma się latami.</td>
        <td>2018 i 2022; rzepak ~80%</td>
        <td class="zr-B">B</td></tr>
      <tr><th scope="row">Pasieka / Kołtowski</th>
        <td style="text-align:left;white-space:normal">kg cukrów/ha dla rzepaku (Puławy) i fasoli wielokwiatowej.</td>
        <td>pomiary polowe</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">polskieule, KPODR</th>
        <td style="text-align:left;white-space:normal">kg miodu/ha dla gryki, maliny, łąk itd. W modelu dzielone przez 1,25 → cukry.</td>
        <td>tabele branżowe</td>
        <td class="zr-B">B</td></tr>
    </tbody>
  </table></div>
  <div class="przewijak"><table>
    <caption>Parametry modelu — skąd stałe, nie z satelity</caption>
    <thead><tr><th scope="col">parametr</th><th scope="col">wartość</th>
    <th scope="col">skąd</th><th scope="col">klasa</th></tr></thead>
    <tbody>
      <tr><th scope="row">baza i próg GDD rzepaku</th>
        <td>1,5&nbsp;°C od 15 III, próg 430</td>
        <td style="text-align:left;white-space:normal">siatka baza×próg na 145 datach pełni z Sentinela (19 obszarów, 9 sezonów);
        start akumulacji „od wznowienia wegetacji" — przesunięcie z 1 II na 15 III poprawiło błąd z 3,9 na 3,2&nbsp;dnia.
        Próg 430 mieści się w podawanym w literaturze zakresie 400–500&nbsp;°C, choć wyprowadzono go niezależnie, z satelity</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">okno kwitnienia rzepaku</th>
        <td>−{int(fen.get('ksztalt_kwitnienia',{}).get('przed_pelnia',10))} / +{int(fen.get('ksztalt_kwitnienia',{}).get('po_pelni',12))} dni od pełni</td>
        <td style="text-align:left;white-space:normal">mediana połowy szczytu NDYI 2018–2026
        (n={fen.get('ksztalt_kwitnienia',{}).get('n_przed','?')} przed,
        n={fen.get('ksztalt_kwitnienia',{}).get('n_po','?')} po);
        lata bez przelotu na ramieniu odpadają. Puławy ~20 dni.</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">λ i zasięg lotu</th>
        <td>sezonowo: wiosna 294&nbsp;m / 1178&nbsp;m,<br>lato 1285&nbsp;m / 5142&nbsp;m</td>
        <td style="text-align:left;white-space:normal">λ dobrane <b>numerycznie</b>, żeby średni ważony dystans jądra
        równał się zmierzonemu (Couvillon i in. 2014, odczyt 5&nbsp;tys. tańców:
        wiosna 493&nbsp;m, lato 2156&nbsp;m). Jądra <b>znormalizowane</b> — bez tego
        hektar pożytku letniego liczył się 19× mocniej niż wiosennego, a mapy
        różniły się korelacją 0,612 i tylko 37% wspólnych najlepszych miejsc</td>
        <td class="zr-A">A</td></tr>
      <tr><th scope="row">kształt cukru w oknie</th>
        <td>trójkąt (narastanie–pełnia–spadek)</td>
        <td style="text-align:left;white-space:normal">założenie — nie ma pomiaru, jak nektar rozkłada się dzień po dniu</td>
        <td class="zr-C">C</td></tr>
      <tr><th scope="row">GDD sadu (jabłoń)</th>
        <td>baza 5&nbsp;°C od 1 I, próg {pl(sad['prog'],0)}</td>
        <td style="text-align:left;white-space:normal">baza z literatury sadowniczej; próg tak, by mediana wypadała 5 V. Bez zdjęć pełni.</td>
        <td class="zr-B">B</td></tr>
      <tr><th scope="row">loty pszczół (tylko pilotaż)</th>
        <td>T≥10&nbsp;°C (optimum 20), wiatr &lt;<b>4,2&nbsp;m/s</b>, bez opadu, dzień</td>
        <td style="text-align:left;white-space:normal">progi termiczne: <b>Woyke (2003)</b> — przy 10&nbsp;°C zaczyna się
        zbieranie pokarmu, liczba zbieraczek rośnie dziesięciokrotnie przy 12&nbsp;°C.
        Próg wiatru i metoda ważenia godzin: <b>BEEHAVE</b> (Becher i in. 2014),
        kanoniczny model rodziny pszczelej — godzinowa pogoda → godziny lotne wg
        progów → agregacja dobowa.
        <b>Poprawka:</b> pierwotnie stało tu 8,3&nbsp;m/s z opracowań wtórnych,
        czyli dwukrotnie liberalniej niż w modelu źródłowym; po zmianie średnia
        sprawność lotna sezonu 2025 spadła z 0,390 na 0,370.
        Drobna rozbieżność: BEEHAVE podaje optimum jako plateau 20–30&nbsp;°C,
        u nas jest to punkt 20&nbsp;°C z opadaniem powyżej.</td>
        <td class="zr-B">B</td></tr>
    </tbody>
  </table></div>
</section>

<section id="mapa">
  <span class="etap">3 · mapa</span>
  <div class="kolumna"><h2>Jak liczona jest mapa potencjału</h2>
  <p>Każdy piksel: <b>ile cukrów pszczoła dosięgnie, jeśli ul stoi tutaj</b>.
  Trzy kroki, zawsze w tej kolejności.</p>
  <ol>
    <li><b>Gdzie.</b> Raster 100&nbsp;m (1&nbsp;px = 1&nbsp;ha).
    <em>Rolnicy:</em> wszystkie gatunki z GSA 2025 i 2026.
    <em>Satelita:</em> tylko rzepak z klasyfikatora 2019–2025.
    Te dwie mapy nie są mieszane — deklaracje mają pełny skład, ale dwa lata;
    satelita ma siedem lat rzepaku, bez łąk i bez reszty gatunków.</li>
    <li><b>Kiedy.</b> Cukier rozkładany trójkątnie od startu przez pełnię do końca.
    Rzepak: pełnia z GDD, okno −{int(fen.get('ksztalt_kwitnienia',{}).get('przed_pelnia',10))} / +{int(fen.get('ksztalt_kwitnienia',{}).get('po_pelni',12))}. Sad: osobne GDD. Reszta: sztywne daty
    z tabeli — dnia siewu jarów nie znamy.</li>
    <li><b>Zasięg.</b> Splot z jądrem <code>exp(−d / λ)</code>,
    <b>zmiennym sezonowo</b> — zmierzone dystanse lotu różnią się
    czterokrotnie między wiosną a latem (Couvillon i in. 2014: 493&nbsp;m /
    2156&nbsp;m). Jądro wiosenne ma zasięg 1178&nbsp;m, letnie 5142&nbsp;m.
    Każde jest <b>znormalizowane</b>, żeby szersze jądro nie dostawało
    premii za samą szerokość. Wynik w tonach cukrów w nektarze.</li>
  </ol>
  </div>
  <div class="wzor">C(x) = Σ uprawa  udział(x) × kg cukrów/ha × waga dnia
P(x) = Σ<sub>y: d(x,y) ≤ R(pora)</sub>  C(y) · K(d(x,y), pora)

K(d, pora) = exp(−d / λ) / Σ exp(−d / λ)  ×  502,89
wiosna: λ = 294 m, R = 1178 m     lato: λ = 1285 m, R = 5142 m</div>
  <figure class="mapa-hero"><img src="{mapy['woj']}" alt="Mapa potencjału województwa"/>
    <figcaption><b>Co widać.</b> Potencjał sezonowy z deklaracji ARiMR.
    Czerwień = więcej cukrów w zasięgu lotu. Mediana województwa
    {pl(woj['percentyle_t']['50'],1)}&nbsp;t, maksimum
    {pl(woj['percentyle_t']['100'],1)}&nbsp;t. Źródło warstwy upraw: GSA 2025.</figcaption></figure>
  <div class="kolumna" style="margin-top:28px"><h3>Kalendarz w jednym miejscu</h3>
  <p>Poniżej bufor 10&nbsp;km wokół Hrubieszowa — ten sam wzór, mniejszy obszar,
  żeby było widać przebieg sezonu. Niebieski = cały rok, pomarańcz = sam rzepak,
  zielony = po rzepaku (fasola, gryka, łąki).</p></div>
  <figure class="plansza">{wykres_kalendarz(pot)}
    <figcaption><b>Co widać.</b> Oś pozioma: dekady od kwietnia do września.
    Oś pionowa: tony cukrów w zasięgu lotu z tego jednego punktu.
    Wiosna = rzepak, potem przerwa, lato = fasola. Na województwie mechanizm
    ten sam, inne proporcje gatunków.</figcaption></figure>
</section>

<section id="rosliny">
  <span class="etap">4 · rośliny</span>
  <div class="kolumna"><h2>Wydajności i terminy — skąd każda liczba</h2>
  <p>Jednostka: <b>kg cukrów w nektarze na hektar</b>, nie kg miodu.
  Tabele branżowe podają miód; tu dzielone przez 1,25 (miód ≈ 80% cukrów).
  Areał w tys. ha: deklaracje ARiMR, całe województwo, 2025.</p>
  <p>W szczycie sezonu ~78% cukru to rzepak i ~15% fasola — oba z badań (A).
  Reszta to tabele (B). TUZ (łąki) nie jest gatunkiem: 32&nbsp;kg to rząd
  wielkości, okno V–VIII to założenie (C).</p></div>
  <div class="przewijak"><table>
    <caption>Dokumentacja upraw. Klasa A = pomiar, B = tabela miodowa / 1,25, C = założenie</caption>
    <thead><tr><th scope="col">uprawa</th><th scope="col">tys. ha</th>
    <th scope="col">kg cukrów/ha</th><th scope="col">kwitnienie</th>
    <th scope="col">klasa</th><th scope="col">źródło</th></tr></thead>
    <tbody>{tab_rosl}</tbody>
  </table></div>
</section>

<section id="satelita">
  <span class="etap">5 · satelita</span>
  <div class="kolumna"><h2>Jak na zdjęciu widać, że to rzepak i że kwitnie</h2>
  <p>Satelita nie „widzi ula”. Liczy dwa indeksy z pasm Sentinel-2.
  Wykresy poniżej: sezon {rok}, średnia z pikseli o znanym gatunku
  (deklaracje). To podpis, na którym stoi klasyfikator i data pełni do GDD.</p>
  <p><b>Jak czytać wykres.</b> Poziomo: data przelotu. Pionowo: wartość indeksu
  (stosunek pasm, bez jednostki). Pomarańczowy pas: okno kwitnienia rzepaku.
  Pomarańcz z kropkami = rzepak. Szare = pszenica, jęczmień, żyto, kukurydza, łąki.
  Niebieska kreska = las (kontrola: czy skok nie zdarza się też drzewom).</p></div>
  <div class="przewijak"><table>
    <caption>Trzy narzędzia po drodze — żadne nie jest mapą ula</caption>
    <thead><tr><th scope="col">nazwa</th><th scope="col">co to jest</th>
    <th scope="col">skąd</th><th scope="col">co z tego</th></tr></thead>
    <tbody>
      <tr><th scope="row">NDYI</th>
        <td style="text-align:left;white-space:normal">żółtość: (zielony − niebieski) / suma</td>
        <td>Sentinel-2, pasma B3 i B2</td>
        <td style="text-align:left;white-space:normal">szczyt na polu = pełnia. Cecha klasyfikatora i data do kalibracji progu.</td></tr>
      <tr><th scope="row">NDVI</th>
        <td style="text-align:left;white-space:normal">zieloność: (NIR − czerwony) / suma</td>
        <td>Sentinel-2, pasma NIR i czerwone</td>
        <td style="text-align:left;white-space:normal">przy kwitnieniu rzepaku spada (płatki zasłaniają liście). Druga noga podpisu.</td></tr>
      <tr><th scope="row">GDD</th>
        <td style="text-align:left;white-space:normal">suma ciepła, nie zdjęcie</td>
        <td>ERA5, baza 1,5&nbsp;°C od 15 III</td>
        <td style="text-align:left;white-space:normal">licznik = 430 → pełnia. Zdjęcia uczą progu, potem wystarcza sam termometr.</td></tr>
    </tbody>
  </table></div>
  <figure class="plansza">{wykres_profil(prof['wiersze'], "NDYI", .05, .45, rok, (135,145),
      "1. Żółtość (NDYI) — tu widać kwiaty",
      "NDYI  ·  im wyżej, tym bardziej żółto",
      "pełnia: pole najżółtsze")}
    <figcaption><b>Wniosek.</b> W oknie kwitnienia rzepak wychodzi ponad zboża —
    stąd dzień pełni. Las też skacze (liście w maju). Bez maski gruntów ornych
    maksimum NDYI wskazałoby las, nie pole.</figcaption></figure>
  <figure class="plansza">{wykres_profil(prof['wiersze'], "NDVI", .25, .95, rok, (135,145),
      "2. Zieloność (NDVI) — tu widać, że to kwiaty, nie liście",
      "NDVI  ·  im wyżej, tym bardziej zielono",
      "dołek: płatki zasłaniają liście")}
    <figcaption><b>Wniosek.</b> W dacie szczytu NDYI rzepak ma dołek NDVI.
    Zboża i las dalej się zielenią. Sama żółtość mogłaby być liśćmi, sam spadek
    zieleni — suszą. Razem = kwitnienie. Klasyfikator używa obu.</figcaption></figure>
  <div class="uwaga kolumna">
    <p>Progu na surowym NDYI nie ma: każda zieleń ma ~0,2–0,3. Liczy się
    nadwyżka wobec innych pól z tego samego dnia. Datę pełni bierze parabola
    przez trzy najwyższe punkty — satelita nie lata codziennie.</p>
  </div>
</section>

<section id="gdd">
  <span class="etap">6 · GDD i zgodność map</span>
  <div class="kolumna"><h2>Data kwitnienia i czy mapy mówią to samo</h2>
  <p>Tabele F1 i dokładności są na górze (<a href="#jakosc">jakość modeli</a>).
  Tu reszta: korelacja warstw i błąd daty pełni.</p>
  <h3>Zgodność map — czy warstwy mówią to samo</h3>
  <p>Po rozmyciu jądrem zasięgu lotu (tak, jak widzi pszczoła). Korelacja r:
  1 = identyczne mapy. EUCROPMAP ma ~80% dla rzepaku, więc r z tą mapą
  to dolne oszacowanie.</p></div>
  <div class="przewijak"><table>
    <caption>r po splocie jądrem zasięgu lotu</caption>
    <thead><tr><th scope="col">porównanie</th><th scope="col">r</th>
    <th scope="col">co to sprawdza</th></tr></thead>
    <tbody>
      <tr><th scope="row">detekcja 2025 ↔ GSA 2025</th>
        <td class="mocne">{pl(sr['walidacje']['det2025_vs_gsa2025'])}</td>
        <td style="text-align:left;white-space:normal">czy klasyfikator zgadza się z rolnikiem w tym samym roku</td></tr>
      <tr><th scope="row">detekcja 2022 ↔ EUCROPMAP 2022</th>
        <td class="mocne">{pl(sr['walidacje']['det2022_vs_eucropmap2022'])}</td>
        <td style="text-align:left;white-space:normal">czy zgadza się z niezależną mapą UE</td></tr>
      <tr><th scope="row">GSA 2025 ↔ GSA 2026</th>
        <td>{pl(stab['korelacje']['2025 GSA vs 2026 GSA'])}</td>
        <td style="text-align:left;white-space:normal">czy rejon rzepakowy stoi w miejscu</td></tr>
      <tr><th scope="row">EUCROPMAP 2018 ↔ GSA 2026</th>
        <td>{pl(stab['korelacje']['2018 EUCROPMAP vs 2026 GSA'])}</td>
        <td style="text-align:left;white-space:normal">stabilność na 8 lat</td></tr>
      <tr><th scope="row">stara mapa rzepak+łąki ↔ deklaracje</th>
        <td>{pl(tel['korelacja_pelna'])}</td>
        <td style="text-align:left;white-space:normal">test z WorldCover 2021; łąki idą z deklaracji, bo dla upraw trwałych pamięć bije detekcję</td></tr>
      <tr><th scope="row">potencjał GSA 2025 ↔ 2026</th>
        <td class="mocne">{pl(sez['korelacja'])}</td>
        <td style="text-align:left;white-space:normal">cała mapa cukru, nie sam rzepak. Top-10% wraca w {pl(100*sez['top10_zgoda'],0)}%</td></tr>
    </tbody>
  </table></div>

  <div class="kolumna"><h3>GDD — czy temperatura przewiduje dzień pełni</h3>
  <p>Pomarańcz na wykresie: dzień, w którym pole było najżółtsze (NDYI).
  Niebieski: dzień, w którym suma GDD doszła do progu. Pionowa kreska = błąd.
  Przerywana linia: gdyby co rok wpisywać średnią datę — to model ma bić.</p></div>
  <figure class="plansza">{wykres_fenologia(fen)}
    <figcaption><b>Obszar {gl_nazwa}.</b> Źródło „prawdy”: Sentinel-2, nie BBCH z pola.
    RMSE na 52 czystych obserwacjach z 19 obszarów: {pl(m['rmse_dni'],1)} dnia.</figcaption></figure>
  <div class="przewijak"><table>
    <caption>RMSE w dniach — niżej lepiej</caption>
    <thead><tr><th scope="col">predyktor</th><th scope="col">RMSE</th>
    <th scope="col">wobec GDD</th></tr></thead>
    <tbody>
      <tr><th scope="row">GDD (1,5&nbsp;°C, 430)</th>
        <td class="mocne">{pl(m['rmse_dni'],1)}</td><td>—</td></tr>
      <tr><th scope="row">zawsze średnia data</th>
        <td>{pl(odn['stala'],1)}</td>
        <td>{pl(odn['stala']/m['rmse_dni'],1)}× gorzej</td></tr>
      <tr><th scope="row">jak rok temu</th>
        <td>{pl(odn['persystencja'],1)}</td>
        <td>{pl(odn['persystencja']/m['rmse_dni'],1)}× gorzej</td></tr>
    </tbody>
  </table></div>
  <div class="przewijak"><table>
    <caption>Jeden wspólny próg na 115&nbsp;km z południa na północ</caption>
    <thead><tr><th scope="col">obszar</th><th scope="col">szer.</th>
    <th scope="col">n</th><th scope="col">RMSE</th><th scope="col">obciążenie</th></tr></thead>
    <tbody>{tab_obszary}</tbody>
  </table></div>
  <div class="przewijak"><table>
    <caption>Rok po roku, {gl_nazwa} — satelita vs GDD</caption>
    <thead><tr><th scope="col">rok</th><th scope="col">satelita</th>
    <th scope="col">GDD</th><th scope="col">błąd [dni]</th></tr></thead>
    <tbody>{tab_fen}</tbody>
  </table></div>
  <div class="uwaga kolumna">
    <p>Odrzucane są pojedyncze obserwacje odchylone od mediany sezonu o więcej
    niż 8&nbsp;dni — awarie odczytu krzywych NDYI. <b>Bez odrzucania RMSE
    rośnie z 3,2 na 7,1&nbsp;dnia</b>, a najgorszy przypadek z 12 na 38 dni.</p>
    <p>430 nie jest przy tym jedyną dobrą liczbą: dwanaście par
    baza&nbsp;×&nbsp;próg mieści się w 0,1 dnia od optimum, w zakresie bazy
    0,25–2,25&nbsp;°C i progu 395–510. Zagęszczanie siatki nic nie daje —
    ogranicza nas rozdzielczość danych, nie siatki.</p>
  </div>
  <div class="kolumna"><h3>Prognoza w sezonie — test, nie narzędzie</h3>
  <p>Udajemy, że stoimy np. 15 IV i znamy pogodę tylko do tego dnia,
  dalej średnią z lat. Bez live temperatur to nie działa u pszczelarza.
  Wniosek z testu: GDD bije „zawsze średnią datę” dopiero ~3 tygodnie
  przed pełnią.</p></div>
  <div class="przewijak"><table>
    <caption>Hindcast na {m_fen["n"]} obserwacjach z {m_fen["obszarow"]} obszarów</caption>
    <thead><tr><th scope="col">pytasz</th><th scope="col">dni przed pełnią</th>
    <th scope="col">RMSE</th></tr></thead>
    <tbody>
      {tab_prog}
      <tr><th scope="row">po sezonie (cała pogoda)</th><td>0</td>
        <td class="mocne">{pl(m['rmse_dni'],1)}</td></tr>
    </tbody>
  </table></div>
  <div class="kolumna"><h3>Czy ERA5 kłamie wobec stacji</h3>
  <p>Porównanie reanalizy z termometrem IMGW w Zamościu, {imgw['n_dni']} dni
  lutego–maja. Różnica terminu kwitnienia jest mniejsza niż błąd samego GDD
  (3,2 dnia w walidacji krzyżowej) — na mapę wystarcza ERA5.</p></div>
  <div class="przewijak"><table>
    <caption>ERA5 vs IMGW Zamość 595</caption>
    <thead><tr><th scope="col">miara</th><th scope="col">wartość</th></tr></thead>
    <tbody>
      <tr><th scope="row">błąd średni T</th><td>{imgw['bias_K']:+.2f} K</td></tr>
      <tr><th scope="row">RMSE dobowe T</th><td>{pl(imgw['rmse_K'],2)} K</td></tr>
      <tr><th scope="row">korelacja T</th><td>{pl(imgw['r'],3)}</td></tr>
      <tr><th scope="row">różnica daty pełni</th>
        <td>{imgw['roznica_srednia_d']:+.1f} dnia (maks. {pl(imgw['roznica_maks_d'],0)})</td></tr>
    </tbody>
  </table></div>
</section>

<section id="metoda">
  <span class="etap">6b · metoda</span>
  <div class="kolumna"><h2>Jak to policzono — krok po kroku</h2>
  <p>Ta sekcja zbiera cały łańcuch obliczeń w jednym miejscu. Każdy krok ma
  skrypt, który go odtwarza, i źródło, z którego bierze parametry.</p>
  </div>

  <h3>1 · Jądro zasięgu lotu</h3>
  <div class="kolumna">
  <p>Pszczoła nie zbiera z piksela, na którym stoi ul, tylko z otoczenia,
  ważąc bliższe pola mocniej. Waga maleje wykładniczo z odległością:</p>
  </div>
  <div class="wzor">K(d) = exp(−d / λ)   dla d ≤ R,   0 dalej</div>
  <div class="kolumna">
  <p><b>λ nie jest zgadywane.</b> Dobierane jest bisekcją tak, aby średni
  ważony dystans jądra równał się dystansowi <b>zmierzonemu</b> — Couvillon
  i in. (<i>PLOS ONE</i> 9(4), 2014) odczytali ok. 5&nbsp;tys. tańców
  pszczelich i podali średnie dystanse lotu wg pory roku. Zasięg R = 4λ
  obejmuje ~99% masy jądra.</p>
  </div>
  <table class="tab"><thead><tr><th>pora</th><th>zmierzony dystans</th>
    <th>λ</th><th>zasięg R</th></tr></thead><tbody>
    <tr><td>wiosna (rzepak)</td><td><b>493 m</b></td><td>294 m</td><td>1178 m</td></tr>
    <tr><td>lato (gryka, odrost TUZ)</td><td><b>2156 m</b></td><td>1285 m</td><td>5142 m</td></tr>
    <tr><td>jesień</td><td><b>1275 m</b></td><td>760 m</td><td>3041 m</td></tr>
  </tbody></table>
  <div class="kolumna">
  <p>Numeryka zamiast wzoru, bo dla jądra nieobciętego średnia ≈ 3λ, ale
  <b>po obcięciu ta zależność przestaje obowiązywać</b>.</p>
  <p><b>Jądra są normalizowane</b> do stałej masy. Bez tego szersze jądro
  letnie sumowało się do 943, a wiosenne do 50 — hektar pożytku letniego
  wchodził do wyniku <b>19 razy mocniej</b>, wyłącznie z geometrii. Skutek
  był mierzalny i absurdalny: rzepak (150&nbsp;626&nbsp;ha, 50,9% cukrów)
  dawał na mapie 8,8%, a gryka — jedenaście razy mniejsza powierzchniowo —
  23,5%. Po normalizacji udziały odtwarzają bilans z hektarów co do
  dziesiątej części punktu.</p>
  <p class="mniej">Ograniczenie: badanie prowadzono w Anglii (Sussex).
  Brak analogicznych pomiarów dla Polski jest ograniczeniem modelu.</p>
  </div>

  <h3>2 · Od upraw do potencjału</h3>
  <div class="wzor">C(x) = Σ<sub>uprawa</sub>  udział(x) × kg cukrów/ha × waga dnia
P(x) = Σ<sub>y</sub>  C(y) · K(d(x,y), pora)</div>
  <div class="kolumna">
  <p>Splot liczony przez FFT — jądro letnie ma 103×103 piksele, a mapa
  1806×2237, więc splot bezpośredni byłby nie do policzenia. Siatka 100 m,
  rasteryzacja działek w 20 m i uśrednianie.</p>
  </div>

  <h3>3 · Kiedy kwitnie — model termiczny</h3>
  <div class="kolumna">
  <p>Suma temperatur efektywnych <b>od 15&nbsp;III</b> — czyli od wznowienia
  wegetacji, nie od daty kalendarzowej; kwitnienie w dniu, w którym
  skumulowane GDD przekracza próg:</p>
  </div>
  <div class="wzor">GDD = Σ max( (Tmax + Tmin)/2 − baza , 0 )</div>
  <div class="kolumna">
  <p>Dla rzepaku <b>baza i próg dobrane łącznie</b> na 145 obserwacjach
  z <b>19 obszarów</b> i 9 sezonów: baza 1,5&nbsp;°C, próg 430, akumulacja
  od 15&nbsp;III. Pozostałe gatunki mają bazę z literatury, a próg
  <b>zakotwiczony</b> tak, by mediana trafiała w tabelaryczną datę
  kwitnienia.</p>
  <p><b>Walidacja krzyżowa leave-one-out</b>: dla każdej obserwacji
  parametry dobierane na pozostałych, błąd liczony na odłożonej. Wynik
  <b>3,21&nbsp;dnia</b> (RMSE), błąd bezwzględny 3,2&nbsp;dnia.</p>
  <p><b>Próba rozszerzona z 7 na 19 obszarów</b> właśnie po to, by sprawdzić,
  czy wynik nie jest artefaktem doboru miejsc. Nie jest: na trzykrotnie
  większym zbiorze błąd wyszedł 3,21&nbsp;dnia wobec 3,19 wcześniej,
  a przeszukanie siatki wskazało <b>te same parametry</b> co na próbie
  pierwotnej.</p>
  <p>Odrzucane są pojedyncze obserwacje odchylone od mediany sezonu o więcej
  niż 8&nbsp;dni — to awarie odczytu krzywych NDYI. Próg wyprowadzono
  z fizyki (rozrzut modelowany między obszarami 2–5&nbsp;dni plus ok.
  3&nbsp;dni niepewności odczytu), a wynik jest na jego wybór odporny:
  3,17&nbsp;dnia przy progu 6, 3,21 przy 8. <b>Bez odrzutu 7,09&nbsp;dnia</b>,
  więc filtrowanie jest konieczne, nie kosmetyczne.</p>
  </div>

  <h3>4 · Detekcja upraw</h3>
  <div class="kolumna">
  <p>Las losowy na kompozytach półmiesięcznych od września do września.
  Cechy: <b>NDVI i NDYI jako anomalie sceny</b> (odjęta mediana pól ornych
  z tej samej sceny — usuwa wpływ oświetlenia i daty przelotu) oraz
  <b>VV, VH i VH−VV</b> w dB z Sentinela-1.</p>
  <p>Klasyfikator wytrenowano na <b>jednym sezonie (2025)</b>, bo deklaracje
  ARiMR istnieją tylko dla 2025 i 2026 — nie ma prawdy terenowej dla lat
  wcześniejszych. Zastosowano go następnie do <b>lat 2019–2025</b>.</p>
  <p>Przeniesienie modelu na inne lata jest <b>zmierzone, nie założone</b>:
  ucz&nbsp;2025 → sprawdź&nbsp;2026 daje dla rzepaku r&nbsp;=&nbsp;0,958
  wobec odniesienia „rosło tam, gdzie rok temu" = 0,338. Kalibracja
  areałowa z 2025 przeniesiona na inne lata, kontrola niezależna:
  EUCROPMAP&nbsp;2022 podaje 147&nbsp;701&nbsp;ha, model
  138&nbsp;518&nbsp;ha — <b>różnica 6%</b>.</p>
  </div>

  <h3>5 · Podział warstw — kryterium pomiarowe</h3>
  <div class="kolumna">
  <p>Do warstwy satelitarnej trafia gatunek, dla którego <b>detekcja bije
  odniesienie „rosło tam rok temu"</b>. Dla upraw trwałych jest odwrotnie —
  malina ma model 0,878 wobec pamięci 0,847, bo plantacja stoi dekadę
  w tym samym miejscu. Wstawienie tam detekcji <b>pogorszyłoby</b> mapę.</p>
  </div>
  <table class="tab"><thead><tr><th>warstwa</th><th>gatunki</th>
    <th>udział w cukrach</th></tr></thead><tbody>
    <tr><td>satelitarna</td><td>rzepak ozimy, gryka, słonecznik</td><td><b>58,8%</b></td></tr>
    <tr><td>deklaracje ARiMR</td><td>pozostałe 13, w tym oba pokosy TUZ</td><td>41,2%</td></tr>
  </tbody></table>

  <h3>6 · Z ton cukru na rodziny</h3>
  <div class="wzor">pojemność = cukier w zasięgu lotu / 72 kg na rodzinę</div>
  <div class="kolumna">
  <p>72 kg cukrów = 90 kg miodu rocznie ÷ 1,25. <b>Jest to dzielenie przez
  stałą</b>, więc nie zmienia obrazu mapy ani kolejności miejsc — daje
  wyłącznie liczbę, którą pszczelarz umie porównać ze swoim stanem
  posiadania. Nasycenie wprowadza dopiero bilans dekadowy, gdzie podaż
  zestawiana jest z zapotrzebowaniem w danym okresie.</p>
  </div>

  <h3>7 · Od mapy do współrzędnych</h3>
  <div class="kolumna">
  <p>Maksima lokalne pola potencjału, rozdzielone o 8 km, żeby rekomendacje
  opisywały rozłączne obszary. Dla każdego liczony <b>promień
  równoważności</b> — do jakiej odległości potencjał trzyma się powyżej
  95 / 90 / 80% maksimum.</p>
  <p>Mediany: <b>100 m</b> (próg 5%), 200 m (10%), 300 m (20%). Wynik
  <b>obala wcześniejsze założenie</b>, że pole potencjału jest w skali
  stu metrów płaskie — nie jest, mimo splotu jądrem o zasięgu 1178 m.
  Mapa 100 m niesie więc informację o wyborze <b>miejsca</b>, a nie tylko
  rejonu.</p>
  </div>
</section>

<section id="miejsca">
  <span class="etap">7 · wynik</span>
  <div class="kolumna"><h2>Najlepsze miejsca — wynik końcowy</h2>
  <p>Maksima lokalne mapy pojemności, rozdzielone o 8&nbsp;km, żeby opisywały
  rozłączne obszary pożytkowe. Dla każdego liczony <b>promień
  równoważności</b> — jak daleko można się odsunąć, tracąc mniej niż 5, 10
  i 20% pożytku.</p>
  <p class="dopisek">Liczba rodzin = ile rodzin pszczelich wyżywi pożytek
  w zasięgu lotu z tego punktu, przy zapotrzebowaniu 72&nbsp;kg cukrów na
  rodzinę. Mediana województwa to {mediana_rodzin} rodzin.</p>
  </div>
  <div class="przewijak"><table>
    <caption>12 lokalizacji o najwyższej pojemności, przeciętny rok z 7 sezonów</caption>
    <thead><tr><th scope="col">#</th><th scope="col">rodzin</th>
      <th scope="col">−5%</th><th scope="col">−10%</th><th scope="col">−20%</th>
      <th scope="col">szerokość</th><th scope="col">długość</th></tr></thead>
    <tbody>{wiersze_miejsc}</tbody>
  </table></div>
  <figure class="mapa-hero"><img src="{mapy_miejsce1}" alt="Mapa miejsca nr 1"/>
    <figcaption><b>Miejsce nr 1 z bliska.</b> Wycinek 3&nbsp;km: kolor to
    potencjał, linie to granice działek ARiMR, okręgi to promienie
    równoważności. Widać, że czołówkę robią tu <b>sady i krzewy jagodowe</b>
    — malina, jabłoń, porzeczka — a nie rzepak, którego jest w tym wycinku
    ledwie 74&nbsp;ha. Gdyby projekt stał wyłącznie na detekcji satelitarnej,
    przegapiłby najlepsze miejsce w województwie.</figcaption></figure>
  <div class="kolumna">
  <p><b>Jak to czytać w terenie.</b> Wewnątrz promienia równoważności mapa nie
  rozstrzyga — o wyborze decyduje dojazd, osłona od wiatru i dostęp do wody.
  Mediana promienia przy progu 5% wynosi 100&nbsp;m, przy 20% — 300&nbsp;m.</p>
  <p>Wynik ten <b>obala wcześniejsze założenie</b>, że pole potencjału jest
  w skali stu metrów płaskie. Nie jest: przesunięcie o 100&nbsp;m potrafi
  kosztować ponad 5% pożytku, bo waga sąsiedniego pola spada wtedy o 29%.
  Mapa w rozdzielczości 100&nbsp;m niesie więc informację o wyborze
  <b>miejsca</b>, a nie tylko rejonu.</p>
  </div>
</section>

<section id="produkty">
  <span class="etap">7 · produkty</span>
  <div class="kolumna"><h2>Co powstało i czego nie ma</h2>
  <ul>
    <li><b>kalendarz.html</b> — trzy warstwy: rolnicy (wszystkie uprawy,
    2025/26), satelita (3 gatunki wędrujące, 2019–2025) i <b>produkt
    końcowy</b> składający jedno z drugim. Suwak co 5 dni, przełącznik
    jednostki tony&nbsp;/&nbsp;rodziny.</li>
    <li><b>Mapy województwa</b> — potencjał sezonowy, przeciętny rok,
    niezawodność (ile z 7 sezonów miejsce było w top 20%).</li>
    <li><b>Lista najlepszych miejsc</b> — współrzędne z promieniem
    równoważności oraz mapy lokalne 3&nbsp;km z granicami działek ARiMR.</li>
    <li><b>Lotność</b> — tylko bufor pilotażowy. W 2025 pogoda zabrała ~61%
    potencjału. Na całe województwo nie ma siatki godzinowej.</li>
  </ul>
  <p><b>Nie ma:</b> walidacji zbiorem miodu z pasiek (największa dziura),
  konkurencji pasiek, GDD dla upraw jarych (nieznana data siewu),
  <b>prognozy lokalizacji</b> — model przewiduje termin kwitnienia, ale nie
  to, gdzie rzepak stanie w przyszłym sezonie — oraz działającego
  mikroserwisu (model jest, API nie).</p></div>
  <figure class="mapa-hero"><img src="{mapy['sredni']}" alt="Przeciętny rok i niezawodność"/>
    <figcaption><b>Przeciętny rok i niezawodność.</b> Lewa: średni potencjał
    (rzepak z wielu sezonów + reszta ze średniej GSA). Prawa: w ilu latach
    miejsce było w najlepszych 20% rzepaku — definicja własna, nie norma branżowa.</figcaption></figure>
</section>

<section id="uwaga">
  <span class="etap">8 · granice</span>
  <div class="kolumna"><h2>Na co uważać i co kiedyś</h2>
  <p>Kalendarz i ten raport to model badawczy plus narzędzie. To jeszcze nie
  jest decyzja „stawiaj tu ul” — i nie przez brak kolejnego klasyfikatora.</p>

  <h3>Na co uważać przy odczycie</h3>
  <ul>
    <li>Liczba to <b>cukier w nektarze w zasięgu lotu</b>, nie kilogramy
    miodu. Model nie zna siły rodziny, konkurencji pasiek ani zgody
    właściciela na ustawienie ula.</li>
    <li>Przeliczenie na <b>rodziny</b> (÷72 kg cukrów) to dzielenie przez
    stałą — daje liczbę porównywalną ze stanem posiadania, ale <b>nie zmienia
    mapy ani kolejności miejsc</b>. Nie wprowadza nasycenia, wbrew temu, co
    zapisano we wcześniejszej wersji.</li>
    <li>Trzy warstwy to nie to samo. <b>Rolnicy:</b> wszystkie gatunki, ale
    tylko 2025 i 2026. <b>Satelita:</b> siedem sezonów, ale wyłącznie trzy
    gatunki wędrujące (rzepak, gryka, słonecznik). <b>Produkt końcowy:</b>
    złożenie — każdy gatunek z tego źródła, które dla niego wygrało w teście
    przenoszenia.</li>
    <li>Klasyfikator wytrenowano na <b>jednym sezonie (2025)</b>, bo tylko
    dla niego istnieją deklaracje jako prawda terenowa. Zastosowanie go do
    lat 2019–2025 jest uzasadnione <b>zmierzonym</b> przenoszeniem, a nie
    założeniem.</li>
    <li><b>Przewaga detekcji nad pamięcią zależy od pytania.</b> Odniesienie
    „rosło tam rok temu" daje 0,338 dla <em>konkretnej działki</em> — rzepak
    wraca na to samo pole co 3–4 lata. Ale produktem jest <em>mapa gęstości
    po splocie</em>, a ta jest stabilna: deklaracje 2025 wobec 2026 korelują
    <b>0,795</b>. Detekcja podnosi to do 0,991, więc poprawa jest realna, ale
    <b>nie trzykrotna</b> — trzykrotna dotyczy poziomu działek. Detekcja
    pozostaje niezbędna z innego powodu: dla lat 2019–2024 deklaracji
    po prostu nie ma.</li>
    <li><b>Areałów rocznych gatunków innych niż rzepak nie wolno czytać jako
    zmian w rolnictwie.</b> Malina to krzew wieloletni, a wykryty areał skacze
    15-krotnie między latami — to szum klasyfikacji. Wiarygodna jest seria
    rzepaku (zmienność 5%, kontrola EUCROPMAP −6%) oraz przeciętny rok
    i warstwa niezawodności.</li>
    <li>Pas przy granicy województwa jest zaniżony: pszczoła dosięgnie pól
    po drugiej stronie, model ich nie widzi.</li>
    <li>„Niezawodność” = w ilu sezonach z 7 miejsce było w najlepszych 20%.
    Dotyczy <b>warstwy wędrującej</b> (z detekcji) — dla łąk i sadów
    z deklaracji ta miara nie ma sensu. Definicja własna, nie norma.</li>
    <li>Model fenologiczny trafia w <b>żółty szczyt NDYI z Sentinela</b>, nie
    w skalę BBCH agronoma przy krzaku. Błąd <b>3,21&nbsp;dnia</b> (walidacja
    krzyżowa leave-one-out, <b>145 obserwacji z 19 obszarów</b> i 9 sezonów).</li>
    <li><b>Odrzucane są pojedyncze obserwacje</b> odchylone od mediany sezonu
    o więcej niż 8&nbsp;dni — awarie odczytu krzywych NDYI, nie zmienność
    zjawiska. Próg wyprowadzono z fizyki: model przewiduje między obszarami
    rozrzut 2–5&nbsp;dni, do czego dochodzi ok. 3&nbsp;dni niepewności odczytu.
    Wynik jest na ten wybór odporny (3,17&nbsp;dnia przy progu 6, 3,21 przy 8),
    ale <b>bez odrzutu rośnie do 7,09&nbsp;dnia</b>, a najgorszy przypadek
    z 12 na 38 dni.</li>
    <li><b>Próbę rozszerzono z 7 na 19 obszarów</b>, żeby sprawdzić, czy błąd
    nie jest artefaktem doboru miejsc. Nie jest — na trzykrotnie większym
    zbiorze wyszedł ten sam, a przeszukanie siatki wskazało te same parametry.</li>
    <li><b>Trójkątny kształt kwitnienia</b> w obrębie okna pozostaje
    założeniem. Szerokość okna rzepaku jest zmierzona z wielu lat NDYI, ale
    liniowy narost i spadek w środku — nie.</li>
    <li><b>Podstawa wydajności ujednolicona.</b> Wszystkie gatunki stoją na
    tabelach branżowych przeliczonych ÷1,25 z kg miodu na kg cukrów. Rzepak
    przeniesiono z podstawy produkcyjnej (115) na tabelaryczną (88), bo
    mieszanie dwóch różnych wielkości zawyżało go o ~30% względem reszty.
    Badanie z Puław służy teraz za <b>walidację</b>, nie za źródło.</li>
    <li><b>Zasięg lotu pochodzi z badania brytyjskiego</b> (Couvillon i in.
    2014, Sussex). Brak analogicznych pomiarów dla Polski jest ograniczeniem
    modelu. Sam <b>kształt</b> jądra jest natomiast nieszkodliwy: trzy różne
    postacie funkcji spadku, skalibrowane do tej samej zmierzonej średniej,
    dają mapy o korelacji ≥&nbsp;0,997 i ≥&nbsp;93% wspólnych najlepszych
    miejsc.</li>
    <li><b>Wartość pożytkowa łąk (TUZ) to najsłabsza liczba w modelu</b> —
    21,4% cukrów opiera się na wartości, której nie da się uściślić, bo skład
    runi różni się między działkami. Zmierzono jednak skutek: przy zmianie
    z 32 na 6 kg cukrów/ha korelacja mapy pozostaje 0,966, a 93% najlepszych
    miejsc się nie zmienia.</li>
    <li><b>Sprawdzian wobec GUS daje przedział, nie liczbę.</b> Tabele
    branżowe nie rozstrzygają, czy podana wydajność to produkcja hektara, czy
    realny odbiór — więc mapa daje 6,5–20,8 tys. ton miodu. Scenariusz pasiek
    zawodowych (10,4) mieści się w tym przedziale, scenariusz wszystkich
    rodzin (23,2) leży 11% nad górnym końcem.</li>
  </ul>

  <h3>Czego bym teraz nie robił</h3>
  <ul>
    <li><b>Nie dokładać kolejnych gatunków do warstwy satelitarnej.</b> Nie
    dlatego, że się nie da — dlatego, że dla upraw trwałych detekcja jest
    <em>gorsza</em> od deklaracji. Malina ma model 0,878 wobec pamięci 0,847,
    fasola 0,880 wobec 0,949. Wstawienie ich tam pogorszyłoby mapę.</li>
    <li><b>Nie schodzić do 10&nbsp;m z modelem.</b> Dane na to pozwalają, ale
    maksimum policzone na siatce 100&nbsp;m leży w tym samym miejscu —
    dostalibyśmy ten sam punkt po stukrotnie dłuższym liczeniu. Sensowne
    zejście to wybór działki spośród sąsiednich, i ten poziom już mamy.</li>
    <li><b>Nie zmniejszać rozmycia mapy.</b> To nie jest efekt graficzny,
    tylko zasięg lotu pszczoły. Kosmetyczną część (interpolację) usunięto;
    reszta jest modelem i jej redukcja oznaczałaby twierdzenie, że pszczoły
    latają bliżej, niż zmierzono.</li>
    <li><b>Nie stawiać mikroserwisu z pogodą na żywo</b>, zanim ktoś z terenu
    realnie użyje tej strony. Model prognozy jest policzony i zwalidowany —
    brakuje tylko opakowania go w API, a to nie jest praca badawcza.</li>
  </ul>

  <h3>W przyszłości — w tej kolejności</h3>
  <ol>
    <li><b>Zbiory z pasiek wobec mapy.</b> Największa dziura. Kilkanaście
    notatek „ile z rzepaku, ile z lata, który sezon” waży więcej niż kolejna
    warstwa satelitarna. Ranking cukru może być poprawny i mimo to mylący,
    jeśli rejon jest już obsadzony albo maj zjadła pogoda.</li>
    <li><b>Klasyfikator działający w trakcie sezonu.</b> Rzepak ozimy sieje
    się w sierpniu i zimuje zielony, więc jest widoczny na długo przed
    kwitnieniem. Model uczony wyłącznie na oknach dostępnych do marca
    wskazałby pola na dwa miesiące wcześniej — wtedy łańcuch domknąłby się
    w całości: <em>gdzie</em> ze zdjęć zimowych, <em>kiedy</em> z pogody.
    Dziś projekt przewiduje termin, ale nie lokalizację.</li>
    <li><b>Wpływ zmiany rewizyty Sentinela-1 na szereg.</b> Do końca 2021
    wynosiła 6 dni, w latach 2022–2024 dwanaście (awaria Sentinela-1B), od
    2025 znów 6. Przy oknach półmiesięcznych warstwa radarowa jest w środku
    szeregu rzadsza — to może tłumaczyć część niestabilności przypisanej
    dotąd szumowi klasyfikacji. Nie sprawdzone.</li>
    <li><b>Niezależna walidacja polowa fenologii rzepaku.</b> Dziś model
    porównywany jest z inną estymacją satelitarną (krzywe NDYI). Dla lipy
    i robinii mamy obserwacje IMGW z 51 stacji (błąd 2,8 dnia i −1 dzień),
    dla rzepaku nie ma nic równoważnego.</li>
  </ol>
  <p>Test na teraz: wysłać <code>kalendarz.html</code> komuś z terenu i pytać,
  czy czerwone plamy zgadzają się z tym, gdzie stawiają.</p></div>
</section>

<section>
  <span class="etap">Odsyłacze</span>
  <div class="kolumna"><h2>Literatura i zbiory</h2>
  <ul>
    <li>Nektarowanie rzepaku, <i>Pasieka</i> 2/2003 —
      <a href="https://pasieka24.pl/index.php/pl-pl/pasieka-czasopismo-dla-pszczelarzy/104-pasieka-2-2003/1258-pszszczoy-na-rzepaku-obfito-nektarowania-rzepaku-ozimego">pasieka24.pl</a></li>
    <li>Kołtowski, fasola wielokwiatowa, <i>Pasieka</i> 3/2005 —
      <a href="https://pasieka24.pl/index.php/pl-pl/pasieka-czasopismo-dla-pszczelarzy/86-pasieka-3-2005/914-jaka-wartosc-dla-pszczol-ma-fasola-wielokwiatowa-phaseolus-coccineus-l">pasieka24.pl</a></li>
    <li>Tabela wydajności miodowych —
      <a href="https://polskieule.pl/wydajnosc-miodowa-roslin/">polskieule.pl</a></li>
    <li>Miododajne rośliny rolnicze, KPODR —
      <a href="https://technologia.kpodr.pl/index.php/2012/04/06/miododajne-rosliny-rolnicze/">kpodr.pl</a></li>
    <li>d'Andrimont i in., EUCROPMAP, RSE 2021 —
      <a href="https://doi.org/10.1016/j.rse.2021.112708">doi:10.1016/j.rse.2021.112708</a></li>
    <li>ESA WorldCover —
      <a href="https://esa-worldcover.org">esa-worldcover.org</a></li>
    <li>Open-Meteo (ERA5) —
      <a href="https://open-meteo.com/">open-meteo.com</a></li>
    <li>Geoportal ARiMR, deklaracje GSA —
      <a href="https://geoportal.arimr.gov.pl/">geoportal.arimr.gov.pl</a></li>
  </ul>
  <p>Pełna karta każdej stałej: <code>ZRODLA.md</code>. Tabele branżowe
  najpewniej idą z atlasu Kołtowskiego, ale bez wprost cytatu są z drugiej ręki.</p>

  </div>
</section>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    prof, kl = czytaj("profil_2022.json"), czytaj("klasyfikator_gsa.json")
    fen, pot = czytaj("fenologia.json"), czytaj("potencjal_gsa.json")
    fin = czytaj("fenologia_final.json")
    gl = fin["glowny"]
    fen = {**fen,
           "obserwacje": fin["obserwacje"][gl],
           "przewidywania": fin["przewidywania"][gl],
           "model": {"baza": fin["model"]["baza"], "start": fin["model"]["start"],
                     "prog_gdd": fin["model"]["prog"],
                     "rmse_dni": fin["model"]["rmse"]},
           "odniesienia": {"stala": fin["odniesienie_stala"],
                           "persystencja": fen["odniesienia"]["persystencja"]},
           "final": fin}

    mapy = {
        "woj": png_b64(MAPY / "mapa_wojewodztwa.png"),
        "sredni": png_b64(MAPY / "mapa_sredni_rok.png"),
        "miejsce1": png_b64(MAPY / "mapa_dzialki_1.png"),
    }
    html = strona(prof, kl, fen, pot, mapy)
    wyj = ROOT / "raport.html"
    wyj.write_text(html, encoding="utf-8")
    print(f"zapisano {wyj.name}: {wyj.stat().st_size/1e6:.1f} MB")
