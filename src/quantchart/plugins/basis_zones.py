"""预设2：basis_review + 击球区矩形/区内触发线/窗口低点连线价差（对应 V2 图）。"""
from ..core.indicators import apply_indicators
from ..core.plugins import StrategyOutput, register_strategy
from ..core.signals import daily_min_events, window_min_events
from .basis_review import PANELS as BASE_PANELS


@register_strategy("basis_zones")
def run(df, slots, trigger=250.0, zones=None, **params):
    df = apply_indicators(df, [{"name": "vwap"}, {"name": "basis"},
                               {"name": "basis_rate"}])
    zones = zones or []
    events = list(daily_min_events(df, slots, "basis"))
    events += window_min_events(df, [(z["from"], z["to"]) for z in zones], "fut_low")

    last = df["datetime"].dropna().iloc[-1]
    lead_text = f"距{last.month}.{last.day}收盘价 +{{diff}}（{{pct}}%）"
    extra = []
    for z in zones:
        extra.append({"type": "zone", **z})
        extra.append({"type": "hline", "value": trigger, "axis": "y2",
                      "from": z["from"], "to": z["to"],
                      "color": "#0e6e64", "dash": "dash", "width": 1.3})
    extra.append({"type": "hline", "col_last": "fut_close", "axis": "y",
                  "color": "#83898f", "dash": "dash",
                  "label": f"现价（{last.month}.{last.day}收盘）"})
    extra.append({"type": "leader_tag", "ref": "window_min",
                  "ref_value_col": "fut_close", "text": lead_text,
                  "ax": 92, "ay": -120})
    layers = BASE_PANELS[0]["layers"][:-2] + extra + BASE_PANELS[0]["layers"][-2:]
    return StrategyOutput(df=df, events=events,
                          panels=[{**BASE_PANELS[0], "layers": layers}])
