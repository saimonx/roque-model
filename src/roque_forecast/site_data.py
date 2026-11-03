"""Data for the web page's accuracy figures: site/data/evaluation.json.

- comparison: how well RoqueModel works on 2024-2026 (hours never used to train the copy
  that is measured), against what really happened and against the weather forecast read
  literally (reports/results/hourly_scores.csv has the usual technical scores);
- search: the settings search and the other models tried (compare.py).

The check of the closure label against the Liverpool Telescope (validate.py) is in
docs/DETALLES_TECNICOS.md, not on the page.

Usage:
    .venv/bin/python -m roque_forecast.site_data
"""

import json

import pandas as pd

from roque_forecast import config
from roque_forecast.tonight import SITE_DATA_DIR, clean

RESULTS = config.PROJECT_DIR / "reports" / "results"


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


def build() -> dict:
    return clean({
        "generated_utc": pd.Timestamp.now(tz="UTC").floor("min").isoformat().replace("+00:00", "Z"),
        "comparison": comparison(),
        # Settings search and other models tried (compare.py), for the page's sections 2 and 6.
        "search": json.loads((RESULTS / "model_search.json").read_text()) if (RESULTS / "model_search.json").exists() else None,
    })


def main() -> int:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = SITE_DATA_DIR / "evaluation.json"
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", path.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
