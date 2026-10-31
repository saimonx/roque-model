"""Publish the live weather and tonight's forecast as FIWARE entities.

FIWARE is the open-source IoT platform behind many smart-city and observatory
data platforms. Its core piece, the **Orion Context Broker**, keeps the CURRENT
state of "entities" (a weather station, a forecast...) behind a standard REST
API called **NGSI-v2**. Every change is forwarded to **QuantumLeap**, which
stores it as a time series in **CrateDB**; **Grafana** draws the history.
The whole stack runs locally with Docker (infra/docker-compose.yml).

Entities follow the public FIWARE **Smart Data Models** (dataModel.Weather), so
any tool that understands them can read ours:

| Entity id                                   | Type             | Fed by                           |
|---------------------------------------------|------------------|----------------------------------|
| urn:ngsi-ld:WeatherObserved:ORM-GTC          | WeatherObserved  | GTC live panel (collect live, 15 min) |
| urn:ngsi-ld:WeatherObserved:ORM-NOT          | WeatherObserved  | NOT station (tonight.py)          |
| urn:ngsi-ld:WeatherForecast:ORM-tonight      | WeatherForecast  | our night forecast (tonight.py)   |

Following the data model, relative humidity is a fraction (0.65, not 65 %).
Attributes the data model does not define (dome-closure probability, seeing...)
are added with clear names, as the models allow.

Every entity carries `TimeInstant` = the time of the measurement (or of the
forecast). QuantumLeap uses it as the time index, so a late update or a backfill
lands at the right moment in the history.

Usage:
    .venv/bin/python -m roque_forecast.fiware provision      # history subscription (once)
    .venv/bin/python -m roque_forecast.fiware backfill       # last ~30 days of history
    .venv/bin/python -m roque_forecast.fiware status
"""

import argparse
import gzip
import json
import logging
import math
import os
import sys

import pandas as pd
import requests

from roque_forecast import config
from roque_forecast.sources import gtc_atmosportal, not_mast

log = logging.getLogger("fiware")

# Ports shifted by one from the FIWARE defaults (1026, 8668) so this stack can run
# next to another local FIWARE stack. Override with environment variables if needed.
ORION_URL = os.environ.get("ROQUE_ORION_URL", "http://localhost:1027")
QUANTUMLEAP_URL = os.environ.get("ROQUE_QUANTUMLEAP_URL", "http://localhost:8669")
TIMEOUT_S = 5

GTC_ID = "urn:ngsi-ld:WeatherObserved:ORM-GTC"
NOT_ID = "urn:ngsi-ld:WeatherObserved:ORM-NOT"
FORECAST_ID = "urn:ngsi-ld:WeatherForecast:ORM-tonight"
SUBSCRIPTION_DESCRIPTION = "Roque weather and night forecast to QuantumLeap, history for Grafana"

# Approximate positions of the two weather stations (WGS84, [longitude, latitude]).
LOCATIONS = {GTC_ID: [-17.8919, 28.7566], NOT_ID: [-17.8851, 28.7573]}
SOURCES = {
    GTC_ID: ("GTC weather station, atmosportal", "https://atmosportal.gtc.iac.es/"),
    NOT_ID: ("NOT weather station", "https://www.not.iac.es/weather/"),
}

# GTC live panel row name -> (attribute, conversion)
PANEL_ATTRIBUTES = {
    "Outdoor Temp": ("temperature", float),
    "Outdoor Humidity": ("relativeHumidity", lambda v: v / 100),
    "Dew Point": ("dewPoint", float),
    "Pressure": ("atmosphericPressure", float),
    "Wind Mean": ("windSpeed", float),
    "Wind Peak": ("gustSpeed", float),
    "Solar Rad": ("solarRadiation", float),
    "Acc Rain (24h)": ("precipitation", float),
    "External PM10": ("pm10", float),
    "Rain": ("rainDetected", lambda v: str(v).strip().lower() == "true"),
}
# GTC month series (graphics/<var>_month.php) -> (attribute, conversion), for the backfill.
SERIES_ATTRIBUTES = {
    "temperature": ("temperature", float),
    "humidity": ("relativeHumidity", lambda v: v / 100),
    "dewpoint": ("dewPoint", float),
    "pressure": ("atmosphericPressure", float),
    "winspeed": ("windSpeed", float),
    "windpeak": ("gustSpeed", float),
    "solarrad": ("solarRadiation", float),
}


