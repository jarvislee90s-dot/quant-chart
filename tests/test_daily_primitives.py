import pandas as pd
import plotly.graph_objects as go
import pytest

from quantchart.render.primitives import Ctx, draw
from quantchart.render.theme import DARK


def _ctx():
    df = pd.DataFrame({
        "pos": [0.0, 1.0, 2.0],
        "datetime": pd.to_datetime(["2026-08-25", "2026-08-26", "2026-08-27"]),
        "open": [1.0, 2.0, 3.0], "high": [2.0, 3.0, 4.0],
        "low": [0.5, 1.5, 2.5], "close": [1.5, 2.5, 3.5],
    })
    return Ctx(slots=None, df=df)


def test_candle_trace_and_colors():
    fig = go.Figure()
    draw(fig, {"type": "candle"}, _ctx())
    tr = fig.data[0]
    assert tr.type == "candlestick"
    assert tr.increasing.line.color == DARK["up"]
    assert tr.decreasing.line.color == DARK["down"]
    assert tr.showlegend is False


def test_trendline_line_and_label():
    fig = go.Figure()
    draw(fig, {"type": "trendline", "from": ["2026-08-25", 1.0], "to": ["2026-08-27", 3.0],
               "color": "#f1c40f", "dash": "dash", "label": "通道"}, _ctx())
    tr = fig.data[0]
    assert list(tr.x) == [0.0, 2.0] and list(tr.y) == [1.0, 3.0]
    assert tr.line.dash == "dash" and tr.showlegend is False
    assert fig.layout.annotations[0].text == "通道"


