import pandas as pd
import plotly.graph_objects as go

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