# --------------------------------------------------------------------------
# Building NGSI-v2 entities
# --------------------------------------------------------------------------
def attribute(value) -> dict | None:
    """NGSI-v2 attribute {"type", "value"}; missing numbers are left out (None)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, bool):
        return {"type": "Boolean", "value": value}
    if isinstance(value, (int, float)):
        return {"type": "Number", "value": round(float(value), 4)}
    if isinstance(value, pd.Timestamp):
        return {"type": "DateTime", "value": value.isoformat().replace("+00:00", "Z")}
    # Orion rejects these characters in text values (a protection against script injection).
    return {"type": "Text", "value": str(value).translate(str.maketrans("", "", "<>\"'=;()"))}


def entity(entity_id: str, entity_type: str, time: pd.Timestamp, values: dict) -> dict:
    """An entity with TimeInstant (the measurement time) and the non-missing attributes."""
    out = {"id": entity_id, "type": entity_type, "TimeInstant": attribute(time)}
    for name, value in values.items():
        attr = attribute(value)
        if attr is not None:
            out[name] = attr
    return out


def station_entity(entity_id: str, time: pd.Timestamp, values: dict) -> dict:
    name, url = SOURCES[entity_id]
    static = {"dateObserved": time, "name": name, "source": url, "dataOrigin": "real"}
    out = entity(entity_id, "WeatherObserved", time, static | values)
    out["location"] = {"type": "geo:json", "value": {"type": "Point", "coordinates": LOCATIONS[entity_id]}}
    return out


def gtc_panel_entity(panel: dict) -> dict:
    """WeatherObserved from one parsed GTC live panel (gtc_atmosportal.parse_panel)."""
    time = pd.Timestamp(panel["station_time_utc"], tz="UTC")
    values, warnings = {}, []
    for row in panel["rows"]:
        if row["section"] == "gtc" and row["name"] in PANEL_ATTRIBUTES and row["value"] is not None:
            name, convert = PANEL_ATTRIBUTES[row["name"]]
            values[name] = convert(row["value"])
        if row.get("status") not in (None, "ok"):
            warnings.append(row["name"])
    # The panel colours a row when the GTC considers the value a warning: keep the list.
    values["panelWarnings"] = ", ".join(warnings) if warnings else "none"
    return station_entity(GTC_ID, time, values)


def not_minute_entity(row: pd.Series) -> dict:
    return station_entity(NOT_ID, row["time_utc"], {
        "temperature": row["temp_c"], "relativeHumidity": row["humidity_pct"] / 100,
        "atmosphericPressure": row["pressure_hpa"], "windSpeed": row["wind_speed_ms"],
        "windDirection": row["wind_dir_deg"],
    })


def forecast_entity(page: dict) -> dict:
    """WeatherForecast for tonight, from the page data written by tonight.py."""
    f, night, inputs = page["forecast"], page["night"], page["inputs"]
    return entity(FORECAST_ID, "WeatherForecast", pd.Timestamp(page["issued_utc"]), {
        "dateIssued": pd.Timestamp(page["issued_utc"]),
        "validFrom": pd.Timestamp(night["start_utc"]), "validTo": pd.Timestamp(night["end_utc"]),
        "nightDate": night["date"], "forecastMode": page["mode"],
        # Night averages of the weather forecast (ECMWF IFS through Open-Meteo)
        "relativeHumidity": inputs["fc_rh_mean"] / 100 if inputs.get("fc_rh_mean") is not None else None,
        "temperature": inputs.get("fc_temp_mean"), "windSpeed": inputs.get("fc_wind_mean"),
        # Our two forecasts (hourly.py and train.py): expected closed hours = sum of the hourly
        # probabilities; one seeing value for the night.
        "domeClosedHours": f["closed_h"], "openHoursForecast": f["open_h"], "closureRisk": f["risk"],
        "seeingForecast": f["seeing_arcsec"], "nightLengthHours": night["length_h"],
        "hourlyClosureProbability": [{"hourStart": h["t"], "probability": h["p_closed"]} for h in page["hours"]],
        "dataOrigin": "model forecast",
    })


# --------------------------------------------------------------------------
# Talking to Orion and QuantumLeap
# --------------------------------------------------------------------------
def upsert(entities: list[dict]) -> None:
    """Create or update entities in one request (NGSI-v2 batch "append")."""
    r = requests.post(f"{ORION_URL}/v2/op/update", json={"actionType": "append", "entities": entities},
                      timeout=TIMEOUT_S)
    r.raise_for_status()


def safely(action, *args) -> bool:
    """Run an update; if the local stack is not running, log it and carry on.

    FIWARE is an optional layer here: the forecast and the collectors must keep
    working when Docker is stopped.
    """
    try:
        action(*args)
        return True
    except requests.ConnectionError:
        log.info("FIWARE stack not running at %s: skipped", ORION_URL)
    except requests.RequestException:
        log.exception("FIWARE update failed")
    return False


def push_gtc_panel(panel: dict) -> bool:
    return safely(lambda: upsert([gtc_panel_entity(panel)]))


def push_forecast(page: dict) -> bool:
    """Tonight's forecast plus the latest NOT minute (both computed by tonight.py)."""
    now = page["station_now"]
    row = pd.Series({"time_utc": pd.Timestamp(now["time_utc"]), "temp_c": now["temp"], "humidity_pct": now["rh"],
                     "pressure_hpa": now["pressure"], "wind_speed_ms": now["wind"], "wind_dir_deg": None})
    ok = safely(lambda: upsert([forecast_entity(page), not_minute_entity(row)]))
    if ok:
        log.info("FIWARE: forecast and NOT station updated in Orion")
    return ok


