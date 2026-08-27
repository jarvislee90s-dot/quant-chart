"""四段流水线编排：适配→槽位→插件→渲染。"""
from ..adapters.auto import auto_load
from ..render.figure import build_figure
from .plugins import get_strategy, load_plugins
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


def merge_panels(default_panels: list, user_panels: list) -> list:
    """用户 panels 覆盖默认（MVP：整体替换或取默认）。"""
    return user_panels or default_panels


def run_pipeline(cfg: dict, title: str = "") -> tuple:
    df, rep = auto_load(cfg["input"])
    slots = build_slots(df)
    load_plugins()
    out = get_strategy(cfg["strategy"])(slots.df, slots, **cfg.get("params", {}))
    panels = merge_panels(out.panels, cfg.get("panels"))
    panels = [{**p, "layers": _wire_events(p.get("layers", []), out.events)}
              for p in panels]
    if not title:
        title = f"{cfg['strategy']}（{cfg['input'].get('range', ['',''])[0]}–{cfg['input'].get('range', ['',''])[1]}）"
    fig = build_figure(out.df, slots, panels, rep, title=title)
    return fig, rep
