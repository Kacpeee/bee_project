// Model fenologiczny w przegladarce - odpowiednik model_fenologiczny.py.
//
// Istnieje, bo strona statyczna nie ma serwera, ktory by liczyl. Naglowek
// model_fenologiczny.py ostrzega przed druga kopia obliczen, wiec:
//   - zaden parametr nie jest tu wpisany; M wstrzykuje eksport_statyczny.py
//     z wyniki/json/, tak samo jak czyta je Python,
//   - zgodnosc sprawdza test_rownowaznosc.py (te same punkty przez oba
//     jezyki, porownanie 11 pol widocznych dla uzytkownika).
//
// prognozaLokalna() zwraca obiekt o TYM SAMYM ksztalcie, co trasa
// /prognoza_obszar, zeby kod rysujacy wynik w serwis.py STRONA dzialal
// bez zmian.

const M = __MODEL__;
const MIES = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"];

function odDoy(doy, rok){ const d = new Date(Date.UTC(rok,0,1));
  d.setUTCDate(d.getUTCDate() + Math.round(doy) - 1); return d; }
function dzM(doy, rok){ const d = odDoy(doy,rok);
  return d.getUTCDate() + " " + MIES[d.getUTCMonth()]; }
function isoM(doy, rok){ return odDoy(doy,rok).toISOString().slice(0,10); }
function doyZ(txt){ const c = txt.split("-").map(Number);
  return Math.round((Date.UTC(c[0],c[1]-1,c[2]) - Date.UTC(c[0],0,1))/864e5) + 1; }

// UWAGA: Math.round NIE zachowuje sie jak round() w Pythonie.
// Python zaokragla polowke do liczby PARZYSTEJ (round(512.5) = 512),
// JavaScript zawsze w gore (Math.round(512.5) = 513). Wspolrzedne sa
// przycinane do siatki 0,1 stopnia, wiec punkt konczacy sie na .x5 -
// np. 51,25 - trafial w kazdym jezyku do INNEJ komorki, czyli innej
// pogody, i data kwitnienia rozjezdzala sie o dzien. Wykryl to
// test_rownowaznosc.py; w drugim takim punkcie roznica pogody przypadkiem
// nie przesunela daty, wiec blad byl tam niewidoczny.
function zaokrPy(x){
  const p = Math.floor(x), r = x - p;
  if (r > 0.5) return p + 1;
  if (r < 0.5) return p;
  return (p % 2 === 0) ? p : p + 1;
}
function przytnij(v){ return Math.round(zaokrPy(v/0.1) * 0.1 * 1000) / 1000; }

async function pobierzOM(url){
  for (let i = 0; i < 5; i++){
    const r = await fetch(url);
    if (r.status !== 429){
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }
    await new Promise(function(s){ setTimeout(s, 2000 * (i + 1)); });
  }
  throw new Error("Open-Meteo: limit zapytan, sprobuj za chwile");
}

// PAMIEC PODRECZNA NA CZAS OTWARCIA STRONY.
// Klimatologia to osiem lat historii i jest IDENTYCZNA dla wszystkich
// sezonow w tym samym punkcie. Bez tego kazde przelaczenie roku pobieralo
// ja od nowa i Open-Meteo zaczynalo zwracac 429. Python ma odpowiednik
// na dysku (_DYSK w model_fenologiczny.py).
const CACHE_OM = {};
function pobierzZC(url){
  if (!(url in CACHE_OM)){
    CACHE_OM[url] = pobierzOM(url).catch(function(e){ delete CACHE_OM[url]; throw e; });
  }
  return CACHE_OM[url];
}

async function dobowe(lat, lon, od, doD){
  const dzis = new Date();
  const dzisS = dzis.toISOString().slice(0,10);
  const graniczna = new Date(dzis.getTime() - 6*864e5).toISOString().slice(0,10);
  const wynik = {};
  if (od < dzisS){
    const kon = doD < graniczna ? doD : graniczna;
    const d = (await pobierzZC("https://archive-api.open-meteo.com/v1/archive?latitude="
      + lat + "&longitude=" + lon + "&start_date=" + od + "&end_date=" + kon
      + "&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FWarsaw")).daily;
    for (let i = 0; i < d.time.length; i++){
      if (d.temperature_2m_max[i] != null && d.temperature_2m_min[i] != null)
        wynik[d.time[i]] = [d.temperature_2m_max[i], d.temperature_2m_min[i]];
    }
  }
  if (doD >= graniczna){
    try {
      const d = (await pobierzZC("https://api.open-meteo.com/v1/forecast?latitude="
        + lat + "&longitude=" + lon
        + "&daily=temperature_2m_max,temperature_2m_min&past_days=10&forecast_days=16"
        + "&timezone=Europe%2FWarsaw")).daily;
      for (let i = 0; i < d.time.length; i++){
        if (d.temperature_2m_max[i] != null && d.temperature_2m_min[i] != null)
          wynik[d.time[i]] = [d.temperature_2m_max[i], d.temperature_2m_min[i]];
      }
    } catch(e) {}
  }
  // FILTR DO ZADANEGO ZAKRESU - konieczny, nie kosmetyczny.
  // Endpoint prognozy zwraca dni wokol DZISIAJ niezaleznie od pytania;
  // bez tego sierpien wpadal do nastepnego sezonu jako "pogoda realna",
  // a niepewnosc spadala dwukrotnie dla sezonu, o ktorym nie wiadomo nic.
  const f = {};
  for (const t in wynik) if (t >= od && t <= doD) f[t] = wynik[t];
  return f;
}

