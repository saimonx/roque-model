"""Tests for the live part: which night is "tonight", last night's outcome,
FIWARE entities and the page's accuracy figures (dashboards: test_contract.py)."""

import json

import numpy as np
import pandas as pd

from roque_forecast import fiware, site_data, tonight


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


def test_forecast_vs_measured_pairs_each_hour():
    now = pd.Timestamp("2026-10-31 12:00", tz="UTC")
    times = pd.date_range(now - pd.Timedelta(hours=3), now, freq="min", inclusive="left")
    minutes = pd.DataFrame({"time_utc": times, "humidity_pct": 50.0})
    forecast = pd.DataFrame({"time_utc": pd.date_range(now - pd.Timedelta(hours=3), periods=3, freq="h"),
                             "relative_humidity_2m": [95.0, 96.0, 97.0]})
    rows = tonight.forecast_vs_measured(forecast, minutes, now)
    assert [r["forecast"] for r in rows] == [95.0, 96.0, 97.0]
    assert all(r["measured"] == 50.0 for r in rows)



def test_a_source_that_fails_falls_back_to_its_last_good_copy(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(tonight, "LAST_DIR", tmp_path / "last")
    monkeypatch.setattr(tonight, "LAST_TIMES", tmp_path / "last" / "fetched.json")
    first, second = pd.Timestamp("2026-11-02 08:05", tz="UTC"), pd.Timestamp("2026-11-02 09:05", tz="UTC")
    stale = {}

    # A good download is kept as the last copy, with its time.
    tonight.fetch_or_last("not", tmp_path / "a" / "not.tsv.gz", first, stale,
                          lambda dest: (dest.parent.mkdir(parents=True, exist_ok=True), dest.write_text("good")))
    assert stale == {}

    # The next run fails: the last copy is used and the page is told when it is from.
    def down(dest):
        raise requests.ConnectionError("NOT is down")
    dest = tmp_path / "b" / "not.tsv.gz"
    dest.parent.mkdir()
    tonight.fetch_or_last("not", dest, second, stale, down)
    assert dest.read_text() == "good"
    assert stale == {"not": "2026-11-02T08:05:00Z"}


def test_a_source_that_fails_with_no_copy_still_raises(tmp_path, monkeypatch):
    import pytest
    import requests
    monkeypatch.setattr(tonight, "LAST_DIR", tmp_path / "last")
    monkeypatch.setattr(tonight, "LAST_TIMES", tmp_path / "last" / "fetched.json")

    def down(dest):
        raise requests.ConnectionError("down")
    with pytest.raises(requests.ConnectionError):
        tonight.fetch_or_last("r2d2", tmp_path / "r2d2.html", pd.Timestamp("2026-11-02", tz="UTC"), {}, down)


def test_comparison_counts_wrong_hours_false_alarms_and_misses(tmp_path, monkeypatch):
    monkeypatch.setattr(site_data.config, "PROCESSED_DIR", tmp_path)
    # Four test hours: two really closed. The model gets one closed hour and one open hour wrong.
    pd.DataFrame({"closed": [1, 1, 0, 0], "p_final": [0.9, 0.2, 0.6, 0.1],
                  "p_provisional": [0.9, 0.9, 0.1, 0.1], "raw": [1.0, 1.0, 1.0, 1.0]}).to_parquet(
        tmp_path / "hour_predictions.parquet")
    c = site_data.comparison()
    assert c["hours"] == 4 and c["real_closed_h"] == 2
    assert c["final"] == {"closed_h": 2, "wrong": 0.5, "false_alarm_h": 1, "missed_h": 1}
    assert c["provisional"]["wrong"] == 0.0
    assert c["raw"] == {"closed_h": 4, "wrong": 0.5, "false_alarm_h": 2, "missed_h": 0}
    assert c["always_open_wrong"] == 0.5
