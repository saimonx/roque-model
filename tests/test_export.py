"""Tests for the training-data export (export_data.py)."""

import pandas as pd

from roque_forecast import export_data, hourly


def test_every_model_input_is_described():
    # The download must explain every column the model reads.
    assert set(hourly.CLOSURE_FEATURES) <= set(export_data.COLUMNS)
    assert export_data.COLUMNS["closed"][0] == "0/1"


def test_wrong_share_counts_like_the_page():
    # 0.5 or more means "closed"; three of four hours right.
    test = pd.DataFrame({"closed": [1, 0, 1, 0], "p_final": [0.5, 0.49, 0.2, 0.1]})
    assert export_data.wrong_share(test, "p_final") == 0.25


def test_column_table_is_markdown():
    table = export_data.column_table({"a": ("m/s", "wind", "NOT")})
    assert table.splitlines()[-1] == "| `a` | m/s | wind | NOT |"
