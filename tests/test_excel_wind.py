# tests/test_excel_wind.py
import os

import pandas as pd
from quantchart.adapters.excel_wind import load_wind_pair

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_load_wind_pair_aligns_and_fills():
    df, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx")
    assert rep.days == 2 and rep.rows == 2 * 242
    assert list(df.columns[:3]) == ["datetime", "fut_open", "fut_high"]
    assert df["fut_close"].notna().all()
    assert rep.filled_index == 2          # 指数端每天缺 14:59
    assert rep.filled_future == 0
    assert abs(df["idx_close"].iloc[-2] - df["idx_close"].iloc[-3]) < 1e-9  # ffill 生效（填充的14:59==14:58）

def test_date_range_filter():
    df, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx",
                             start="2026-08-20", end="2026-08-20")
    assert rep.days == 1 and len(df) == 242

def test_footnote_text():
    _, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx")
    assert "Wind Excel" in rep.footnote() and "484" in rep.footnote()
