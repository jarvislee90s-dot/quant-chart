import pandas as pd
import plotly.graph_objects as go
import pytest

from quantchart.adapters.common import DailyQualityReport
from quantchart.core.session import build_daily_slots
from quantchart.render.figure_daily import build_daily_figure


def _daily_df(n=10):
    idx = pd.bdate_range("2026-06-01", periods=n)
    return pd.DataFrame({"datetime": idx, "open": [7000 + i for i in range(n)],
                         "high": [7100 + i for i in range(n)],
                         "low": [6950 + i for i in range(n)],
                         "close": [7050 + i for i in range(n)], "volume": 100.0})


def _panels():
    return [{"title": "主图", "layers": [{"type": "candle"}]}]


def test_build_daily_figure_dark_single_panel():
    df = _daily_df()
    slots = build_daily_slots(df)
    fig = build_daily_figure(df, slots, _panels(),
                             DailyQualityReport("x", 10, 10), title="测试")
    assert fig.layout.paper_bgcolor == "#0d1117"
    assert fig.layout.xaxis.rangeslider.visible is False
    assert fig.layout.yaxis.range[0] < df["low"].min()      # 下留白
    texts = [a.text for a in fig.layout.annotations]
    assert any("测试" in t for t in texts)
    assert any("交易日10天" in t for t in texts)


def test_build_daily_figure_rejects_multi_panel():
    df = _daily_df(3)
    slots = build_daily_slots(df)
    with pytest.raises(ValueError, match="单面板"):
        build_daily_figure(df, slots, [{"layers": []}, {"layers": []}],
                           DailyQualityReport("x", 3, 3))