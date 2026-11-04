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
# # 01: análisis exploratorio de las condiciones de observación en el Roque de los Muchachos
#
# > **Estudio previo, conservado tal cual.** El modelo actual (RoqueModel, un random forest que pronostica cada
# > hora de la noche) y sus resultados están en `docs/DETALLES_TECNICOS.md` y en la web.
#
# **Proyecto independiente, sin afiliación con GRANTECAN ni con ningún observatorio.** Todos los datos son reales y públicos:
# archivo meteorológico del NOT (1997→), monitor de seeing R2D2 del ING (2018→) y contabilidad nocturna del
# Telescopio William Herschel publicada por el ING (2007→). Las fuentes están en el README.
#
# Preguntas de este notebook:
# 1. ¿Cómo de completa es cada fuente, año a año?
# 2. ¿La regla de cierre de cúpula reconstruida con la humedad (cerrar con ≥ 90 %, reabrir tras 20 min por debajo)
#    coincide con las horas que el WHT perdió de verdad por el tiempo?
# 3. ¿Cómo es el seeing y qué variables meteorológicas se mueven con él?
# 4. ¿Cómo de fuertes son las referencias más simples (persistencia: «esta noche = anoche»)? Cualquier modelo tiene que superarlas.
#
# Cada **noche** se etiqueta con la fecha en que empieza y solo se usa la **noche astronómica**
# (Sol a más de 18° por debajo del horizonte).

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from roque_forecast import config, plotting

plotting.apply_style()
BLUE, ORANGE = plotting.SERIES[0], plotting.SERIES[1]

nights = pd.read_parquet(config.PROCESSED_DIR / "nights.parquet")
nights = nights[nights.index < pd.Timestamp.now().normalize()]  # finished nights only
print(f"{len(nights):,} nights, {nights.index.min().date()} → {nights.index.max().date()}")

# %% [markdown]
# ## 1. Cobertura de los datos
#
# Una noche cuenta como «útil» para la meteorología cuando al menos el 80 % de sus bloques de 10 minutos tiene datos del NOT;
# para el seeing, cuando R2D2 registró al menos 40 valores; para las pérdidas, cuando la página del ING tiene contabilidad real.

# %%
usable = pd.DataFrame({
    "NOT weather": nights["coverage"] >= 0.8,
    "R2D2 seeing": nights["seeing_median"].notna(),
    "WHT accounting": nights["wht_has_accounting"].fillna(False).astype(bool),
}).groupby(nights["year"]).sum()

fig, ax = plt.subplots(figsize=(10, 3.6))
for i, column in enumerate(usable.columns):
    ax.plot(usable.index, usable[column], marker="o", markersize=4, label=column, color=plotting.SERIES[i])
ax.set_ylim(0, 380)
ax.set_ylabel("usable nights per year")
ax.set_title("Usable nights per year and source")
ax.legend(loc="center left", bbox_to_anchor=(0, 0.42), ncols=3)
plotting.save(fig, "01_coverage")
usable.T

# %% [markdown]
# ## 2. Cierres de cúpula reconstruidos frente a pérdidas reales por el tiempo
#
# La exportación pública del NOT no incluye indicadores de lluvia ni de cúpula, así que el cierre se reconstruye con la humedad.
# Si la regla tiene sentido, la fracción cerrada de cada noche debería seguir a la fracción de la
# noche que el WHT (4,2 m, misma montaña) perdió por el tiempo.

# %%
both = nights[["dome_closed_frac", "wht_weather_lost_frac"]].dropna()
corr = both.corr().iloc[0, 1]
print(f"{len(both):,} nights with both values; Pearson correlation = {corr:.2f}")

monthly = both.groupby(both.index.month).mean()
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(monthly.index, monthly["dome_closed_frac"] * 100, marker="o", markersize=5, color=BLUE,
        label="Rebuilt closure (NOT humidity ≥ 90 %)")
ax.plot(monthly.index, monthly["wht_weather_lost_frac"] * 100, marker="o", markersize=5, color=ORANGE,
        label="WHT time lost to weather (ING)")
ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
ax.set_ylabel("% of the night")
ax.set_ylim(0, None)
ax.set_title("Seasonal cycle: rebuilt closures vs. real weather losses")
ax.legend(loc="upper center")
plotting.save(fig, "02_closure_vs_losses_monthly")

# %% [markdown]
# Noche a noche: ¿con qué frecuencia coinciden las dos fuentes en que «se perdió la mayor parte de la noche»?

# %%
closed_most = both["dome_closed_frac"] > 0.5
lost_most = both["wht_weather_lost_frac"] > 0.5
agreement = pd.crosstab(closed_most.rename("rebuilt: closed > 50 %"), lost_most.rename("WHT: lost > 50 %"))
print(f"Agreement: {(closed_most == lost_most).mean():.1%} of nights")
agreement

# %%
fig, ax = plt.subplots(figsize=(5.5, 5))
ax.hexbin(both["dome_closed_frac"] * 100, both["wht_weather_lost_frac"] * 100, gridsize=20, bins="log",
          cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list("blue", plotting.BLUE_RAMP), mincnt=1)
