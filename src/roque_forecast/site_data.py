"""Data for the web page's evidence sections: site/data/evaluation.json.

Three kinds of evidence, kept apart on the page:

1. **How well the two forecasts work** on 2024-2026 (nights never used for training
   or for any choice), against the simplest references, in plain words and in the
   usual technical scores (reports/results/hourly_scores.csv, seeing_metrics.csv).
2. **Whether the closure label reflects reality**: the checks against the GTC
   archive, the Liverpool Telescope and the WHT (validate.py, validation.json).
3. **Live track record**: every forecast issued by tonight.py next to what really
   happened that night. For each night the scored forecast is the FIRST final one
   (issued right after the night starts); later runs use newer weather forecasts
   issued while the night is already under way, so scoring them would flatter the
   model. Without a final one, the last provisional forecast is scored.

Usage:
    .venv/bin/python -m roque_forecast.site_data
"""

import json

import numpy as np
import pandas as pd

from roque_forecast import config
from roque_forecast.tonight import FORECASTS_DIR, MODEL_VERSION, SITE_DATA_DIR, clean

RESULTS = config.PROJECT_DIR / "reports" / "results"
RECENT_NIGHTS = 60


def scores() -> pd.DataFrame:
    return pd.read_csv(RESULTS / "hourly_scores.csv")


def seeing_scores() -> pd.DataFrame:
    seeing = pd.read_csv(RESULTS / "seeing_metrics.csv")
    return seeing[seeing["inputs"] == "forecast archive"]


def pick(table: pd.DataFrame, **match) -> pd.Series:
    for key, value in match.items():
        table = table[table[key] == value]
    return table.iloc[0]


def plain_summary() -> list[dict]:
    """The evaluation in plain words: our forecast and the simplest references, in units
    anyone can read. Yes/no: "right" = of the "closed" calls, the share that was right;
    "caught" = of the closed hours, the share that was called. Numbers: mean error."""
    s, seeing = scores(), seeing_scores()
    hour = {m: pick(s, forecast="hour closed", method=m) for m in
            ["raw forecast", "precasting", "model, provisional", "model, final"]}
    night = {m: pick(s, forecast="night closed hours", method=m) for m in
             ["climatology", "persistence", "raw forecast", "model, provisional", "model, final"]}
    see = {m: pick(seeing, method=m)["mae"] for m in
           ["climatology (month)", "persistence (last night)", "gradient boosting, forecast only", "gradient boosting"]}
    return [
        {"key": "hour", "kind": "yesno",
         "ours": {m: {"right": hour[f"model, {m}"]["right"], "caught": hour[f"model, {m}"]["caught"]}
                  for m in ("final", "provisional")},
         "refs": [{"name": "raw", "right": hour["raw forecast"]["right"], "caught": hour["raw forecast"]["caught"]},
                  {"name": "precasting", "right": hour["precasting"]["right"], "caught": hour["precasting"]["caught"]}]},
        {"key": "night", "kind": "number", "unit": " h", "digits": 1,
         "ours": {m: night[f"model, {m}"]["mae"] for m in ("final", "provisional")},
         "refs": [{"name": n, "value": night[k]["mae"]} for n, k in
                  [("climatology", "climatology"), ("persistence", "persistence"), ("raw", "raw forecast")]]},
        {"key": "seeing", "kind": "number", "unit": "″", "digits": 2,
         "ours": {"final": see["gradient boosting"], "provisional": see["gradient boosting, forecast only"]},
         "refs": [{"name": "climatology", "value": see["climatology (month)"]},
                  {"name": "persistence", "value": see["persistence (last night)"]}]},
    ]


def technical() -> dict:
    s = scores()
    return {"hour": s[s["forecast"] == "hour closed"].to_dict(orient="records"),
            "night": s[s["forecast"] == "night closed hours"].to_dict(orient="records"),
            "seeing": seeing_scores().to_dict(orient="records")}


def reliability() -> list[dict]:
    """Test hours grouped by the probability given (10 % bins): how often was the dome closed?"""
    hours = pd.read_parquet(config.PROCESSED_DIR / "hour_predictions.parquet")
    groups = pd.cut(hours["p_final"], np.linspace(0, 1, 11), include_lowest=True)
    table = hours.groupby(groups, observed=True).agg(predicted=("p_final", "mean"), observed=("closed", "mean"),
                                                     hours=("closed", "size"))
    return table.reset_index(drop=True).to_dict(orient="records")


def recent_nights() -> list[dict]:
    nights = pd.read_parquet(config.PROCESSED_DIR / "night_predictions.parquet").tail(RECENT_NIGHTS)
    return [{"night": str(n.date()), "closed_h": r.closed, "forecast_h": r.p_final, "raw_h": r.raw}
            for n, r in zip(nights.index, nights.itertuples())]


def seeing_quantiles() -> list[float]:
    """Percentiles 1-99 of the nightly median seeing (R2D2, all nights): the scale on the page."""
    nights = pd.read_parquet(config.PROCESSED_DIR / "nights.parquet", columns=["seeing_median"])
    return [round(float(v), 3) for v in nights["seeing_median"].dropna().quantile(np.arange(1, 100) / 100)]


def read_jsonl(path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.DataFrame([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line])


def track_record() -> list[dict]:
    issued = read_jsonl(FORECASTS_DIR / "issued.jsonl")
    outcomes = read_jsonl(FORECASTS_DIR / "outcomes.jsonl")
    if issued.empty or outcomes.empty or "model" not in issued:
        return []
    issued = issued[issued["model"] == MODEL_VERSION].sort_values("issued_utc")
    first_final = issued[issued["mode"] == "final"].groupby("night").head(1)
    last_provisional = issued[issued["mode"] == "provisional"].groupby("night").tail(1)
    last_provisional = last_provisional[~last_provisional["night"].isin(first_final["night"])]
    best = pd.concat([first_final, last_provisional])
    joined = best.merge(outcomes, on="night", how="inner").sort_values("night", ascending=False)
    return joined[["night", "mode", "closed_h", "seeing_arcsec", "dome_closed_h", "seeing_median"]].to_dict(
        orient="records")


def build() -> dict:
    return clean({
        "generated_utc": pd.Timestamp.now(tz="UTC").floor("min").isoformat().replace("+00:00", "Z"),
        "plain": plain_summary(),
        "technical": technical(),
        "validation": json.loads((RESULTS / "validation.json").read_text()),
        "reliability": reliability(),
        "recent": recent_nights(),
        "seeing_quantiles": seeing_quantiles(),
        "track_record": track_record(),
    })


def main() -> int:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = SITE_DATA_DIR / "evaluation.json"
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", path.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
