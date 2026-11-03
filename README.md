# RoqueModel

Un modelo de previsión de apertura de la cúpula del telescopio para observar desde el Roque de los
Muchachos (repositorio `roque-model`).

Esta noche en el **Observatorio del Roque de los Muchachos** (La Palma, Canarias), hora a hora: **¿estará
abierta la cúpula?**

- **Web en directo, actualizada cada hora:** https://saimonx.github.io/roque-model/
- **Panel público de Grafana** (Grafana Cloud, mismos datos): https://ardentcloset2195.grafana.net/public-dashboards/da7d86c2a1c543a38467827c9f34b1c8 (lo genera `src/roque_forecast/cloud_dashboard.py`; lee el `tonight.json` publicado con la fuente de datos Infinity)
- **Datos de entrenamiento, para descargar y comprobar:** https://github.com/saimonx/roque-model/releases/download/training-data/roquemodel_data.zip (ver [Datos](#datos))

> **Proyecto independiente.** Es un proyecto personal. **No está afiliado, respaldado ni hecho por encargo
> de** GRANTECAN, el IAC, el ING, el NOT, el TNG, el Telescopio Liverpool ni ninguna otra institución.
> Todos los datos salen de sus páginas web públicas y se citan más abajo.

![Web, versión en español (28 oct 2026)](reports/figures/13_web_es.jpg)

## Qué pronostica: dos modelos y una etiqueta comprobada con un telescopio