ax.plot([0, 100], [0, 100], color=plotting.TEXT_SECONDARY, linewidth=1, linestyle="--")
ax.set_xlabel("rebuilt closure (% of night)")
ax.set_ylabel("WHT lost to weather (% of night)")
ax.set_title("Each night (darker = more nights)")
plotting.save(fig, "02_closure_vs_losses_nights")

# %% [markdown]
# Las noches que la regla no detecta son las interesantes: las pérdidas sin humedad alta suelen deberse a
# **viento**, **polvo (calima)**, **nieve o hielo en la cúpula** o nubes con aire seco. Indican qué
# entradas adicionales necesita el modelo de cierre.

# %%
missed = both[(both["wht_weather_lost_frac"] > 0.5) & (both["dome_closed_frac"] < 0.1)]
print(f"{len(missed)} nights lost by the WHT with < 10 % rebuilt closure")
nights.loc[missed.index, ["humidity_max", "wind_max", "wind_mean", "temp_mean", "wht_weather_lost_h"]].describe().round(1)

# %% [markdown]
# ## 3. Seeing (R2D2, mediana de la noche)

# %%
seeing = nights["seeing_median"].dropna()
print(f"{len(seeing):,} nights. Median of nightly medians = {seeing.median():.2f}\"; "
      f"25-75 % = {seeing.quantile(.25):.2f}\"–{seeing.quantile(.75):.2f}\"")

fig, ax = plt.subplots(figsize=(10, 3.6))
ax.hist(seeing, bins=np.arange(0.2, 3.0, 0.05), color=BLUE, edgecolor=plotting.SURFACE, linewidth=0.5)
ax.axvline(seeing.median(), color=plotting.TEXT_PRIMARY, linewidth=1)
ax.annotate(f"median {seeing.median():.2f}\"", (seeing.median(), ax.get_ylim()[1] * 0.9),
            xytext=(6, 0), textcoords="offset points", color=plotting.TEXT_PRIMARY)
ax.set_xlabel("nightly median seeing (arcsec, smaller is better)")
ax.set_ylabel("nights")
ax.set_title("Distribution of nightly seeing, R2D2 2018–2026")
plotting.save(fig, "03_seeing_hist")

# %% [markdown]
# ¿Cómo cambia el seeing con el tiempo? Se divide cada variable en cuantiles y se dibuja la mediana del
# seeing por tramo (resistente a valores atípicos), con la banda del 25–75 %.

# %%
features = {"wind_mean": "mean wind (m/s)", "wind_max": "max wind (m/s)", "humidity_mean": "mean humidity (%)",
            "pressure_mean": "mean pressure (hPa)", "temp_drop": "temperature drop in the night (°C)",
            "temp_mean": "mean temperature (°C)"}
data = nights[list(features) + ["seeing_median"]].dropna()

fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharey=True)
for ax, (column, label) in zip(axes.flat, features.items()):
    bins = pd.qcut(data[column], 10, duplicates="drop")
    stats = data.groupby(bins, observed=True)["seeing_median"].quantile([.25, .5, .75]).unstack()
    centres = data.groupby(bins, observed=True)[column].median()
    ax.fill_between(centres, stats[0.25], stats[0.75], color=BLUE, alpha=0.15, linewidth=0)
    ax.plot(centres, stats[0.5], color=BLUE, marker="o", markersize=4)
    ax.set_xlabel(label)
    ax.set_title(f"r = {data[column].corr(data['seeing_median'], method='spearman'):+.2f}", fontsize=10)
axes[0, 0].set_ylabel("seeing (\")")
axes[1, 0].set_ylabel("seeing (\")")
fig.suptitle("Median nightly seeing vs. weather (Spearman r in each title)", x=0.01, ha="left",
             fontweight="bold", color=plotting.TEXT_PRIMARY)
fig.tight_layout()
plotting.save(fig, "03_seeing_vs_weather")

# %% [markdown]
# La dirección del viento importa en la cima de una montaña: el aire que llega sobre la caldera de la isla es más
# turbulento que el que llega desde mar abierto.

# %%
data = nights[["wind_dir_mean", "seeing_median"]].dropna()
sectors = pd.cut(data["wind_dir_mean"], np.arange(0, 361, 45), labels=["N–NE", "NE–E", "E–SE", "SE–S", "S–SW", "SW–W", "W–NW", "NW–N"], include_lowest=True)
by_sector = data.groupby(sectors, observed=True)["seeing_median"].agg(["median", "size"])
fig, ax = plt.subplots(figsize=(10, 3.4))
ax.bar(by_sector.index.astype(str), by_sector["median"], color=BLUE, width=0.6)
for x, (median, n) in enumerate(by_sector.itertuples(index=False)):
    ax.annotate(f"{median:.2f}\"\n(n={n})", (x, median), ha="center", va="bottom", fontsize=8,
                color=plotting.TEXT_SECONDARY, xytext=(0, 2), textcoords="offset points")
