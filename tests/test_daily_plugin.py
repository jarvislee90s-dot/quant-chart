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
def _intraday_plugin_df(bars_per_day=16, days=30):
    rows = []
    p = 0.0
    for d in pd.bdate_range("2026-06-01", periods=days):
        for i in range(bars_per_day):
            rows.append({"datetime": d + pd.Timedelta(hours=9, minutes=30 + 15 * i),
                         "pos": p, "close": float(i % 7),
                         "high": float(i % 7) + 20.0, "low": float(i % 7) - 20.0})
            p += 1
    return pd.DataFrame(rows)


def test_ma_windows_converted_to_working_days():
    load_plugins()
    df = _intraday_plugin_df()                 # 16根/日
    out = get_strategy("daily_candle")(df, None, ma=[5])
    w = 5 * 16
    assert out.df["ma5"].iloc[-1] == pytest.approx(df["close"].iloc[-w:].mean())


def test_ma_unit_bar_opts_out():
    load_plugins()
    df = _intraday_plugin_df()
    out = get_strategy("daily_candle")(df, None, ma=[5], ma_unit="bar")
    assert out.df["ma5"].iloc[-1] == pytest.approx(df["close"].iloc[-5:].mean())


def test_ma_unit_invalid():
    load_plugins()
    with pytest.raises(ValueError, match="ma_unit"):
        get_strategy("daily_candle")(_df(), None, ma_unit="week")


def test_channels_param_auto_fit():
    load_plugins()
    df = _intraday_plugin_df()
    out = get_strategy("daily_candle")(df, None,
                                       channels=[{"start": df["datetime"].iloc[20].isoformat(),
                                                  "end": df["datetime"].iloc[-1].isoformat(),
                                                  "color": "#39d353", "dash": "dash"}])
    ch = [l for l in out.panels[0]["layers"] if l["type"] == "channel"]
    assert len(ch) == 1
    assert ch[0]["color"] == "#39d353" and ch[0]["dash"] == "dash"
    assert ch[0]["from"][0] == df.loc[20, "pos"]
    assert ch[0]["lower"] >= 0.0 and ch[0]["upper"] >= 0.0


def test_channels_param_requires_start_end():
    load_plugins()
    with pytest.raises(ValueError, match=r"channels\[0\]"):
        get_strategy("daily_candle")(_intraday_plugin_df(), None, channels=[{"color": "#fff"}])


def test_channels_rule_anchor_peak_and_breakout():
    load_plugins()
    df = _intraday_plugin_df(bars_per_day=4, days=30)
    peak_dt = df.loc[df["high"].idxmax(), "datetime"]
    out = get_strategy("daily_candle")(df, None,
                                       channels=[{"start": {"peak": True},
                                                  "end": {"above": 2.5, "after": str(peak_dt.date())},
                                                  "color": "#39d353"}])
    ch = [l for l in out.panels[0]["layers"] if l["type"] == "channel"]
    assert len(ch) == 1
    assert any("锚点解析" in n for n in out.notes)


def test_channels_rule_anchor_no_hit():
    load_plugins()
    with pytest.raises(ValueError, match="无命中"):
        get_strategy("daily_candle")(_intraday_plugin_df(), None,
                                     channels=[{"start": "2026-06-01", "end": {"above": 99999.0}}])


def test_channels_rule_anchor_invalid():
    load_plugins()
    with pytest.raises(ValueError, match="锚点规则非法"):
        get_strategy("daily_candle")(_intraday_plugin_df(), None,
                                     channels=[{"start": {"sideways": True}, "end": "2026-07-01"}])
