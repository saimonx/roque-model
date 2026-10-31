"""Tests for the live part: which night is "tonight", last night's outcome,
FIWARE entities, Grafana dashboards and the live track record."""

import json

import numpy as np
import pandas as pd

from roque_forecast import dashboards, fiware, site_data, tonight


def test_tonight_is_the_running_night_or_the_next_one():
    afternoon = pd.Timestamp("2026-10-28 15:00", tz="UTC")
    after_midnight = pd.Timestamp("2026-10-29 02:00", tz="UTC")
    next_morning = pd.Timestamp("2026-10-29 09:00", tz="UTC")
    assert tonight.tonight_window(afternoon)["night"] == pd.Timestamp("2026-10-28")
    assert tonight.tonight_window(after_midnight)["night"] == pd.Timestamp("2026-10-28")  # same night
    assert tonight.tonight_window(next_morning)["night"] == pd.Timestamp("2026-10-29")
    window = tonight.tonight_window(afternoon)
    assert 9 < window["length_h"] < 11  # late October: ~10 h of astronomical night
    assert window["start"] > afternoon


def test_last_night_counts_closure_with_the_full_label():
    window = tonight.tonight_window(pd.Timestamp("2026-10-27 12:00", tz="UTC"))
    minutes = pd.DataFrame({"time_utc": pd.date_range(window["start"], window["end"], freq="min")})
    # Humid (>= 90 %) during the first quarter of the night, dry afterwards.
    quarter = window["start"] + (window["end"] - window["start"]) / 4
    minutes["humidity_pct"] = np.where(minutes["time_utc"] < quarter, 95.0, 50.0)
    minutes["wind_speed_ms"], minutes["temp_c"] = 5.0, 5.0  # calm and above freezing: humidity only
    seeing = pd.DataFrame({"time_utc": pd.date_range(window["start"], periods=60, freq="2min"),
                           "seeing_arcsec": 0.8})
    out = tonight.last_night(minutes, seeing, pd.Timestamp("2026-10-27"))
    # A quarter of the night plus the 20 minutes the rule waits before reopening.
    expected = 0.25 + 20 / (window["length_h"] * 60)
    assert abs(out["dome_closed_frac"] - expected) < 0.01
    assert out["seeing_median"] == 0.8


def test_clean_turns_nan_into_null_for_json():
    assert json.dumps(tonight.clean({"a": np.float64("nan"), "b": [np.float32(1.5)]})) == '{"a": null, "b": [1.5]}'


def test_gtc_panel_entity_follows_the_smart_data_model():
    panel = {"station_time_utc": "2026-10-28 10:21:05", "rows": [
        {"section": "gtc", "name": "Outdoor Humidity", "value": 64.6, "status": "ok"},
        {"section": "gtc", "name": "Rain", "value": "False", "status": "ok"},
        {"section": "gtc", "name": "Acc Rain (24h)", "value": 0.0, "status": "warning"},
    ]}
    entity = fiware.gtc_panel_entity(panel)
    assert entity["type"] == "WeatherObserved"
    assert entity["relativeHumidity"] == {"type": "Number", "value": 0.646}  # a fraction, not %
    assert entity["rainDetected"] == {"type": "Boolean", "value": False}
    assert entity["TimeInstant"]["value"] == "2026-10-28T10:21:05Z"
    # Orion forbids parentheses in text: they are removed.
    assert entity["panelWarnings"]["value"] == "Acc Rain 24h"


def test_missing_values_are_left_out_of_entities():
    entity = fiware.entity("x", "WeatherObserved", pd.Timestamp("2026-10-28", tz="UTC"),
                           {"temperature": float("nan"), "windSpeed": 3.0})
    assert "temperature" not in entity and entity["windSpeed"]["value"] == 3.0


def test_dashboards_are_the_same_in_both_languages():
    es, en = dashboards.dashboard("es"), dashboards.dashboard("en")
    assert [p["type"] for p in es["panels"]] == [p["type"] for p in en["panels"]]
    assert [p.get("targets") for p in es["panels"]][:7] == [p.get("targets") for p in en["panels"]][:7]
    assert es["title"] != en["title"]


def test_track_record_scores_the_first_final_forecast_of_each_night(tmp_path, monkeypatch):
    monkeypatch.setattr(site_data, "FORECASTS_DIR", tmp_path)
    v = tonight.MODEL_VERSION
    issued = [
        {"issued_utc": "2026-10-28T15:00Z", "night": "2026-10-28", "mode": "provisional", "model": v,
         "closed_h": 2, "seeing_arcsec": 0.7},
        {"issued_utc": "2026-10-28T20:05Z", "night": "2026-10-28", "mode": "final", "model": v,
         "closed_h": 8, "seeing_arcsec": 0.8},
        {"issued_utc": "2026-10-28T23:05Z", "night": "2026-10-28", "mode": "final", "model": v,
         "closed_h": 9, "seeing_arcsec": 0.8},
        {"issued_utc": "2026-10-28T20:00Z", "night": "2026-10-28", "mode": "final", "model": "old",
         "closed_h": 1, "seeing_arcsec": 0.8},  # an earlier model version is never scored
    ]
    (tmp_path / "issued.jsonl").write_text("".join(json.dumps(r) + "\n" for r in issued))
    (tmp_path / "outcomes.jsonl").write_text(json.dumps(
        {"night": "2026-10-28", "dome_closed_frac": 0.8, "dome_closed_h": 8.1, "seeing_median": None}) + "\n")
    record = site_data.track_record()
    # The first final forecast (20:05), not a later one issued in the middle of the night.
    assert len(record) == 1 and record[0]["mode"] == "final" and record[0]["closed_h"] == 8


def test_forecast_vs_measured_pairs_each_hour():
    now = pd.Timestamp("2026-10-31 12:00", tz="UTC")
    times = pd.date_range(now - pd.Timedelta(hours=3), now, freq="min", inclusive="left")
    minutes = pd.DataFrame({"time_utc": times, "humidity_pct": 50.0})
    forecast = pd.DataFrame({"time_utc": pd.date_range(now - pd.Timedelta(hours=3), periods=3, freq="h"),
                             "relative_humidity_2m": [95.0, 96.0, 97.0]})
    rows = tonight.forecast_vs_measured(forecast, minutes, now)
    assert [r["forecast"] for r in rows] == [95.0, 96.0, 97.0]
    assert all(r["measured"] == 50.0 for r in rows)

