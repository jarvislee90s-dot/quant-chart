import datetime as dtm
import pandas as pd
import plotly.graph_objects as go
from quantchart.core.session import build_slots, day_grid
from quantchart.render.primitives import Ctx, draw

def _ctx():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i,
                        "basis": 300.0 - i * .1}
                       for i, t in enumerate(day_grid(d))])
    slots = build_slots(df)
    return Ctx(slots=slots, df=slots.df), slots

def test_line_adds_trace():
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "line", "col": "fut_close", "name": "收盘", "color": "#123456"}, ctx)
    assert fig.data[0].line.color == "#123456" and fig.data[0].name == "收盘"

def test_area_adds_two_fills_on_y2():
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "area", "col": "basis", "axis": "y2"}, ctx)
    assert len(fig.data) == 3 and all(t.fill == "tozeroy" for t in fig.data[:2])
    assert fig.data[0].yaxis == "y2"

def test_zone_rect_and_hline():
    ctx, slots = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "zone", "from": "2026-08-19 13:00", "to": "2026-08-19 14:00",
               "price": [6950, 7050], "label": "Z1"}, ctx)
    draw(fig, {"type": "hline", "value": 250, "axis": "y2",
               "from": "2026-08-19 13:00", "to": "2026-08-19 14:00"}, ctx)
    assert fig.layout.shapes[0].type == "rect"
    assert fig.layout.shapes[1].y0 == 250 and fig.layout.shapes[1].yref == "y2"
    assert any("Z1" in (a.text or "") for a in fig.layout.annotations)


def test_hline_to_only_label_uses_data_coords():
    # P2#3 回归：只给 to 不给 from 时，线体与标注都必须是数据坐标——
    # 原实现标注 xref 退化为 paper、x 取数据 pos（如 242），锚点错位到纸面外
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "hline", "value": 250, "axis": "y2",
               "to": "2026-08-19 14:00", "label": "仅to端"}, ctx)
    shape = fig.layout.shapes[0]
    ann = fig.layout.annotations[0]
    assert shape.xref == "x" and shape.x0 == 0.0          # 缺省 from 端 = 数据首 pos
    assert shape.x0 == ann.x and ann.xref == "x"         # 标注锚在线体左端、同坐标系
    assert ann.yref == "y2" and ann.y == 250


def test_hline_from_only_label_at_from_x():
    # P2#3 回归：只给 from 时标注锚在 from 端（数据坐标），线体延伸到数据末 pos
    ctx, slots = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "hline", "value": 260, "axis": "y2",
               "from": "2026-08-19 13:00", "label": "仅from端"}, ctx)
    shape = fig.layout.shapes[0]
    ann = fig.layout.annotations[0]
    assert shape.xref == "x" and shape.x1 == float(slots.n_all - 1)
    assert ann.xref == "x" and ann.x == shape.x0


def test_hline_paper_full_width_label_unchanged():
    # 纸面全宽（无 from/to）行为不变：线体与标注均 paper 坐标、左端 0
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "hline", "value": 250, "axis": "y", "label": "纸面线"}, ctx)
    shape = fig.layout.shapes[0]
    ann = fig.layout.annotations[0]
    assert shape.xref == "paper" and shape.x0 == 0 and shape.x1 == 1
    assert ann.xref == "paper" and ann.x == 0
