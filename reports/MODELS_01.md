# Models 01 — Forecasting tonight at the Roque de los Muchachos

> **Independent project**, not affiliated with GRANTECAN or any observatory. All data are real and public.
> Notebook: [`notebooks/02_models.ipynb`](../notebooks/02_models.ipynb). Code: `src/roque_forecast/features.py`,
> `src/roque_forecast/train.py`. Metrics: [`reports/results/`](results/).

## The question

At the start of the night, using only what is known at that moment:
1. **Will the dome have to close?** The label is the NOT humidity rule (≥ 90 %, reopen after 20 min
   below) closing it for at least 1 hour. That happens on about 1 night in 5.
2. **How good will the seeing be?** The label is the median R2D2 DIMM seeing of the night.
3. **How many hours will be lost to weather?** The label is the WHT nightly accounting.

## Inputs (all available before the night starts)

| Group | Inputs | Source |
|---|---|---|
| Forecast for the night | humidity (mean, max), dew-point spread, temperature and its drop, wind (mean, max, east–west and north–south parts), cloud cover, precipitation, pressure | ECMWF IFS HRES 9 km through the [Open-Meteo](https://open-meteo.com) forecast archives (CC BY 4.0) |
| Station before the night | humidity (mean, max), wind and pressure in the 2 h before astronomical night | NOT weather archive |
| Persistence | last night's closure fraction and median seeing | NOT, R2D2 |
| Season | sine and cosine of the day of the year | — |

Real forecasts, not measured weather, are what make the evaluation honest. Two archives are used:
- **Training and main test:** first hours of each model run, from 2017. This is slightly *better* than the
  afternoon forecast.
- **Check:** the forecasts issued 24 h earlier, from 2025. These are slightly *worse* than the afternoon
  forecast.

The real skill lies between the two results.

## Method

- **Time split:** train 2017–2022 (2,191 nights), choose settings on 2023 (365), test on 2024–Oct 2026 (1,031).
  The test years were never used for any choice.
- **Models:** gradient boosting (scikit-learn `HistGradientBoosting`; a 2×2×2 grid chosen on 2023), with a
  linear or logistic regression as a simpler alternative. Seeing is modelled on a log scale.
- **Reference methods:** each is turned into a probability using the training years only.
  - climatology: the usual value for the month;
  - persistence: same as last night;
  - precasting: the conditions at the station just before the night;
  - for closure only, a plain rule on the forecast humidity.

## Results on the test years (2024–2026)

### 1. Dome closure (1,025 nights)

| Method | Brier ↓ | Brier skill vs climatology ↑ | AUC ↑ | Closures warned | False alarms |
|---|---|---|---|---|---|
| Climatology (month) | 0.149 | 0 | 0.70 | — | — |
| Persistence (last night) | 0.131 | 0.12 | 0.72 | 56 % | 44 % |
| Precasting (humidity ≥ 90 % before the night) | 0.082 | 0.45 | 0.83 | 71 % | 17 % |
| Forecast rule (forecast humidity ≥ 95 %) | 0.153 | −0.02 | 0.64 | — | — |
| **Gradient boosting** | **0.067** | **0.55** | **0.96** | **79 %** | 25 % |
| Logistic regression | 0.078 | 0.48 | 0.95 | 78 % | 27 % |
| Gradient boosting, forecast only | 0.094 | 0.37 | 0.91 | 68 % | 33 % |

- **Best model:** gradient boosting cuts the Brier score by 18 % against the best reference (precasting).
- **24-hour-old forecasts** (398 nights in 2025–2026): skill 0.56, against 0.44 for precasting. The result
  holds when the forecast is older.
- **Strongest input:** the station humidity just before the night. The model refines that reading with the
  forecast wind and precipitation.
- **Forecast only:** without the station readings (for example, planning tomorrow night) the forecast is still
  far better than climatology or persistence. It does not reach precasting.
- **Calibration:** probabilities between 40 % and 90 % are somewhat too high (reliability diagram in the
  notebook).

![Closure skill](figures/06_closure_skill.png)

### 2. Seeing (780 nights with R2D2 data)

| Method | RMSE (″) ↓ | MAE (″) ↓ | RMSE skill vs climatology ↑ |
|---|---|---|---|
| Climatology (month) | 0.350 | 0.227 | 0 |
| Persistence (last night) | 0.415 | 0.278 | −0.19 |
| **Gradient boosting** (with the jet-stream wind) | **0.284** | **0.197** | **0.19** |
| Gradient boosting, without the jet-stream wind | 0.286 | 0.198 | 0.18 |
| Linear regression (log) | 0.288 | 0.202 | 0.18 |
| Gradient boosting, forecast only | 0.310 | 0.219 | 0.11 |

- **24-hour-old forecasts:** 0.303″ against 0.378″ for climatology (skill 0.20).
- **Jet-stream wind (added 28 Oct 2026).** Turbulence high up blurs the stars even when the ground is calm.
  The ECMWF archive has no pressure levels, so the 200 hPa wind (~12 km) comes from the NOAA GFS archive,
  which starts in March 2021; older nights have no value (gradient boosting handles gaps natively). It was
  accepted on the validation year only (RMSE 0.347″ → 0.340″ on 2023). On the test years the gain is small
  but holds in both archives (0.286″ → 0.284″; 24 h old: 0.306″ → 0.303″). The dome models do not use it.
- **Strongest input:** the station wind before the night, then temperature and season. This matches
  Abárzuza et al. 2025.
- **Limit:** a linear model is almost as good. Most of the turbulence is in layers the ground station does
  not see, so the remaining error is large.

### 3. Hours lost to weather (WHT)

**Why a calibration line.** Only three years combine a forecast archive with a reliable WHT log: 2017, 2018
and 2023. Section 6 of the EDA explains which years are reliable. Those three years are too few for their own
model. Instead, the closure-hours forecast is converted with one factor fitted on those years:
`lost = 0.85 × predicted closed hours`.

- The predicted hours used for the fit come from models that had not seen that year ("out of fold").
- A free intercept was rejected on the same years, before looking at 2026. It added 0.6 h to every clear
  night.

| Test set | Method | RMSE (h) ↓ | MAE (h) ↓ |
|---|---|---|---|
| **2026** (reliable, 299 nights) | Climatology (month, 2010–2018) | 2.99 | 2.09 |
| | Persistence (last night) | 3.23 | 1.42 |
| | **Calibrated closure forecast** | **2.65** | **1.36** |
| 2024–2025 (suspect log, comparison only) | Climatology | 2.65 | 2.09 |
| | Persistence | 2.87 | 1.21 |
| | Calibrated closure forecast | 2.93 | 1.55 |

- **2026:** the forecast beats both references on both scores.
- **2024–2025:** it does not, because in those years the log books many closed nights as observed. The model
  is right about the weather and the label is not. This is why those years are excluded from fitting.

## 4. Hour by hour (added 28 Oct 2026, `hourly.py`)

One row per night hour with at least 30 minutes of astronomical night (32,153 hours, 2017–2026). Labels:
dome closed for at least half of the hour (NOT humidity rule); at least one minute of wind ≥ 22.2 m/s
(80 km/h, the INT closing limit); hourly median R2D2 seeing. Inputs: the forecast at mid-hour (ECMWF;
GFS 750 hPa wind from 2021), plus the nightly inputs and the position of the hour in the night. Same
split and the same rule: settings chosen on 2023, results on 2024–2026 (8,577 hours).

| Closure for humidity | Brier ↓ | Skill vs climatology ↑ | AUC | Closed hours caught | Wrong "close" calls |
|---|---|---|---|---|---|
| Climatology (month) | 0.127 | 0 | 0.65 | — | — |
| Raw forecast, read literally (yes/no) | 0.569 | −3.46 | 0.64 | 95 % | 79 % |
| Precasting (humidity before night ≥ 90 %) | 0.071 | 0.44 | 0.87 | 81 % | 34 % |
| **Gradient boosting** | **0.057** | **0.55** | **0.96** | 73 % | 25 % |
| Gradient boosting, forecast only | 0.078 | 0.38 | 0.92 | 59 % | 31 % |

- **Wind** is rare (1.4 % of hours) and the 10 m wind of the ECMWF grid point is useless at the summit
  (mean 1.3 m/s, never above 6.5 m/s), so the GFS 750 hPa wind was added. Probabilities stay badly calibrated
  (Brier skill 0.01 final, −0.24 forecast only) but the ranking is good (AUC 0.96 / 0.95), so the model
  drives a **warning** with the threshold that maximises the Peirce score on 2023: on the test hours it
  catches 90 % (final) / 80 % (forecast only) of the windy hours, with 85–88 % false alarms. The raw
  forecast read literally catches 4 %.
- **Seeing**: RMSE 0.358″ against 0.409″ for monthly climatology (skill 0.13); forecast only 0.373″.
- **Ice and dust** are warnings from simple rules (no label to evaluate them yet; the dust forecast archive
  starts in 2022).

## 5. Liverpool Telescope labels: hours lost, clear sky and dust (added 28 Oct 2026, `extra_models.py`)

The Liverpool Telescope (LT, robotic 2 m on the Roque) publishes one report per night since 2007: hours
observing, lost to weather, lost to faults, and a comment with the reason. It is filled in the same way
every year, so unlike the WHT log every year can be used: train 2017–2022, settings on 2023, test 2024–2026.
The LT is more cautious than a staffed telescope (it closes for ice risk, cloud or dust), so its labels say
what the LT did, not what the GTC did.

| Forecast (test 2024–2026) | Reference | Model |
|---|---|---|
| LT hours lost to weather (1,026 nights) | climatology RMSE 3.71 h, persistence MAE 1.92 h | **RMSE 2.52 h**, MAE 1.51 h (skill 0.32); forecast only 2.74 h |
| Photometric sky (689 observed nights) | persistence Brier 0.224 (skill 0.12) | **Brier 0.211** (skill 0.17), AUC 0.74 |
| Dust noted in the report (18 of 1,026 nights) | climatology Brier 0.017 | logistic regression on the CAMS dust forecast: Brier 0.018 (no skill), AUC 0.78 |

- **Dust is used as a warning, not a probability.** The CAMS forecast archive starts in August 2022: 514
  training nights with only 11 dust events, so the threshold is chosen on those training nights. A forecast
  dust maximum ≥ 20 µg/m³ catches 12 of the 18 test events (Peirce 0.50) against 3 of 18 with the 50 µg/m³
  used before (the EU daily PM10 limit). Either way most warnings are false alarms (93 %).
- **Raw forecast cloud** read literally (mean cloud < 20 % → photometric) has no skill (Brier skill −0.01):
  the grid-point cloud is the sea of clouds below the summit, the same bias as for humidity.
- **Sources looked at and not usable:** the ING dust and sky-brightness links are images (PNG plots), not
  data; the TNG and GTC dust values are only published for the last 24 h / current value (collected since
  27 Oct 2026); the IAC PWV page did not respond.

## Limitations and next steps

- **Proxy labels.** The closure label is a rule rebuilt from humidity. Wind, dust and ice closures are not in
  it, and none of the labels are the GTC's own operating decisions.
- **One forecast model at one grid point.** The grid point is 4 km away, on smoothed terrain, and is usually
  wetter and calmer than the summit. The model learns to correct that.
- **Closure recalibration, tested and rejected (28 Oct 2026).** Isotonic regression was checked without
  touching the test years: out-of-fold probabilities for each year 2017–2023 (model trained on the other six),
  then a nested leave-one-year-out fit of the isotonic curve. Brier 0.0517 raw against 0.0521 recalibrated
  (forecast-only model: 0.0922 against 0.0933), so it is not applied. The check runs on every training
  (`train.calibration_check`, saved in `results/settings.json`). On the test years the model is somewhat
  over-confident between 40 % and 90 %; with ~250 nights in those bins this may be noise or a change in the
  climate of the last years, and the live track record is where to watch it.
- **Possible improvements:** an hourly version for the decision during the night; a longer archive of
  pressure-level forecasts for the jet stream (training now has it only from 2021).
