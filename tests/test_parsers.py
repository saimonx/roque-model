"""Tests for the parsers, using small real files saved in tests/fixtures/.

Why test parsers? If a website changes its format, these tests (run against
freshly downloaded files) tell us immediately, instead of silently producing
wrong data. Run them with:  .venv/bin/python -m pytest
"""

from pathlib import Path

from roque_forecast.sources import gtc_atmosportal, ing_nights, not_mast, r2d2, tng

FIXTURES = Path(__file__).parent / "fixtures"


def test_not_parse_reads_minutes_with_tidy_columns():
    df = not_mast.parse(FIXTURES / "not_sample.tsv.gz")
    assert list(df.columns) == [
        "time_utc", "humidity_pct", "pressure_hpa", "temp_c", "wind_dir_deg", "wind_speed_ms",
    ]
    assert len(df) == 5
    assert str(df["time_utc"].dt.tz) == "UTC"
    assert df.loc[0, "humidity_pct"] == 12.3


def test_not_finds_temporary_download_link():
    html = 'created.<p>Number of measurements: 43111<p><a href="/temp/NOTMetData1793125455.gz">'
    assert not_mast.find_download_link(html) == "https://www.not.iac.es/temp/NOTMetData1793125455.gz"
    assert not_mast.find_download_link("<html>no data</html>") is None


def test_r2d2_parse_skips_header_and_incomplete_lines():
    df = r2d2.parse(FIXTURES / "r2d2_sample.html")
    assert df.loc[0, "seeing_arcsec"] == 0.9213
    assert df["seeing_arcsec"].between(0.1, 10).all()
    # The fixture is cut in the middle of a line: that line must be ignored.
    assert df["time_utc"].iloc[-1].strftime("%H:%M:%S") == "00:11:13"


def test_ing_night_accounting():
    night = ing_nights.parse(FIXTURES / "ing_night_2026-09-01.html")
    assert night["night"] == "2026-09-01"
    assert night["weather_lost_h"] == 3.0
    # Decimal hours are floats: compare with a tolerance, never with ==.
    assert abs(night["observed_h"] + night["weather_lost_h"] - night["night_h"]) < 1e-9
    assert night["moon_illumination_pct"] == 75


def test_hhmm_to_hours():
    assert ing_nights.hhmm_to_hours("10:30") == 10.5
    assert ing_nights.hhmm_to_hours("") is None


def test_gtc_series():
    raw = (FIXTURES / "gtc_humidity_month_head.json").read_bytes()
    df = gtc_atmosportal.parse_series(raw, "humidity")
    assert list(df.columns) == ["time_utc", "humidity"]
    assert len(df) == 5


def test_gtc_panel_rows_and_status_colours():
    panel = gtc_atmosportal.parse_panel((FIXTURES / "gtc_home.html").read_text(encoding="utf-8"))
    assert panel["station_time_utc"] == "2026-10-27 18:26:20"
    rows = {row["name"]: row for row in panel["rows"]}
    assert rows["Outdoor Humidity"]["value"] == 89.7
    assert rows["Outdoor Humidity"]["unit"] == "%"
    assert rows["Outdoor Humidity"]["status"] == "warning"  # yellow row
    assert rows["Rain"]["value"] == "False"
    assert rows["TNG Dust"]["section"] == "external"
    assert rows["TNG Dust"]["age"] == "0.1 h"


def test_tng_series_and_current():
    df = tng.parse_series((FIXTURES / "tng_dust_24h.json").read_bytes(), "dust")
    assert len(df) > 0 and df["dust"].notna().all()
    current = {row["name"]: row for row in tng.parse_current((FIXTURES / "tng_current.json").read_bytes())}
    assert "dust_d0_5" in current  # dust counts by particle size
    assert isinstance(current["humidity"]["epoch_ms"], int)
