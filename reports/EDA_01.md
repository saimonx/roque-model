[English](EDA_01.en.md) · **Español**

# EDA 01: condiciones de observación en el Roque de los Muchachos

> **Estudio previo (27–28 oct 2026), conservado tal cual.** El modelo actual (RoqueModel, un random forest que
> pronostica cada hora de la noche) y sus resultados están en [docs/DETALLES_TECNICOS.md](../docs/DETALLES_TECNICOS.md)
> y en la [web](https://saimonx.github.io/roque-model/).

Proyecto independiente, sin afiliación con GRANTECAN ni con ningún observatorio. Solo datos públicos reales (ver el README).
Análisis completo y código: [`notebooks/01_eda.ipynb`](../notebooks/01_eda.ipynb).

> **Estado (28 oct 2026):** las tres fuentes históricas están completas: meteorología del NOT (1997–2026),
> seeing R2D2 (2018–2026) y contabilidad nocturna del WHT publicada por el ING (2007–2026, 7.239 páginas de noches).

## Datos

| Fuente | Noches útiles | Periodo |
|---|---|---|
| Meteorología del NOT, ≥ 80 % de la noche cubierto | 10.682 | feb 1997 → hoy (cada 5 min hasta 2006, cada minuto desde 2007) |
| Seeing R2D2, ≥ 40 valores en la noche | 2.054 | sep 2018 → hoy |
| Contabilidad del WHT (ING), con contabilidad real en la página | 7.193 | ene 2007 → hoy |

Cada noche se etiqueta con la fecha en que empieza y solo se usa la **noche astronómica** (Sol por debajo de −18°).
Nuestras horas de crepúsculo coinciden al minuto con las del ING.

![Noches útiles por año](figures/01_coverage.png)

## 1. La regla de cierre de cúpula reconstruida con la humedad funciona

La exportación pública del NOT no incluye indicadores de lluvia ni de cúpula, así que el cierre se reconstruyó con la humedad
(cerrar con ≥ 90 %, reabrir tras 20 min por debajo). Comparada con las horas que el WHT perdió de verdad por el tiempo:

- **Correlación 0,64** noche a noche en 7.156 noches (**0,74 en 2007–2018**; el apartado 4 explica por qué los años
  posteriores dan menos); **90 %** de coincidencia en «se perdió más de la mitad de la noche».
- El ciclo estacional coincide: casi nada perdido en julio y agosto, lo peor en invierno. En los 30 años completos de datos del
  NOT, el cierre reconstruido ocupa el **0,4 %** de la noche en julio y el **23–28 %** de noviembre a enero.
- La regla **se queda corta en las pérdidas de invierno**. El WHT perdió la mayor parte de 274 noches con menos de un 10 % de
  cierre reconstruido; la mediana de su humedad máxima es de solo el 43 % y la de su viento máximo, 10 m/s. Apuntan a otras
  causas (viento, polvo/calima, nieve y hielo en las cúpulas, nubes con aire seco). Son las entradas adicionales que necesita
  el modelo de cierre.

![Ciclo estacional](figures/02_closure_vs_losses_monthly.png)

## 2. Seeing

- Mediana de las medianas por noche: **0,81″** (25–75 %: 0,67″–1,04″), cerca de los 0,77″ publicados para el TNG en
  2017–2024 (de Sepibus, Masciadri et al. 2026).
- **El viento es el factor individual más fuerte:** Spearman r = +0,58 con el viento máximo de la noche y +0,46 con el medio.
  La mediana del seeing pasa de ~0,65″ en noches en calma a ~1,2″ con viento fuerte. Coincide con Abárzuza et al. 2025, donde
  la racha máxima de viento en 1 minuto era la variable más importante.
- **Las noches frías son peores** (r = −0,32 con la temperatura media), sobre todo por efecto del invierno.
- La humedad por sí sola apenas influye en el seeing (r ≈ 0); la presión y el enfriamiento de la noche tienen efectos débiles.
- **Dirección del viento:** los vientos del este (E–SE, 0,96″) son claramente peores que los del oeste y el norte (0,72″), lo
  que encaja con aire que llega sobre la caldera y la cresta de la isla en lugar de hacerlo desde mar abierto.

![Seeing frente al tiempo](figures/03_seeing_vs_weather.png)
![Seeing según la dirección del viento](figures/03_seeing_by_wind_direction.png)

## 3. Las referencias que tiene que superar cualquier modelo

| Objetivo | Corr(esta noche, anoche) | RMSE de persistencia | RMSE de climatología mensual |
|---|---|---|---|
| Mediana del seeing de la noche (″) | 0,37 | 0,41 | **0,34** |
| Cierre reconstruido (fracción de la noche) | 0,55 | 0,31 | 0,31 |
| Tiempo perdido por meteorología en el WHT (fracción) | 0,48 | 0,33 | 0,31 |

- En el **seeing**, «igual que anoche» es *peor* que «el valor típico de este mes». El seeing cambia mucho de una noche a otra,
  así que el listón es la climatología (RMSE 0,34″) y, dentro de la noche, el *precasting* (el valor de la última hora).
- En los **cierres**, persistencia y climatología son igual de buenas: el mal tiempo llega en rachas de varios días. Un modelo
  útil tiene que predecir cuándo empieza y acaba una racha, y para eso hace falta la **previsión** del tiempo, no solo las
  observaciones pasadas.

## 4. Calidad de la etiqueta: la contabilidad del WHT no es igual de fiable todos los años

En **2019–2022 y 2024–2025** el WHT declara aproximadamente la mitad de pérdidas por meteorología que otros años (8–12 % del
tiempo de noche frente a 16–28 %), mientras que el cierre basado en la humedad sigue en su 12–17 % habitual. Un cambio real
del tiempo movería las dos líneas.

![Por año](figures/05_losses_per_year.png)

Las páginas de contabilidad lo explican: muchas noches el WHT declara **toda la noche como observada, sin pérdidas por
meteorología, técnicas ni de otro tipo**, aunque la humedad del NOT mantuvo las cúpulas cerradas al menos el 80 % de la noche.
Parecen partes sin rellenar, no observación real (parte de ese periodo coincide con la adaptación del WHT para el instrumento
WEAVE; la causa no está documentada públicamente).

| Periodo | Noches cerradas ≥ 80 % (NOT) | …de las que el WHT dice «todo observado» |
|---|---|---|
| 2007–2018 | 453 | 62 (14 %) |
| 2019–2026 | 276 | 156 (57 %) |

La correlación noche a noche baja de **0,74** (2007–2018) a **0,46** (2019–2026).

**Consecuencia para el modelado:** las pérdidas del WHT solo se pueden usar como etiqueta de entrenamiento tras quitar las
218 noches sospechosas (o los años afectados). Esta decisión se toma de forma explícita en el paso de modelado y se comunica,
nunca se oculta.

## Siguientes pasos

Hecho en el paso de modelado ([MODELS_01.md](MODELS_01.md)). Las pérdidas del WHT solo se ajustan con años de registro fiable
(2017, 2018, 2023) y se prueban con 2026; 2019–2022 y 2024–2025 se muestran solo para comparar.
