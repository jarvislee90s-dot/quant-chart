import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.signals import daily_min_events, window_min_events

def _df():
    d = dtm.date(2026, 8, 19)
    rows = [{"datetime": t, "basis": 300.0 - i * 0.5, "fut_low": 7000 + i}
            for i, t in enumerate(day_grid(d))]
    return pd.DataFrame(rows)

def test_daily_min():
    df, slots = _df(), None
    slots = build_slots(df)
    evs = daily_min_events(slots.df, slots, col="basis")
    assert len(evs) == 1
    assert abs(evs[0].value - df["basis"].min()) < 1e-9
    assert evs[0].kind == "daily_min" and evs[0].label == f"{df['basis'].min():.0f}"

def test_window_min_per_day():
    df = _df()
    slots = build_slots(df)
    evs = window_min_events(slots.df, [("2026-08-19 11:30", "2026-08-19 15:00")], col="fut_low")
    assert len(evs) == 1 and evs[0].kind == "window_min"
    assert evs[0].value == df[df["datetime"] >= pd.Timestamp("2026-08-19 11:30")]["fut_low"].min()

def test_event_meta_default_none():
    from quantchart.core.signals import Event
    e = Event(pos=1.0, dt=pd.Timestamp("2026-08-21 09:39"), value=7104.4,
              label="买1手", kind="trade_exec:buy")
    assert e.meta is None
    e2 = Event(pos=1.0, dt=pd.Timestamp("2026-08-21 09:39"), value=7104.4,
               label="买1手", kind="trade_exec:buy", meta={"action": "buy"})
    assert e2.meta["action"] == "buy"
