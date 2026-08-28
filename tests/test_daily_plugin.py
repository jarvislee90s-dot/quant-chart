import pandas as pd
import pytest

from quantchart.core.plugins import get_strategy, load_plugins
from quantchart.render.theme import DARK


def _df():
    return pd.DataFrame({"close": [float(i) for i in range(1, 31)],
                         "datetime": pd.date_range("2026-06-01", periods=30)})


def test_ma_columns_computed():
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5, 10])
    assert out.df["ma5"].iloc[-1] == pytest.approx(28.0)      # mean(26..30)
    assert out.df["ma10"].iloc[-1] == pytest.approx(25.5)     # mean(21..30)


def test_default_layers_candle_plus_mas():
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5, 10])
    types = [l["type"] for l in out.panels[0]["layers"]]
    assert types == ["candle", "line", "line"]
    assert out.panels[0]["layers"][0]["up"] == DARK["up"]
    assert out.panels[0]["layers"][1]["col"] == "ma5"


def test_annotation_passthrough_in_order():
    load_plugins()
    ann = [{"type": "text", "at": ["2026-06-10", 25], "text": "标注"},
           {"type": "trendline", "from": ["2026-06-01", 1], "to": ["2026-06-30", 30]}]
    out = get_strategy("daily_candle")(_df(), None, ma=[5], annotations=ann)
    assert out.panels[0]["layers"][-2:] == ann


def test_hline_defaults_to_main_axis():
    # 分钟路径 _hline 缺省 axis=y2（贴水副轴）；日线单面板必须注入主轴 y
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None,
                                       annotations=[{"type": "hline", "value": 20}])
    h = out.panels[0]["layers"][-1]
    assert h["type"] == "hline" and h["axis"] == "y"


def test_annotation_missing_type():
    load_plugins()
    with pytest.raises(ValueError, match=r"annotations\[0\]"):
        get_strategy("daily_candle")(_df(), None, annotations=[{"value": 1}])


def test_annotation_unknown_type():
    load_plugins()
    with pytest.raises(ValueError, match=r"annotations\[1\].type 非法"):
        get_strategy("daily_candle")(_df(), None,
                                     annotations=[{"type": "hline", "value": 1},
                                                  {"type": "magic", "x": 1}])


def test_ma_validation():
    load_plugins()
    with pytest.raises(ValueError, match="ma"):
        get_strategy("daily_candle")(_df(), None, ma=[0])