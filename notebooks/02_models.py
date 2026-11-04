# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 02: previsión de esta noche: cierre de cúpula, seeing y horas perdidas
#
# > **Estudio previo, conservado tal cual.** El modelo actual (RoqueModel, un random forest que pronostica cada
# > hora de la noche) y sus resultados están en `docs/DETALLES_TECNICOS.md` y en la web.
#
# **Proyecto independiente, sin afiliación con GRANTECAN ni con ningún observatorio.** Todos los datos son reales y públicos.
# Entradas conocidas al empezar la noche: la previsión ECMWF IFS HRES (archivo de Open-Meteo), la estación del NOT
# en las 2 horas antes de la noche, lo que pasó anoche y la época del año (`src/roque_forecast/features.py`).
#
# Entrenar con 2017–2022, elegir ajustes con 2023 y **probar con 2024–2026** (ningún paso los ha visto). Cada modelo se
# compara con métodos de referencia que tiene que superar: climatología, persistencia y precasting.
# Generado con `python -m roque_forecast.features` y `python -m roque_forecast.train`.

# %%
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from roque_forecast import config, plotting

plotting.apply_style()
BLUE, ORANGE, AQUA, YELLOW = plotting.SERIES[:4]
RESULTS = config.PROJECT_DIR / "reports" / "results"
closure = pd.read_csv(RESULTS / "closure_metrics.csv")
seeing = pd.read_csv(RESULTS / "seeing_metrics.csv")
lost = pd.read_csv(RESULTS / "lost_hours_metrics.csv")
predictions = pd.read_parquet(config.PROCESSED_DIR / "predictions.parquet")
test = predictions[predictions["split"] == "test"]
print(json.loads((RESULTS / "settings.json").read_text()))


# %%
def skill_bars(ax, frame, column, title, xlabel):
    """Horizontal bars, one per method; models in blue, baselines in grey."""
    frame = frame.iloc[::-1]
    colors = [BLUE if kind == "model" else plotting.GRID for kind in frame["kind"]]
    ax.barh(frame["method"], frame[column], color=colors, height=0.6)
    for y, value in enumerate(frame[column]):
        ax.annotate(f"{value:.2f}", (max(value, 0), y), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9, color=plotting.TEXT_SECONDARY)
    ax.axvline(0, color=plotting.TEXT_SECONDARY, linewidth=1)
    ax.set_title(title)
    ax.set_xlabel(xlabel)


# %% [markdown]
# ## 1. Riesgo de cierre de cúpula
#
# Etiqueta: la regla de humedad (cerrar con ≥ 90 %, reabrir tras 20 min por debajo) cierra la cúpula al menos 1 hora.
# Ocurre aproximadamente 1 de cada 5 noches. Medidas: **Brier** (error cuadrático medio de la probabilidad; cuanto más bajo, mejor) y
# **Brier skill** frente a la climatología (0 = no mejora «lo habitual de este mes», 1 = perfecto).

# %%
closure[["inputs", "method", "nights", "brier", "brier_skill_vs_climatology", "auc", "hit_rate", "false_alarm_ratio"]]

# %%
fig, ax = plt.subplots(figsize=(10, 3.6))
skill_bars(ax, closure[closure["inputs"] == "forecast archive"], "brier_skill_vs_climatology",
           "Dome closure, test 2024–2026: Brier skill against climatology (blue = models)",
           "Brier skill (higher is better)")
plotting.save(fig, "06_closure_skill")

# %% [markdown]
# ¿Un «30 %» previsto se cierra de verdad el 30 % de las veces? El **diagrama de fiabilidad** agrupa las noches de prueba por
# probabilidad prevista y lo compara con la frecuencia real de cierre. Sobre la diagonal = fiable.

# %%
bins = np.linspace(0, 1, 11)
groups = pd.cut(test["p_closed"], bins, include_lowest=True)
reliability = test.groupby(groups, observed=True).agg(predicted=("p_closed", "mean"),
                                                      observed=("closed", "mean"), nights=("closed", "size"))
fig, ax = plt.subplots(figsize=(5.2, 5))
ax.plot([0, 1], [0, 1], color=plotting.TEXT_SECONDARY, linestyle="--", linewidth=1)
ax.plot(reliability["predicted"], reliability["observed"], color=BLUE, marker="o", markersize=7)
for _, row in reliability.iterrows():
    ax.annotate(f"{row['nights']:.0f}", (row["predicted"], row["observed"]), xytext=(6, -10),
                textcoords="offset points", fontsize=8, color=plotting.TEXT_SECONDARY)
ax.set_xlabel("predicted probability of closure")
ax.set_ylabel("observed share of nights closed")
ax.set_title("Reliability, test 2024–2026\n(numbers = nights per bin)")
plotting.save(fig, "07_closure_reliability")

# %% [markdown]
# ¿Qué entradas importan? **Importancia por permutación**: se barajan los valores de una entrada en las noches de prueba y se mide
# cuánto empeora el Brier.

# %%
def importance_plot(name, title, figure):
    imp = pd.read_csv(RESULTS / f"{name}_importance.csv").head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.barh(imp["feature"], imp["importance"], xerr=imp["std"], color=BLUE, height=0.6,
            error_kw={"ecolor": plotting.TEXT_SECONDARY, "linewidth": 1})
    ax.set_title(title)
    ax.set_xlabel("loss of score when the input is shuffled")
    plotting.save(fig, figure)


