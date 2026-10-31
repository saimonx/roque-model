"""Data for the web page's evidence sections: site/data/evaluation.json.

Two kinds of evidence, kept apart on the page:

1. **How well RoqueModel works** on 2024-2026 (hours never used to train the copy
   that is measured), against the simplest references, in plain words and in the
   usual technical scores (reports/results/hourly_scores.csv).
2. **Live track record**: every forecast issued by tonight.py next to what really
   happened that night. For each night the scored forecast is the FIRST final one
   (issued right after the night starts); later runs use newer weather forecasts
   issued while the night is already under way, so scoring them would flatter the
   model. Without a final one, the last provisional forecast is scored.

The check of the closure label against the Liverpool Telescope (validate.py) stays
in the README and the report, not on the page.

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


def pick(table: pd.DataFrame, **match) -> pd.Series:
    for key, value in match.items():
        table = table[table[key] == value]
    return table.iloc[0]


def plain_summary() -> list[dict]:
    """The evaluation in plain words: our forecast and the simplest references, in units
    anyone can read. Yes/no: "right" = of the "closed" calls, the share that was right;
    "caught" = of the closed hours, the share that was called. Numbers: mean error."""
    s = scores()
    hour = {m: pick(s, forecast="hour closed", method=m) for m in
            ["raw forecast", "precasting", "model, provisional", "model, final"]}
    night = {m: pick(s, forecast="night closed hours", method=m) for m in
             ["climatology", "persistence", "raw forecast", "model, provisional", "model, final"]}
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
    ]


def comparison() -> dict:
    """Test hours 2024-2026: what really happened, what the weather forecast alone would
    have done, and what our model says (a "closed" call = probability >= 50 %)."""
    hours = pd.read_parquet(config.PROCESSED_DIR / "hour_predictions.parquet")
    real = hours["closed"] == 1

    def calls(said: pd.Series) -> dict:
        return {"closed_h": int(said.sum()),
                "wrong": round(float((said != real).mean()), 3),          # share of hours it gets wrong
                "false_alarm_h": int((said & ~real).sum()),               # closes when it was open
                "missed_h": int((~said & real).sum())}                    # stays open when it was closed

    return {"hours": len(hours), "real_closed_h": int(real.sum()),
            "raw": calls(hours["raw"] >= 0.5),
            "final": calls(hours["p_final"] >= 0.5),
            "provisional": calls(hours["p_provisional"] >= 0.5),
            # Saying "open" every hour is wrong exactly in the closed hours: the floor to beat.
            "always_open_wrong": round(float(real.mean()), 3)}


def technical() -> dict:
    s = scores()
    return {"hour": s[s["forecast"] == "hour closed"].to_dict(orient="records"),
            "night": s[s["forecast"] == "night closed hours"].to_dict(orient="records")}


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
    return joined[["night", "mode", "closed_h", "dome_closed_h"]].to_dict(
        orient="records")


def build() -> dict:
    return clean({
        "generated_utc": pd.Timestamp.now(tz="UTC").floor("min").isoformat().replace("+00:00", "Z"),
        "comparison": comparison(),
        # Settings search and other models tried (compare.py), for RoqueModel's cards 1 and 5.
        "search": json.loads((RESULTS / "model_search.json").read_text()) if (RESULTS / "model_search.json").exists() else None,
        "plain": plain_summary(),
        "technical": technical(),
        "reliability": reliability(),
        "recent": recent_nights(),
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