| Pregunta | Pronóstico | Aprende de |
|---|---|---|
| **¿Estará abierta la cúpula, y cuándo?** | **RoqueModel**: para cada hora de la noche, la probabilidad de que la cúpula esté cerrada (`hourly.py`). Las horas cerradas previstas de la noche son la suma de sus horas. | La **etiqueta de cierre** (ver [más abajo](#cuándo-cuenta-como-cerrada)), reconstruida minuto a minuto con la estación meteorológica del NOT desde 1997 (`dome.py`). |
| **¿Qué nitidez?** | El seeing mediano de la noche (`train.py`; se calcula en directo y se envía a FIWARE, no se muestra en la web). | El monitor de seeing R2D2 del ING (2018 →). |

### Cómo funciona RoqueModel

- **Un modelo:** recibe los datos de una hora y devuelve un número, la probabilidad de que la cúpula esté
  cerrada en esa hora. Las horas cerradas de la noche son la suma de sus horas.
- **Qué recibe:** unos 30 datos: la previsión de esa hora (humedad, viento, temperatura, nubes, lluvia,
  presión), la previsión de toda la noche, la estación de la cumbre justo antes de la noche, lo que pasó
  anoche, y la época del año y la hora de la noche.
- **Cómo aprendió:** primero se entrenó una copia con las horas de noche de 2017–2023 (ajustes elegidos con
  la búsqueda de abajo) y se probó en 2024–2026, años que no había visto: todas las cifras de este README
  salen de esa copia. Después, el modelo en directo se volvió a entrenar con los mismos ajustes con todo
  2017–2026 (30.044 horas, 5.163 cerradas). Comprobado antes: con los mismos ajustes, añadir 2024 al
  entrenamiento mejoró las cifras de 2025–2026 (se equivoca en el 9,5 % → 8,8 % de las horas; provisional
  12,0 % → 11,5 %).
- **Por dentro:** un random forest (`RandomForestClassifier` de scikit-learn): 150 árboles de decisión, cada
  uno entrenado con una muestra al azar de las horas y mirando una parte al azar de los datos en cada
  pregunta; el porcentaje es la media de las respuestas de los árboles.
- **Por qué un random forest y por qué estos ajustes** (`compare.py`, `results/model_search.json`): los dos
  tipos de modelo más fuertes tuvieron una búsqueda de ajustes igual de amplia, puntuada en tres años de
  validación (2021, 2022 y 2023, cada uno aprendiendo de los demás años de 2017–2023): gradient boosting, 162
  combinaciones (tasa de aprendizaje, hojas por árbol, mínimo de horas por hoja, L2, 150/300/600 árboles), y
  random forest, 288 (mínimo de horas por hoja de 1 a 50, parte de los datos en cada pregunta, Gini o
  entropía, huecos tal cual o rellenados con la mediana, 150/300/600 árboles). La regresión logística y una
  red neuronal pequeña tuvieron búsquedas menores. Random forest elegido: el definitivo, 150 árboles, 3 horas
  por hoja, 25 % de los datos en cada pregunta, entropía y huecos tal cual; el provisional, 150 árboles, 10
  horas por hoja, √datos en cada pregunta, entropía y huecos tal cual.

  | Modelo (prueba 2024–2026) | Acierta (definitivo) | Acierta (provisional) | Brier (definitivo) | AUC | Brier en validación |
  |---|---|---|---|---|---|
  | **Random forest** | **91,1 %** | **88,5 %** | **0,0628** | 0,951 | 0,0595 |
  | Gradient boosting | 90,7 % | 88,2 % | 0,0667 | 0,951 | 0,0594 |
  | Red neuronal (MLP) | 90,4 % | 87,6 % | 0,0718 | 0,949 | 0,0650 |
  | Regresión logística | 88,9 % | 87,2 % | 0,0804 | 0,930 | 0,0658 |

  En los años de validación los dos modelos de árboles empatan (sumando las dos versiones, su Brier se
  diferencia en un 0,9 %, mientras que de un año a otro cambia más de un 30 %, y cada uno gana uno de los
  tres años). Regla: si están a menos de un 2 % en validación, decide el menor error en la prueba, y el random
  forest es mejor en la prueba en las dos versiones. Como esta elección miró los años de prueba, sus cifras
  de prueba pueden ser algo optimistas; ningún ajuste se eligió con ellos, y el registro diario de
  pronósticos es una prueba que ninguna elección ha visto. A cambio: hora a hora es mejor, pero sus totales
  por noche son algo peores de media (error medio 0,87 h frente a 0,77 h; el RMSE, 1,68 h frente a 1,75 h,
  es mejor), porque la media de muchos árboles casi nunca da a una hora un 0 % exacto.
- **Dos versiones:** provisional (antes de la noche, con todos los datos menos la estación de la cumbre, que
  aún no existe) y definitiva (desde que empieza la noche, con todos los datos).
- **El desglose de cada hora** de la web se calcula aparte (`explain.py`): cuánto cambia el porcentaje al
  cambiar un dato por el de una hora normal (valores de Shapley exactos).

**¿Por qué un modelo y no la propia previsión del tiempo?** El modelo meteorológico ve la montaña más baja de
lo que es, dentro del mar de nubes que queda por debajo de la cumbre: leído tal cual (humedad ≥ 90 % →
cerrar) dice «cerrar» en la mayoría de las horas de noche, y en 2024–2026 solo acertó 2 de cada 10 de esos
«cerrar». Los modelos aprenden a corregirlo con 7 años de previsiones archivadas frente a lo que pasó en la
cumbre.

### Cuándo cuenta como cerrada

Lo mide minuto a minuto la estación meteorológica del NOT en la cumbre. La cúpula cuenta como cerrada si se
cumple cualquiera de estas condiciones (`dome.py`):

| Motivo | Cierra cuando | Reabre cuando | De dónde sale el valor |
|---|---|---|---|
| Humedad | la humedad llega al **90 %** | lleva **20 minutos seguidos** por debajo del 90 % | Regla de cierre del telescopio NOT |
| Viento | el viento llega a **80 km/h** (22,2 m/s) | lleva **20 minutos seguidos** por debajo | Límite de cierre del telescopio INT (procedimiento de alertas del ING) |
| Hielo | temperatura ≤ **0 °C** y la humedad llegó al 90 % en las **24 h** anteriores | la temperatura sube de 0 °C | Regla propia, ajustada con los partes del Telescopio Liverpool de 2017–2022 (añade 29 noches; el LT perdió 26 de ellas) |

Una hora cuenta como cerrada si la cúpula está cerrada al menos 30 de sus 60 minutos. Las nubes y el polvo no
entran: no hay un registro público fiable de ellos en la cumbre para todos los años.

### ¿Refleja la realidad la etiqueta?

No hay un registro público de cuándo cierra el GTC, así que la etiqueta se compara con **un telescopio real
para todos los años**: el **Telescopio Liverpool** (robótico de 2 m en la misma montaña), que anota cada
noche desde 2007 cuántas horas perdió por el tiempo (`validate.py`). A los dos se les hace la misma pregunta,
noche a noche: **¿se perdió al menos la mitad de la noche?**

- **Coinciden en 87 de cada 100 noches** (3.322 noches, 2017–2026).
- Cuando la etiqueta dice que la noche se perdió (529 noches), el LT también la perdió **96 de cada 100
  veces**.
- Cuando la etiqueta deja la cúpula abierta toda la noche (2.458 noches), el LT tampoco perdió la noche
  **90 de cada 100 veces**.
- El LT pierde más noches que la etiqueta (909 frente a 529): también cierra por nubes, polvo o precaución, y
  la etiqueta solo mide humedad, viento y hielo.

| Año | Noches | Coinciden (de 100) | Perdidas según la etiqueta | Perdidas por el LT | Perdidas por los dos |
|---|---|---|---|---|---|
| 2026 | 273 | 92 | 48 | 69 | 47 |
| 2025 | 317 | 87 | 52 | 94 | 52 |
| 2024 | 314 | 85 | 45 | 83 | 41 |
| 2023 | 316 | 88 | 61 | 94 | 59 |
| 2022 | 346 | 90 | 66 | 97 | 65 |
| 2021 | 357 | 72 | 51 | 148 | 50 |
| 2020 | 350 | 86 | 56 | 100 | 54 |
| 2019 | 341 | 93 | 34 | 51 | 31 |
| 2018 | 358 | 92 | 75 | 95 | 70 |
| 2017 | 350 | 87 | 41 | 78 | 37 |

Para especialistas: correlación entre las horas perdidas por el LT y las horas cerradas según la etiqueta,
0,74.

**¿Por qué una sola fuente?** Para que la comprobación signifique lo mismo todos los años. No se usan: el
archivo público del GTC (los tiempos de exposición indican cuándo estuvo abierto, pero los datos se publican
un año después y solo había 2024–2025), el tiempo perdido por meteorología del TNG (solo publica el último
año) y la contabilidad del WHT (algunos años da por observadas noches con la cúpula cerrada).

## Resultados (años de prueba 2024–2026, nunca usados para entrenar ni para elegir ningún ajuste)

**Hora a hora, frente a lo que pasó de verdad** (8.577 horas de noche; «cerrar» = humedad prevista ≥ 90 %, o
probabilidad del modelo ≥ 50 %):

| | Horas con la cúpula cerrada | Se equivoca en | Cierra sin hacer falta | Deja abierta cuando habría que cerrar |
|---|---|---|---|---|
| Lo que pasó de verdad (medido en la cumbre) | 1.453 h | — | — | — |
| Solo la previsión del tiempo | 6.111 h | 57 de cada 100 horas | 4.756 h | 98 h |
| **RoqueModel (definitivo)** | **1.390 h** | **9 de cada 100 horas** | 351 h | 414 h |
| RoqueModel (provisional) | 1.237 h | 12 de cada 100 horas | 385 h | 601 h |

Decir «abierta» todas las horas se equivocaría en 17 de cada 100 horas (las cerradas), así que el modelo
también supera ese mínimo.

| Pronóstico | Referencias más sencillas | RoqueModel (definitivo) |
|---|---|---|
| Cúpula cerrada, cada hora (8.577 horas) | previsión tal cual: acierta 2 de cada 10 «cerrar»; humedad justo antes de la noche: acierta 7 de cada 10 | **acierta 7 de cada 10 y detecta 7 de cada 10**; Brier 0,063 (skill 0,54), AUC 0,95 |
| Horas cerradas de la noche (1.028 noches) | lo normal del mes: se desvía 2,0 h; igual que anoche: 1,3 h; previsión tal cual: 4,7 h | **se desvía 0,9 h de media** (provisional, antes de la noche: 1,2 h) |
| Seeing de la noche (780 noches) | lo normal del mes: se desvía 0,23″; igual que anoche: 0,28″ | **se desvía 0,20″** (RMSE 0,284″ frente a 0,350″) |

Dos modos, para que un pronóstico nunca use información que no podía tener: **provisional** (por la tarde:
previsión del tiempo, lo de anoche y la época del año) y **definitivo** (desde que empieza la noche
astronómica, añadiendo la estación del NOT en las 2 horas antes de la noche, el dato que más ayuda).

**Probado y descartado** (documentado en [MODELS_01](reports/MODELS_01.md)): modelos por noche separados de
cierre y de horas perdidas del WHT (sustituidos por el modelo por horas y su suma), modelos de horas perdidas
y de cielo despejado del Liverpool (no mejoran «igual que anoche» para el cielo), un aviso de polvo de CAMS
(demasiados pocos casos), el seeing hora a hora (no mejora el modelo por noche) y la recalibración isotónica
(sin mejora).

## Datos

Todos los datos son **reales y públicos**; nada en este proyecto es simulado.

| Uso | Fuente | Periodo |
|---|---|---|
| Etiqueta (lo que pasó) | [Archivo meteorológico del NOT](https://www.not.iac.es/weather/archive/met/index.php), minuto a minuto: humedad, viento, temperatura, presión | 1997 → hoy |
| Etiqueta (lo que pasó) | [Monitor de seeing R2D2 del ING](https://astro.ing.iac.es/seeing/) | sep 2018 → hoy |
| Entradas (lo que se sabía) | Previsiones ECMWF IFS HRES archivadas por [Open-Meteo](https://open-meteo.com) ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), tal como se emitieron | 2017 → hoy |
| Entradas (lo que se sabía) | NOAA GFS archivado por Open-Meteo: viento a 750 hPa (altura de la cumbre) y a 200 hPa (corriente en chorro) | mar 2021 → hoy |
| Comprobar la etiqueta | [Partes nocturnos del Telescopio Liverpool](https://telescope.livjm.ac.uk/Reports/): horas perdidas por el tiempo cada noche | 2007 → hoy |
| Solo el estudio por noches | [Contabilidad nocturna del ING](https://a.ing.iac.es/weather/archive/) (horas perdidas del WHT) | 2007 → hoy |
| En directo, solo para mostrar | Panel de [atmosportal del GTC](https://atmosportal.gtc.iac.es/) (estado actual en FIWARE, no se guarda); [meteorología del TNG](https://tngweb.tng.iac.es/weather) (se guarda) | en directo |

**Descarga los datos de entrenamiento** (zip de 1 MB, [release `training-data`](https://github.com/saimonx/roque-model/releases/tag/training-data),
generado por `src/roque_forecast/export_data.py`):

- `roquemodel_training_hours.csv`: las 30.044 horas de noche (2017–2026) con las que se entrenó el
  RoqueModel en directo, cada una con su etiqueta y todos sus datos de entrada;
- `roquemodel_test_predictions.csv`: la respuesta de la copia probada para cada hora de 2024–2026, la de la
  previsión sola y lo que pasó, para poder recalcular las cifras de arriba;
- `README.md`: unidad, significado y fuente pública de cada columna, y cómo volver a descargar cualquier hora
  de la fuente original.

Las descargas se identifican con un User-Agent descriptivo, esperan entre peticiones y solo usan páginas
enlazadas desde las webs públicas.

## Estado

| Paso | Estado |
|---|---|
| Descargadores, histórico completo, tablas limpias, EDA — [informe](reports/EDA_01.md), [notebook](notebooks/01_eda.ipynb) | hecho |
| Estudio por noches (cierre, seeing, horas perdidas del WHT) — [informe](reports/MODELS_01.md), [notebook](notebooks/02_models.ipynb) | hecho |
| Etiqueta de cierre con humedad, viento y hielo; modelo de cierre por horas; comprobación con el Liverpool | hecho |
| Pronóstico de esta noche, en directo, cada hora (GitHub Actions); entidades FIWARE + Grafana (local y Grafana Cloud) | hecho |
| Web en GitHub Pages | hecho |

## Hallazgos principales de los datos

- Una regla de cierre reconstruida solo con la humedad sigue las horas que el WHT perdió de verdad por el
  tiempo (r = 0,74 en 2007–2018), pero se queda corta en invierno; añadir a la etiqueta el viento fuerte y el
  hielo cierra la mayor parte de esa diferencia (ver las comprobaciones de arriba).
- La contabilidad del WHT no es igual de fiable todos los años: desde 2019, muchas noches con las cúpulas
  cerradas por humedad aparecen como observadas del todo y sin pérdidas. Esos años (2019–2022, 2024–2025) no
  se usan para ajustar modelos y solo se enseñan como comparación.
- El viento es lo que más influye en el seeing (Spearman +0,58 con el viento máximo de la noche); los vientos
  del este dan el peor seeing.
- Para el seeing, la climatología mensual (RMSE 0,34″) mejora a «igual que anoche» (0,41″): ese es el
  listón que tiene que superar un modelo.

![Seeing frente al tiempo](reports/figures/03_seeing_vs_weather.png)

## Referencias científicas

- Abárzuza et al. 2025, *RNAAS* 9(2), [doi:10.3847/2515-5172/adb14f](https://doi.org/10.3847/2515-5172/adb14f) — random forest que predice el seeing del Roque con datos de la estación meteorológica.
- de Sepibus, Masciadri et al. 2026, [arXiv:2607.12900](https://arxiv.org/abs/2607.12900) — persistencia y «precasting» como referencias mínimas para pronosticar el seeing.
- Lombardi et al. 2007, [arXiv:astro-ph/0702570](https://arxiv.org/abs/astro-ph/0702570) — viento y humedad frente al seeing en el Roque.

## Puesta en marcha

Necesita [uv](https://docs.astral.sh/uv/) (instala Python 3.13 si hace falta).

```bash
uv sync                                          # crea .venv e instala las dependencias
.venv/bin/python -m pytest                       # ejecuta los tests
.venv/bin/python -m roque_forecast.backfill not  # descarga histórica (también: r2d2, ing); reanudable
.venv/bin/python -m roque_forecast.build_tables  # ficheros brutos -> data/processed/*.parquet
.venv/bin/python -m roque_forecast.backfill forecasts  # previsiones archivadas de Open-Meteo (~30 s)
.venv/bin/python -m roque_forecast.features      # una fila por noche: datos conocidos al anochecer + etiquetas
.venv/bin/python -m roque_forecast.train         # entrena y compara con las referencias -> reports/results/
.venv/bin/python -m roque_forecast.hourly        # modelo de cierre por horas -> reports/results/hourly_scores.csv
.venv/bin/python -m roque_forecast.backfill liverpool    # partes nocturnos del Telescopio Liverpool (2007 -> hoy)
.venv/bin/python -m roque_forecast.validate      # comprobación de la etiqueta -> reports/results/validation.json
```

### Pronóstico de esta noche y la web

```bash
.venv/bin/python -m roque_forecast.tonight      # datos en directo + modelos -> site/data/tonight.json
.venv/bin/python -m roque_forecast.site_data    # evaluación + historial en directo -> site/data/evaluation.json
.venv/bin/python -m http.server 8765 -d site    # abre http://localhost:8765
scripts/update_tonight.sh                       # los dos pasos (tarea horaria); ROQUE_PUBLISH=1 también publica
```

La web empieza por la previsión de esta noche, en dos líneas de horas, cada una con su leyenda y su acierto
histórico frente a lo que se cerró de verdad: la **previsión del RoqueModel** (probabilidad en verde,
amarillo o rojo; con el modelo actual, provisional o definitivo) y **lo que pasaría si solo se tuviera en
cuenta la previsión del tiempo** (las reglas de la etiqueta leídas tal cual: cerrar o abrir). Al tocar una
hora se ve cómo se calcula en esa línea: en el modelo, un punto de partida más lo que suma o resta cada grupo
de datos (la humedad, el viento, la temperatura, las nubes, la lluvia y la presión previstas para esa hora,
una a una, y después la previsión de toda la noche, la estación de la cumbre, lo de anoche y la época del
año; valores de Shapley exactos sobre diez grupos, `explain.py`); en la previsión, qué regla se cumple.
Debajo, «Más información acerca de RoqueModel» en apartados plegados: qué es, cómo se ha ajustado, cómo se ha
entrenado, cómo pronostica, cuánto acierta, otros modelos probados, datos en tiempo real, datos a tener en
cuenta y referencias.

Cada ejecución queda registrada en `data/forecasts/issued.jsonl`. Cada ejecución anota también lo que pasó
de verdad la noche anterior (`outcomes.jsonl`), así que se va formando un **historial en directo** con el
primer pronóstico definitivo de cada noche.

**En la nube, cada hora** (`.github/workflows/forecast.yml`): GitHub Actions instala el paquete desde
`uv.lock`, descarga los modelos entrenados y las pocas tablas que necesitan de la release `runtime`
(`scripts/build_runtime.sh` los empaqueta y los sube; hay que volver a ejecutarlo tras reentrenar), recupera
el registro de pronósticos de la web publicada, ejecuta `tonight` y `site_data`, y publica.
`scripts/publish_site.sh` sube `site/` (con el registro de pronósticos en `forecasts/`) a la rama `gh-pages`
como un único commit forzado, para que las actualizaciones de cada hora no se acumulen en el historial de
`main`. El programador propio de GitHub se salta la mayoría de las ejecuciones en un repositorio con poca
actividad (hizo 1 de 40 el 1 nov 2026), así que la tarea horaria del Mac (`scripts/update_tonight.sh`, que
ejecuta el pronóstico en local para FIWARE y Grafana) también lanza el flujo, que empieza al momento; el
programador queda como reserva cuando el Mac está apagado.

### FIWARE + Grafana (local, Docker)

```bash
docker compose -f infra/docker-compose.yml up -d     # Orion :1027, QuantumLeap :8669, Grafana :3001
.venv/bin/python -m roque_forecast.fiware provision  # suscripción Orion -> QuantumLeap (una vez)
.venv/bin/python -m roque_forecast.fiware backfill   # opcional: últimos 30 días de la estación del NOT
.venv/bin/python -m roque_forecast.dashboards        # vuelve a generar los paneles en español e inglés
```

| Entidad | Tipo ([Smart Data Models](https://github.com/smart-data-models/dataModel.Weather)) | La actualiza |
|---|---|---|
| `urn:ngsi-ld:WeatherObserved:ORM-GTC` | `WeatherObserved` | `collect live` (cada 15 min; solo el estado actual, su historial no se guarda) |
| `urn:ngsi-ld:WeatherObserved:ORM-NOT` | `WeatherObserved` | `tonight` (cada hora) |
| `urn:ngsi-ld:WeatherForecast:ORM-tonight` | `WeatherForecast` (+ horas cerradas, probabilidad de cierre por hora, seeing) | `tonight` (cada hora) |

![Panel de Grafana, versión en español (28 oct 2026)](reports/figures/14_grafana_es.jpg)

Los puertos están desplazados uno respecto a los de FIWARE por defecto, para que la pila pueda funcionar al
lado de otra pila FIWARE. Si Docker no está en marcha, el pronóstico y los recolectores siguen y se saltan
este paso.

### Recolectores (macOS)

```bash
scripts/install_collectors.sh               # instala los 2 LaunchAgents
scripts/install_collectors.sh --uninstall   # los quita
```

| Agente | Cuándo | Qué |
|---|---|---|
| `live` | cada 15 min | valores actuales del TNG → `data/raw/live/YYYY-MM/YYYY-MM-DD.jsonl`; panel en directo del GTC → solo la entidad FIWARE (la estación del GTC no se guarda) |
| `daily` | 10:07 y 22:07 | series de las últimas 24 h y tiempo perdido del TNG → `data/raw/tng/YYYY-MM-DD/` |
| `tonight` (se instala aparte: `install_collectors.sh tonight`) | cada hora a los :05 | `scripts/update_tonight.sh` |

## Estructura

```
src/roque_forecast/
  config.py          coordenadas del observatorio, carpetas, ajustes de descarga respetuosa
  polite_http.py     cliente HTTP común (User-Agent, espera, reintentos)
  collect.py         recolector por línea de comandos (live / daily / sample)
  backfill.py        descarga masiva y reanudable de los archivos históricos
  build_tables.py    ficheros brutos -> tablas Parquet limpias (minutos, puntos R2D2, noches ING, noches)
  astro.py           altura del Sol y noche astronómica (fórmulas de la NOAA, comprobadas con el ING)
  dome.py            etiqueta de cierre reconstruida minuto a minuto: humedad, viento fuerte, hielo
  features.py        tabla de modelado: previsión + estación antes de la noche + persistencia + época, y etiquetas
  train.py           modelos por noche: seeing (en directo), cierre y horas del WHT (solo estudio)
  hourly.py          modelo de cierre por horas, provisional y definitivo, frente a las referencias
  compare.py         búsqueda de ajustes y comparación de modelos (random forest, gradient boosting, logística, MLP)
  explain.py         por qué cada hora tiene su porcentaje: punto de partida + lo que aporta cada grupo de datos
  validate.py        comprueba la etiqueta con los partes del Telescopio Liverpool, año a año
  plotting.py        estilo común de las figuras (paleta apta para daltonismo)
  tonight.py         pronóstico de esta noche con datos en directo (modos provisional y definitivo)
  site_data.py       evaluación e historial en directo para la web
  fiware.py          entidades NGSI-v2, actualizaciones en Orion, suscripción a QuantumLeap y carga inicial
  dashboards.py      paneles de Grafana (español e inglés) desde una sola definición
  cloud_dashboard.py panel público de Grafana Cloud
  export_data.py     datos de entrenamiento descargables
  sources/           un módulo por fuente de datos: descarga + lectura
site/                web estática (index.html, assets/; data/ se genera)
infra/               Docker Compose para Orion, QuantumLeap, CrateDB y Grafana
scripts/             instalador de LaunchAgents, actualización horaria y publicación en gh-pages
notebooks/           notebooks de análisis (fuente .py + .ipynb ejecutado)
reports/             hallazgos escritos, figuras y tablas de métricas (reports/results/)
tests/               tests de lectura con ficheros reales pequeños (tests/fixtures/), ventanas de tiempo y particiones
launchd/             plantillas de LaunchAgent
data/                datos descargados (no van a git)
```
