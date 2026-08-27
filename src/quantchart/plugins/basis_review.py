"""预设1：价格+均价+贴水+每日贴水最低标注（对应 Backset V1 图）。"""
from ..core.indicators import apply_indicators
from ..core.plugins import StrategyOutput, register_strategy
from ..core.signals import daily_min_events

PANELS = [{
    "title": "主图",
    "layers": [
        {"type": "line", "col": "fut_vwap", "name": "IM2612 日内均价（累计VWAP）",
         "color": "#ef8a1c", "dash": "dash", "width": 1.6},
        {"type": "line", "col": "fut_close", "name": "IM2612 分钟收盘价",
         "color": "#1c4e9d", "width": 2.2},
        {"type": "area", "col": "basis", "axis": "y2"},
        {"type": "events", "ref": "daily_min", "axis": "y2",
         "symbol": "triangle-down", "color": "#701820"},
        {"type": "day_seps"},
        {"type": "day_labels"},
    ],
}]


@register_strategy("basis_review")
def run(df, slots, **params):
    df = apply_indicators(df, [{"name": "vwap"}, {"name": "basis"},
                               {"name": "basis_rate"}])
    events = list(daily_min_events(df, slots, "basis"))
    return StrategyOutput(df=df, events=events, panels=PANELS)
