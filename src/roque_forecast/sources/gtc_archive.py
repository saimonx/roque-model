"""GTC Public Archive (CAB, CSIC-INTA): when did the GTC really take science data?

https://gtc.sdc.cab.inta-csic.es/gtc/index.jsp is the public archive of the 10.4 m
GTC. Every public exposure comes with its start and end time. The GTC never takes
science exposures with the dome closed, so the archive says, minute by minute, when
the GTC was certainly OPEN and observing.

It is used only to CHECK the project's closure label (validate.py), not to train:
- data become public one year after they are taken;
- the archive covers only part of the open time (technical nights, programmes not
  in the archive, and the very heavy EMIR files are left out here), so "no data"
  does not mean "closed".

Access: the public search form (dates and instruments) followed by its CSV export,
limited to 5,000 rows per search. The light instruments (OSIRIS, MEGARA, HiPERCAM,
HORuS, CIRCE, CanariCam) fit in one search per month; a month that does not fit is
split in halves. The server is slow (about 1-2 minutes per search), so downloads are
sequential with a pause between requests.
"""

import io
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = "https://gtc.sdc.cab.inta-csic.es/gtc"
# The archive refuses requests without browser-like headers (HTTP 500).
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 roque-night-forecast research",
           "Accept": "text/html,application/xhtml+xml,text/csv", "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}
ALL = ["OSI_LSS", "OSI_MOS", "CC_SPE", "EMIR_SPE", "MEG_SPE", "MEG_IFU", "HORuS_SPE", "OSI_BBI", "OSI_TF", "CC_IMG",
       "CIR_IMG", "EMIR_BBI", "EMIR_MBI", "EMIR_NBI", "HIP_IMG", "CC_POL", "CC_SPOL", "CIR_POL"]
LIGHT = [c for c in ALL if not c.startswith("EMIR")]  # EMIR writes thousands of frames a night


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(f"{BASE}/index.jsp", timeout=60)
    s.get(f"{BASE}/jsp/searchform.jsp", timeout=180)
    return s


def search(s: requests.Session, first: date, last: date, codes: list[str]) -> str | None:
    """CSV of the products observed from `first` to `last` (inclusive), or None if over 5,000 rows."""
    fields = [("origen", "searchform.jsp"), ("id", "null"), ("radius", "5"),
              ("dateinit_d", str(first.day)), ("dateinit_m", str(first.month)), ("dateinit_y", str(first.year)),
              ("dateend_d", str(last.day)), ("dateend_m", str(last.month)), ("dateend_y", str(last.year)),
              *[("instCode", c) for c in codes], ("prog_id", ""), ("prog_pi", ""), ("obl_id", ""),
              ("lp", "-"), ("order_by", "Observing Date"), ("rpp", "10"), ("pts", "1"), ("submit", "Send")]
    multipart = [(k, (None, v)) for k, v in fields] + [("file", ("", b"", "application/octet-stream"))]
    s.post(f"{BASE}/jsp/searchres.jsp", files=multipart, timeout=900)
    csv = s.get(f"{BASE}/resultCSV", timeout=900)
    return csv.text if csv.status_code == 200 else None


def download_month(s: requests.Session, first: date, last: date, folder: Path, pause_s: float = 3.0) -> None:
    """Save light-instrument products of a date range, halving the range if it is too big."""
    path = folder / f"light_{first}_{last}.csv"
    if path.exists():
        return
    text = search(s, first, last, LIGHT)
    time.sleep(pause_s)
    if text is None:
        if first == last:
            raise RuntimeError(f"more than 5,000 light-instrument products on {first}")
        middle = first + (last - first) / 2
        download_month(s, first, middle, folder, pause_s)
        download_month(s, middle + timedelta(days=1), last, folder, pause_s)
        return
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_exposures(folder: Path) -> pd.DataFrame:
    """All downloaded exposures: start and end time (UTC), instrument and object."""
    frames = [pd.read_csv(io.StringIO(f.read_text(encoding="utf-8")), skipinitialspace=True, dtype=str)
              for f in sorted(folder.glob("*.csv")) if f.read_text(encoding="utf-8").strip()]
    if not frames:
        return pd.DataFrame(columns=["t0", "t1", "instrument", "object"])
    exp = pd.concat(frames, ignore_index=True).drop_duplicates("Prod ID")
    out = pd.DataFrame({"t0": pd.to_datetime(exp["Init.Time"], utc=True, errors="coerce"),
                        "t1": pd.to_datetime(exp["End Time"], utc=True, errors="coerce"),
                        "instrument": exp["Instr."], "object": exp["Object"]}).dropna(subset=["t0", "t1"])
    # Keep plausible exposures (some rows have the end before the start, or last for days).
    return out[(out["t1"] >= out["t0"]) & (out["t1"] - out["t0"] < pd.Timedelta(hours=3))].reset_index(drop=True)
