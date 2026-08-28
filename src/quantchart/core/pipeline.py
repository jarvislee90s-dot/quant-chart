"""四段流水线编排：适配→槽位→插件→(trades展开)→渲染。"""
import pandas as pd

from ..adapters.auto import auto_load
from ..render.figure import build_figure
from .plugins import get_strategy, load_plugins
from .position import expand_trades
from .session import build_slots


def _wire_events(layers: list, events: list) -> list:
    by_kind = {}
    for e in events:
        by_kind.setdefault(e.kind, []).append(e)
    out = []
    for spec in layers:
        if spec.get("type") in ("events", "leader_tag") and "events" not in spec:
            spec = {**spec, "events": by_kind}
        out.append(spec)
    return out


def merge_panels(default_panels: list, user_panels: list,
                 extra_panels: list | None = None) -> list:
    """优先级：panels（整体替换）> extra_panels（追加）> 插件默认。"""
    return (user_panels or default_panels) + (extra_panels or [])


def run_pipeline(cfg: dict, title: str = "", row_heights: list | None = None) -> tuple:
    df, rep = auto_load(cfg["input"])
    slots = build_slots(df)
    load_plugins()
    out = get_strategy(cfg["strategy"])(slots.df, slots, **cfg.get("params", {}))

    trades = cfg.get("trades")
    if trades is None and cfg.get("trades_csv"):
        raw = pd.read_csv(cfg["trades_csv"])
        trades = raw.to_dict("records")
    if trades:
        out.df, trade_events = expand_trades(out.df, trades,
                                             float(cfg.get("contract_mult", 200)))
        out.events = list(out.events) + trade_events

    panels = merge_panels(out.panels, cfg.get("panels"), cfg.get("extra_panels"))
    if trades and not any(s.get("ref") == "trade_exec"
                          for s in panels[0].get("layers", [])):
        # 有交易明细时自动在面板0 追加买卖点事件层（除非用户已自行配置）
        trade_layer = {"type": "events", "ref": "trade_exec", "axis": "y",
                       "style_map": {"buy": {"symbol": "triangle-up", "color": "#c0392b"},
                                     "sell": {"symbol": "triangle-down", "color": "#1e8449"},
                                     "close": {"symbol": "x", "color": "#55595f"}}}
        panels = [{**panels[0], "layers": panels[0].get("layers", []) + [trade_layer]}] + panels[1:]
    panels = [{**p, "layers": _wire_events(p.get("layers", []), out.events)}
              for p in panels]
    if not title:
        title = f"{cfg['strategy']}（{cfg['input'].get('range', ['',''])[0]}–{cfg['input'].get('range', ['',''])[1]}）"
    fig = build_figure(out.df, slots, panels, rep, title=title, row_heights=row_heights)
    return fig, rep