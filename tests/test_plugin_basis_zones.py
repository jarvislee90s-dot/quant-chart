import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.plugins import get_strategy, load_plugins

ZONES = [{"from": "2026-08-19 11:30", "to": "2026-08-19 15:00",
          "price": [6950, 7050], "label": "Z1"}]

def _df():
    d = dtm.date(2026, 8, 19)
    return pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                          "fut_volume": 10.0, "fut_amount": 1.4,
                          "idx_close": 7300.0 + i} for i, t in enumerate(day_grid(d))])

def test_zones_plugin_layers_and_events():
    load_plugins()
    df = _df()
    slots = build_slots(df)
    out = get_strategy("basis_zones")(slots.df, slots, trigger=250.0, zones=ZONES)
    kinds = {e.kind for e in out.events}
    assert "daily_min" in kinds and "window_min" in kinds
    types = [l["type"] for l in out.panels[0]["layers"]]
    assert "zone" in types and "hline" in types and "leader_tag" in types
    hl = [l for l in out.panels[0]["layers"] if l["type"] == "hline"][0]
    assert hl["value"] == 250.0 and hl["from"] == ZONES[0]["from"]
    lt = [l for l in out.panels[0]["layers"] if l["type"] == "leader_tag"][0]
    assert "{diff}" in lt["text"] and "{pct}" in lt["text"]
