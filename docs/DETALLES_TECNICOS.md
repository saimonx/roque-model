# RoqueModel — detalles técnicos

Complemento del [README](../README.md) y de la [web](https://saimonx.github.io/roque-model/): cómo se
construye la etiqueta, cómo se comprueba, cómo se eligió el modelo, todas las cifras de la prueba y cómo
funciona el pronóstico de cada hora.

## Índice

1. [La etiqueta: cuándo cuenta como cerrada](#1-la-etiqueta-cuándo-cuenta-como-cerrada)
2. [¿Refleja la realidad la etiqueta?](#2-refleja-la-realidad-la-etiqueta)
3. [El modelo y cómo se eligió](#3-el-modelo-y-cómo-se-eligió)
4. [Resultados completos de la prueba (2024–2026)](#4-resultados-completos-de-la-prueba-20242026)
5. [Probado y descartado](#5-probado-y-descartado)
6. [Hallazgos de los datos](#6-hallazgos-de-los-datos)
7. [Cómo funciona cada hora](#7-cómo-funciona-cada-hora)
8. [FIWARE](#8-fiware)
9. [Todos los comandos](#9-todos-los-comandos)
10. [Estructura del código](#10-estructura-del-código)

## 1. La etiqueta: cuándo cuenta como cerrada

No hay un registro público de cuándo cierra el GTC, así que la etiqueta «cúpula cerrada» se reconstruye
minuto a minuto con la estación meteorológica del NOT en la cumbre, desde 1997 (`dome.py`). La cúpula cuenta
como cerrada si se cumple cualquiera de estas condiciones:

| Motivo | Cierra cuando | Reabre cuando | De dónde sale el valor |
|---|---|---|---|
| Humedad | la humedad llega al **90 %** | lleva **20 minutos seguidos** por debajo del 90 % | Regla de cierre del telescopio NOT |
| Viento | el viento llega a **80 km/h** (22,2 m/s) | lleva **20 minutos seguidos** por debajo | Límite de cierre del telescopio INT (procedimiento de alertas del ING) |
| Hielo | temperatura ≤ **0 °C** y la humedad llegó al 90 % en las **24 h** anteriores | la temperatura sube de 0 °C | Regla propia, ajustada con los partes del Telescopio Liverpool de 2017–2022 (añade 29 noches; el LT perdió 26 de ellas) |

Una hora cuenta como cerrada si la cúpula está cerrada al menos 30 de sus 60 minutos. Las nubes y el polvo no
entran: no hay un registro público fiable de ellos en la cumbre para todos los años.

## 2. ¿Refleja la realidad la etiqueta?

La etiqueta se compara con **un telescopio real para todos los años**: el **Telescopio Liverpool** (robótico
de 2 m en la misma montaña), que anota cada noche desde 2007 cuántas horas perdió por el tiempo
(`validate.py`). A los dos se les hace la misma pregunta, noche a noche: **¿se perdió al menos la mitad de la
noche?**

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

Correlación entre las horas perdidas por el LT y las horas cerradas según la etiqueta: 0,74.

**¿Por qué una sola fuente?** Para que la comprobación signifique lo mismo todos los años. No se usan: el
archivo público del GTC (los tiempos de exposición indican cuándo estuvo abierto, pero los datos se publican
un año después y solo había 2024–2025), el tiempo perdido por meteorología del TNG (solo publica el último
año) y la contabilidad del WHT (algunos años da por observadas noches con la cúpula cerrada).

## 3. El modelo y cómo se eligió

- **Qué recibe:** 33 datos por hora: la previsión de esa hora (humedad, margen al punto de rocío, viento a
  750 hPa, temperatura, nubes, lluvia, presión), la previsión de toda la noche, la estación del NOT en las 2
  horas antes de la noche, lo que pasó anoche (horas cerradas y seeing) y la época del año y la hora de la
  noche (`hourly.py`, `features.py`).
- **Dos versiones:** provisional (antes de la noche, sin la estación de la cumbre, que aún no existe) y
  definitiva (desde que empieza la noche astronómica, con todos los datos).
- **Separación de años:** los ajustes se eligen solo con 2017–2023 (validación en 2021, 2022 y 2023, ver
  abajo) y la prueba es 2024–2026. La copia probada aprendió de 2017–2023; el modelo en directo se volvió a entrenar con los mismos ajustes con
  todo 2017–2026 (30.044 horas, 5.163 cerradas). Comprobado antes: añadir 2024 al entrenamiento mejoró las
  cifras de 2025–2026 (se equivoca en el 9,5 % → 8,8 % de las horas; provisional 12,0 % → 11,5 %;
  `reports/results/refit_check.json`).
- **Búsqueda de ajustes** (`compare.py`, `reports/results/model_search.json`): los dos tipos de modelo más
  fuertes tuvieron una búsqueda igual de amplia, puntuada en tres años de validación (2021, 2022 y 2023, cada
  uno aprendiendo de los demás años de 2017–2023): gradient boosting, 162 combinaciones (tasa de
  aprendizaje, hojas por árbol, mínimo de horas por hoja, L2, 150/300/600 árboles), y random forest, 288
  (mínimo de horas por hoja de 1 a 50, parte de los datos en cada pregunta, Gini o entropía, huecos tal cual
  o rellenados con la mediana, 150/300/600 árboles). La regresión logística y una red neuronal pequeña
  tuvieron búsquedas menores.

| Modelo (prueba 2024–2026) | Acierta (definitivo) | Acierta (provisional) | Brier (definitivo) | AUC | Brier en validación |
|---|---|---|---|---|---|
| **Random forest** | **91,1 %** | **88,5 %** | **0,0628** | 0,951 | 0,0595 |
| Gradient boosting | 90,7 % | 88,2 % | 0,0667 | 0,951 | 0,0594 |
| Red neuronal (MLP) | 90,3 % | 87,6 % | 0,0718 | 0,949 | 0,0650 |
| Regresión logística | 88,9 % | 87,2 % | 0,0804 | 0,930 | 0,0658 |

En validación, los dos modelos de árboles empatan (sumando las dos versiones, su Brier se diferencia en un
0,9 %, mientras que de un año a otro cambia más de un 30 %, y cada uno gana uno de los tres años). Regla: si
están a menos de un 2 % en validación, decide el menor error en la prueba, y el random forest es mejor en la
prueba en las dos versiones. Como esta elección miró los años de prueba, sus cifras de prueba pueden ser algo
optimistas; ningún ajuste se eligió con ellos.

**Random forest elegido** (`RandomForestClassifier` de scikit-learn): definitivo, 150 árboles, 3 horas por
hoja, 25 % de los datos en cada pregunta, entropía y huecos tal cual; provisional, 150 árboles, 10 horas por
hoja, √datos en cada pregunta, entropía y huecos tal cual. Entrenarlo tarda alrededor de un segundo en un Mac
M4.

**Desglose de cada hora** (`explain.py`): valores de Shapley exactos sobre diez grupos de datos, con un fondo
de 200 horas de noche de 2021–2023. El punto de partida es la media del modelo en ese fondo (≈ 20 %), y la
suma del punto de partida y de lo que aporta cada grupo da exactamente el porcentaje de la hora.

## 4. Resultados completos de la prueba (2024–2026)

Años nunca usados para entrenar ni para elegir ajustes. **Hora a hora, frente a lo que pasó de verdad**
(8.577 horas de noche; «cerrar» = la previsión pasa algún límite de la etiqueta, o probabilidad del modelo ≥
50 %):

| | Horas con la cúpula cerrada | Acierta | Cierra sin hacer falta | Deja abierta cuando habría que cerrar |
|---|---|---|---|---|
| Lo que pasó de verdad (medido en la cumbre) | 1.453 h | — | — | — |
| Solo la previsión del tiempo | 6.111 h | 43 % de las horas | 4.756 h | 98 h |
| **RoqueModel (definitivo)** | **1.390 h** | **91 % de las horas** | 351 h | 414 h |
| RoqueModel (provisional) | 1.237 h | 89 % de las horas | 385 h | 601 h |
| Decir siempre «abierta» | 0 h | 83 % de las horas | 0 h | 1.453 h |

Frente a otras referencias sencillas:

| Pronóstico | Referencias | RoqueModel (definitivo) |
|---|---|---|
| Cúpula cerrada, cada hora | previsión tal cual: acierta 22 de cada 100 «cerrar»; humedad justo antes de la noche (precasting): 67 de cada 100 | **acierta 75 de cada 100 «cerrar» y detecta 72 de cada 100 horas cerradas**; Brier 0,063, AUC 0,95 |
| Horas cerradas de la noche (1.028 noches) | lo normal del mes: se desvía 2,0 h; igual que anoche: 1,3 h; previsión tal cual: 4,7 h | **se desvía 0,9 h de media** (provisional: 1,2 h) |
| Seeing de la noche (780 noches; solo FIWARE, no en la web) | lo normal del mes: se desvía 0,23″; igual que anoche: 0,28″ | **se desvía 0,20″** (RMSE 0,284″ frente a 0,350″) |

**Por qué la previsión sola falla tanto:** el modelo meteorológico ve la montaña más baja de lo que es, dentro
del mar de nubes que queda por debajo de la cumbre, así que leído tal cual dice «cerrar» en la mayoría de las
horas de noche. RoqueModel aprende a corregirlo con años de previsiones archivadas frente a lo que pasó en la
cumbre.

## 5. Probado y descartado

Documentado en [MODELS_01](../reports/MODELS_01.md) (en inglés):

- modelos por noche separados de cierre y de horas perdidas del WHT (sustituidos por el modelo por horas y su
  suma);
- modelos de horas perdidas y de cielo despejado del Telescopio Liverpool (el de cielo despejado apenas mejora
  «igual que anoche»: Brier skill 0,17 frente a 0,12);
- un aviso de polvo con CAMS (demasiados pocos casos);
- seeing hora a hora (no mejora el modelo por noche);
- recalibración isotónica de las probabilidades (sin mejora).

## 6. Hallazgos de los datos

- Una regla de cierre reconstruida solo con la humedad sigue las horas que el WHT perdió de verdad por el
  tiempo (r = 0,74 en 2007–2018), pero se queda corta en invierno; añadir el viento fuerte y el hielo cierra
  la mayor parte de esa diferencia.
- La contabilidad del WHT no es igual de fiable todos los años: desde 2019, muchas noches con las cúpulas
  cerradas por humedad aparecen como observadas del todo. Por eso esos años (2019–2022, 2024–2025) no se
  usaron en el estudio de horas perdidas del WHT (RoqueModel no usa el WHT).
- El viento es lo que más influye en el seeing (Spearman +0,58 con el viento máximo de la noche); los vientos
  del este dan el peor seeing.
- Para el seeing, la climatología mensual (RMSE 0,34″) mejora a «igual que anoche» (0,41″): ese es el listón
  que tiene que superar un modelo.

Análisis completo, en inglés: [EDA_01](../reports/EDA_01.md) ([notebook](../notebooks/01_eda.ipynb)) y
[MODELS_01](../reports/MODELS_01.md) ([notebook](../notebooks/02_models.ipynb)).

## 7. Cómo funciona cada hora

1. **GitHub Actions** (`.github/workflows/forecast.yml`) instala el paquete desde `uv.lock` y descarga los
   modelos entrenados de la release `runtime`. `scripts/build_runtime.sh` los empaqueta y hay que volver a
   ejecutarlo tras reentrenar.
2. `tonight.py` descarga la previsión más reciente (ECMWF y GFS de Open-Meteo), la estación del NOT y el
   seeing de anoche, decide si toca el modelo provisional o el definitivo y escribe `site/data/tonight.json`.
   Si una fuente no responde, usa su última copia buena y la web lo avisa.
3. `site_data.py` escribe `site/data/evaluation.json`: las cifras de acierto de la web.
4. `scripts/publish_site.sh` sube `site/` a la rama `gh-pages` como un único commit, para que las
   actualizaciones de cada hora no se acumulen en el historial de `main`. GitHub Pages la sirve.
5. `tonight.py` publica también el pronóstico en **FIWARE** (apartado 8), y el **panel público de Grafana
   Cloud** lo lee de ahí: la web y Grafana dan las mismas cifras porque salen del mismo cálculo. El panel lo
   genera `cloud_dashboard.py`.

Cada ejecución queda registrada (`forecasts/issued.jsonl`, publicado con la web) junto con lo que pasó de
verdad la noche anterior (`outcomes.jsonl`): es un historial en directo que ninguna elección de ajustes ha
visto. El programador de GitHub se salta muchas ejecuciones en repositorios con poca actividad, así que el
flujo también se lanza desde fuera cada hora (`gh workflow run`); el programador queda como reserva.

**Vigilancia cada hora** (`infra/cloud/monitor.py`, cron del servidor a los :35): comprueba la web (pronóstico
reciente y coherente: probabilidades entre 0 y 1, horas abiertas + cerradas = noche, el modelo que toca según la
hora), FIWARE (Orion, QuantumLeap, que coincide con la web, historial reciente, escritura sin token rechazada,
certificado HTTPS), el panel público de Grafana (abre y sus paneles tienen datos), GitHub (últimas ejecuciones
correctas y flujos activos) y el propio servidor (contenedores, disco, memoria). Arregla solo lo que puede
(arranca contenedores parados y, con un token, relanza el pronóstico) y avisa por correo a través de
Healthchecks.io, que también avisa si la comprobación deja de llegar (servidor caído). Estado ahora:
![vigilancia](https://healthchecks.io/b/2/0437fc28-5880-4f5a-b616-9f2a2ea0c8bb.svg)

**Errores con Sentry** (`observability.py`): en GitHub Actions, `tonight` y `site_data` envían a
[Sentry](https://sentry.io) cualquier excepción y cualquier error registrado (por ejemplo, una escritura en FIWARE
que falla), con la traza, el commit que corría y lo que se registró antes. Los avisos (una fuente que no responde
y se sustituye por su última copia) no se envían solos. Sin `SENTRY_DSN` (en el Mac, en los tests) no se envía
nada. Healthchecks.io dice *que* algo va mal; Sentry dice *por qué*.

## 8. FIWARE

[FIWARE](https://www.fiware.org) es la plataforma abierta de datos de sensores (IoT) que usa el GTC. RoqueModel
publica cada hora su pronóstico como entidades NGSI-v2 con el formato estándar de
[Smart Data Models](https://github.com/smart-data-models/dataModel.Weather) (`fiware.py`), y el panel público de
Grafana lee de ahí, como en la plataforma del GTC.

| Entidad | Tipo | Qué contiene |
|---|---|---|
| `urn:ngsi-ld:WeatherForecast:ORM-tonight` | `WeatherForecast` | el pronóstico de esta noche: horas cerradas, probabilidad de cada hora, la previsión sola, la previsión del tiempo hora a hora y el seeing previsto |
| `urn:ngsi-ld:WeatherObserved:ORM-NOT` | `WeatherObserved` | la estación del NOT; su historial (medias de 10 minutos) va a QuantumLeap |
| `urn:ngsi-ld:WeatherObserved:ORM-GTC` | `WeatherObserved` | solo en local: el panel en directo del GTC (valor actual; su historial no se guarda) |

**En producción** (`infra/cloud/`): un servidor pequeño en la nube (Hetzner CAX11, ARM) con Orion (estado
actual, sobre MongoDB) y QuantumLeap (historial, sobre CrateDB), detrás de Caddy, que da HTTPS automático y
controla el acceso: cualquiera puede leer, y solo el pronóstico de cada hora (GitHub Actions, con un token) puede
escribir. Orion y QuantumLeap solo se publican para x86, así que en ese servidor ARM funcionan con emulación.

- Estado actual: https://178-105-253-255.sslip.io/orion/v2/entities?options=keyValues
- Historial: https://178-105-253-255.sslip.io/ql/v2/entities/urn:ngsi-ld:WeatherObserved:ORM-NOT?lastN=10

**En local**, la misma pila con Docker y un panel de Grafana propio (`infra/docker-compose.yml`, `dashboards.py`).
Si no está en marcha, el pronóstico sigue y se salta este paso.

```bash
docker compose -f infra/docker-compose.yml up -d     # Orion :1027, QuantumLeap :8669, CrateDB :4201, Grafana :3001
.venv/bin/python -m roque_forecast.fiware provision  # suscripción Orion -> QuantumLeap (una vez)
```

## 9. Todos los comandos

```bash
uv sync                                                  # crea .venv e instala las dependencias
.venv/bin/python -m pytest                               # ejecuta los tests
.venv/bin/python -m roque_forecast.backfill not          # descarga histórica (también: r2d2, ing); reanudable
.venv/bin/python -m roque_forecast.build_tables          # ficheros brutos -> data/processed/*.parquet
.venv/bin/python -m roque_forecast.backfill forecasts    # previsiones archivadas de Open-Meteo
.venv/bin/python -m roque_forecast.features              # tabla de modelado y etiquetas
.venv/bin/python -m roque_forecast.train                 # modelos por noche (seeing) -> reports/results/
.venv/bin/python -m roque_forecast.compare               # búsqueda de ajustes y comparación de modelos
.venv/bin/python -m roque_forecast.hourly                # RoqueModel -> reports/results/hourly_scores.csv
.venv/bin/python -m roque_forecast.backfill liverpool    # partes nocturnos del Telescopio Liverpool
.venv/bin/python -m roque_forecast.validate              # comprobación de la etiqueta -> reports/results/validation.json
.venv/bin/python -m roque_forecast.export_data           # datos de entrenamiento descargables
.venv/bin/python -m roque_forecast.tonight               # pronóstico de esta noche -> site/data/tonight.json
.venv/bin/python -m roque_forecast.site_data             # evaluación e historial -> site/data/evaluation.json
.venv/bin/python -m roque_forecast.dashboards            # panel local de Grafana para FIWARE
.venv/bin/python -m roque_forecast.cloud_dashboard       # panel público de Grafana Cloud
```

## 10. Estructura del código

```
src/roque_forecast/
  config.py          coordenadas del observatorio, carpetas, ajustes de descarga respetuosa
  polite_http.py     cliente HTTP común (User-Agent, espera, reintentos)
  sources/           un módulo por fuente de datos: descarga + lectura
  collect.py         recolector: panel en directo del GTC a FIWARE (no guarda nada)
  backfill.py        descarga masiva y reanudable de los archivos históricos
  build_tables.py    ficheros brutos -> tablas Parquet limpias
  astro.py           altura del Sol y noche astronómica (fórmulas de la NOAA)
  dome.py            etiqueta de cierre minuto a minuto: humedad, viento fuerte, hielo
  features.py        tabla de modelado: previsión + estación antes de la noche + anoche + época
  train.py           modelos por noche: seeing (en directo), cierre y horas del WHT (solo estudio)
  compare.py         búsqueda de ajustes y comparación de modelos
  hourly.py          RoqueModel: cierre por horas, provisional y definitivo, frente a las referencias
  explain.py         desglose de cada hora (valores de Shapley exactos)
  validate.py        comprobación de la etiqueta con el Telescopio Liverpool, año a año
  tonight.py         pronóstico de esta noche con datos en directo
  site_data.py       evaluación e historial en directo para la web
  export_data.py     datos de entrenamiento descargables
  fiware.py          entidades NGSI-v2, Orion y QuantumLeap
  dashboards.py      panel local de Grafana para FIWARE
  cloud_dashboard.py panel público de Grafana Cloud
  plotting.py        estilo común de las figuras
site/                web estática (index.html, assets/; data/ se genera)
infra/               Docker Compose (Orion, QuantumLeap, CrateDB, Grafana) y paneles
scripts/             actualización horaria, publicación y release de modelos
notebooks/           notebooks de análisis (fuente .py + .ipynb ejecutado)
reports/             informes, figuras y tablas de métricas
tests/               tests con ficheros reales pequeños (tests/fixtures/); se ejecutan en cada push (tests.yml)
launchd/             plantillas para programar la actualización en macOS
data/                datos descargados (no van a git)
```
