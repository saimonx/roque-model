// Every text on the page, in Spanish and English. app.js picks one dictionary.
// Keys used in index.html: data-i18n (plain text) and data-i18n-html (trusted HTML written here).
window.I18N = {
  es: {
    subtitle: "Pronóstico de la noche en el Observatorio del Roque de los Muchachos (La Palma)",
    theme: "Cambiar tema claro/oscuro",
    independent: "Proyecto independiente de portfolio, no afiliado a GRANTECAN ni a ningún observatorio. Datos reales y públicos; no es una herramienta operativa.",
    tonight: "Esta noche",
    night_of: "Noche del {date}",
    window: "Noche astronómica (Sol 18° bajo el horizonte): {start} – {end} hora canaria · {hours} h",
    mode_provisional: "Provisional",
    mode_final: "Definitivo",
    note_provisional: "Calculado solo con el pronóstico meteorológico, lo que pasó anoche y la época del año. A partir de las {time} (inicio de la noche) se usan también las 2 horas previas de la estación del NOT y el pronóstico pasa a definitivo.",
    note_final: "Calculado con el pronóstico meteorológico, la estación del NOT en las 2 horas antes de la noche, lo que pasó anoche y la época del año: el mismo modelo que se evaluó con las noches de 2024–2026.",
    closure_title: "Riesgo de tener que cerrar la cúpula",
    closure_help: "«Cerrar» = al menos 1 hora de cúpula cerrada por humedad, con la regla pública del NOT: se cierra con humedad ≥ 90 % y se reabre tras 20 minutos seguidos por debajo.",
    closure_more: "Qué tiene en cuenta",
    closure_more_text: `<ul>
<li><b>Pronóstico de la noche</b> (ECMWF): humedad, margen hasta el punto de rocío, nubes, lluvia, viento, temperatura y presión.</li>
<li><b>Estación del NOT en las 2 h antes de la noche</b>: lo que más pesa. Solo existe desde que empieza la noche; antes, el pronóstico es provisional y se calcula sin ella.</li>
<li><b>Anoche</b>: cuánto tiempo estuvo cerrada (el tiempo va por rachas).</li>
<li><b>Época del año.</b></li>
</ul>
<p>Modelo de gradient boosting entrenado con las noches de 2017–2023. No cubre cierres por viento, polvo o hielo, y no son decisiones reales del GTC.</p>`,
    seeing_title: "Seeing previsto (nitidez)",
    lost_title: "Horas perdidas por meteo",
    risk_low: "Bajo", risk_medium: "Medio", risk_high: "Alto",
    closure_ref: "Lo normal en {month}: {clim}. Si anoche se repitiera: {pers}.{prec}",
    closure_prec: " Regla «ya hay humedad antes de la noche»: {p}.",
    closed_hours: "Horas con la cúpula cerrada previstas: {h} h",
    seeing_excellent: "Excelente", seeing_good: "Bueno", seeing_average: "Normal", seeing_poor: "Malo",
    seeing_ref: "Lo normal en {month}: {clim}″",
    seeing_help: "Mediana de la noche en segundos de arco (″). Menos es mejor: 0,5″ excelente, 1,5″ malo.",
    lost_of: "de {h} h de noche",
    lost_ref: "Lo normal en {month} (WHT 2010–2018): {clim} h",
    lost_help: "Equivalente en la contabilidad nocturna del telescopio WHT (ING): 0,85 × horas de cierre previstas.",
    moon_text: "Luna {pct} iluminada ({phase}). {when}. Noche oscura sin Luna: {dark} de {total} h.",
    moon_rises: "Sale a las {time}", moon_sets: "Se pone a las {time}",
    moon_all_night: "Está sobre el horizonte toda la noche", moon_none: "No sale durante la noche",
    moon_phases: { new: "luna nueva", waxing_crescent: "creciente", first_quarter: "cuarto creciente", waxing_gibbous: "gibosa creciente",
      full: "luna llena", waning_gibbous: "gibosa menguante", last_quarter: "cuarto menguante", waning_crescent: "menguante" },
    moon_help: "La Luna no cambia el riesgo de cierre ni el seeing, pero ilumina el cielo: los objetos débiles necesitan noche oscura. Cálculo propio de su posición (precisión ~0,3°).",
    importance_closure: "Qué pesa más: cierre de cúpula",
    importance_seeing: "Qué pesa más: seeing",
    importance_text: "Importancia por permutación en las noches de prueba (2024–2026): cuánto empeora el modelo si se barajan los valores de una entrada, como parte del total. Las 8 entradas principales.",
    eval_reliability: "¿Las probabilidades son fiables?",
    reliability_text: "Noches de prueba agrupadas por la probabilidad dada (de 10 en 10 %). Si el modelo dice 70 %, la cúpula debería cerrarse unas 7 de cada 10 de esas noches. Se probó a recalibrarlas (regresión isotónica) con una validación cruzada por años en 2017–2023: el Brier pasó de {raw} a {iso}, es decir, no mejoró, así que no se aplica. En 2024–2026, entre el 40 % y el 90 %, la cúpula se cerró algo menos de lo que decía el modelo: se vigila con el historial en directo.",
    rel_x: "Probabilidad pronosticada", rel_y: "Se cerró de verdad", rel_model: "Gradient boosting (noches de prueba)", rel_perfect: "Calibración perfecta",
    flow: [
      ["Datos reales", "Meteo del NOT minuto a minuto desde 1997, seeing R2D2, contabilidad del WHT y pronósticos archivados (ECMWF y GFS)."],
      ["Una fila por noche", "Solo lo que se sabía al empezar la noche: pronóstico, estación 2 h antes, lo de anoche y la época del año."],
      ["Modelos", "Gradient boosting entrenado con 2017–2022 y ajustado con 2023."],
      ["Prueba honesta", "Noches 2024–2026 nunca vistas, frente a climatología, persistencia y precasting."],
      ["En directo", "Cada hora: pronóstico de esta noche, entidades FIWARE, Grafana y esta web."],
    ],
    tile_of_night: "Riesgo {level}, de {h} h de noche",
    mode_box_provisional: "<b>Pronóstico provisional.</b> Antes de que empiece la noche solo sabemos la previsión meteorológica, lo que pasó anoche y la época del año. A las {time} se añade lo que mide la estación de la cumbre justo antes de la noche, que es lo que más ayuda, y pasa a <b>definitivo</b>. Cuando dice «cerrar», acierta el {prov} % de las veces en provisional y el {fin} % en definitivo.",
    mode_box_final: "<b>Pronóstico definitivo.</b> Además de la previsión meteorológica, lo que pasó anoche y la época del año, ya usa lo que midió la estación de la cumbre justo antes de la noche, que es lo que más ayuda. Cuando dice «cerrar», acierta el {fin} % de las veces (en provisional, el {prov} %).",
    sum_hours: "Se espera la cúpula cerrada unas {h} de las {total} horas de noche, por humedad o viento.",
    sum_sky: "Probabilidad de cielo despejado: {p}.",
    origin_title: "De dónde sale cada número",
    origin_table: `<thead><tr><th>Lo que ves</th><th>Cómo se calcula</th><th>Aprendido de</th></tr></thead><tbody>
<tr><td>% de cada hora</td><td>Probabilidad de cúpula cerrada por <b>humedad o viento</b>: une el modelo de humedad y el de viento de esa hora</td><td>Estación del NOT, minuto a minuto (regla de humedad y viento de más de 80 km/h)</td></tr>
<tr><td>Cúpula cerrada (h)</td><td>La suma de los % de todas las horas: las horas de cierre que se esperan</td><td>Lo mismo</td></tr>
<tr><td>Aviso «Viento»</td><td>El modelo de viento pasa de su umbral. Avisa casi siempre que hay viento fuerte, pero da muchas falsas alarmas</td><td>Viento medido en la cumbre</td></tr>
<tr><td>Aviso «Hielo»</td><td>Regla sencilla: 0,5 °C o menos con humedad alta</td><td>—</td></tr>
<tr><td>Horas perdidas por meteo</td><td>Otro modelo, para la noche entera, con todos los motivos (humedad, hielo, viento, nubes, calima)</td><td>Partes del Liverpool Telescope</td></tr>
<tr><td>Cielo despejado</td><td>Otro modelo, para la noche entera: si se observa, ¿estará el cielo limpio? Solo por noche: los partes no dicen la hora</td><td>Partes del Liverpool Telescope</td></tr>
<tr><td>Seeing</td><td>Modelos de nitidez, de la noche y de cada hora. No cambian el riesgo de cierre</td><td>Monitor de seeing R2D2</td></tr>
<tr><td>Luna</td><td>Cálculo astronómico, no es un pronóstico</td><td>—</td></tr>
</tbody>`,
    eval_plain: "Resumen, en palabras sencillas",
    eval_plain_note: "Todo con noches y horas de 2024–2026 que los modelos no vieron al aprender. «Acierta 7 de cada 10» = de cada 10 veces que dice «sí», 7 son verdad. «Detecta 8 de cada 10» = de cada 10 casos reales, avisó de 8.",
    eval_technical: "Ver las cifras técnicas (para especialistas)",
    glossary: `<ul>
<li><b>Brier:</b> error medio de una probabilidad (0 es perfecto). <b>Acierto vs. clima:</b> cuánto error quita frente a decir siempre «lo normal del mes» (0 = nada, 1 = todo).</li>
<li><b>AUC:</b> lo bien que ordena casos (0,5 = al azar, 1 = perfecto).</li>
<li><b>MAE:</b> error medio, en las mismas unidades (segundos de arco u horas). <b>RMSE:</b> parecido, pero castiga más los errores grandes.</li>
</ul>`,
    plain_col_what: "Qué se predice", plain_col_ours: "Nuestro modelo", plain_col_ref: "Lo más sencillo que hay que batir",
    plain_yesno: "acierta {r} de cada 10; detecta {c} de cada 10",
    plain_number: "se equivoca de media {v}",
    plain_warning: "detecta {c} de cada 10 horas con viento fuerte, pero solo {r} de cada 10 avisos se cumplen",
    plain_refs: { raw: "Previsión meteorológica sola", precasting: "Mirar la humedad justo antes de la noche", persistence: "Decir «igual que anoche»", climatology: "Decir «lo normal del mes»", none: "La previsión sola no avisa nunca (su viento es demasiado flojo)" },
    plain_what: { hour: "Cúpula cerrada en cada hora", night: "Que la cúpula cierre esa noche", sky: "Cielo despejado", seeing: "Seeing de la noche", lost: "Horas perdidas por meteo", wind: "Aviso de viento" },
    tile_closed: "Cúpula cerrada (previsto)", tile_any: "Que cierre en algún momento: {p}",
    tile_lost_wht: "Solo por humedad (criterio WHT): {h} h",
    tile_sky: "Cielo despejado (fotométrico)", tile_sky_help: "Probabilidad de cielo limpio de nubes y polvo si se observa",
    sky_low: "Probable", sky_medium: "Incierto", sky_high: "Poco probable",
    seeing_better: "Mejor que el {p} % de las noches del Roque",
    moonlight_yes: "sí ({p})", moonlight_no: "no",
    eval_lt: "Horas perdidas por meteo (partes del Liverpool Telescope)",
    eval_lt_text: "Horas de noche perdidas por meteo que anota cada noche el Liverpool Telescope, robótico, en el Roque (cuenta humedad, hielo, viento, nubes y calima). Prueba 2024–2026.",
    eval_sky: "Cielo fotométrico (despejado)",
    eval_sky_text: "Noches en que el Liverpool observó: ¿el cielo fue fotométrico (sin nubes ni polvo que alteren el brillo de las estrellas)? Prueba 2024–2026.",
    tile_closure: "Riesgo de cerrar (1 h o más)", tile_seeing: "Seeing (nitidez)", tile_lost: "Horas perdidas por meteo", tile_moon: "Luna",
    tile_usual: "Lo normal en {month}: {v}",
    moon_tile: "{phase}. {when}. Noche sin Luna: {dark} h",
    note_provisional_short: "provisional hasta las {time}, cuando se añade la estación del NOT",
    note_final_short: "definitivo, con la estación del NOT antes de la noche",
    sum_risk: "Riesgo {level} de cerrar por humedad ({p} para la noche).",
    sum_flat: "Parecido toda la noche.",
    sum_peak: "Lo más probable hacia las {time} ({p}).",
    sum_warn: "Avisos: {list}.",
    sum_warn_item: "{name} ({n} de {total} h)",
    sum_nowarn: "Sin avisos de viento ni de hielo.",
    hours_title: "Hora a hora",
    hours_text: "<b>Previsión sola</b>: la humedad del modelo meteorológico leída tal cual (≥ 90 % = cerrar); en la cumbre casi siempre sale demasiado húmeda. <b>Nuestro pronóstico</b>: la probabilidad de cúpula cerrada por humedad o viento, corregida con 7 años de datos de la cumbre.",
    col_hour: "Hora", col_raw: "Previsión sola", col_ours: "Nuestro pronóstico", col_seeing_h: "Seeing", col_warn: "Avisos", col_moon: "Luz de Luna",
    raw_closes: "cerraría", raw_opens: "abriría",
    warn_wind: "Viento", warn_ice: "Hielo",
    moon_up: "arriba",
    warnings_more: "Qué significa cada aviso",
    warnings_text: `<ul>
<li><b>Viento:</b> rachas de más de 80 km/h, el límite de cierre del telescopio INT en el Roque. Lo da un modelo por horas entrenado con el viento medido en la cumbre: en 2024–2026 avisó en 9 de cada 10 horas con viento de cierre, pero 5 de cada 6 avisos fueron falsas alarmas.</li>
<li><b>Hielo:</b> previsión de 0,5 °C o menos con humedad alta, o hielo en la estación del NOT en las últimas 24 h. Regla sencilla, sin evaluar.</li>
<li><b>Luz de Luna:</b> la Luna está sobre el horizonte en esa hora; su luz aclara el cielo y molesta para objetos débiles. No cierra la cúpula.</li>
<li><b>Seeing:</b> nitidez prevista para cada hora. No cierra la cúpula.</li>
</ul>`,
    how_short: `<li><b>La previsión sola falla en la cumbre.</b> El modelo meteorológico ve la montaña más baja de lo que es, dentro del mar de nubes: en 2024–2026 dijo «cerrar» 8 de cada 10 noches y solo se cerró 1 de cada 4.</li>
<li><b>Por eso aprendemos de los datos.</b> Comparando 7 años de previsiones con lo que midió la estación del NOT en la cumbre, el modelo aprende a corregir la previsión. Usa también la estación justo antes de la noche y lo que pasó anoche.</li>
<li><b>Comprobado con noches que nunca vio (2024–2026).</b> Hora a hora, cuando la previsión sola dice «cerrar» se equivoca 8 de cada 10 veces; nuestro modelo, 1 de cada 4.</li>`,
    how_note: "La humedad, el viento, el hielo y el polvo cierran la cúpula; el seeing no, solo dice si la noche será buena. Las horas perdidas y el cielo despejado se aprenden de los partes del Liverpool Telescope, que cuenta todos los motivos; el cierre por horas, de la humedad. Viento y hielo son avisos.",
    fold_eval: "¿Funciona? La evaluación completa",
    fold_model: "Detalles del modelo",
    fold_live: "La cumbre en directo",
    eval_hourly: "Hora a hora: ¿cuándo acierta un «cerrar»?",
    eval_hourly_text: "Horas de noche de 2024–2026. «Detectadas»: horas en que de verdad pasó y se avisó. «Falsas alarmas»: avisos que no se cumplieron. Nuestro modelo dice «cerrar» cuando la probabilidad pasa del 50 %.",
    col_event: "Qué", col_hits: "Detectadas", col_far2: "Falsas alarmas",
    raw_alone: "Previsión sola", model_final: "Nuestro modelo (definitivo)", model_provisional: "Nuestro modelo (provisional)",
    events: { closed: "Cierre por humedad", windy: "Viento de cierre", shut: "Cúpula cerrada (humedad o viento)" },
    why_title: "Las entradas de esta noche",
    why_text: "Las entradas del modelo para esta noche. La más influyente, cuando está disponible, es la humedad de la estación justo antes de la noche.",
    hourly_title: "Pronóstico hora a hora",
    hourly_text: "Modelo ECMWF IFS (9 km) en el punto del observatorio, vía Open-Meteo. Zona sombreada: noche astronómica. El punto de rejilla suele salir más húmedo y con menos viento que la cumbre; el modelo aprende a corregirlo.",
    rh: "Humedad (%)", wind: "Viento (m/s)", cloud: "Nubes (%)", limit90: "Límite de cierre (90 %)",
    station_title: "Últimas 24 horas en la cumbre",
    station_text: "Estación del NOT (medias de 10 min). Última medida: {time} hora canaria — humedad {rh} %, viento {wind} m/s, {temp} °C.",
    gtc_title: "Panel en directo de la estación del GTC",
    gtc_text: "Valores publicados por atmosportal ({time} UTC). Los colores de estado son los de la propia web.",
    gtc_none: "Sin lectura reciente del panel del GTC.",
    status_ok: "ok", status_warning: "aviso",
    eval_title: "¿Funciona? Evaluación honesta",
    eval_text: "Los modelos se entrenaron con 2017–2022, se ajustaron con 2023 y se prueban aquí con 2024–2026, noches que no vieron nunca. Usan los pronósticos archivados que se emitieron entonces, no la meteo medida después. Cada modelo se compara con métodos de referencia sencillos que debe batir.",
    eval_closure: "Cierre de cúpula: acierto frente a «lo normal del mes»",
    eval_recent: "Últimas 60 noches de la prueba",
    eval_recent_text: "Barras: probabilidad de cierre que dio el modelo. Puntos naranjas: noches en las que la cúpula se cerró de verdad (≥ 1 h).",
    eval_seeing: "Seeing: pronóstico frente a lo medido (R2D2, ING)",
    eval_lost: "Horas perdidas (contabilidad del WHT)",
    eval_lost_text: "Se prueba en 2026. En 2024–2025 la contabilidad del WHT da por observadas muchas noches con la cúpula cerrada, así que esos años solo se muestran para comparar.",
    track_title: "Historial en directo",
    track_text: "Cada pronóstico emitido por esta web frente a lo que pasó. Se llena noche a noche.",
    track_empty: "Todavía no hay noches terminadas con pronóstico emitido.",
    col_method: "Método", col_nights: "Noches", col_brier: "Brier", col_skill: "Acierto vs. clima", col_auc: "AUC",
    col_hit: "Cierres avisados", col_far: "Falsas alarmas", col_rmse: "RMSE", col_mae: "MAE",
    col_night: "Noche", col_mode: "Tipo", col_p: "Prob. cierre", col_fc_h: "Cierre previsto", col_real_h: "Cierre real",
    col_fc_seeing: "Seeing previsto", col_real_seeing: "Seeing real", col_set: "Prueba",
    skill_axis: "Acierto frente a la climatología (Brier skill; más es mejor)",
    predicted: "Pronóstico", measured: "Medido", closed_real: "Cerrada (real)", probability: "Probabilidad",
    how_title: "Cómo funciona",
    how_text: `<ul>
<li><b>Etiquetas:</b> la cúpula «se cierra» con la regla pública del NOT (humedad ≥ 90 %, reabrir tras 20 min por debajo), reconstruida minuto a minuto desde 1997; el seeing es la mediana nocturna del monitor R2D2 del ING; las horas perdidas son las de la contabilidad nocturna del WHT.</li>
<li><b>Entradas:</b> el pronóstico ECMWF de la noche, la estación del NOT en las 2 h previas, lo que pasó anoche y la época del año; para el seeing, además, el viento a 200 hPa (~12 km, la corriente en chorro) del modelo GFS, archivado desde marzo de 2021. Nada que no se supiera al empezar la noche.</li>
<li><b>Modelos:</b> gradient boosting (scikit-learn) para la probabilidad de cierre, las horas de cierre y el seeing (en escala logarítmica); una recta calibrada convierte horas de cierre en horas perdidas del WHT.</li>
<li><b>Referencias:</b> climatología (lo normal del mes), persistencia (igual que anoche) y «precasting» (las condiciones justo antes de la noche). Si un modelo no las bate, no aporta.</li>
<li><b>Límites:</b> la etiqueta de cierre solo mira la humedad (no viento, polvo ni hielo) y ninguna etiqueta son decisiones reales de operación del GTC.</li>
<li><b>Datos en vivo:</b> además se publican como entidades FIWARE (<code>WeatherObserved</code>, <code>WeatherForecast</code>) en un Orion Context Broker local, con histórico en QuantumLeap/CrateDB y paneles de Grafana en español e inglés.</li>
</ul>`,
    data_title: "En qué datos se basa todo",
    data_intro: "Todos los datos son reales y públicos; no hay nada simulado. Esto es lo que se usa, de dónde sale y para qué.",
    data_html: `<h3>Histórico: para entrenar y evaluar los modelos</h3>
<div class="table-wrap"><table class="text"><thead><tr><th>Fuente</th><th>Qué da</th><th>Periodo</th><th>Para qué se usa</th></tr></thead><tbody>
<tr><td><a href="https://www.not.iac.es/weather/archive/met/index.php">Estación meteorológica del NOT</a> (Nordic Optical Telescope, en el Roque)</td><td>Humedad, temperatura, presión y viento, cada minuto (cada 5 min hasta 2006)</td><td>1997 → hoy</td><td>Saber cuándo se cerró la cúpula (regla de humedad, ver abajo) y las entradas «2 h antes de la noche»</td></tr>
<tr><td><a href="https://astro.ing.iac.es/seeing/">Monitor de seeing R2D2</a> (Isaac Newton Group)</td><td>Seeing medido cada 15–35 s de noche</td><td>sep 2018 → hoy</td><td>El seeing real de cada noche (mediana)</td></tr>
<tr><td><a href="https://a.ing.iac.es/weather/archive/">Contabilidad nocturna del WHT</a> (Isaac Newton Group)</td><td>Horas perdidas por meteo y por averías en el telescopio William Herschel</td><td>2007 → hoy</td><td>Las horas perdidas reales. Solo años fiables (2017, 2018, 2023 y 2026): otros años dan por observadas noches con la cúpula cerrada</td></tr>
<tr><td>Pronósticos archivados del modelo ECMWF IFS (<a href="https://open-meteo.com/">Open-Meteo</a>)</td><td>El pronóstico hora a hora en el observatorio tal como se emitió entonces (no la meteo que hubo después)</td><td>2017 → hoy (emitidos 24 h antes: 2025 → hoy)</td><td>Entradas de los modelos</td></tr>
<tr><td>Pronósticos archivados del modelo NOAA GFS (<a href="https://open-meteo.com/">Open-Meteo</a>)</td><td>Viento a 200 hPa (~12 km, corriente en chorro) y a 750 hPa (~2,5 km, altura de la cumbre)</td><td>mar 2021 → hoy</td><td>Seeing y viento por horas</td></tr>
<tr><td><a href="https://telescope.livjm.ac.uk/Reports/">Partes nocturnos del Liverpool Telescope</a> (robótico, en el Roque)</td><td>Horas observadas, perdidas por meteo y por averías, y el motivo («humedad», «hielo», «calima», «fotométrica»…)</td><td>2007 → hoy</td><td>Horas perdidas por meteo y cielo fotométrico</td></tr>
</tbody></table></div>
<h3>En directo: para el pronóstico de esta noche</h3>
<div class="table-wrap"><table class="text"><thead><tr><th>Fuente</th><th>Cada cuánto</th><th>Para qué se usa</th></tr></thead><tbody>
<tr><td>Pronóstico de hoy de ECMWF y GFS (Open-Meteo)</td><td>Cada hora</td><td>Entradas del pronóstico de esta noche y gráfica hora a hora</td></tr>
<tr><td>Estación del NOT, últimas 36 h</td><td>Cada hora</td><td>Las 2 h antes de la noche (pronóstico definitivo), cuánto se cerró anoche y la gráfica de 24 h</td></tr>
<tr><td>Seeing R2D2 de los últimos días</td><td>Cada hora</td><td>El seeing de anoche</td></tr>
<tr><td>Parte de anoche del Liverpool Telescope</td><td>Una vez al día</td><td>Horas perdidas y cielo despejado de anoche</td></tr>
<tr><td><a href="https://atmosportal.gtc.iac.es/">Panel de la estación del GTC</a> (atmosportal)</td><td>Cada 15 min</td><td>Se muestra en la web y en FIWARE/Grafana; no entra en los modelos (solo publica el último mes)</td></tr>
<tr><td>Series del GTC (30 días) y del <a href="https://tngweb.tng.iac.es/weather">TNG</a> (24 h, polvo por tamaño)</td><td>Cada semana / cada día</td><td>Se guardan para acumular histórico; todavía no entran en los modelos</td></tr>
</tbody></table></div>
<h3>Calculado en este proyecto</h3>
<ul>
<li><b>Cierre de cúpula:</b> no existe un registro público de cuándo cierra el GTC. Se reconstruye minuto a minuto desde 1997 con la regla pública del NOT: se cierra con humedad ≥ 90 % y se reabre tras 20 minutos seguidos por debajo.</li>
<li><b>Noche astronómica y Luna:</b> posición del Sol y de la Luna con fórmulas astronómicas propias (comprobadas con la librería PyEphem).</li>
</ul>
<p class="muted small">Las descargas se identifican, esperan al menos 2 s entre peticiones y solo usan páginas enlazadas desde las webs públicas.</p>`,
    sources_title: "Referencias científicas",
    sources_text: `<ul>
<li>Abárzuza et al. 2025, RNAAS 9(2) — random forest para el seeing del Roque a partir de la estación meteorológica.</li>
<li>de Sepibus, Masciadri et al. 2026, arXiv:2607.12900 — persistencia y precasting como métodos de referencia mínimos.</li>
<li>Lombardi et al. 2007, arXiv:astro-ph/0702570 — viento y humedad frente al seeing en el Roque.</li>
</ul>
<p>Las fuentes de datos están en «En qué datos se basa todo», al principio de la página.</p>`,
    updated: "Pronóstico emitido: {time} hora canaria. Evaluación generada: {eval}.",
    footer: "Roque Night Forecast · proyecto independiente · código y metodología en GitHub (saimonx/roque-night-forecast).",
    months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    na: "—",
    methods: {
      "climatology (month)": "Climatología (lo normal del mes)",
      "climatology (month, 2010-2018)": "Climatología (mes, 2010–2018)",
      "persistence (last night)": "Persistencia (igual que anoche)",
      "precasting (humidity before night >= 90 %)": "Precasting (humedad antes de la noche ≥ 90 %)",
      "forecast rule (forecast humidity >= 95 %)": "Regla del pronóstico (humedad prevista ≥ 95 %)",
      "gradient boosting": "Gradient boosting (nuestro modelo)",
      "logistic regression": "Regresión logística",
      "linear regression": "Regresión lineal (log)",
      "gradient boosting, forecast only": "Gradient boosting, solo pronóstico",
      "gradient boosting, no jet stream": "Gradient boosting, sin corriente en chorro",
      "calibrated closure forecast": "Pronóstico de cierre calibrado (nuestro modelo)",
      "raw forecast, read literally (cloud < 20 %)": "Previsión sola (nubes previstas < 20 %)",
    },
    sets: { "reliable test year (2026)": "2026 (fiable)", "suspect years 2024-2025 (comparison only)": "2024–2025 (dudoso, solo comparación)" },
    features: {
      fc_rh_mean: ["Humedad prevista (media)", "%"], fc_rh_max: ["Humedad prevista (máx.)", "%"],
      fc_dew_spread_min: ["Margen mínimo al punto de rocío", "°C"], fc_temp_mean: ["Temperatura prevista", "°C"],
      fc_temp_drop: ["Enfriamiento previsto", "°C"], fc_wind_mean: ["Viento previsto (medio)", "m/s"],
      fc_wind_max: ["Viento previsto (máx.)", "m/s"], fc_wind_u: ["Viento hacia el este", "m/s"],
      fc_wind_v: ["Viento hacia el norte", "m/s"], fc_cloud_mean: ["Nubes previstas (media)", "%"],
      fc_cloud_max: ["Nubes previstas (máx.)", "%"], fc_precip_sum: ["Precipitación prevista", "mm"],
      fc_pressure_mean: ["Presión prevista", "hPa"], fc_jet_mean: ["Corriente en chorro (200 hPa)", "m/s"],
      pre_humidity_mean: ["Humedad NOT, 2 h antes (media)", "%"], pre_humidity_max: ["Humedad NOT, 2 h antes (máx.)", "%"],
      pre_wind_mean: ["Viento NOT, 2 h antes", "m/s"], pre_pressure_mean: ["Presión NOT, 2 h antes", "hPa"],
      prev_dome_closed_frac: ["Cúpula cerrada anoche", "%"], prev_seeing_median: ["Seeing de anoche", "″"],
      doy_sin: ["Época del año (seno)", ""], doy_cos: ["Época del año (coseno)", ""],
    },
  },

  en: {
    subtitle: "Tonight's forecast for the Roque de los Muchachos Observatory (La Palma)",
    theme: "Toggle light/dark theme",
    independent: "Independent portfolio project, not affiliated with GRANTECAN or any observatory. Real, public data; not an operational tool.",
    tonight: "Tonight",
    night_of: "Night of {date}",
    window: "Astronomical night (Sun 18° below the horizon): {start} – {end} Canary time · {hours} h",
    mode_provisional: "Provisional",
    mode_final: "Final",
    note_provisional: "Computed from the weather forecast, last night's outcome and the time of year only. From {time} (start of the night) the 2 hours before the night at the NOT station are added and the forecast becomes final.",
    note_final: "Computed from the weather forecast, the NOT station in the 2 hours before the night, last night's outcome and the time of year: the same model that was tested on the 2024–2026 nights.",
    closure_title: "Risk of having to close the dome",
    closure_help: "“Close” = at least 1 hour with the dome closed by humidity, using the NOT's public rule: close at humidity ≥ 90 % and reopen after 20 minutes in a row below it.",
    closure_more: "What it takes into account",
    closure_more_text: `<ul>
<li><b>The night's forecast</b> (ECMWF): humidity, margin to the dew point, cloud, rain, wind, temperature and pressure.</li>
<li><b>The NOT station in the 2 h before the night</b>: the strongest input. It only exists once the night starts; before that, the forecast is provisional and computed without it.</li>
<li><b>Last night</b>: how long the dome was closed (weather comes in spells).</li>
<li><b>Time of year.</b></li>
</ul>
<p>Gradient-boosting model trained on the 2017–2023 nights. It does not cover closures for wind, dust or ice, and these are not real GTC decisions.</p>`,
    seeing_title: "Forecast seeing (sharpness)",
    lost_title: "Hours lost to weather",
    risk_low: "Low", risk_medium: "Medium", risk_high: "High",
    closure_ref: "Usual for {month}: {clim}. If last night repeated: {pers}.{prec}",
    closure_prec: " Rule \"already humid before the night\": {p}.",
    closed_hours: "Forecast hours with the dome closed: {h} h",
    seeing_excellent: "Excellent", seeing_good: "Good", seeing_average: "Average", seeing_poor: "Poor",
    seeing_ref: "Usual for {month}: {clim}″",
    seeing_help: "Night median in arcseconds (″). Lower is better: 0.5″ excellent, 1.5″ poor.",
    lost_of: "of a {h} h night",
    lost_ref: "Usual for {month} (WHT 2010–2018): {clim} h",
    lost_help: "As booked in the nightly log of the WHT telescope (ING): 0.85 × forecast closure hours.",
    moon_text: "Moon {pct} lit ({phase}). {when}. Dark time without the Moon: {dark} of {total} h.",
    moon_rises: "Rises at {time}", moon_sets: "Sets at {time}",
    moon_all_night: "Above the horizon all night", moon_none: "Does not rise during the night",
    moon_phases: { new: "new Moon", waxing_crescent: "waxing crescent", first_quarter: "first quarter", waxing_gibbous: "waxing gibbous",
      full: "full Moon", waning_gibbous: "waning gibbous", last_quarter: "last quarter", waning_crescent: "waning crescent" },
    moon_help: "The Moon does not change the closure risk or the seeing, but it brightens the sky: faint targets need dark time. Own computation of its position (~0.3° accuracy).",
    importance_closure: "What matters most: dome closure",
    importance_seeing: "What matters most: seeing",
    importance_text: "Permutation importance on the test nights (2024–2026): how much worse the model gets when one input is shuffled, as a share of the total. Top 8 inputs.",
    eval_reliability: "Can the probabilities be trusted?",
    reliability_text: "Test nights grouped by the probability given (10 % bins). When the model says 70 %, the dome should close on about 7 in 10 of those nights. Recalibration (isotonic regression) was tried with a year-by-year cross-validation on 2017–2023: the Brier score went from {raw} to {iso}, no improvement, so it is not applied. In 2024–2026, between 40 % and 90 %, the dome closed somewhat less often than the model said: the live track record keeps an eye on it.",
    rel_x: "Forecast probability", rel_y: "Actually closed", rel_model: "Gradient boosting (test nights)", rel_perfect: "Perfect calibration",
    flow: [
      ["Real data", "NOT weather minute by minute since 1997, R2D2 seeing, the WHT night log and archived forecasts (ECMWF and GFS)."],
      ["One row per night", "Only what was known when the night started: forecast, station 2 h before, last night and the time of year."],
      ["Models", "Gradient boosting trained on 2017–2022 and tuned on 2023."],
      ["Honest test", "Unseen 2024–2026 nights, against climatology, persistence and precasting."],
      ["Live", "Every hour: tonight's forecast, FIWARE entities, Grafana and this page."],
    ],
    tile_of_night: "{level} risk, of a {h} h night",
    mode_box_provisional: "<b>Provisional forecast.</b> Before the night starts we only know the weather forecast, last night's outcome and the time of year. At {time} the summit station's readings just before the night are added (they help the most) and it becomes <b>final</b>. When it says \"close\", it is right {prov} % of the time when provisional and {fin} % when final.",
    mode_box_final: "<b>Final forecast.</b> On top of the weather forecast, last night and the time of year, it now uses what the summit station measured just before the night, which helps the most. When it says \"close\", it is right {fin} % of the time (provisional: {prov} %).",
    sum_hours: "The dome is expected to be closed for about {h} of the {total} night hours, for humidity or wind.",
    sum_sky: "Chance of a clear sky: {p}.",
    origin_title: "Where each number comes from",
    origin_table: `<thead><tr><th>What you see</th><th>How it is computed</th><th>Learnt from</th></tr></thead><tbody>
<tr><td>% for each hour</td><td>Chance that the dome is shut for <b>humidity or wind</b>: joins the humidity model and the wind model for that hour</td><td>NOT station, minute by minute (humidity rule and wind above 80 km/h)</td></tr>
<tr><td>Dome closed (h)</td><td>The sum of all hourly %: the closed hours to expect</td><td>Same</td></tr>
<tr><td>"Wind" warning</td><td>The wind model goes past its threshold. It warns almost every time there is strong wind, but with many false alarms</td><td>Wind measured at the summit</td></tr>
<tr><td>"Ice" warning</td><td>Simple rule: 0.5 °C or less with high humidity</td><td>—</td></tr>
<tr><td>Hours lost to weather</td><td>Another model, for the whole night, with every reason (humidity, ice, wind, cloud, dust)</td><td>Liverpool Telescope reports</td></tr>
<tr><td>Clear sky</td><td>Another model, for the whole night: if observing, will the sky be clean? Per night only: the reports do not give the hour</td><td>Liverpool Telescope reports</td></tr>
<tr><td>Seeing</td><td>Sharpness models, for the night and for each hour. They do not change the closing risk</td><td>R2D2 seeing monitor</td></tr>
<tr><td>Moon</td><td>Astronomical computation, not a forecast</td><td>—</td></tr>
</tbody>`,
    eval_plain: "Summary, in plain words",
    eval_plain_note: "All on 2024–2026 nights and hours the models never saw while learning. \"Right 7 in 10\" = of every 10 times it says \"yes\", 7 are true. \"Catches 8 in 10\" = of every 10 real cases, it warned about 8.",
    eval_technical: "Show the technical figures (for specialists)",
    glossary: `<ul>
<li><b>Brier:</b> average error of a probability (0 is perfect). <b>Skill vs. climate:</b> how much error it removes against always saying "the usual for the month" (0 = none, 1 = all).</li>
<li><b>AUC:</b> how well it ranks cases (0.5 = random, 1 = perfect).</li>
<li><b>MAE:</b> average error, in the same units (arcseconds or hours). <b>RMSE:</b> similar, but punishes big errors more.</li>
</ul>`,
    plain_col_what: "What is forecast", plain_col_ours: "Our model", plain_col_ref: "The simplest thing to beat",
    plain_yesno: "right {r} in 10; catches {c} in 10",
    plain_number: "off by {v} on average",
    plain_warning: "catches {c} in 10 hours with strong wind, but only {r} in 10 warnings come true",
    plain_refs: { raw: "Raw weather forecast", precasting: "Looking at humidity just before the night", persistence: "Saying \"same as last night\"", climatology: "Saying \"the usual for the month\"", none: "The raw forecast never warns (its wind is far too weak)" },
    plain_what: { hour: "Dome closed each hour", night: "Dome closing that night", sky: "Clear sky", seeing: "Seeing of the night", lost: "Hours lost to weather", wind: "Wind warning" },
    tile_closed: "Dome closed (expected)", tile_any: "Closing at some point: {p}",
    tile_lost_wht: "Humidity only (WHT criterion): {h} h",
    tile_sky: "Clear sky (photometric)", tile_sky_help: "Probability of a sky free of cloud and dust when observing",
    sky_low: "Likely", sky_medium: "Uncertain", sky_high: "Unlikely",
    seeing_better: "Better than {p} % of Roque nights",
    moonlight_yes: "yes ({p})", moonlight_no: "no",
    eval_lt: "Hours lost to weather (Liverpool Telescope reports)",
    eval_lt_text: "Night hours lost to weather as booked every night by the robotic Liverpool Telescope on the Roque (humidity, ice, wind, cloud and dust). Test 2024–2026.",
    eval_sky: "Photometric (clear) sky",
    eval_sky_text: "Nights the Liverpool Telescope observed: was the sky photometric (no cloud or dust changing the brightness of the stars)? Test 2024–2026.",
    tile_closure: "Risk of closing (1 h or more)", tile_seeing: "Seeing (sharpness)", tile_lost: "Hours lost to weather", tile_moon: "Moon",
    tile_usual: "Usual for {month}: {v}",
    moon_tile: "{phase}. {when}. Moonless night: {dark} h",
    note_provisional_short: "provisional until {time}, when the NOT station is added",
    note_final_short: "final, with the NOT station before the night",
    sum_risk: "Risk of closing for humidity: {level} ({p} for the night).",
    sum_flat: "About the same all night.",
    sum_peak: "Most likely around {time} ({p}).",
    sum_warn: "Warnings: {list}.",
    sum_warn_item: "{name} ({n} of {total} h)",
    sum_nowarn: "No wind or ice warnings.",
    hours_title: "Hour by hour",
    hours_text: "<b>Raw forecast</b>: the weather model's humidity read literally (≥ 90 % = close); at the summit it is almost always too wet. <b>Our forecast</b>: the probability that the dome is shut for humidity or wind, corrected with 7 years of summit data.",
    col_hour: "Hour", col_raw: "Raw forecast", col_ours: "Our forecast", col_seeing_h: "Seeing", col_warn: "Warnings", col_moon: "Moonlight",
    raw_closes: "would close", raw_opens: "would open",
    warn_wind: "Wind", warn_ice: "Ice",
    moon_up: "up",
    warnings_more: "What each warning means",
    warnings_text: `<ul>
<li><b>Wind:</b> gusts above 80 km/h, the closing limit of the INT telescope on the Roque. It comes from an hourly model trained on the wind measured at the summit: in 2024–2026 it warned in 9 of 10 hours with closing wind, but 5 of 6 warnings were false alarms.</li>
<li><b>Ice:</b> forecast of 0.5 °C or less with high humidity, or ice at the NOT station in the last 24 h. Simple rule, not evaluated.</li>
<li><b>Moonlight:</b> the Moon is above the horizon that hour; its light brightens the sky and gets in the way of faint targets. It does not close the dome.</li>
<li><b>Seeing:</b> forecast sharpness for each hour. It does not close the dome.</li>
</ul>`,
    how_short: `<li><b>The raw forecast fails at the summit.</b> The weather model sees the mountain lower than it is, inside the sea of clouds: in 2024–2026 it said "close" on 8 of 10 nights and only 1 in 4 closed.</li>
<li><b>So we learn from the data.</b> Comparing 7 years of forecasts with what the NOT station measured at the summit, the model learns to correct the forecast. It also uses the station just before the night and last night's outcome.</li>
<li><b>Tested on nights it never saw (2024–2026).</b> Hour by hour, when the raw forecast says "close" it is wrong 8 times in 10; our model, 1 in 4.</li>`,
    how_note: "Humidity, wind, ice and dust close the dome; seeing does not, it only says how good the night will be. Hours lost and clear sky are learnt from the Liverpool Telescope reports, which count every reason; hourly closure, from humidity. Wind and ice are warnings.",
    fold_eval: "Does it work? The full evaluation",
    fold_model: "Model details",
    fold_live: "The summit, live",
    eval_hourly: "Hour by hour: when is a \"close\" right?",
    eval_hourly_text: "Night hours of 2024–2026. \"Caught\": hours when it really happened and a warning was given. \"False alarms\": warnings that did not happen. Our model says \"close\" when its probability is above 50 %.",
    col_event: "What", col_hits: "Caught", col_far2: "False alarms",
    raw_alone: "Raw forecast", model_final: "Our model (final)", model_provisional: "Our model (provisional)",
    events: { closed: "Closure for humidity", windy: "Closing wind", shut: "Dome shut (humidity or wind)" },
    why_title: "Tonight's inputs",
    why_text: "The model inputs for tonight. When available, the most influential is the station humidity just before the night.",
    hourly_title: "Hour-by-hour forecast",
    hourly_text: "ECMWF IFS model (9 km) at the observatory, through Open-Meteo. Shaded: astronomical night. The grid point is usually wetter and calmer than the summit; the model learns to correct that.",
    rh: "Humidity (%)", wind: "Wind (m/s)", cloud: "Cloud (%)", limit90: "Closing limit (90 %)",
    station_title: "Last 24 hours on the summit",
    station_text: "NOT weather station (10-minute means). Latest reading: {time} Canary time — humidity {rh} %, wind {wind} m/s, {temp} °C.",
    gtc_title: "Live panel of the GTC weather station",
    gtc_text: "Values published by atmosportal ({time} UTC). Status colours are the site's own.",
    gtc_none: "No recent reading of the GTC panel.",
    status_ok: "ok", status_warning: "warning",
    eval_title: "Does it work? An honest evaluation",
    eval_text: "The models were trained on 2017–2022, tuned on 2023 and are tested here on 2024–2026, nights they never saw. They use the archived forecasts issued at the time, not the weather measured afterwards. Every model is compared with simple reference methods it has to beat.",
    eval_closure: "Dome closure: skill against \"the usual for the month\"",
    eval_recent: "Last 60 test nights",
    eval_recent_text: "Bars: closure probability given by the model. Orange dots: nights when the dome really closed (≥ 1 h).",
    eval_seeing: "Seeing: forecast against measured (R2D2, ING)",
    eval_lost: "Hours lost (WHT log)",
    eval_lost_text: "Tested on 2026. In 2024–2025 the WHT log books many closed nights as observed, so those years are shown for comparison only.",
    track_title: "Live track record",
    track_text: "Every forecast issued by this page against what happened. It fills up night by night.",
    track_empty: "No finished night with an issued forecast yet.",
    col_method: "Method", col_nights: "Nights", col_brier: "Brier", col_skill: "Skill vs. climate", col_auc: "AUC",
    col_hit: "Closures warned", col_far: "False alarms", col_rmse: "RMSE", col_mae: "MAE",
    col_night: "Night", col_mode: "Type", col_p: "Closure prob.", col_fc_h: "Forecast closed", col_real_h: "Actually closed",
    col_fc_seeing: "Forecast seeing", col_real_seeing: "Measured seeing", col_set: "Test set",
    skill_axis: "Skill against climatology (Brier skill; higher is better)",
    predicted: "Forecast", measured: "Measured", closed_real: "Closed (actual)", probability: "Probability",
    how_title: "How it works",
    how_text: `<ul>
<li><b>Labels:</b> the dome "closes" by the NOT's public rule (humidity ≥ 90 %, reopen after 20 min below), rebuilt minute by minute since 1997; seeing is the nightly median of the ING R2D2 monitor; hours lost come from the WHT nightly log.</li>
<li><b>Inputs:</b> the ECMWF forecast for the night, the NOT station in the 2 h before it, last night's outcome and the time of year; for the seeing, also the 200 hPa wind (~12 km, the jet stream) from the GFS model, archived since March 2021. Nothing that was not known when the night started.</li>
<li><b>Models:</b> gradient boosting (scikit-learn) for the closure probability, the closure hours and the seeing (on a log scale); a calibrated line turns closure hours into WHT hours lost.</li>
<li><b>References:</b> climatology (the usual for the month), persistence (same as last night) and precasting (the conditions just before the night). A model that does not beat them adds nothing.</li>
<li><b>Limits:</b> the closure label only looks at humidity (not wind, dust or ice), and none of the labels are real GTC operating decisions.</li>
<li><b>Live data:</b> also published as FIWARE entities (<code>WeatherObserved</code>, <code>WeatherForecast</code>) in a local Orion Context Broker, with history in QuantumLeap/CrateDB and Grafana dashboards in Spanish and English.</li>
</ul>`,
    data_title: "The data everything is based on",
    data_intro: "All data are real and public; nothing is simulated. This is what is used, where it comes from and what for.",
    data_html: `<h3>Historical: to train and evaluate the models</h3>
<div class="table-wrap"><table class="text"><thead><tr><th>Source</th><th>What it gives</th><th>Period</th><th>Used for</th></tr></thead><tbody>
<tr><td><a href="https://www.not.iac.es/weather/archive/met/index.php">NOT weather station</a> (Nordic Optical Telescope, on the Roque)</td><td>Humidity, temperature, pressure and wind, every minute (every 5 min until 2006)</td><td>1997 → today</td><td>When the dome closed (humidity rule, see below) and the "2 h before the night" inputs</td></tr>
<tr><td><a href="https://astro.ing.iac.es/seeing/">R2D2 seeing monitor</a> (Isaac Newton Group)</td><td>Seeing measured every 15–35 s at night</td><td>Sep 2018 → today</td><td>The real seeing of each night (median)</td></tr>
<tr><td><a href="https://a.ing.iac.es/weather/archive/">WHT nightly log</a> (Isaac Newton Group)</td><td>Hours lost to weather and to faults on the William Herschel Telescope</td><td>2007 → today</td><td>The real hours lost. Reliable years only (2017, 2018, 2023 and 2026): other years book closed nights as observed</td></tr>
<tr><td>Archived ECMWF IFS forecasts (<a href="https://open-meteo.com/">Open-Meteo</a>)</td><td>The hourly forecast at the observatory as it was issued at the time (not the weather that happened)</td><td>2017 → today (issued 24 h earlier: 2025 → today)</td><td>Model inputs</td></tr>
<tr><td>Archived NOAA GFS forecasts (<a href="https://open-meteo.com/">Open-Meteo</a>)</td><td>Wind at 200 hPa (~12 km, jet stream) and 750 hPa (~2.5 km, summit height)</td><td>Mar 2021 → today</td><td>Seeing and hourly wind</td></tr>
<tr><td><a href="https://telescope.livjm.ac.uk/Reports/">Liverpool Telescope night reports</a> (robotic, on the Roque)</td><td>Hours observed, lost to weather and to faults, and the reason ("humidity", "ice", "calima", "photometric"…)</td><td>2007 → today</td><td>Hours lost to weather and photometric sky</td></tr>
</tbody></table></div>
<h3>Live: for tonight's forecast</h3>
<div class="table-wrap"><table class="text"><thead><tr><th>Source</th><th>How often</th><th>Used for</th></tr></thead><tbody>
<tr><td>Today's ECMWF and GFS forecast (Open-Meteo)</td><td>Every hour</td><td>Inputs of tonight's forecast and the hour-by-hour chart</td></tr>
<tr><td>NOT station, last 36 h</td><td>Every hour</td><td>The 2 h before the night (final forecast), how long the dome was closed last night, and the 24 h chart</td></tr>
<tr><td>R2D2 seeing of the last days</td><td>Every hour</td><td>Last night's seeing</td></tr>
<tr><td>Last night's Liverpool Telescope report</td><td>Once a day</td><td>Last night's hours lost and clear sky</td></tr>
<tr><td><a href="https://atmosportal.gtc.iac.es/">GTC weather station panel</a> (atmosportal)</td><td>Every 15 min</td><td>Shown on the page and in FIWARE/Grafana; not a model input (it only publishes the last month)</td></tr>
<tr><td>GTC series (30 days) and <a href="https://tngweb.tng.iac.es/weather">TNG</a> series (24 h, dust by particle size)</td><td>Weekly / daily</td><td>Stored to build up a history; not model inputs yet</td></tr>
</tbody></table></div>
<h3>Computed in this project</h3>
<ul>
<li><b>Dome closure:</b> there is no public record of when the GTC closes. It is rebuilt minute by minute since 1997 with the NOT's public rule: close at humidity ≥ 90 % and reopen after 20 minutes in a row below it.</li>
<li><b>Astronomical night and Moon:</b> Sun and Moon positions from our own astronomical formulas (checked against the PyEphem library).</li>
</ul>
<p class="muted small">Downloads identify themselves, wait at least 2 s between requests and only use pages linked from the public sites.</p>`,
    sources_title: "Scientific references",
    sources_text: `<ul>
<li>Abárzuza et al. 2025, RNAAS 9(2) — random forest for Roque seeing from the weather station.</li>
<li>de Sepibus, Masciadri et al. 2026, arXiv:2607.12900 — persistence and precasting as minimum reference methods.</li>
<li>Lombardi et al. 2007, arXiv:astro-ph/0702570 — wind and humidity against seeing at the Roque.</li>
</ul>
<p>The data sources are in "The data everything is based on", at the top of the page.</p>`,
    updated: "Forecast issued: {time} Canary time. Evaluation generated: {eval}.",
    footer: "Roque Night Forecast · independent project · code and method on GitHub (saimonx/roque-night-forecast).",
    months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    na: "—",
    methods: {
      "climatology (month)": "Climatology (usual for the month)",
      "climatology (month, 2010-2018)": "Climatology (month, 2010–2018)",
      "persistence (last night)": "Persistence (same as last night)",
      "precasting (humidity before night >= 90 %)": "Precasting (humidity before night ≥ 90 %)",
      "forecast rule (forecast humidity >= 95 %)": "Forecast rule (forecast humidity ≥ 95 %)",
      "gradient boosting": "Gradient boosting (our model)",
      "logistic regression": "Logistic regression",
      "linear regression": "Linear regression (log)",
      "gradient boosting, forecast only": "Gradient boosting, forecast only",
      "gradient boosting, no jet stream": "Gradient boosting, without the jet stream",
      "calibrated closure forecast": "Calibrated closure forecast (our model)",
      "raw forecast, read literally (cloud < 20 %)": "Raw forecast (forecast cloud < 20 %)",
    },
    sets: { "reliable test year (2026)": "2026 (reliable)", "suspect years 2024-2025 (comparison only)": "2024–2025 (suspect, comparison only)" },
    features: {
      fc_rh_mean: ["Forecast humidity (mean)", "%"], fc_rh_max: ["Forecast humidity (max)", "%"],
      fc_dew_spread_min: ["Smallest dew-point margin", "°C"], fc_temp_mean: ["Forecast temperature", "°C"],
      fc_temp_drop: ["Forecast cooling", "°C"], fc_wind_mean: ["Forecast wind (mean)", "m/s"],
      fc_wind_max: ["Forecast wind (max)", "m/s"], fc_wind_u: ["Wind towards the east", "m/s"],
      fc_wind_v: ["Wind towards the north", "m/s"], fc_cloud_mean: ["Forecast cloud (mean)", "%"],
      fc_cloud_max: ["Forecast cloud (max)", "%"], fc_precip_sum: ["Forecast precipitation", "mm"],
      fc_pressure_mean: ["Forecast pressure", "hPa"], fc_jet_mean: ["Jet stream (200 hPa)", "m/s"],
      pre_humidity_mean: ["NOT humidity, 2 h before (mean)", "%"], pre_humidity_max: ["NOT humidity, 2 h before (max)", "%"],
      pre_wind_mean: ["NOT wind, 2 h before", "m/s"], pre_pressure_mean: ["NOT pressure, 2 h before", "hPa"],
      prev_dome_closed_frac: ["Dome closed last night", "%"], prev_seeing_median: ["Last night's seeing", "″"],
      doy_sin: ["Time of year (sine)", ""], doy_cos: ["Time of year (cosine)", ""],
    },
  },
};
