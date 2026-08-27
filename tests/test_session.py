import datetime as dtm
import numpy as np
import pandas as pd
from quantchart.core.session import day_grid, build_slots

def _synth_days(n=3):
    rows = []
    for i, d in enumerate([dtm.date(2026, 8, 19) + dtm.timedelta(days=i) for i in range(n)]):
        for t in day_grid(d):
            rows.append({"datetime": t, "fut_close": 7000.0 + i * 10 + t.hour})
    return pd.DataFrame(rows)

def test_day_grid_len():
    assert len(day_grid(dtm.date(2026, 8, 19))) == 242

def test_build_slots_positions_and_seps():
    slots = build_slots(_synth_days(3))
    assert slots.n_all == 3 * 242 + 2          # 2 个隔日空位
    assert len(slots.sep_center) == 2
    df = slots.df
    assert df["pos"].notna().all()
    assert df["pos"].max() == slots.n_all - 1
    d0, d1 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    assert slots.day_span[d0][1] + 2 == slots.day_span[d1][0]   # 隔1个空位

def test_tick_labels_skip_rules():
    slots = build_slots(_synth_days(2))
    labs = dict(zip(slots.tick_pos, slots.tick_lab))
    assert any(v == "" for v in labs.values())   # 13:00 与非末日15:00 留空
    assert labs[slots.day_span[dtm.date(2026, 8, 19)][0]] == "09:30"
