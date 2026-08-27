import datetime as dtm
import pandas as pd
import plotly.graph_objects as go
from quantchart.core.session import build_slots, day_grid
from quantchart.core.signals import daily_min_events, window_min_events
from quantchart.render.primitives import Ctx, draw

def _ctx():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                        "basis": 300.0 - i * .1} for i, t in enumerate(day_grid(d))])
    slots = build_slots(df)
    ctx = Ctx(slots=slots, df=slots.df)
    ev = {"daily_min": daily_min_events(slots.df, slots, "basis"),
          "window_min": window_min_events(slots.df, [("2026-08-19 11:30", "2026-08-19 15:00")], "fut_low")}
    return ctx, ev

def test_events_markers_and_labels():
    ctx, ev = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "events", "ref": "daily_min", "events": ev,
               "axis": "y2", "symbol": "triangle-down"}, ctx)
    assert fig.data[0].marker.symbol == "triangle-down"
    assert any("291" in (a.text or "") or (a.text or "").isdigit() for a in fig.layout.annotations)

def test_leader_tag_annotation_math():
    ctx, ev = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "leader_tag", "ref": "window_min", "events": ev,
               "ref_value_col": "fut_close",
               "text": "距期末 +{diff}（{pct}%）"}, ctx)
    txt = [a.text for a in fig.layout.annotations if a.text and "距期末" in a.text]
    assert txt, "应有价差标注"
    ev0 = ev["window_min"][0]
    ref = ctx.df["fut_close"].dropna().iloc[-1]
    assert f"+{ref - ev0.value:.0f}" in txt[0]
    assert any(t.mode == "lines" for t in fig.data)   # 连线到基准线（Scatter 点线）

def test_day_seps_and_labels():
    d1, d2 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    df = pd.DataFrame([{"datetime": t} for d in (d1, d2) for t in day_grid(d)])
    slots = build_slots(df)
    ctx = Ctx(slots=slots, df=slots.df)
    fig = go.Figure()
    draw(fig, {"type": "day_seps"}, ctx)
    draw(fig, {"type": "day_labels"}, ctx)
    assert any(sh.type == "line" and sh.x0 == sh.x1 for sh in fig.layout.shapes)
    assert any((a.text or "") == "08-19" for a in fig.layout.annotations)