ax.set_ylabel("median seeing (\")")
ax.set_xlabel("mean wind direction during the night (from)")
ax.set_title("Seeing by wind direction")
ax.set_ylim(0, by_sector["median"].max() * 1.25)
plotting.save(fig, "03_seeing_by_wind_direction")

# %% [markdown]
# ## 4. ¿Cómo de fuerte es la persistencia?
#
# La previsión más simple: esta noche será como anoche. Si anoche predice bien esta noche, un
# modelo tiene que hacerlo mejor para ser útil (de Sepibus, Masciadri et al. 2026).

# %%
def persistence_scores(series: pd.Series) -> dict:
    daily = series.asfreq("D")
    pair = pd.DataFrame({"tonight": daily, "last_night": daily.shift(1)}).dropna()
    error = pair["tonight"] - pair["last_night"]
    climatology = pair["tonight"].groupby(pair.index.month).transform("mean")
    return {
        "nights": len(pair),
        "corr(tonight, last night)": pair.corr().iloc[0, 1],
        "persistence RMSE": np.sqrt((error ** 2).mean()),
        "monthly-climatology RMSE": np.sqrt(((pair["tonight"] - climatology) ** 2).mean()),
    }

pd.DataFrame({
    "seeing median (\")": persistence_scores(nights["seeing_median"]),
    "rebuilt closure (fraction)": persistence_scores(nights["dome_closed_frac"]),
    "WHT weather lost (fraction)": persistence_scores(nights["wht_weather_lost_frac"]),
}).round(3)

# %% [markdown]
# ## 5. Visión a largo plazo: pérdidas por el tiempo por año (WHT)

# %%
accounted = nights.loc[nights["wht_has_accounting"].fillna(False).astype(bool)]
yearly = accounted.groupby("year").agg(
    lost=("wht_weather_lost_h", "sum"), night=("wht_night_h", "sum"), n=("wht_night_h", "size"),
    closed_pct=("dome_closed_frac", "mean"))
yearly["lost_pct"] = (yearly["lost"] / yearly["night"]).clip(upper=1) * 100
yearly["closed_pct"] *= 100
yearly = yearly[yearly["n"] >= 300]  # complete years only

fig, ax = plt.subplots(figsize=(10, 3.4))
ax.plot(yearly.index, yearly["closed_pct"], marker="o", markersize=5, color=BLUE,
        label="Rebuilt closure (NOT humidity ≥ 90 %)")
ax.plot(yearly.index, yearly["lost_pct"], marker="o", markersize=5, color=ORANGE,
        label="WHT time lost to weather (ING)")
ax.set_ylim(0, None)
ax.set_xticks(yearly.index[::2])
ax.set_ylabel("% of dark time")
ax.set_title("Per year: rebuilt closures vs. WHT weather losses (complete years)")
ax.legend(loc="lower left")
plotting.save(fig, "05_losses_per_year")
yearly.round(1)

# %% [markdown]
# ## 6. Calidad de la etiqueta: ¿se puede confiar en las pérdidas del WHT todos los años?
#
# En 2019–2022 y 2024–2025 el WHT declara aproximadamente la mitad de pérdidas por el tiempo que otros años, mientras que el
# cierre basado en la humedad sigue en el mismo nivel. Un cambio real del tiempo movería los dos. La propia
# contabilidad apunta a la causa: muchas noches la página declara **toda la noche como observada,
# sin pérdidas de ningún tipo**, aunque la humedad del NOT mantuvo las cúpulas cerradas casi toda la noche. Parecen
# noches con el parte sin rellenar, no observación real (el WHT se estaba adaptando para
# el instrumento WEAVE en parte de ese periodo). La causa no está documentada públicamente, así que solo se
# señalan. Se cuentan por año.

# %%
all_observed = ((accounted["wht_weather_lost_h"] == 0) & (accounted["wht_tech_lost_h"] == 0)
                & (accounted["wht_other_lost_h"] == 0))
closed_all_night = accounted["dome_closed_frac"] >= 0.8
suspect = accounted[all_observed & closed_all_night]
quality = pd.DataFrame({
    "nights closed ≥ 80 % (NOT)": closed_all_night.groupby(accounted["year"]).sum(),
    "…of which WHT says 'all observed'": (all_observed & closed_all_night).groupby(accounted["year"]).sum(),
})
quality["share (%)"] = (quality.iloc[:, 1] / quality.iloc[:, 0] * 100).round(0)
print(f"{len(suspect)} suspect nights in total")
quality.T

# %%
early = accounted["year"].between(2007, 2018)
for label, mask in [("2007–2018", early), ("2019–2026", ~early)]:
    pair = accounted.loc[mask, ["dome_closed_frac", "wht_weather_lost_frac"]].dropna()
    print(f"{label}: {len(pair):,} nights, correlation rebuilt closure vs. WHT losses = "
          f"{pair.corr().iloc[0, 1]:.2f}")

# %% [markdown]
# ## Resumen
# Las conclusiones están en `reports/EDA_01.md`.
