// Every text on the page, in Spanish and English. app.js picks one dictionary.
// Keys used in index.html: data-i18n (plain text) and data-i18n-html (trusted HTML written here).
window.I18N = {
  es: {
    subtitle: "Esta noche en el Observatorio del Roque de los Muchachos (La Palma)",
    theme: "Cambiar tema claro/oscuro",
    independent: "Proyecto independiente de portfolio, no afiliado a GRANTECAN ni a ningún observatorio. Datos reales y públicos; no es una herramienta operativa.",
    night_of: "Noche del {date}",
    window: "Noche astronómica de {start} a {end} hora canaria ({hours} h) · actualizado a las {updated}",
    mode_provisional: "Provisional hasta las {time} ⓘ", mode_final: "Definitivo desde las {time} ⓘ", final_word: "definitivo",
    mode_provisional_text: "Antes de que empiece la noche aún no existe lo que más ayuda: lo que mide la estación de la cumbre justo antes de la noche. Por eso ahora se usan la previsión del tiempo, lo que pasó anoche y la época del año. A las {time} se añade la estación y el pronóstico pasa a definitivo. Cuando dice «cerrar», acierta el {prov} de las veces en provisional y el {fin} en definitivo.",
    mode_final_text: "Ya usa lo que midió la estación de la cumbre justo antes de la noche, que es lo que más ayuda, además de la previsión del tiempo, lo de anoche y la época del año. Cuando dice «cerrar», acierta el {fin} de las veces (en provisional, el {prov}).",
    headline: "Se podrá observar unas {open} de las {total} horas de noche",
    cell_title: "{time}: {p} de que la cúpula esté cerrada",
    moon_up_word: "Luna sobre el horizonte",
    strip_legend: "Cada casilla es una hora: probabilidad de que la cúpula esté cerrada por humedad, viento o hielo (<span class=\"sw\" style=\"background:var(--good)\"></span> menos del 20 %, <span class=\"sw\" style=\"background:var(--warning)\"></span> 20–50 %, <span class=\"sw\" style=\"background:var(--critical)\"></span> más del 50 %). ☾ = Luna sobre el horizonte.",
    fact_seeing: "Nitidez (seeing) prevista", fact_moon: "Luna", fact_usual: "Lo normal",
    seeing_excellent: "Excelente", seeing_good: "Buena", seeing_average: "Normal", seeing_poor: "Mala",
    seeing_better: "Mejor que el {p} % de las noches del Roque. Menos es mejor.",
    moon_rises: "Sale a las {time}", moon_sets: "Se pone a las {time}",
    moon_all_night: "Arriba toda la noche", moon_none: "No sale en toda la noche",
    moon_text: "{phase}. {when}. Noche oscura sin Luna: {dark} h.",
    moon_phases: { new: "Luna nueva", waxing_crescent: "Creciente", first_quarter: "Cuarto creciente", waxing_gibbous: "Gibosa creciente",
      full: "Luna llena", waning_gibbous: "Gibosa menguante", last_quarter: "Cuarto menguante", waning_crescent: "Menguante" },
    usual_text: "Horas de cúpula cerrada en una noche normal de {month}. Esta noche se esperan {h} h.",
    updated: "Pronóstico emitido: {time} hora canaria.",
    how_title: "Cómo lo sabemos",
    how1: "<b>La previsión del tiempo sola falla en la cumbre.</b> El modelo meteorológico ve la montaña más baja de lo que es, dentro del mar de nubes: esta noche diría «cerrar» en {n} de las {total} horas. En 2024–2026, cada vez que decía «cerrar» acertaba solo {r} de cada 10.",
    how2: "<b>Por eso aprendemos de los datos.</b> Comparamos 7 años de previsiones con lo que pasó de verdad en la cumbre, medido minuto a minuto por la estación del NOT: cúpula cerrada por humedad, viento o hielo. El modelo aprende a corregir la previsión.",
    how3: "<b>Comprobado con noches que nunca vio (2024–2026).</b> Cuando dice «cerrar», acierta {r} de cada 10. Las horas cerradas de la noche las acierta con un error medio de {err} h (lo normal del mes falla {clim} h).",
    fold_real: "¿Refleja la realidad la etiqueta de cierre?",
    real_intro: "No hay un registro público de cuándo cierra el GTC. Nuestra etiqueta (humedad, viento o hielo, medidos en la cumbre) se comprueba con cuatro fuentes públicas independientes:",
    check_gtc: "<b>Archivo público del GTC ({from} a {to}).</b> Cada imagen científica del cielo lleva su hora: en esos minutos la cúpula estaba abierta seguro. El GTC estuvo tomando imágenes {h} horas y solo el {p} % de ese tiempo nuestra etiqueta decía «cerrada». En las {n} noches que la etiqueta da como cerradas enteras, el GTC no tomó ninguna imagen. Solo sirve en un sentido: una noche sin imágenes puede ser técnica, no cerrada.",
    check_gtc_gap: "<b>Desde {after}, sin datos del GTC:</b> el archivo los hace públicos un año después. Esos meses se comprueban con el Liverpool y el TNG.",
    check_tng: "<b>Telescopio Nazionale Galileo ({from} a {to}).</b> Publica las horas perdidas por meteo de cada noche del último año. Siguen a las nuestras (correlación {r}) y perdió el {p} % de las {n} noches que la etiqueta cierra enteras.",
    check_lt: "<b>Partes del Liverpool Telescope ({from} a {to}).</b> Sus horas perdidas por meteo siguen a las nuestras (correlación {r}). De las {n} noches que la etiqueta cierra enteras, el Liverpool también perdió el {p} %. Es más prudente: pierde de media {lt} h por noche frente a nuestras {lab} h.",
    check_wht: "<b>Contabilidad del telescopio WHT (2010 en adelante).</b> Cuadra en los años fiables y se hunde en los años en que da por observadas noches con la cúpula cerrada (⚠).",
    years_title: "Año por año: con qué se comprueba cada año",
    years_note: "GTC: parte del tiempo observando en que la etiqueta decía «cerrada» (lo ideal es 0 %). Resto: correlación entre sus horas perdidas por meteo y nuestras horas cerradas (1 = cuadran del todo). «—» = esa fuente no tiene datos de ese año.",
    col_year: "Año", col_gtc: "GTC", col_lt: "Liverpool", col_tng: "TNG", col_wht: "WHT",
    rules_title: "Cuándo cuenta como cerrada",
    rules_intro: "Lo mide minuto a minuto la estación meteorológica del NOT, en la cumbre. La cúpula cuenta como cerrada si se cumple cualquiera de estas tres cosas:",
    rules_cols: ["Motivo", "Se cierra cuando…", "Se vuelve a abrir cuando…", "De dónde sale el valor"],
    rules_rows: [
      ["Humedad", "la humedad llega al <b>90 %</b>", "lleva <b>20 min seguidos</b> por debajo del 90 %", "Regla de cierre del telescopio NOT"],
      ["Viento", "el viento llega a <b>80 km/h</b> (22,2 m/s)", "lleva <b>20 min seguidos</b> por debajo", "Límite de cierre del telescopio INT (ING)"],
      ["Hielo", "la temperatura baja a <b>0 °C</b> o menos y la humedad ha llegado al 90 % en las <b>24 h</b> anteriores", "la temperatura sube de 0 °C", "Nuestra regla, ajustada con los partes del Liverpool de 2017–2022"],
    ],
    rules_note: "Una hora cuenta como cerrada si la cúpula está cerrada al menos 30 de sus 60 minutos. No se incluyen nubes ni polvo: no hay un dato público fiable en la cumbre para todos los años.",
    fold_eval: "¿Cuánto acierta?",
    eval_intro: "Todo con noches de 2024–2026 que los modelos nunca vieron al aprender, frente a lo más sencillo que hay que batir.",
    eval_note: "«Acierta 7 de cada 10» = de cada 10 veces que dice «cerrar», 7 lo estuvo. «Detecta 7 de cada 10» = de cada 10 horas cerradas, avisó de 7.",
    plain_yesno: "acierta {r} de cada 10; detecta {c} de cada 10",
    plain_error: "se equivoca de media {v}",
    provisional_word: "provisional",
    refs: { raw: "Previsión del tiempo sola", precasting: "Humedad justo antes de la noche", climatology: "Lo normal del mes", persistence: "Igual que anoche" },
    what: { hour: "Cúpula cerrada en cada hora", night: "Horas cerradas de la noche", seeing: "Seeing de la noche" },
    col_what: "Qué se predice", col_ours: "Nuestro pronóstico (definitivo)", col_refs: "Lo que hay que batir",
    recent_title: "Últimas 60 noches de la prueba",
    recent_text: "Barras: horas de cúpula cerrada que pronosticó el modelo. Puntos: las que de verdad lo estuvieron.",
    forecast_word: "Pronóstico", actual_word: "Real", hours_word: "Horas",
    reliability_title: "¿Son fiables los porcentajes?",
    reliability_text: "Horas de 2024–2026 agrupadas por el porcentaje que dio el modelo. Si dice 30 %, la cúpula debería estar cerrada unas 3 de cada 10 de esas horas: cuanto más cerca de la diagonal, mejor.",
    eval_reliability: "Fiabilidad de los porcentajes",
    rel_x: "Porcentaje pronosticado", rel_y: "Cerrada de verdad", rel_model: "Nuestro modelo", rel_perfect: "Perfecto",
    track_title: "Historial en directo",
    track_text: "Cada pronóstico emitido por esta web frente a lo que pasó. Se llena noche a noche.",
    track_empty: "Todavía no hay noches terminadas con pronóstico emitido.",
    col_night: "Noche", col_mode: "Tipo", col_fc_h: "Cerrada (pronóstico)", col_real_h: "Cerrada (real)",
    col_fc_seeing: "Seeing (pronóstico)", col_real_seeing: "Seeing (real)",
    technical: "Ver las cifras técnicas (para especialistas)",
    glossary: `<ul>
<li><b>Brier:</b> error medio de un porcentaje (0 es perfecto). <b>Skill:</b> cuánto error quita frente a «lo normal del mes» (0 nada, 1 todo).</li>
<li><b>AUC:</b> lo bien que ordena las horas de más a menos riesgo (0,5 al azar, 1 perfecto).</li>
<li><b>MAE:</b> error medio en horas o segundos de arco. <b>RMSE:</b> parecido, pero castiga más los errores grandes.</li>
</ul>`,
    col_method: "Método", col_scores: "Cifras",
    fold_data: "Datos y fuentes",
    data_html: `<p>Todos los datos son reales y públicos; no hay nada simulado.</p>
<div class="table-wrap"><table class="text"><thead><tr><th>Para qué</th><th>Fuente</th><th>Periodo</th></tr></thead><tbody>
<tr><td><b>Aprender qué pasó:</b> cúpula cerrada por humedad (≥ 90 %, reabrir tras 20 min), viento (rachas de más de 80 km/h) o hielo (0 °C o menos tras humedad alta en 24 h)</td><td><a href="https://www.not.iac.es/weather/archive/met/index.php">Estación meteorológica del NOT</a>, minuto a minuto</td><td>1997 → hoy</td></tr>
<tr><td><b>Aprender qué pasó:</b> nitidez (seeing) de cada noche</td><td><a href="https://astro.ing.iac.es/seeing/">Monitor R2D2</a> (Isaac Newton Group)</td><td>2018 → hoy</td></tr>
<tr><td><b>Entradas:</b> lo que se pronosticó en su momento (no lo que pasó después)</td><td>Pronósticos archivados ECMWF y GFS (viento en altura) vía <a href="https://open-meteo.com/">Open-Meteo</a></td><td>2017 → hoy (GFS desde 2021)</td></tr>
<tr><td><b>Entradas:</b> la estación 2 h antes de la noche y lo que pasó anoche</td><td>Estación del NOT y R2D2</td><td>en directo</td></tr>
<tr><td><b>Comprobar la etiqueta</b></td><td><a href="https://gtc.sdc.cab.inta-csic.es/gtc/index.jsp">Archivo público del GTC</a> (CAB), <a href="https://telescope.livjm.ac.uk/Reports/">partes del Liverpool Telescope</a>, <a href="https://a.ing.iac.es/weather/archive/">contabilidad del WHT</a></td><td>2024 · 2007 → hoy · 2007 → hoy</td></tr>
<tr><td><b>Solo se muestra</b></td><td><a href="https://atmosportal.gtc.iac.es/">Panel de la estación del GTC</a></td><td>en directo</td></tr>
<tr><td><b>Calculado aquí</b></td><td>Noche astronómica y Luna (fórmulas astronómicas propias)</td><td>—</td></tr>
</tbody></table></div>
<p class="muted small">Probado y descartado por no aportar: calima prevista (CAMS), cielo despejado (partes del Liverpool) y seeing hora a hora. Las descargas se identifican, esperan entre peticiones y solo usan páginas enlazadas desde las webs públicas.</p>`,
    fold_live: "La cumbre en directo",
    station_title: "Últimas 24 horas en la estación del NOT",
    station_text: "Medias de 10 minutos. Última medida: {time} hora canaria — humedad {rh} %, viento {wind} m/s, {temp} °C.",
    raw_title: "La previsión del tiempo tal cual",
    raw_text: "Humedad y nubes del modelo ECMWF en el punto del observatorio. En la cumbre casi siempre sale demasiado húmeda: por eso no se usa directamente. Zona sombreada: la noche.",
    rh: "Humedad (%)", cloud: "Nubes (%)", limit90: "Límite de cierre (90 %)",
    gtc_title: "Panel de la estación del GTC",
    gtc_text: "Valores publicados por atmosportal ({time} UTC).",
    gtc_none: "Sin lectura reciente del panel del GTC.",
    fold_refs: "Referencias",
    refs_html: `<ul>
<li>Abárzuza et al. 2025, RNAAS 9(2): random forest para el seeing del Roque.</li>
<li>de Sepibus, Masciadri et al. 2026, arXiv:2607.12900: persistencia y precasting como métodos de referencia mínimos.</li>
<li>Lombardi et al. 2007, arXiv:astro-ph/0702570: viento y humedad frente al seeing en el Roque.</li>
<li>ING, procedimiento de alarmas del INT: cierre con humedad ≥ 90 % y con rachas de más de 80 km/h.</li>
</ul>`,
    footer: "Roque Night Forecast · proyecto independiente · código y metodología en GitHub (saimonx/roque-night-forecast).",
    months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    na: "—",
  },

  en: {
    subtitle: "Tonight at the Roque de los Muchachos Observatory (La Palma)",
    theme: "Toggle light/dark theme",
    independent: "Independent portfolio project, not affiliated with GRANTECAN or any observatory. Real, public data; not an operational tool.",
    night_of: "Night of {date}",
    window: "Astronomical night from {start} to {end} Canary time ({hours} h) · updated at {updated}",
    mode_provisional: "Provisional until {time} ⓘ", mode_final: "Final since {time} ⓘ", final_word: "final",
    mode_provisional_text: "Before the night starts, what helps the most does not exist yet: the summit station's readings just before the night. So it now uses the weather forecast, last night and the time of year. At {time} the station is added and the forecast becomes final. When it says \"close\", it is right {prov} of the time when provisional and {fin} when final.",
    mode_final_text: "It now uses what the summit station measured just before the night, which helps the most, on top of the weather forecast, last night and the time of year. When it says \"close\", it is right {fin} of the time (provisional: {prov}).",
    headline: "About {open} of the {total} night hours should be observable",
    cell_title: "{time}: {p} chance that the dome is closed",
    moon_up_word: "Moon above the horizon",
    strip_legend: "Each box is one hour: chance that the dome is closed for humidity, wind or ice (<span class=\"sw\" style=\"background:var(--good)\"></span> below 20 %, <span class=\"sw\" style=\"background:var(--warning)\"></span> 20–50 %, <span class=\"sw\" style=\"background:var(--critical)\"></span> above 50 %). ☾ = Moon above the horizon.",
    fact_seeing: "Forecast sharpness (seeing)", fact_moon: "Moon", fact_usual: "Usual",
    seeing_excellent: "Excellent", seeing_good: "Good", seeing_average: "Average", seeing_poor: "Poor",
    seeing_better: "Better than {p} % of Roque nights. Lower is better.",
    moon_rises: "Rises at {time}", moon_sets: "Sets at {time}",
    moon_all_night: "Up all night", moon_none: "Does not rise tonight",
    moon_text: "{phase}. {when}. Moonless dark time: {dark} h.",
    moon_phases: { new: "New Moon", waxing_crescent: "Waxing crescent", first_quarter: "First quarter", waxing_gibbous: "Waxing gibbous",
      full: "Full Moon", waning_gibbous: "Waning gibbous", last_quarter: "Last quarter", waning_crescent: "Waning crescent" },
    usual_text: "Closed hours on a usual {month} night. Tonight: {h} h expected.",
    updated: "Forecast issued: {time} Canary time.",
    how_title: "How we know",
    how1: "<b>The weather forecast alone fails at the summit.</b> The weather model sees the mountain lower than it is, inside the sea of clouds: tonight it would say \"close\" in {n} of the {total} hours. In 2024–2026, each time it said \"close\" it was right only {r} times in 10.",
    how2: "<b>So we learn from the data.</b> We compare 7 years of forecasts with what really happened at the summit, measured minute by minute by the NOT weather station: dome closed for humidity, wind or ice. The model learns to correct the forecast.",
    how3: "<b>Tested on nights it never saw (2024–2026).</b> When it says \"close\", it is right {r} times in 10. It gets the night's closed hours with an average error of {err} h (the usual for the month misses by {clim} h).",
    fold_real: "Does the closure label reflect reality?",
    real_intro: "There is no public record of when the GTC closes. Our label (humidity, wind or ice, measured at the summit) is checked against four independent public sources:",
    check_gtc: "<b>GTC public archive ({from} to {to}).</b> Every science image of the sky carries its time: in those minutes the dome was certainly open. The GTC was taking images for {h} hours, and only {p} % of that time did our label say \"closed\". On the {n} nights the label calls fully closed, the GTC took no images at all. It works one way only: a night without images may be a technical night, not a closed one.",
    check_gtc_gap: "<b>From {after}, no GTC data:</b> the archive makes them public one year later. Those months are checked with the Liverpool and the TNG.",
    check_tng: "<b>Telescopio Nazionale Galileo ({from} to {to}).</b> It publishes the hours lost to weather each night of the last year. They follow ours (correlation {r}) and it lost {p} % of the {n} nights the label closes fully.",
    check_lt: "<b>Liverpool Telescope reports ({from} to {to}).</b> Its hours lost to weather follow ours (correlation {r}). Of the {n} nights the label closes fully, the Liverpool also lost {p} %. It is more cautious: it loses {lt} h per night on average against our {lab} h.",
    check_wht: "<b>WHT telescope accounting (2010 on).</b> It agrees in the reliable years and drops in the years when it books nights with the dome closed as observed (⚠).",
    years_title: "Year by year: what checks each year",
    years_note: "GTC: share of its observing time when the label said \"closed\" (ideally 0 %). Others: correlation between their hours lost to weather and our closed hours (1 = full agreement). \"—\" = no data from that source that year.",
    col_year: "Year", col_gtc: "GTC", col_lt: "Liverpool", col_tng: "TNG", col_wht: "WHT",
    rules_title: "When it counts as closed",
    rules_intro: "Measured minute by minute by the NOT weather station at the summit. The dome counts as closed if any of these three things happens:",
    rules_cols: ["Reason", "Closes when…", "Reopens when…", "Where the value comes from"],
    rules_rows: [
      ["Humidity", "humidity reaches <b>90 %</b>", "it has been below 90 % for <b>20 minutes in a row</b>", "NOT telescope closing rule"],
      ["Wind", "wind reaches <b>80 km/h</b> (22.2 m/s)", "it has been below for <b>20 minutes in a row</b>", "INT telescope closing limit (ING)"],
      ["Ice", "temperature drops to <b>0 °C</b> or below and humidity reached 90 % in the previous <b>24 h</b>", "temperature rises above 0 °C", "Our rule, tuned on Liverpool reports 2017–2022"],
    ],
    rules_note: "An hour counts as closed if the dome is closed for at least 30 of its 60 minutes. Cloud and dust are not included: there is no reliable public summit record for every year.",
    fold_eval: "How good is it?",
    eval_intro: "All on 2024–2026 nights the models never saw while learning, against the simplest things to beat.",
    eval_note: "\"Right 7 in 10\" = of every 10 times it says \"close\", 7 were closed. \"Catches 7 in 10\" = of every 10 closed hours, it warned about 7.",
    plain_yesno: "right {r} in 10; catches {c} in 10",
    plain_error: "off by {v} on average",
    provisional_word: "provisional",
    refs: { raw: "Weather forecast alone", precasting: "Humidity just before the night", climatology: "The usual for the month", persistence: "Same as last night" },
    what: { hour: "Dome closed each hour", night: "Closed hours of the night", seeing: "Seeing of the night" },
    col_what: "What is forecast", col_ours: "Our forecast (final)", col_refs: "What it has to beat",
    recent_title: "Last 60 test nights",
    recent_text: "Bars: closed hours the model forecast. Dots: the hours that really were closed.",
    forecast_word: "Forecast", actual_word: "Actual", hours_word: "Hours",
    reliability_title: "Can the percentages be trusted?",
    reliability_text: "Hours of 2024–2026 grouped by the percentage the model gave. When it says 30 %, the dome should be closed in about 3 of 10 of those hours: the closer to the diagonal, the better.",
    eval_reliability: "Reliability of the percentages",
    rel_x: "Forecast percentage", rel_y: "Actually closed", rel_model: "Our model", rel_perfect: "Perfect",
    track_title: "Live track record",
    track_text: "Every forecast issued by this page against what happened. It fills up night by night.",
    track_empty: "No finished night with an issued forecast yet.",
    col_night: "Night", col_mode: "Type", col_fc_h: "Closed (forecast)", col_real_h: "Closed (actual)",
    col_fc_seeing: "Seeing (forecast)", col_real_seeing: "Seeing (actual)",
    technical: "Show the technical figures (for specialists)",
    glossary: `<ul>
<li><b>Brier:</b> average error of a percentage (0 is perfect). <b>Skill:</b> how much error it removes against "the usual for the month" (0 none, 1 all).</li>
<li><b>AUC:</b> how well it ranks hours from most to least risky (0.5 random, 1 perfect).</li>
<li><b>MAE:</b> average error in hours or arcseconds. <b>RMSE:</b> similar, but punishes big errors more.</li>
</ul>`,
    col_method: "Method", col_scores: "Scores",
    fold_data: "Data and sources",
    data_html: `<p>All data are real and public; nothing is simulated.</p>
<div class="table-wrap"><table class="text"><thead><tr><th>What for</th><th>Source</th><th>Period</th></tr></thead><tbody>
<tr><td><b>Learning what happened:</b> dome closed for humidity (≥ 90 %, reopen after 20 min), wind (gusts above 80 km/h) or ice (0 °C or less after high humidity within 24 h)</td><td><a href="https://www.not.iac.es/weather/archive/met/index.php">NOT weather station</a>, minute by minute</td><td>1997 → today</td></tr>
<tr><td><b>Learning what happened:</b> sharpness (seeing) of each night</td><td><a href="https://astro.ing.iac.es/seeing/">R2D2 monitor</a> (Isaac Newton Group)</td><td>2018 → today</td></tr>
<tr><td><b>Inputs:</b> what was forecast at the time (not what happened later)</td><td>Archived ECMWF and GFS (upper-air wind) forecasts via <a href="https://open-meteo.com/">Open-Meteo</a></td><td>2017 → today (GFS from 2021)</td></tr>
<tr><td><b>Inputs:</b> the station 2 h before the night and last night</td><td>NOT station and R2D2</td><td>live</td></tr>
<tr><td><b>Checking the label</b></td><td><a href="https://gtc.sdc.cab.inta-csic.es/gtc/index.jsp">GTC public archive</a> (CAB), <a href="https://telescope.livjm.ac.uk/Reports/">Liverpool Telescope reports</a>, <a href="https://a.ing.iac.es/weather/archive/">WHT accounting</a></td><td>2024 · 2007 → today · 2007 → today</td></tr>
<tr><td><b>Shown only</b></td><td><a href="https://atmosportal.gtc.iac.es/">GTC weather station panel</a></td><td>live</td></tr>
<tr><td><b>Computed here</b></td><td>Astronomical night and Moon (own astronomical formulas)</td><td>—</td></tr>
</tbody></table></div>
<p class="muted small">Tried and dropped because they added nothing: forecast dust (CAMS), clear sky (Liverpool reports) and hour-by-hour seeing. Downloads identify themselves, wait between requests and only use pages linked from the public sites.</p>`,
    fold_live: "The summit, live",
    station_title: "Last 24 hours at the NOT station",
    station_text: "10-minute means. Latest reading: {time} Canary time — humidity {rh} %, wind {wind} m/s, {temp} °C.",
    raw_title: "The weather forecast as it is",
    raw_text: "Humidity and cloud from the ECMWF model at the observatory. At the summit it is almost always too wet: that is why it is not used directly. Shaded: the night.",
    rh: "Humidity (%)", cloud: "Cloud (%)", limit90: "Closing limit (90 %)",
    gtc_title: "GTC weather station panel",
    gtc_text: "Values published by atmosportal ({time} UTC).",
    gtc_none: "No recent reading of the GTC panel.",
    fold_refs: "References",
    refs_html: `<ul>
<li>Abárzuza et al. 2025, RNAAS 9(2): random forest for Roque seeing.</li>
<li>de Sepibus, Masciadri et al. 2026, arXiv:2607.12900: persistence and precasting as minimum reference methods.</li>
<li>Lombardi et al. 2007, arXiv:astro-ph/0702570: wind and humidity against seeing at the Roque.</li>
<li>ING, INT alarm procedure: close at humidity ≥ 90 % and with gusts above 80 km/h.</li>
</ul>`,
    footer: "Roque Night Forecast · independent project · code and method on GitHub (saimonx/roque-night-forecast).",
    months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    na: "—",
  },
};
