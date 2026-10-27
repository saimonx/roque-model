# EDA 01 — Observing conditions at the Roque de los Muchachos

Independent project, not affiliated with GRANTECAN or any observatory. Real public data only (see README).
Full analysis and code: [`notebooks/01_eda.ipynb`](../notebooks/01_eda.ipynb).

> **Status (27 Oct 2026):** NOT weather (1997–2026) and R2D2 seeing (2018–2026) are complete.
> The ING night-by-night download (~7,000 pages at one every 3 s) is still running, so every
> number that uses the **WHT accounting covers only 2007–2008 for now** and will be refreshed.

## Data

| Source | Nights usable | Period |
|---|---|---|
| NOT weather, ≥ 80 % of the night covered | 10,682 | Feb 1997 → today (5-min sampling until 2006, 1 min from 2007) |
| R2D2 seeing, ≥ 40 values in the night | 2,054 | Sep 2018 → today |
| WHT accounting (ING) | *downloading* | 2007 → today |

A night is labelled with the date on which it starts and only **astronomical night** (Sun below −18°) is
used. Our twilight times match the ING's to the minute.

![Usable nights per year](figures/01_coverage.png)

## 1. The dome-closure rule rebuilt from humidity works

The NOT public export has no rain or dome flags, so the closure was rebuilt from humidity
(close at ≥ 90 %, reopen after 20 min below). Compared with the hours the WHT really lost to weather:

- **Correlation 0.72** night by night; **89 %** agreement on "more than half of the night lost".
- The seasonal cycle matches: almost nothing lost in July–August, worst in winter. Over the full 30 years of
  NOT data the rebuilt closure takes **0.4 %** of the night in July and **23–28 %** from November to January.
- The rule **under-estimates winter losses**. Nights lost without high humidity point to other causes
  (wind, dust/calima, snow and ice on the domes, cloud over dry air). These are the extra inputs the
  closure model needs.

![Seasonal cycle](figures/02_closure_vs_losses_monthly.png)

## 2. Seeing

- Median of nightly medians **0.81″** (25–75 %: 0.67″–1.04″), close to the 0.77″ reported for the TNG
  2017–2024 (de Sepibus, Masciadri et al. 2026).
- **Wind is the strongest single driver:** Spearman r = +0.58 with the night's maximum wind and +0.46
  with the mean. Median seeing goes from ~0.65″ in calm nights to ~1.2″ with strong wind. This agrees
  with Abárzuza et al. 2025, where the 1-min maximum wind gust was the most important variable.
- **Cold nights are worse** (r = −0.32 with mean temperature), largely a winter effect.
- Humidity alone barely matters for seeing (r ≈ 0); pressure and the night's cooling have weak effects.
- **Wind direction:** easterly winds (E–SE, 0.96″) are clearly worse than westerly and northerly winds
  (0.72″), consistent with air arriving over the island's caldera and ridge instead of the open ocean.

![Seeing vs weather](figures/03_seeing_vs_weather.png)
![Seeing by wind direction](figures/03_seeing_by_wind_direction.png)

## 3. The baselines any model must beat

| Target | Corr(tonight, last night) | Persistence RMSE | Monthly-climatology RMSE |
|---|---|---|---|
| Nightly median seeing (″) | 0.37 | 0.41 | **0.34** |
| Rebuilt closure (fraction of night) | 0.55 | 0.31 | 0.31 |
| WHT weather lost (fraction, 2007–08 only) | 0.44 | 0.38 | 0.33 |

- For **seeing**, "same as last night" is *worse* than "typical value for this month". Seeing changes a
  lot from night to night, so the bar to beat is climatology (RMSE 0.34″), and within the night,
  *precasting* (last hour's value).
- For **closures**, persistence and climatology are equally good: bad weather comes in spells lasting
  several days. A useful model has to predict when a spell starts and ends, which needs the weather
  **forecast**, not only past observations.

## Next steps
1. Finish the ING download; refresh sections 1 and 3 with ~19 years of accounting.
2. Archived weather forecasts (Open-Meteo historical forecast API) as model inputs for "tonight".
3. Models (logistic/linear → random forest / gradient boosting) with a time-based split
   (train ≤ 2023, validate 2024, test 2025–26), always reported against the baselines above.
