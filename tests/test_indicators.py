import datetime as dtm
import numpy as np
import pandas as pd
from quantchart.core.indicators import apply_indicators, REGISTRY
from quantchart.core.session import day_grid

def _df():
    d1, d2 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    rows = []
    for d in (d1, d2):
        for i, t in enumerate(day_grid(d)):
            rows.append({"datetime": t, "fut_close": 7000 + i * .1,
                         "fut_volume": 10.0, "fut_amount": 7000 * 200 * 10 / 1e6 * (i + 1),
                         "idx_close": 7300 + i * .1})
    return pd.DataFrame(rows)

def test_registry_has_builtin():
    assert {"basis", "basis_rate", "vwap"} <= set(REGISTRY)

def test_basis_chain():
    df = apply_indicators(_df(), [{"name": "basis"}, {"name": "basis_rate"}])
    assert abs(df["basis"].iloc[0] - 300.0) < 1e-9
    assert abs(df["basis_rate"].iloc[0] - 300 / 7300 * 100) < 1e-9

def test_vwap_per_day_reset():
    df = apply_indicators(_df(), [{"name": "vwap"}])
    day = df["datetime"].dt.date
    first_d1 = df.loc[day == dtm.date(2026, 8, 19), "fut_vwap"].iloc[0]
    first_d2 = df.loc[day == dtm.date(2026, 8, 20), "fut_vwap"].iloc[0]
    assert abs(first_d1 - df["fut_close"].iloc[0]) < 1.0      # 首分钟≈现价
    assert abs(first_d1 - first_d2) < 1.0                     # 每日重置

def test_unknown_indicator_raises():
    try:
        apply_indicators(_df(), [{"name": "nope"}])
        assert False
    except KeyError as e:
        assert "nope" in str(e)
