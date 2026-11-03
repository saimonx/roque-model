"""The pieces that read the forecast must agree with what it writes.

tonight.py writes site/data/tonight.json, which the web page (site/assets/app.js) reads, and
publishes the same forecast to FIWARE, which the public Grafana Cloud dashboard
(infra/grafana/cloud/roquemodel.json) reads. These tests catch a
field renamed or removed on one side only, and dashboards edited by hand instead of being
regenerated from their Python definition.
"""

import json
import re
from pathlib import Path

import pandas as pd

from roque_forecast import cloud_dashboard, config, dashboards, fiware, tonight

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = json.loads((FIXTURES / "tonight_sample.json").read_text(encoding="utf-8"))


def forecast_key_values() -> dict:
    """Tonight's forecast entity as Orion returns it with options=keyValues (what Grafana reads)."""
    entity = fiware.forecast_entity(SAMPLE)
    return {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in entity.items()}


def test_grafana_cloud_reads_only_fields_the_forecast_entity_has():
    # Grafana reads tonight's forecast entity from Orion; the station history (QuantumLeap) is
    # selected with a JSONata expression and checked by hand.
    entity = forecast_key_values()
    for panel in cloud_dashboard.dashboard()["panels"]:
        for target in panel.get("targets", []):
            if target["url"] != cloud_dashboard.FORECAST_URL:
                continue
            root = target["root_selector"]
            rows = entity[root] if root else [entity]
            assert rows, f"panel {panel['id']}: nothing under {root!r}"
            for column in target["columns"]:
                assert column["selector"] in rows[0], f"panel {panel['id']}: no field {column['selector']!r}"


def test_web_page_and_forecast_agree_on_the_top_level_fields():
    app = (config.PROJECT_DIR / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    # What the page reads from tonight.json (it gets the file as `d`). "stale" is left out:
    # it only appears when a live source did not answer.
    page_reads = {"issued_utc", "mode", "night", "hours", "model", "explain", "station_now",
                  "hourly", "forecast_vs_measured", "station_24h"}
    for field in page_reads:
        assert re.search(rf"\bd\.{field}\b", app), f"the page no longer reads {field!r}: update this list"
    assert page_reads <= set(SAMPLE), page_reads - set(SAMPLE)


def test_hourly_curve_has_the_fields_the_charts_read():
    window = {"start": pd.Timestamp("2026-11-03 19:45", tz="UTC"), "end": pd.Timestamp("2026-11-04 06:10", tz="UTC")}
    times = pd.date_range("2026-11-03 18:00", "2026-11-04 07:00", freq="h", tz="UTC")
    forecast = pd.DataFrame({"time_utc": times, "relative_humidity_2m": 80.0, "wind_speed_10m": 5.0,
                             "temperature_2m": 4.0, "dew_point_2m": 1.0, "cloud_cover": 50.0,
                             "precipitation": 0.0, "surface_pressure": 775.0})
    curve = tonight.hourly_curve(forecast, None, window)
    assert curve[0]["t"] == "2026-11-03T20:00:00Z"  # only night hours
    assert set(curve[0]) == set(SAMPLE["hourly"][0])


def test_saved_dashboards_are_the_generated_ones():
    assert json.loads(dashboards.DASHBOARD_FILE.read_text(encoding="utf-8")) == dashboards.dashboard()
    assert json.loads(cloud_dashboard.OUT_FILE.read_text(encoding="utf-8")) == cloud_dashboard.dashboard()