def provision() -> None:
    """Subscribe QuantumLeap to every change of our entity types (only once)."""
    existing = requests.get(f"{ORION_URL}/v2/subscriptions", timeout=TIMEOUT_S).json()
    if any(s.get("description") == SUBSCRIPTION_DESCRIPTION for s in existing):
        print("subscription already exists")
        return
    subscription = {
        "description": SUBSCRIPTION_DESCRIPTION,
        "subject": {"entities": [{"idPattern": ".*", "type": "WeatherObserved"},
                                 {"idPattern": ".*", "type": "WeatherForecast"}]},
        # Inside Docker, Orion reaches QuantumLeap by its service name.
        "notification": {"http": {"url": "http://quantumleap:8668/v2/notify"},
                         "metadata": ["dateCreated", "dateModified"]},
    }
    r = requests.post(f"{ORION_URL}/v2/subscriptions", json=subscription, timeout=TIMEOUT_S)
    r.raise_for_status()
    print("subscription created:", r.headers.get("Location"))


def notify_quantumleap(entities: list[dict], batch: int = 300) -> None:
    """Send past values straight to QuantumLeap's notification endpoint.

    Orion only holds the current state, so pushing a month of history through it
    would just overwrite the same entity thousands of times. QuantumLeap accepts
    the same message Orion would send, with many versions of an entity at once.
    """
    for i in range(0, len(entities), batch):
        payload = {"subscriptionId": "backfill", "data": entities[i:i + batch]}
        r = requests.post(f"{QUANTUMLEAP_URL}/v2/notify", json=payload, timeout=60)
        r.raise_for_status()


def gtc_history(days: int) -> list[dict]:
    """GTC station from the newest 30-day download (collect weekly), as 10-minute means."""
    folders = sorted((config.RAW_DIR / "gtc_atmosportal").glob("*/"))
    if not folders:
        return []
    columns = []
    for var, (name, convert) in SERIES_ATTRIBUTES.items():
        path = folders[-1] / f"{var}_month.json.gz"
        if path.exists():
            series = gtc_atmosportal.parse_series(gzip.decompress(path.read_bytes()), var).set_index("time_utc")[var]
            columns.append(series.resample("10min").mean().map(convert).rename(name))
    table = pd.concat(columns, axis=1)
    table = table[table.index > table.index.max() - pd.Timedelta(days=days)]
    return [station_entity(GTC_ID, t, row.to_dict()) for t, row in table.iterrows()]


def not_history(days: int) -> list[dict]:
    """NOT station from the clean minute table (build_tables.py), as 10-minute means."""
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    minutes = pd.read_parquet(config.PROCESSED_DIR / "not_minutes.parquet",
                              columns=["time_utc", "humidity_pct", "pressure_hpa", "temp_c", "wind_speed_ms",
                                       "wind_dir_deg"], filters=[("time_utc", ">=", start)])
    # Add the newest live download (tonight.py keeps the last 36 h), which is more recent than the table.
    live = sorted((config.RAW_DIR / "tonight").glob("*/not.tsv.gz"))
    if live:
        minutes = pd.concat([minutes, not_mast.parse(live[-1])]).drop_duplicates("time_utc")
    minutes = minutes[minutes["time_utc"] >= start]
    blocks = minutes.set_index("time_utc").resample("10min").mean().dropna(how="all").reset_index()
    return [not_minute_entity(row) for _, row in blocks.iterrows()]


def backfill(days: int) -> None:
    for name, entities in [("GTC", gtc_history(days)), ("NOT", not_history(days))]:
        notify_quantumleap(entities)
        print(f"{name}: {len(entities)} past states sent to QuantumLeap")


def status() -> None:
    r = requests.get(f"{ORION_URL}/v2/entities", params={"options": "keyValues", "limit": 20}, timeout=TIMEOUT_S)
    print(json.dumps(r.json(), indent=1, ensure_ascii=False)[:4000])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("provision")
    sub.add_parser("status")
    bf = sub.add_parser("backfill")
    bf.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)
    if args.command == "provision":
        provision()
    elif args.command == "backfill":
        backfill(args.days)
    else:
        status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