importance_plot("closure", "Dome closure: 10 most important inputs (test)", "08_closure_importance")

# %% [markdown]
# ## 2. Seeing
#
# Etiqueta: mediana del seeing R2D2 de la noche (segundos de arco). Medidas: RMSE (raíz del error cuadrático medio, en segundos de arco) y
# skill frente a la climatología. Aquí la persistencia es peor que la climatología: la turbulencia de una noche dice
# poco de la siguiente.

# %%
seeing[["inputs", "method", "nights", "rmse", "mae", "rmse_skill_vs_climatology"]]

# %%
fig, ax = plt.subplots(figsize=(10, 3))
skill_bars(ax, seeing[seeing["inputs"] == "forecast archive"], "rmse_skill_vs_climatology",
           "Seeing, test 2024–2026: RMSE skill against climatology (blue = models)",
           "RMSE skill (higher is better)")
plotting.save(fig, "09_seeing_skill")

# %%
seen = test.dropna(subset=["seeing_median"])
fig, ax = plt.subplots(figsize=(5.2, 5))
ax.scatter(seen["pred_seeing"], seen["seeing_median"], s=12, color=BLUE, alpha=0.45, linewidth=0)
ax.plot([0.4, 2.5], [0.4, 2.5], color=plotting.TEXT_SECONDARY, linestyle="--", linewidth=1)
ax.set_xlim(0.4, 2.5)
ax.set_ylim(0.3, 3.4)
ax.set_xlabel('predicted seeing (")')
ax.set_ylabel('measured median seeing (")')
ax.set_title("Seeing, test nights 2024–2026")
plotting.save(fig, "10_seeing_predicted_vs_measured")

# %%
importance_plot("seeing", "Seeing: 10 most important inputs (test)", "11_seeing_importance")

# %% [markdown]
# ## 3. Horas perdidas por el tiempo (WHT)
#
# Las horas de cierre previstas se convierten en horas del WHT con un único factor ajustado en los años cuyo
# registro del WHT es fiable (2017, 2018, 2023) y se prueban con 2026. 2024–2025 se muestran solo para comparar: en esos
# años el WHT da por totalmente observadas muchas noches cerradas (apartado 6 del EDA), así que ningún modelo puede coincidir con ellos.

# %%
lost[["inputs", "method", "nights", "rmse", "mae", "rmse_skill_vs_climatology"]]

# %%
year = predictions[(predictions["year"] == 2026)].dropna(subset=["wht_weather_lost_h"])
weekly = year[["wht_weather_lost_h", "pred_lost_h", "dome_closed_h"]].resample("W").sum()
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(weekly.index, weekly["wht_weather_lost_h"], color=ORANGE, marker="o", markersize=4,
        label="WHT hours lost to weather (log)")
ax.plot(weekly.index, weekly["pred_lost_h"], color=BLUE, marker="o", markersize=4, label="forecast")
ax.set_ylabel("hours per week")
ax.set_title("Hours lost to weather per week, 2026 (test year)")
ax.legend(loc="upper right")
plotting.save(fig, "12_lost_hours_2026")

# %% [markdown]
# ## 4. Con una previsión emitida 24 horas antes
#
# El archivo de entrenamiento une las primeras horas de cada ejecución del modelo, algo mejor que la previsión
# que tiene un operador por la tarde. Open-Meteo también guarda las previsiones hechas 24 h antes (desde 2025): algo
# peores que la realidad. Las filas con `inputs = 24 h old forecast` de arriba usan esas previsiones, en las noches de prueba de 2025–2026.
# El skill apenas cambia, porque casi todo viene de las lecturas de la estación antes de la noche y de la
# época del año; sin ellas (`forecast only`), la previsión sigue superando a todas las referencias en el seeing, pero pierde
# frente al precasting en la cúpula.

# %%
both = pd.concat([closure.assign(target="closure", score=closure["brier_skill_vs_climatology"]),
                  seeing.assign(target="seeing", score=seeing["rmse_skill_vs_climatology"])])
both[both["kind"] == "model"].pivot_table(index=["target", "method"], columns="inputs", values="score").round(3)

# %% [markdown]
# ## Cómo leer los resultados
# - **Cierre de cúpula:** gradient boosting consigue un Brier skill de 0,55 frente a la climatología, frente a 0,45 de la mejor
#   referencia (precasting: «¿ya hay humedad antes de la noche?»). Sobre todo afina el precasting con la
#   previsión; la humedad de la estación antes de la noche es, con diferencia, la entrada más fuerte. Entre el 40 % y el 90 % las
#   probabilidades son algo altas (diagrama de fiabilidad): un paso de calibración es una posible mejora.
# - **Seeing:** ~18 % menos de RMSE que la climatología. El viento antes de la noche es la entrada más fuerte, como en
#   Abárzuza et al. 2025. Las noches buenas siguen siendo difíciles de distinguir: casi toda la turbulencia está por encima de la
#   capa cercana al suelo que ve la estación.
# - **Horas perdidas:** en 2026 la previsión supera a las dos referencias (RMSE de 2,65 h frente a 2,99 h de la climatología, MAE de
#   1,36 h frente a 1,42 h de la persistencia).
# - **Límites:** un sitio, un modelo de previsión, ~10 años. Las etiquetas son una regla reconstruida (cierre) y un registro
#   humano (WHT), no decisiones del propio GTC.
