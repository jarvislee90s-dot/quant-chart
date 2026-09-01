"""四段流水线编排：适配→槽位→插件→(trades展开)→渲染。"""
import pandas as pd

from ..adapters.auto import auto_load
from ..adapters.daily import load_daily
from ..render.figure import build_figure
from ..render.figure_daily import build_daily_figure
from .config import GRANULARITY_BPD
from .plugins import get_strategy, load_plugins
from .position import expand_trades
from .session import build_daily_slots, build_slots


def _wire_events(layers: list, events: list) -> list:
    by_kind = {}
    for e in events:
        by_kind.setdefault(e.kind, []).append(e)
        if e.kind.startswith("trade_exec"):     # ref="trade_exec"（前缀引用）聚合全部交易事件
            by_kind.setdefault("trade_exec", []).append(e)
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
    if str(cfg["input"].get("mode", "excel")).startswith("daily"):
        return run_daily_pipeline(cfg, title=title)
    row_heights = row_heights or cfg.get("row_heights")   # YAML row_heights 对两条产品线同效
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
    # 长度校验与日线同文案：不符时报中文错误（否则多面板落到 plotly 英文报错，
    # 单面板被 _build_single 静默丢弃，配置写错无迹可寻）
    if row_heights is not None and len(row_heights) != len(panels):
        raise ValueError(f"row_heights 长度 {len(row_heights)} 与面板数 {len(panels)} 不符"
                         "（多面板时每个面板一个高度占比，如 [0.72, 0.28]）")
    fig = build_figure(out.df, slots, panels, rep, title=title, row_heights=row_heights)
    return fig, rep


def run_daily_pipeline(cfg: dict, title: str = "") -> tuple:
    """日线旁路：daily_* 通道 → 日线槽位 → 插件 → 深色主题组装（单面板）。"""
    if cfg.get("trades") or cfg.get("trades_csv"):
        raise ValueError("日线模式暂不支持 trades/trades_csv 交易明细（接口保留，日线口径后续适配）")
    inp = cfg["input"]
    df, rep = load_daily(inp)
    gran = inp.get("granularity", "auto")
    slots = build_daily_slots(df, tick_anchor=inp.get("tick_anchor"))
    load_plugins()
    out = get_strategy(cfg["strategy"])(slots.df, slots, **cfg.get("params", {}))

    # 周期校验（granularity 显式时，数据推断与指定必须一致）；auto 时回显推断值
    bpd = slots.n_all / max(1, len(slots.day_span))
    notes = list(out.notes)
    if gran != "auto":
        expected = GRANULARITY_BPD[gran]
        if abs(bpd - expected) > max(1.0, expected * 0.15):
            raise ValueError(f"周期校验失败: 数据推断每交易日约 {bpd:.0f} 根，"
                             f"与指定 granularity={gran}（{expected} 根/日）不符"
                             "——请修正 input.granularity 或检查数据")
    else:
        notes.append(f"周期自动推断: 每交易日约{bpd:.0f}根")
    fd = cfg.get("forecast_days")
    if fd is not None:
        notes.append(f"预测区: {fd:g}个工作日 ≈ {fd * bpd:.0f}根")

    panels = merge_panels(out.panels, cfg.get("panels"), cfg.get("extra_panels"))
    panels = [{**p, "layers": _wire_events(p.get("layers", []), out.events)}
              for p in panels]
    # 标注 pos 锚点防呆：中图位置若用数字 pos，换数据会错位——计数回显到脚注
    pos_anchors = 0
    for spec in (s for p in panels for s in p.get("layers", [])):
        if spec.get("type") not in ("trendline", "arrow", "circle", "text"):
            continue
        first = (spec.get("at") or spec.get("from") or [None])[0]
        if isinstance(first, (int, float)) and not isinstance(first, bool) \
                and first < slots.n_all:
            pos_anchors += 1
    if pos_anchors:
        notes.append(f"标注含{pos_anchors}处pos锚点（换数据需重新校准）")
    if not title:
        title = (f"{cfg['strategy']}（{cfg['input'].get('range', ['',''])[0]}"
                 f"–{cfg['input'].get('range', ['',''])[1]}）")
    heights = cfg.get("row_heights")
    if heights is not None and len(heights) != len(panels):
        raise ValueError(f"row_heights 长度 {len(heights)} 与面板数 {len(panels)} 不符"
                         "（多面板时每个面板一个高度占比，如 [0.72, 0.28]）")
    fig = build_daily_figure(out.df, slots, panels, rep, title=title, notes=notes,
                             forecast_days=cfg.get("forecast_days"),
                             row_heights=heights)
    return fig, rep