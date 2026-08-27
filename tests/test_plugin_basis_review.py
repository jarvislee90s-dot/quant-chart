import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.plugins import get_strategy, load_plugins

def _df():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                        "fut_volume": 10.0, "fut_amount": 1.4,
                        "idx_close": 7300.0 + i} for i, t in enumerate(day_grid(d))])
    return df

def test_plugin_registered_and_output():
    load_plugins()
    strat = get_strategy("basis_review")
    df = _df()
    slots = build_slots(df)
    out = strat(slots.df, slots, trigger=250.0)
    assert "basis" in out.df.columns and "fut_vwap" in out.df.columns
    kinds = {e.kind for e in out.events}
    assert "daily_min" in kinds
    assert isinstance(out.panels, list) and out.panels[0]["layers"]

def test_unknown_strategy():
    load_plugins()
    try:
        get_strategy("nope")
        assert False
    except KeyError:
        pass
