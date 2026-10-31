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
# # 01 — Exploratory analysis of observing conditions at the Roque de los Muchachos
#
# **Independent project, not affiliated with GRANTECAN or any observatory.** All data are real and public:
# NOT weather archive (1997→), ING R2D2 seeing monitor (2018→) and ING nightly accounting of the
# William Herschel Telescope (2007→). See the README for sources.
#
# Questions for this notebook:
# 1. How complete is each source, year by year?
# 2. Does the dome-closure rule rebuilt from humidity (close at ≥ 90 %, reopen after 20 min below)
#    agree with the hours the WHT really lost to weather?
# 3. What does the seeing look like, and which weather variables move with it?
# 4. How strong are the naive baselines (persistence: "tonight = last night")? Any model must beat them.
#
# A **night** is labelled with the date on which it starts, and only **astronomical night**
# (Sun more than 18° below the horizon) is used.

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
# ## 1. Data coverage
#
# A night counts as "usable" for the weather when at least 80 % of its 10-minute blocks have NOT data;
# for seeing when R2D2 recorded at least 40 values; for losses when the ING page has real accounting.

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
# ## 2. Rebuilt dome closures vs. real weather losses
#
# The NOT public export has no rain or dome flags, so the closure is rebuilt from humidity.
# If the rule is sensible, the closed fraction of each night should track the fraction of the
# night the WHT (4.2 m, same mountain) lost to weather.

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
# Night by night: how often do the two sources agree on "most of the night was lost"?

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
# Nights the rule misses are the interesting ones: losses without high humidity are usually
# **wind**, **dust (calima)**, **snow/ice on the dome** or clouds with dry air. They tell us which
# extra inputs the closure model needs.

# %%
missed = both[(both["wht_weather_lost_frac"] > 0.5) & (both["dome_closed_frac"] < 0.1)]
print(f"{len(missed)} nights lost by the WHT with < 10 % rebuilt closure")
nights.loc[missed.index, ["humidity_max", "wind_max", "wind_mean", "temp_mean", "wht_weather_lost_h"]].describe().round(1)

# %% [markdown]
# ## 3. Seeing (R2D2, nightly median)

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
# How does seeing change with the weather? We bin each variable into quantiles and plot the median
# seeing per bin (robust to outliers), with the 25–75 % band.

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
# Wind direction matters at a mountain-top site: air arriving over the island's caldera is more
# turbulent than air arriving from the open ocean.

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
# ## 4. How strong is persistence?
#
# The simplest forecast: tonight will be like last night. If last night predicts tonight well, a
# model must do better than that to be useful (de Sepibus, Masciadri et al. 2026).

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
# ## 5. Long-term view: weather losses per year (WHT)

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
# ## 6. Label quality: can the WHT losses be trusted every year?
#
# In 2019–2022 and 2024–2025 the WHT reports about half the weather losses of other years, while the
# humidity-based closure stays at the same level. A real change in the weather would move both. The
# accounting itself points to the cause: on many nights the page reports the **whole night as observed
# with zero losses of any kind** even though the NOT humidity kept domes closed nearly all night. Those
# look like nights without a filled-in report rather than real observing (the WHT was being adapted for
# the WEAVE instrument in part of that period). The cause is not documented publicly, so we only flag
# them. We count them per year.

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
# ## Summary
# Findings are written up in `reports/EDA_01.md`.