function sezonDomyslny(){
  const dzis = new Date();
  const doy = Math.round((Date.UTC(dzis.getFullYear(), dzis.getMonth(), dzis.getDate())
            - Date.UTC(dzis.getFullYear(),0,1))/864e5) + 1;
  return dzis.getFullYear() + (doy > M.sredni_termin + 20 ? 1 : 0);
}

async function prognozuj(lat, lon, rokWym){
  lat = przytnij(lat); lon = przytnij(lon);
  const dzis = new Date();
  const dzisDoy = Math.round((Date.UTC(dzis.getFullYear(), dzis.getMonth(), dzis.getDate())
                - Date.UTC(dzis.getFullYear(),0,1))/864e5) + 1;
  const rok = rokWym || sezonDomyslny();

  const hist = await dobowe(lat, lon, (rok-8) + "-01-01", (rok-1) + "-12-31");
  if (!Object.keys(hist).length) throw new Error("brak danych historycznych");
  const sumy = {}, licz = {};
  for (const t in hist){
    const k = doyZ(t);
    const g = Math.max((hist[t][0] + hist[t][1])/2 - M.baza, 0);
    sumy[k] = (sumy[k] || 0) + g; licz[k] = (licz[k] || 0) + 1;
  }
  const klim = {};
  for (const k in sumy) klim[k] = sumy[k] / licz[k];

  const biez = await dobowe(lat, lon, rok + "-01-01", rok + "-07-15");
  const realne = {};
  for (const t in biez) realne[doyZ(t)] = Math.max((biez[t][0] + biez[t][1])/2 - M.baza, 0);

  let kum = 0, pelnia = null; const kumTab = [];
  for (let t = 1; t < 200; t++){
    let g = (t in realne) ? realne[t] : (klim[t] || 0);
    if (t < M.start_doy) g = 0;
    kum += g; kumTab.push(kum);
    if (pelnia === null && kum >= M.prog) pelnia = t;
  }
  if (pelnia === null) throw new Error("prog nieosiagniety do 19 VII");

  const klucze = Object.keys(realne).map(Number);
  const ostatni = klucze.length ? Math.max.apply(null, klucze) : 0;
  const wiedza = Math.min(ostatni, pelnia);
  const dost = Object.keys(M.bledy_prognozy).map(Number).sort(function(a,b){ return a-b; });
  let blad, opis;
  if (wiedza >= pelnia){ blad = M.rmse_modelu; opis = "cała pogoda sezonu znana"; }
  else if (wiedza < dost[0]){ blad = M.bledy_prognozy[dost[0]]; opis = "przed sezonem (klimatologia)"; }
  else {
    const k = Math.max.apply(null, dost.filter(function(d){ return d <= wiedza; }));
    blad = M.bledy_prognozy[k]; opis = "pogoda znana do " + dzM(wiedza, rok);
  }

  const okres = Math.max(1, pelnia - M.start_doy + 1);
  let pokrycie = 0;
  for (let t = M.start_doy; t <= pelnia; t++) if (t in realne) pokrycie++;
  const pct = Math.round(pokrycie / okres * 100);

  let dzisD;
  if (rok === dzis.getFullYear()) dzisD = dzisDoy;
  else if (rok < dzis.getFullYear()) dzisD = pelnia;
  else dzisD = 0;
  dzisD = Math.min(dzisD, pelnia);
  const gddTeraz = dzisD >= M.start_doy ? kumTab[Math.min(dzisD-1, kumTab.length-1)] : 0;
  const ost = klucze.filter(function(t){ return t <= dzisD; })
                    .sort(function(a,b){ return a-b; }).slice(-14);
  const tempo = ost.length ? ost.reduce(function(s,t){ return s + realne[t]; }, 0)/ost.length : null;
  const brak = Math.max(0, M.prog - gddTeraz);

  let rodzaj, naglowek, uwaga;
  if (pct === 0){
    rodzaj = "srednia_wieloletnia"; naglowek = "termin typowy";
    uwaga = "To NIE jest prognoza — sezon " + rok + " jeszcze się nie zaczął, "
          + "więc model nie ma żadnej jego pogody i zwraca średnią wieloletnią. "
          + "Akumulacja ciepła rusza __START__, realna prognoza ma sens od połowy "
          + "kwietnia (błąd 5,0 d), a najlepsza jest 1 maja (3,4 d). Poniżej "
          + "możesz obejrzeć sezony minione — tam model zna całą pogodę.";
  } else if (pct < 60){
    rodzaj = "prognoza_wczesna"; naglowek = "prognoza wstępna";
    uwaga = "Część okresu akumulacji to jeszcze klimatologia. Zapytaj ponownie "
          + "bliżej kwitnienia — błąd spadnie.";
  } else {
    rodzaj = "prognoza"; naglowek = "prognoza";
    uwaga = "Model ma większość pogody okresu akumulacji.";
  }

  return {
    lat: lat, lon: lon, sezon: rok, rodzaj: rodzaj, naglowek: naglowek, uwaga: uwaga,
    pelnia: {doy: pelnia, data: isoM(pelnia,rok), opis: dzM(pelnia,rok)},
    poczatek: {data: isoM(pelnia-10,rok), opis: dzM(pelnia-10,rok)},
    koniec: {data: isoM(pelnia+12,rok), opis: dzM(pelnia+12,rok)},
    ustaw_ul: {data: isoM(pelnia-12,rok), opis: dzM(pelnia-12,rok)},
    niepewnosc_dni: Math.round(blad*10)/10,
    przedzial: {od: isoM(pelnia-blad,rok), do: isoM(pelnia+blad,rok)},
    podstawa_bledu: opis, pogoda_realna_pct: pct,
    postep: {
      gdd_teraz: Math.round(gddTeraz), prog: M.prog,
      do_dnia: dzisD >= M.start_doy ? dzM(dzisD,rok) : null,
      procent: Math.round(Math.min(100, gddTeraz/M.prog*100)),
      brakuje_gdd: Math.round(brak),
      tempo_gdd_dzien: tempo ? Math.round(tempo*10)/10 : null,
      dni_w_tym_tempie: (tempo && tempo > 0) ? Math.round(brak/tempo) : null
    },
    model: {baza_C: M.baza, prog_gdd: M.prog, start: "__START__",
            rmse_walidacji_d: M.rmse_modelu, n_obserwacji: M.n_obserwacji},
    zastrzezenie: "model przewiduje termin, nie lokalizację upraw; przed połową "
                + "kwietnia prognoza jest niewiele lepsza od średniej wieloletniej"
  };
}

