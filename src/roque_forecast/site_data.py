"""Data for the web page's "how well does it work" section: site/data/evaluation.json.

Two kinds of evidence, kept apart on the page:

1. **Evaluation on archived forecasts** (2024-2026, never used for training or
   for any choice): the metric tables of reports/results/, the reliability of
   the closure probabilities, the most important inputs, and the last 60 test
   nights, forecast against what happened.
2. **Live track record**: every forecast issued by tonight.py
   (data/forecasts/issued.jsonl) next to what really happened that night
   (data/forecasts/outcomes.jsonl). It starts empty and grows night by night.
   For each night the scored forecast is the FIRST final one (issued right after
   the night starts, with the 2 hours before it at the station). Later runs use
   newer weather forecasts, issued while the night is already under way, so
   scoring them would flatter the model. Without a final one, the last
   provisional forecast is scored.

Usage:
    .venv/bin/python -m roque_forecast.site_data
"""

import json

import numpy as np
import pandas as pd

from roque_forecast import config, train
from roque_forecast.tonight import FORECASTS_DIR, SITE_DATA_DIR, clean

RESULTS = config.PROJECT_DIR / "reports" / "results"
RECENT_NIGHTS = 60


def metric_rows(name: str, columns: list[str]) -> list[dict]:
    table = pd.read_csv(RESULTS / f"{name}_metrics.csv")
    return table[["inputs", "method", "kind", *columns]].to_dict(orient="records")


def recent_nights() -> list[dict]:
    predictions = pd.read_parquet(config.PROCESSED_DIR / "predictions.parquet")
    test = predictions[predictions["split"] == "test"].dropna(subset=["closed"]).tail(RECENT_NIGHTS)
    return [{"night": str(night.date()), "p_closed": r.p_closed, "closed": r.closed, "closed_h": r.dome_closed_h,
             "pred_seeing": r.pred_seeing, "seeing": r.seeing_median}
            for night, r in zip(test.index, test.itertuples())]


def reliability() -> list[dict]:
    predictions = pd.read_parquet(config.PROCESSED_DIR / "predictions.parquet")
    test = predictions[predictions["split"] == "test"].dropna(subset=["closed"])
    groups = pd.cut(test["p_closed"], np.linspace(0, 1, 11), include_lowest=True)
    table = test.groupby(groups, observed=True).agg(predicted=("p_closed", "mean"), observed=("closed", "mean"),
                                                    nights=("closed", "size"))
    return table.reset_index(drop=True).to_dict(orient="records")


def importance(name: str, top: int = 8) -> list[dict]:
    """Most important inputs, with each one's share of the total (negative drops count as 0)."""
    table = pd.read_csv(RESULTS / f"{name}_importance.csv")
    table["share"] = table["importance"].clip(lower=0) / table["importance"].clip(lower=0).sum()
    return table.head(top).to_dict(orient="records")


def hourly_eval() -> list[dict]:
    """Hour by hour, 2024-2026: how often a yes/no call catches the event and how often it is wrong.

    Dome closure: the raw forecast read literally (humidity >= 90 % -> closed) against our
    model saying "closed" when its probability is 50 % or more. Wind: the raw forecast
    against the model's warning (threshold chosen on 2023, see hourly.py).
    """
    events = pd.read_csv(RESULTS / "hourly_events_metrics.csv")
    warnings = pd.read_csv(RESULTS / "hourly_warnings.csv")
    rows = []
    for method, name in [("raw forecast, yes/no", "raw"), ("gradient boosting", "final"),
                         ("gradient boosting, forecast only", "provisional")]:
        r = events[(events["target"] == "closed") & (events["method"] == method)].iloc[0]
        rows.append({"target": "closed", "method": name, "hit_rate": r["hit_rate"],
                     "false_alarm_ratio": r["false_alarm_ratio"]})
    for _, r in warnings[warnings["target"] == "windy"].iterrows():
        name = "raw" if r["warning"].startswith("raw") else ("final" if "final" in r["warning"] else "provisional")
        rows.append({"target": "windy", "method": name, "hit_rate": r["hit_rate"],
                     "false_alarm_ratio": r["false_alarm_ratio"]})
    return rows


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
    if issued.empty or outcomes.empty:
        return []
    issued = issued.sort_values("issued_utc")
    first_final = issued[issued["mode"] == "final"].groupby("night").head(1)
    last_provisional = issued[issued["mode"] == "provisional"].groupby("night").tail(1)
    last_provisional = last_provisional[~last_provisional["night"].isin(first_final["night"])]
    best = pd.concat([first_final, last_provisional])
    joined = best.merge(outcomes, on="night", how="inner").sort_values("night", ascending=False)
    return joined[["night", "mode", "issued_utc", "p_closed", "closed_h", "seeing_arcsec", "lost_h",
                   "dome_closed_h", "seeing_median"]].to_dict(orient="records")


def build() -> dict:
    return clean({
        "generated_utc": pd.Timestamp.now(tz="UTC").floor("min").isoformat().replace("+00:00", "Z"),
        "test_from": str(train.TEST_START.date()),
        "closure": metric_rows("closure", ["nights", "brier", "brier_skill_vs_climatology", "auc", "hit_rate",
                                           "false_alarm_ratio"]),
        "seeing": metric_rows("seeing", ["nights", "rmse", "mae", "rmse_skill_vs_climatology"]),
        "lost_hours": metric_rows("lost_hours", ["nights", "rmse", "mae"]),
        "reliability": reliability(),
        "calibration_check": json.loads((RESULTS / "settings.json").read_text())["closure_calibration_check"],
        "importance": {"closure": importance("closure"), "seeing": importance("seeing")},
        "recent": recent_nights(),
        "track_record": track_record(),
        "hourly_eval": hourly_eval(),
        "seeing_quantiles": seeing_quantiles(),
        "lt_lost_hours": pd.read_csv(RESULTS / "lt_lost_hours_metrics.csv").to_dict(orient="records"),
        "sky_dust": pd.read_csv(RESULTS / "sky_dust_metrics.csv").to_dict(orient="records"),
    })


def main() -> int:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = SITE_DATA_DIR / "evaluation.json"
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", path.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
