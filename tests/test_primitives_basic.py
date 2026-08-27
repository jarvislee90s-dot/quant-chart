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