def test_arrow_data_coords():
    fig = go.Figure()
    draw(fig, {"type": "arrow", "from": ["2026-08-25", 1.0], "to": ["2026-08-25", 3.0],
               "color": "#e0312f", "text": "区间宽度"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.showarrow is True and ann.arrowhead == 2
    assert ann.arrowcolor == "#e0312f" and ann.text == "区间宽度"
    assert ann.axref == "x" and ann.ayref == "y"     # 尾点=from，头点=to（数据坐标）
    assert ann.x == 0.0 and ann.ax == 0.0


def test_tag_right_edge_pill():
    fig = go.Figure()
    draw(fig, {"type": "tag", "value": 2.5, "text": "7560", "color": "#ff8c00"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.xref == "paper" and ann.xanchor == "left"
    assert ann.y == 2.5 and ann.bgcolor == "#ff8c00"
    assert ann.showarrow is False


def test_circle_marker_with_label():
    fig = go.Figure()
    draw(fig, {"type": "circle", "at": ["2026-08-26", 2.5], "color": "#f1c40f", "label": "1"}, _ctx())
    tr = fig.data[0]
    assert tr.marker.symbol == "circle-open"
    assert tr.mode == "markers+text" and tr.text[0] == "1"


def test_text_annotation():
    fig = go.Figure()
    draw(fig, {"type": "text", "at": ["2026-08-25", 3.5], "text": "IM2612合约",
               "size": 16, "color": "#e0312f"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.showarrow is False and ann.text == "IM2612合约"
    assert ann.font.size == 16 and ann.font.color == "#e0312f"


def test_hline_label_bgcolor_default_white():
    fig = go.Figure()
    draw(fig, {"type": "hline", "value": 2.0, "label": "支撑", "from": "2026-08-25",
               "to": "2026-08-27"}, _ctx())
    assert fig.layout.annotations[0].bgcolor == "white"     # 分钟路径行为不变


def test_zone_label_bgcolor_default_white():
    fig = go.Figure()
    draw(fig, {"type": "zone", "from": "2026-08-25", "to": "2026-08-27",
               "price": [1.0, 2.0], "label": "观察区"}, _ctx())
    assert fig.layout.annotations[0].bgcolor == "white"     # 分钟路径行为不变

def test_channel_two_rails_asymmetric():
    fig = go.Figure()
    draw(fig, {"type": "channel", "from": ["2026-08-25", 7000.0], "to": ["2026-08-27", 7100.0],
               "lower": 40.0, "upper": 60.0, "color": "#39d353", "dash": "dash"}, _ctx())
    assert len(fig.data) == 2
    assert list(fig.data[0].y) == [6960.0, 7060.0]      # 下轨 = 中枢 − 40
    assert list(fig.data[1].y) == [7060.0, 7160.0]      # 上轨 = 中枢 + 60
    assert fig.data[0].line.dash == "dash"
    assert fig.data[0].showlegend is False


def test_channel_symmetric_width_and_label():
    fig = go.Figure()
    draw(fig, {"type": "channel", "from": ["2026-08-25", 7000.0], "to": ["2026-08-27", 7100.0],
               "width": 50.0, "label": "外层通道"}, _ctx())
    assert list(fig.data[0].y) == [6950.0, 7050.0]      # width 等宽：中枢±50
    ann = fig.layout.annotations[0]
    assert ann.text == "外层通道" and ann.y == 7100.0    # 标在上轨中点上方


def test_candle_colors_reference_theme(monkeypatch):
    """防漂移守护：_candle 缺省色必须引用 theme.DARK，不得内嵌字面色。"""
    from quantchart.render import theme
    monkeypatch.setitem(theme.DARK, "up", "#abc123")
    monkeypatch.setitem(theme.DARK, "down", "#321cba")
    fig = go.Figure()
    draw(fig, {"type": "candle"}, _ctx())
    assert fig.data[0].increasing.line.color == "#abc123"
    assert fig.data[0].decreasing.line.color == "#321cba"


def _ctx_vol():
    df = _ctx().df
    df["volume"] = [100.0, 200.0, 300.0]
    df["open"] = [3.0, 1.0, 4.0]      # 跌/涨/跌（close 1.5/2.5/3.5）
    df["close"] = [1.5, 2.5, 3.5]
    return Ctx(slots=None, df=df)


def test_volume_bars_colored_by_up_down():
    fig = go.Figure()
    draw(fig, {"type": "volume"}, _ctx_vol())
    tr = fig.data[0]
    assert tr.type == "bar" and tr.name == "成交量"
    assert list(tr.marker.color) == [DARK["down"], DARK["up"], DARK["down"]]  # 跌/涨/跌
    assert tr.showlegend is False


def test_volume_skips_when_column_missing():
    # 无量品种（适配器已丢列/脚注提示）：原语自动省略，不画空面板
    fig = go.Figure()
    draw(fig, {"type": "volume"}, _ctx())
    assert len(fig.data) == 0


def test_volume_skips_when_all_nan():
    ctx = _ctx_vol()
    ctx.df["volume"] = float("nan")
    fig = go.Figure()
    draw(fig, {"type": "volume"}, ctx)
    assert len(fig.data) == 0


def test_volume_binds_ctx_yaxis():
    fig = go.Figure()
    draw(fig, {"type": "volume"}, Ctx(slots=None, df=_ctx_vol().df, yaxis="y2"))
    assert fig.data[0].yaxis == "y2"                  # 多面板时落本面板轴（不混入主图）


def test_volume_custom_colors_and_width():
    fig = go.Figure()
    draw(fig, {"type": "volume", "up": "#111111", "down": "#222222", "width": 0.5},
         _ctx_vol())
    tr = fig.data[0]
    assert list(tr.marker.color) == ["#222222", "#111111", "#222222"]
    assert tr.width == 0.5


def test_volume_requires_ohlc_columns():
    # 缺 open/close 的宽表误用 volume → 中文报错而非裸 KeyError
    ctx = Ctx(slots=None, df=_ctx_vol().df.drop(columns=["open", "close"]))
    fig = go.Figure()
    with pytest.raises(ValueError, match="OHLC"):
        draw(fig, {"type": "volume"}, ctx)
