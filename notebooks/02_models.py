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
# # 02 — Forecasting tonight: dome closure, seeing and hours lost
#
# > **Previous study, kept as it was.** The current model (RoqueModel, a random forest that forecasts each
# > night hour) and its scores are in `docs/DETALLES_TECNICOS.md` (in Spanish) and on the web page.
#
# **Independent project, not affiliated with GRANTECAN or any observatory.** All data are real and public.
# Inputs known at the start of the night: the ECMWF IFS HRES forecast (Open-Meteo archive), the NOT station
# in the 2 hours before the night, last night's outcome and the time of year (`src/roque_forecast/features.py`).
#
# Train 2017–2022, choose settings on 2023, **test on 2024–2026** (never seen by any step). Every model is
# compared with reference methods it must beat: climatology, persistence and precasting.
# Built with `python -m roque_forecast.features` and `python -m roque_forecast.train`.

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
# ## 1. Dome closure risk
#
# Label: the humidity rule (close at ≥ 90 %, reopen after 20 min below) closes the dome for at least 1 hour.
# About 1 night in 5. Scores: **Brier** (mean squared error of the probability; lower is better) and
# **Brier skill** against climatology (0 = no better than "the usual for this month", 1 = perfect).

# %%
closure[["inputs", "method", "nights", "brier", "brier_skill_vs_climatology", "auc", "hit_rate", "false_alarm_ratio"]]

# %%
fig, ax = plt.subplots(figsize=(10, 3.6))
skill_bars(ax, closure[closure["inputs"] == "forecast archive"], "brier_skill_vs_climatology",
           "Dome closure, test 2024–2026: Brier skill against climatology (blue = models)",
           "Brier skill (higher is better)")
plotting.save(fig, "06_closure_skill")

# %% [markdown]
# Is a predicted "30 %" really closed 30 % of the time? The **reliability diagram** groups the test nights by
# predicted probability and compares with how often the dome really closed. On the diagonal = trustworthy.

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
# Which inputs matter? **Permutation importance**: shuffle one input on the test nights and measure how much
# the Brier score worsens.

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
# Label: median R2D2 seeing of the night (arcsec). Scores: RMSE (root mean squared error, in arcsec) and
# skill against climatology. Persistence is worse than climatology here: one night's turbulence says
# little about the next.

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
# ## 3. Hours lost to weather (WHT)
#
# The predicted closure hours are converted to WHT hours with a single factor fitted on the years whose
# WHT log is reliable (2017, 2018, 2023) and tested on 2026. 2024–2025 are shown for comparison only: in those
# years the WHT books many closed nights as fully observed (EDA section 6), so no model can match them.

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
# ## 4. With a forecast issued 24 hours earlier
#
# The training archive stitches the first hours of each model run, which is a little better than the forecast
# an operator has in the afternoon. Open-Meteo also keeps the forecasts made 24 h before (since 2025): a little
# worse than reality. The rows with `inputs = 24 h old forecast` above use those, on 2025–2026 test nights.
# The skill barely changes, because most of it comes from the station readings before the night and from the
# season; without them (`forecast only`), the forecast still beats every baseline for seeing but loses
# against precasting for the dome.

# %%
both = pd.concat([closure.assign(target="closure", score=closure["brier_skill_vs_climatology"]),
                  seeing.assign(target="seeing", score=seeing["rmse_skill_vs_climatology"])])
both[both["kind"] == "model"].pivot_table(index=["target", "method"], columns="inputs", values="score").round(3)

# %% [markdown]
# ## Reading the results
# - **Dome closure:** gradient boosting gets a Brier skill of 0.55 against climatology, against 0.45 for the best
#   reference (precasting: "is it already humid before the night?"). It mostly sharpens precasting with the
#   forecast; the station humidity before the night is by far the strongest input. Between 40 % and 90 % the
#   probabilities are somewhat too high (reliability diagram): a calibration step is a possible improvement.
# - **Seeing:** ~18 % less RMSE than climatology. Wind before the night is the strongest input, as in
#   Abárzuza et al. 2025. Good nights are still hard to tell apart: most of the turbulence is above the
#   ground layer the station sees.
# - **Hours lost:** in 2026 the forecast beats both references (RMSE 2.65 h against 2.99 h for climatology, MAE
#   1.36 h against 1.42 h for persistence).
# - **Limits:** one site, one forecast model, ~10 years. The labels are a rebuilt rule (closure) and a human
#   log (WHT), not the GTC's own decisions.