// Odpowiednik trasy /prognoza_obszar - ten sam ksztalt odpowiedzi,
// zeby kod rysujacy wynik nie wymagal ani jednej zmiany.
async function prognozaLokalna(punkty, rok){
  const lats = punkty.map(function(p){ return p[0]; });
  const lons = punkty.map(function(p){ return p[1]; });
  const clat = lats.reduce(function(a,b){ return a+b; }, 0) / lats.length;
  const clon = lons.reduce(function(a,b){ return a+b; }, 0) / lons.length;
  if (!(49.9 <= clat && clat <= 52.5 && 21.2 <= clon && clon <= 24.4))
    return {blad: "obszar poza województwem lubelskim"};

  let probki = [[clat, clon]];
  if (Math.max.apply(null,lats) - Math.min.apply(null,lats) > 0.15 ||
      Math.max.apply(null,lons) - Math.min.apply(null,lons) > 0.25){
    probki.push([Math.min.apply(null,lats), clon]);
    probki.push([Math.max.apply(null,lats), clon]);
  }
  const wyniki = [], bledy = [];
  for (const p of probki){
    try { wyniki.push(await prognozuj(p[0], p[1], rok)); }
    catch(e){ bledy.push(String(e.message || e)); }
  }
  if (!wyniki.length) return {blad: bledy.join("; ") || "brak wyniku"};

  const doy = wyniki.map(function(w){ return w.pelnia.doy; });
  const g = Object.assign({}, wyniki[0]);
  g.srodek = {lat: Math.round(clat*1e4)/1e4, lon: Math.round(clon*1e4)/1e4};
  g.probek = wyniki.length;
  g.rozrzut_w_obszarze_d = Math.round(Math.max.apply(null,doy) - Math.min.apply(null,doy));
  g.obrys_punktow = punkty.length;
  return g;
}
