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


def _df_with_volume():
    df = _df()
    df["volume"] = 100.0
    return df


def test_volume_panel_appends_second_panel():
    load_plugins()
    out = get_strategy("daily_candle")(_df_with_volume(), None, ma=[5], volume_panel=True)
    assert len(out.panels) == 2
    p1 = out.panels[1]
    assert p1["title"] == "成交量" and p1["y_title"] == "成交量"
    assert p1["range_cols"] == ["volume"]
    assert p1["layers"] == [{"type": "volume", "col": "volume"}]


def test_volume_panel_default_off():
    load_plugins()
    out = get_strategy("daily_candle")(_df_with_volume(), None, ma=[5])
    assert len(out.panels) == 1                      # 缺省行为不变（单面板）


def test_volume_panel_skipped_without_volume_column():
    # 无量品种：不追加空面板（适配器脚注已提示"无量"）
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5], volume_panel=True)
    assert len(out.panels) == 1


def test_volume_panel_invalid_type():
    load_plugins()
    with pytest.raises(ValueError, match="volume_panel"):
        get_strategy("daily_candle")(_df_with_volume(), None, volume_panel="yes")


# ── MA 窗口与数据长度关系（backlog #23）──

def test_ma_window_within_data_kept():
    # 窗口 < 数据长：图层保留，无回显
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5])
    assert [l["name"] for l in out.panels[0]["layers"] if l["type"] == "line"] == ["MA5"]
    assert out.notes == []


def test_ma_window_equals_data_length_kept():
    # 窗口 == 数据长：保留（末点单值 partial，rolling 语义不变），无回显
    load_plugins()
    out = get_strategy("daily_candle")(_df().head(10), None, ma=[10])
    assert [l["name"] for l in out.panels[0]["layers"] if l["type"] == "line"] == ["MA10"]
    assert out.notes == []


def test_ma_window_beyond_dropped_with_note():
    # 窗口 > 数据长：图层移除（不画、不阻断）+ 脚注回显（不静默）
    load_plugins()
    out = get_strategy("daily_candle")(_df().head(12), None, ma=[20, 60])
    assert not any(l["type"] == "line" for l in out.panels[0]["layers"])
    assert any("MA20（20根）" in n and "MA60（60根）" in n and "未绘制" in n
               for n in out.notes)


def test_ma_windows_mixed_keeps_shorter_with_note():
    # 混合：短窗口保留且配色按原序号（不被缺失窗口挤压），长窗口移除并回显
    load_plugins()
    out = get_strategy("daily_candle")(_df().head(12), None, ma=[5, 20, 60])
    line = [l for l in out.panels[0]["layers"] if l["type"] == "line"]
    assert [l["name"] for l in line] == ["MA5"]
    assert line[0]["color"] == DARK["ma_palette"][0]
    assert any("MA20（20根）" in n and "MA60（60根）" in n for n in out.notes)


def test_ma_overflow_intraday_converted_windows():
    # 日内换算路径：ma5 按工作日换算成 80 根，80 > 64 根 → 不画并回显换算后窗口
    load_plugins()
    df = _intraday_plugin_df(bars_per_day=16, days=4)
    out = get_strategy("daily_candle")(df, None, ma=[5])
    assert not any(l["type"] == "line" for l in out.panels[0]["layers"])
    assert any("MA5（80根）" in n for n in out.notes)
