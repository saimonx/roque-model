"""Liverpool Telescope night reports: parsing and labels."""

import pandas as pd

from roque_forecast.sources import liverpool

PAGE = """
<h3>March 2024</h3>
<table>
<tr><th>Date</th><th>Observing</th><th>Weather</th><th>Technical</th><th>Comment</th></tr>
<tr><td>31 Mar</td><td>0.0</td><td>8.9</td><td>0.0</td><td>Ice risk on enclosure mechanisms.</td></tr>
<tr><td>20 Mar</td><td>9.3</td><td>0.0</td><td>0.0</td><td>Photometric with average seeing.</td></tr>
<tr><td>16 Mar</td><td>9.4</td><td>0.0</td><td>0.0</td><td>Non-photometric, high calima levels.</td></tr>
<tr><td>28 Feb</td><td>9.0</td><td>0.0</td><td>0.0</td><td>A February row shown in the March table.</td></tr>
</table>
"""


def test_parse_keeps_only_the_rows_of_each_month(tmp_path):
    path = tmp_path / "lt.html"
    path.write_text(PAGE)
    table = liverpool.parse(path, 2024)
    assert table["night"].tolist() == [pd.Timestamp("2024-03-31"), pd.Timestamp("2024-03-20"),
                                       pd.Timestamp("2024-03-16")]
    assert table.loc[0, "weather_h"] == 8.9


def test_labels_read_photometric_and_reasons(tmp_path):
    path = tmp_path / "lt.html"
    path.write_text(PAGE)
    lab = liverpool.labels(liverpool.parse(path, 2024).set_index("night"))
    assert lab.loc["2024-03-20", "photometric"] == 1
    assert lab.loc["2024-03-16", "photometric"] == 0  # "Non-photometric" is not "photometric"
    assert pd.isna(lab.loc["2024-03-31", "photometric"])  # closed: no sky quality
    assert lab.loc["2024-03-31", "reason_ice"] and lab.loc["2024-03-16", "reason_dust"]
    assert lab.loc["2024-03-31", "weather_frac"] == 1.0
