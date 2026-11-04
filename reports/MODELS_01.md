# Modelos 01: previsión de esta noche en el Roque de los Muchachos

> **Estudio previo (28–31 oct 2026), conservado tal cual.** Los apartados 1–3 son los modelos por noche que se hicieron
> primero (gradient boosting, horas perdidas del WHT); el apartado 4 es la primera versión del modelo por horas. El
> modelo actual (RoqueModel, un random forest que pronostica cada hora de la noche) y sus resultados están en
> [docs/DETALLES_TECNICOS.md](../docs/DETALLES_TECNICOS.md) y en la
> [web](https://saimonx.github.io/roque-model/).

> **Proyecto independiente**, sin afiliación con GRANTECAN ni con ningún observatorio. Todos los datos son reales y públicos.
> Notebook: [`notebooks/02_models.ipynb`](../notebooks/02_models.ipynb). Código: `src/roque_forecast/features.py`,
> `src/roque_forecast/train.py`, `hourly.py`, `validate.py`. Métricas: [`reports/results/`](results/).

## La pregunta

Al empezar la noche, usando solo lo que se sabe en ese momento:
1. **¿Habrá que cerrar la cúpula?** La etiqueta es que la regla de humedad del NOT (≥ 90 %, reabrir tras 20 min por
   debajo) la cierre al menos 1 hora. Ocurre aproximadamente 1 de cada 5 noches.
2. **¿Cómo será el seeing?** La etiqueta es la mediana del seeing DIMM R2D2 de la noche.
3. **¿Cuántas horas se perderán por el tiempo?** La etiqueta es la contabilidad nocturna del WHT.

## Entradas (todas disponibles antes de que empiece la noche)

| Grupo | Entradas | Fuente |
|---|---|---|
| Previsión de la noche | humedad (media, máxima), diferencia con el punto de rocío, temperatura y su descenso, viento (medio, máximo, componentes este-oeste y norte-sur), nubosidad, precipitación, presión | ECMWF IFS HRES 9 km mediante los archivos de previsiones de [Open-Meteo](https://open-meteo.com) (CC BY 4.0) |
| Estación antes de la noche | humedad (media, máxima), viento y presión en las 2 h antes de la noche astronómica | Archivo meteorológico del NOT |
| Persistencia | fracción de cierre y mediana del seeing de anoche | NOT, R2D2 |
| Época del año | seno y coseno del día del año | — |

Lo que hace honesta la evaluación es usar previsiones reales, no el tiempo medido. Se usan dos archivos:
- **Entrenamiento y prueba principal:** primeras horas de cada ejecución del modelo, desde 2017. Es algo *mejor* que la
  previsión de la tarde.
- **Comprobación:** las previsiones emitidas 24 h antes, desde 2025. Son algo *peores* que la previsión de la tarde.

El acierto real está entre los dos resultados.

## Método

- **División temporal:** entrenar con 2017–2022 (2.191 noches), elegir ajustes con 2023 (365), probar con 2024–oct 2026
  (1.031). Los años de prueba no se usaron para ninguna elección.
- **Modelos:** gradient boosting (`HistGradientBoosting` de scikit-learn; una rejilla 2×2×2 elegida con 2023), con una
  regresión lineal o logística como alternativa más sencilla. El seeing se modela en escala logarítmica.
- **Métodos de referencia:** cada uno se convierte en una probabilidad usando solo los años de entrenamiento.
  - climatología: el valor habitual del mes;
  - persistencia: igual que anoche;
  - precasting: las condiciones de la estación justo antes de la noche;
  - solo para el cierre, una regla simple sobre la humedad prevista.

## Resultados en los años de prueba (2024–2026)

### 1. Cierre de cúpula (1.025 noches)

| Método | Brier ↓ | Brier skill frente a climatología ↑ | AUC ↑ | Cierres avisados | Falsas alarmas |
|---|---|---|---|---|---|
| Climatología (mes) | 0,149 | 0 | 0,70 | — | — |
| Persistencia (anoche) | 0,131 | 0,12 | 0,72 | 56 % | 44 % |
| Precasting (humedad ≥ 90 % antes de la noche) | 0,082 | 0,45 | 0,83 | 71 % | 17 % |
| Regla sobre la previsión (humedad prevista ≥ 95 %) | 0,153 | −0,02 | 0,64 | — | — |
| **Gradient boosting** | **0,067** | **0,55** | **0,96** | **79 %** | 25 % |
| Regresión logística | 0,078 | 0,48 | 0,95 | 78 % | 27 % |
| Gradient boosting, solo previsión | 0,094 | 0,37 | 0,91 | 68 % | 33 % |

- **Mejor modelo:** gradient boosting reduce el Brier un 18 % frente a la mejor referencia (precasting).
- **Previsiones de hace 24 horas** (398 noches de 2025–2026): skill 0,56, frente a 0,44 del precasting. El resultado
  se mantiene cuando la previsión es más antigua.
- **Entrada más fuerte:** la humedad de la estación justo antes de la noche. El modelo afina esa lectura con el viento y
  la precipitación previstos.
- **Solo previsión:** sin las lecturas de la estación (por ejemplo, para planificar la noche de mañana) la previsión sigue
  siendo mucho mejor que la climatología o la persistencia. No llega al precasting.
- **Calibración:** las probabilidades entre el 40 % y el 90 % son algo altas (diagrama de fiabilidad en el notebook).

![Skill del cierre](figures/06_closure_skill.png)

### 2. Seeing (780 noches con datos de R2D2)

| Método | RMSE (″) ↓ | MAE (″) ↓ | Skill de RMSE frente a climatología ↑ |
|---|---|---|---|
| Climatología (mes) | 0,350 | 0,227 | 0 |
| Persistencia (anoche) | 0,415 | 0,278 | −0,19 |
| **Gradient boosting** (con el viento de la corriente en chorro) | **0,284** | **0,197** | **0,19** |
| Gradient boosting, sin el viento de la corriente en chorro | 0,286 | 0,198 | 0,18 |
| Regresión lineal (log) | 0,288 | 0,202 | 0,18 |
| Gradient boosting, solo previsión | 0,310 | 0,219 | 0,11 |

- **Previsiones de hace 24 horas:** 0,303″ frente a 0,378″ de la climatología (skill 0,20).
- **Viento de la corriente en chorro (añadido el 28 oct 2026).** La turbulencia en altura emborrona las estrellas aunque
  en el suelo haya calma. El archivo de ECMWF no tiene niveles de presión, así que el viento a 200 hPa (~12 km) viene del
  archivo NOAA GFS, que empieza en marzo de 2021; las noches anteriores no tienen valor (gradient boosting admite huecos
  de forma nativa). Se aceptó solo con el año de validación (RMSE 0,347″ → 0,340″ en 2023). En los años de prueba la
  mejora es pequeña pero se mantiene en los dos archivos (0,286″ → 0,284″; con 24 h de antigüedad: 0,306″ → 0,303″). Los
  modelos de cúpula no lo usan.
- **Entrada más fuerte:** el viento de la estación antes de la noche, y después la temperatura y la época del año.
  Coincide con Abárzuza et al. 2025.
- **Límite:** un modelo lineal es casi igual de bueno. Casi toda la turbulencia está en capas que la estación del suelo
  no ve, así que el error restante es grande.

### 3. Horas perdidas por el tiempo (WHT)

**Por qué una línea de calibración.** Solo tres años combinan un archivo de previsiones con un registro fiable del WHT:
2017, 2018 y 2023. El apartado 4 del EDA explica qué años son fiables. Esos tres años son muy pocos para un modelo propio.
En su lugar, la previsión de horas de cierre se convierte con un único factor ajustado en esos años:
`perdidas = 0,85 × horas cerradas previstas`.

- Las horas previstas que se usan en el ajuste vienen de modelos que no habían visto ese año («out of fold»).
- Un término independiente libre se rechazó con esos mismos años, antes de mirar 2026. Añadía 0,6 h a cada noche despejada.

| Conjunto de prueba | Método | RMSE (h) ↓ | MAE (h) ↓ |
|---|---|---|---|
| **2026** (fiable, 299 noches) | Climatología (mes, 2010–2018) | 2,99 | 2,09 |
| | Persistencia (anoche) | 3,23 | 1,42 |
| | **Previsión de cierre calibrada** | **2,65** | **1,36** |
| 2024–2025 (registro dudoso, solo para comparar) | Climatología | 2,65 | 2,09 |
| | Persistencia | 2,87 | 1,21 |
| | Previsión de cierre calibrada | 2,93 | 1,55 |

- **2026:** la previsión supera a las dos referencias en las dos medidas.
- **2024–2025:** no las supera, porque en esos años el registro da por observadas muchas noches cerradas. El modelo acierta
  con el tiempo y la etiqueta no. Por eso esos años se excluyen del ajuste.

## 4. El diseño usado en directo (28 oct 2026): una etiqueta de cierre, un modelo por horas, tres comprobaciones

Los apartados 1–3 estudian la noche en conjunto. El producto en directo es más sencillo y es el que hay que leer:

| Pregunta | Modelo | Etiqueta |
|---|---|---|
| ¿Está cerrada la cúpula esta hora? | RoqueModel, un random forest por hora de noche (`hourly.py`; modelo y ajustes de `compare.py`), provisional y definitivo | `dome.closed`: humedad ≥ 90 % (reabrir tras 20 min), **o** rachas ≥ 22,2 m/s (80 km/h, límite del INT, misma reapertura), **o** hielo (≤ 0 °C con humedad ≥ 90 % en las 24 h anteriores) |
| ¿Cuántas horas cerrada esta noche? | suma de las probabilidades por hora | la misma etiqueta, sumada en toda la noche |
| Seeing de la noche | apartado 2 (`train.py`) | mediana de R2D2 |

**La regla del hielo** se calibró con los partes del Telescopio Liverpool de 2017–2022 (nunca los años de prueba): añade
29 noches a la etiqueta, y el LT perdió 26 de ellas.

**Franjas por hora:** horas UTC con ≥ 30 minutos de noche astronómica (32.153 horas, 2017–2026). Una hora se etiqueta como
cerrada cuando la etiqueta cubre al menos la mitad, y solo si se midieron ≥ 45 minutos. Entradas: la previsión ECMWF a mitad
de la hora (el viento a 10 m no sirve en la cumbre, media de 1,3 m/s, así que se añade el viento a 750 hPa de GFS desde
2021), las entradas por noche del apartado 1 y la posición de la hora en la noche.

### Resultados en los años de prueba (2024–2026)

Hora a hora frente a lo que pasó de verdad (`site_data.comparison`): la cúpula estuvo cerrada 1.453 de 8.577 horas. Leída
tal cual, la previsión del tiempo cerraría 6.111 horas y se equivoca en el 56,6 % de las horas (4.756 cierres innecesarios,
98 no detectados); el modelo definitivo marca 1.390 horas y se equivoca en el 8,9 % (351 / 414); el provisional, en el
11,5 %. Decir siempre «abierta» se equivoca en el 16,9 %.


| Cúpula cerrada, cada hora (8.577 horas, 17 % cerradas) | Brier ↓ | Skill | AUC | Acierta cuando dice «cerrada» | Horas cerradas detectadas |
|---|---|---|---|---|---|
| Climatología (mes) | 0,136 | 0 | 0,66 | — | — |
| Previsión tal cual | 0,566 | −3,16 | 0,63 | 22 % | 93 % |
| Persistencia (misma hora de anoche) | 0,120 | 0,12 | 0,69 | 52 % | 47 % |
| Precasting (humedad antes de la noche) | 0,081 | 0,41 | 0,85 | 67 % | 77 % |
| Modelo, provisional | 0,084 | 0,38 | 0,91 | 69 % | 59 % |
| **Modelo, definitivo** | **0,063** | **0,54** | **0,95** | **75 %** | **72 %** |

| Horas cerradas de la noche (1.028 noches) | MAE | RMSE |
|---|---|---|
| Climatología (mes) | 1,95 h | 2,87 h |
| Persistencia (anoche) | 1,33 h | 2,94 h |
| Previsión tal cual | 4,67 h | 5,93 h |
| Modelo, provisional | 1,24 h | 2,06 h |
| **Modelo, definitivo** | **0,87 h** | **1,68 h** |

El modelo provisional pierde frente al precasting en la hora: el precasting ya usa la estación justo antes de la noche, algo
que el provisional no puede tener. Cuando empieza la noche, el definitivo también la usa y supera a todas las referencias.

### ¿Refleja la etiqueta la realidad? (`validate.py`, `results/validation.json`)

Comprobada con **una sola fuente para todos los años**, para que la comprobación signifique lo mismo cada año: los partes
nocturnos del **Telescopio Liverpool** (2017–2026, 3.322 noches con parte). A ambos se les pregunta, noche a noche, si se
perdió al menos la mitad de la noche:

- Coinciden en el 87,2 % de las noches (72–93 % según el año; el más bajo, 2021, cuando el LT perdió 148 noches, incluidas
  nubes y polvo).
- Etiqueta «perdida» (529 noches) → el LT también la perdió en el 95,7 %. Etiqueta abierta toda la noche (2.458) → el LT
  conservó la noche en el 89,9 %.
- El LT perdió 909 noches y la etiqueta 529: el LT también cierra por nubes, polvo y precaución.
- Correlación de las horas: 0,74; media de 2,75 h perdidas por el LT frente a 1,61 h cerradas según la etiqueta.

Fuentes estudiadas y no usadas, porque no cubren todos los años de la misma manera:
- **Archivo público del GTC** (CAB): los tiempos de exposición científica muestran cuándo el GTC estuvo con certeza abierto
  (ene 2024 – sep 2025: 1.499 h exponiendo, etiqueta «cerrada» en el 0,8 % de esos minutos), pero los datos se hacen públicos
  un año después y el archivo no puede mostrar cierres.
- **Tiempo perdido por meteorología del TNG:** solo se publican los últimos 365 días (oct 2025 – oct 2026: correlación 0,90).
- **Contabilidad nocturna del WHT:** algunos años dan por observadas noches con la cúpula cerrada (EDA, apartado 4).

### Modelos en directo reentrenados con 2017–2026 (31 oct 2026)

Los resultados anteriores vienen de modelos entrenados con 2017–2023 y probados con 2024–2026. Una vez medidos, el RoqueModel
en directo (definitivo y provisional) se reentrena con los mismos ajustes en todos los años con etiqueta, 2017–2026
(30.044 horas, 5.163 cerradas). Antes de hacerlo: entrenando con 2017–2023 frente a 2017–2024 con los mismos ajustes y
midiendo en 2025–2026, el año adicional mejoró el Brier de 0,0655 a 0,0622 (definitivo) y de 0,0879 a 0,0847 (provisional).
El historial en directo sigue midiendo los modelos reentrenados en las noches nuevas.

### Elección del modelo: random forest (31 oct 2026, `compare.py`)

Gradient boosting (162 combinaciones) y random forest (288) tuvieron búsquedas de ajustes igual de amplias en los años de
validación 2021–2023; la regresión logística y una MLP, más pequeñas. Brier de validación, definitivo / provisional: gradient
boosting 0,0594 / 0,0856, random forest 0,0595 / 0,0869 (por años se alternan: definitivo 0,0516 / 0,0559 / 0,0708 frente a
0,0521 / 0,0568 / 0,0695). A menos de un 2 %, así que decide la prueba: random forest 0,0628 / 0,0839 frente a 0,0667 / 0,0859
(aciertos 91,1 % / 88,5 % frente a 90,7 % / 88,2 %). Esa elección miró los años de prueba, así que esos resultados pueden ser
algo optimistas. Totales por noche: MAE 0,87 h frente a 0,77 h (peor), RMSE 1,68 h frente a 1,75 h (mejor).

### Probado y descartado

- Modelos separados de cierre por noche y de horas del WHT en el producto en directo (apartados 1 y 3): sustituidos por la suma
  del modelo por horas, que responde a las dos cosas con una sola etiqueta.
- Seeing hora a hora: RMSE 0,358″ frente a 0,409″ de la climatología, pero no mejor que el modelo por noche para la noche en
  conjunto, y la etiqueta horaria de R2D2 tiene mucho ruido.
- Modelos separados de humedad y viento combinados como `1 − (1 − p_h)(1 − p_w)`: mismo Brier que un modelo con la etiqueta
  compuesta, así que se mantuvo la etiqueta única.
- Modelos de horas perdidas y de cielo fotométrico del Telescopio Liverpool: la etiqueta del LT mezcla motivos que el GTC no
  comparte (cierra antes), y el modelo fotométrico apenas superaba a la persistencia (Brier skill 0,17 frente a 0,12). Los
  partes del LT se conservan solo como comprobación.
- Aviso de polvo de CAMS: 18 noches de polvo en los años de prueba, archivo de CAMS solo desde agosto de 2022, 93 % de falsas
  alarmas.

## Limitaciones y siguientes pasos

- **Etiquetas aproximadas.** La etiqueta de cierre se reconstruye con la estación del NOT (humedad, viento, hielo). Los cierres
  por polvo y nubes no están en ella, y ninguna de las etiquetas es una decisión de operación del propio GTC (el apartado 4 las
  comprueba).
- **Un modelo de previsión en un punto de la rejilla.** El punto está a 4 km, sobre un terreno suavizado, y suele ser más húmedo
  y tranquilo que la cumbre. El modelo aprende a corregirlo.
- **Recalibración del cierre, probada y rechazada (28 oct 2026).** La regresión isotónica se comprobó sin tocar los años de
  prueba: probabilidades «out of fold» de cada año de 2017–2023 (modelo entrenado con los otros seis) y, después, un ajuste
  anidado de la curva isotónica dejando un año fuera cada vez. Brier 0,0517 sin recalibrar frente a 0,0521 recalibrado (modelo
  solo con previsión: 0,0922 frente a 0,0933), así que no se aplica. La comprobación se ejecuta en cada entrenamiento
  (`train.calibration_check`, guardada en `results/settings.json`). En los años de prueba el modelo se confía algo de más entre
  el 40 % y el 90 %; con ~250 noches en esos tramos puede ser ruido o un cambio en el clima de los últimos años, y es el
  historial en directo donde hay que vigilarlo.
- **Posibles mejoras:** un archivo más largo de previsiones por niveles de presión para la corriente en chorro (ahora el
  entrenamiento solo lo tiene desde 2021).
