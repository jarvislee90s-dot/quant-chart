"""日线深色主题图组装：单面板原路径 + 多面板（make_subplots 共享X，样式对照 reference/05 校准）。"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .primitives import Ctx, draw
from .theme import DARK


FORECAST_DAYS = 2   # 右缘预测区缺省工作日数（可用配置 forecast_days 每图覆盖，如日线图 10-15）


def build_daily_figure(df, slots, panels, rep, title: str = "", notes=None,
                       forecast_days: float | None = None,
                       row_heights: list | None = None) -> go.Figure:
    if not panels:
        raise ValueError("日线面板配置为空（panels/extra_panels 至少需要 1 个面板）")
    if len(panels) == 1:
        return _build_daily_single(df, slots, panels[0], rep, title, notes, forecast_days)
    return _build_daily_multi(df, slots, panels, rep, title, notes, forecast_days, row_heights)


def _build_daily_single(df, slots, panel, rep, title: str, notes, forecast_days) -> go.Figure:
    """单面板：MVP 原路径（多面板改造零侵入）。"""
    fig = go.Figure()
    # 原语按 ctx.df["pos"] 取坐标：统一用 slots.df（含 pos 列），兼容外部传入未加 pos 的 df
    ctx = Ctx(slots=slots, df=slots.df)
    for spec in _remap_daily_axes(panel.get("layers", []), "y"):
        draw(fig, spec, ctx)

    bars_per_day = len(df) / max(1, len(slots.day_span))
    fc_days = FORECAST_DAYS if forecast_days is None else float(forecast_days)
    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor=DARK["bg"], plot_bgcolor=DARK["bg"],
        font=dict(family="Microsoft YaHei, Arial", size=12, color=DARK["font"]),
        margin=dict(l=64, r=150, t=92, b=88),
        xaxis=dict(range=[-2, slots.n_all + fc_days * bars_per_day + 1.5],
                   tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                   tickfont=dict(size=10, color=DARK["font"]),
                   showgrid=False, zeroline=False, linecolor=DARK["axis"],
                   rangeslider=dict(visible=False)),
        yaxis=dict(range=_daily_range(df), gridcolor=DARK["grid"], griddash="dot",
                   zeroline=False, linecolor=DARK["axis"]),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.01, yanchor="bottom",
                    font=dict(size=11, color=DARK["font"]), bgcolor="rgba(0,0,0,0)"),
    )
    _annotate(fig, rep, title, notes, _visibility_warnings(fig))
    return fig


def _remap_daily_axes(layers: list[dict], default_axis: str) -> list[dict]:
    """轴缺省解析：原语缺省轴（area/hline/events 默认 y2——日内贴水 overlay 语义）
    与字面 "y" 统一注入本面板主轴。日线无贴水 overlay，缺省即"本面板轴"——
    所有面板（含面板0/单面板）一律解析：多面板下 y2 恰为第 2 行的真实轴，
    手写层缺省会静默画错面板；单面板下 y2 是幽灵轴（线不可见/触发 _hline 守卫
    误报"副轴请给 from/to"）。插件自产层已注入 axis="y"（no-op），仅手写
    panels:/extra_panels 层受影响。显式 "y2" 视为字面轴引用，不做改写。"""
    out = []
    for spec in layers:
        s = dict(spec)
        if s.get("axis") in (None, "y") and s.get("type") in ("area", "events", "hline"):
            s["axis"] = default_axis
        out.append(s)
    return out


def _build_daily_multi(df, slots, panels, rep, title, notes, forecast_days,
                       row_heights) -> go.Figure:
    """多面板：make_subplots 多行共享X（量柱与K线同 pos 轴垂直对齐），
    顶行主图保留下方预测区，时间刻度只画在最底面板（与日内多面板同构）。"""
    n = len(panels)
    heights = row_heights or ([0.72] + [0.28 / (n - 1)] * (n - 1))
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, row_heights=heights)
    bars_per_day = len(df) / max(1, len(slots.day_span))
    fc_days = FORECAST_DAYS if forecast_days is None else float(forecast_days)
    right = slots.n_all + fc_days * bars_per_day + 1.5
    for i, panel in enumerate(panels, start=1):
        # plotly 主轴（第1行）引用名固定为 x/y（无编号）；y1/x1 不是合法轴引用
        xax = "x" if i == 1 else f"x{i}"
        yax = "y" if i == 1 else f"y{i}"
        layers = _remap_daily_axes(panel.get("layers", []), yax)
        ctx = Ctx(slots=slots, df=slots.df, xaxis=xax, yaxis=yax)
        for spec in layers:
            draw(fig, spec, ctx)

    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor=DARK["bg"], plot_bgcolor=DARK["bg"],
        font=dict(family="Microsoft YaHei, Arial", size=12, color=DARK["font"]),
        margin=dict(l=64, r=150, t=92, b=88),
        xaxis=dict(range=[-2, right], showgrid=False, zeroline=False,
                   linecolor=DARK["axis"], rangeslider=dict(visible=False)),
        yaxis=dict(range=_daily_range(df), gridcolor=DARK["grid"], griddash="dot",
                   zeroline=False, linecolor=DARK["axis"]),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.01, yanchor="bottom",
                    font=dict(size=11, color=DARK["font"]), bgcolor="rgba(0,0,0,0)"),
    )
    panel_notes = []
    for i in range(2, n + 1):
        panel = panels[i - 1]
        layers = panel.get("layers", [])
        # 纵轴取数列：range_cols 显式优先；缺省收所有带 "col" 的图层（line/volume/area
        # 及未来同构原语自动纳入），标注类原语（hline/zone/arrow/…）无 "col" 键天然排除
        cols = panel.get("range_cols") or [s["col"] for s in layers if "col" in s]
        # 0 基线：面板显式 zero_floor: true，或含量柱层时自动
        zero_floor = bool(panel.get("zero_floor", False)) \
            or any(s.get("type") == "volume" for s in layers)
        lo, hi, ranged = _panel_range(df, cols or ["close"], zero_floor=zero_floor)
        if not ranged:
            # 防呆回显（不阻断）：纵轴退化不静默——提示排查方向，避免空面板无迹可寻
            panel_notes.append(
                f"⚠ 面板「{panel.get('title') or i}」无法确定 y 范围"
                "（range_cols 缺失或全 NaN），纵轴退化为 [0,1]"
                "——请检查 range_cols，或对从 0 起算的柱图设 zero_floor: true")
        is_bottom = i == n
        xconf = dict(showgrid=False, zeroline=False, linecolor=DARK["axis"],
                     showticklabels=bool(is_bottom))   # 仅最底面板画刻度
        if is_bottom:
            xconf.update(range=[-2, right], tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                         tickfont=dict(size=10, color=DARK["font"]))
        fig.update_layout(**{f"xaxis{i}": xconf,
                             f"yaxis{i}": dict(range=[lo, hi],
                                               title=dict(text=panel.get("y_title", "")),
                                               gridcolor=DARK["grid"], griddash="dot",
                                               zeroline=False, linecolor=DARK["axis"])})
    _annotate(fig, rep, title, list(notes or []) + panel_notes, _visibility_warnings(fig))
    return fig


def _panel_range(df, cols, zero_floor=False):
    """面板纵轴范围：默认上下留白；zero_floor（量柱面板）下限锁 0，不做下留白。
    列全部缺失/全 NaN（如无量品种手写量面板）退化为 [0,1]——空面板仍成行，不崩；
    第三返回值 False 供上层脚注回显"无法确定 y 范围"防呆提示（不静默）。"""
    arrays = [df[c].dropna().values for c in cols if c in df]
    vals = np.concatenate(arrays) if arrays else np.array([])
    if vals.size == 0:
        return 0.0, 1.0, False
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return (0.0 if zero_floor else lo - span * .10), hi + span * .16, True


def _visibility_warnings(fig) -> list[str]:
    """渲染可见性守卫（P0）：Plotly 对超界元素静默裁剪——扫描全部数据坐标元素，
    超出 xaxis 范围即在脚注警告（多面板共享X，统一对顶轴范围校验）。"""
    vis = []
    rng = fig.layout.xaxis.range
    if rng:
        left, right = float(rng[0]), float(rng[1])
        for t in fig.data:
            tx = getattr(t, "x", None)
            if tx is None:
                continue
            xv = [v for v in tx if v is not None]
            if xv and (max(xv) > right + 1e-6 or min(xv) < left - 1e-6):
                nm = f"'{t.name}'" if getattr(t, "name", None) else t.type
                vis.append(f"{nm} x∈[{min(xv):.0f},{max(xv):.0f}]")
        for a in fig.layout.annotations:
            if getattr(a, "xref", "x") == "paper":
                continue
            if a.x is not None and (float(a.x) > right + 1e-6 or float(a.x) < left - 1e-6):
                vis.append(f"标注'{a.text or ''}'@{float(a.x):.1f}")
            # 箭尾：凡数据轴（x/x2/…，非 paper）均校验——仅查 axref=='x' 会漏掉
            # 多面板副图标注（axref='x2'）的越界箭尾
            if getattr(a, "axref", "x") != "paper" and a.ax is not None \
                    and (float(a.ax) > right + 1e-6 or float(a.ax) < left - 1e-6):
                vis.append(f"标注'{a.text or ''}'尾@{float(a.ax):.1f}")
        for sh in fig.layout.shapes:
            if getattr(sh, "xref", "x") == "paper":
                continue
            for v in (sh.x0, sh.x1):
                if v is not None and (v > right + 1e-6 or v < left - 1e-6):
                    vis.append(f"形状@{v:.1f}")
    return vis


def _annotate(fig, rep, title, notes, vis):
    parts = [rep.footnote()]
    if notes:
        parts.append(" ".join(notes))
    if vis:
        parts.append("⚠ 渲染可见性警告(超界元素成品中不可见): "
                     + "；".join(vis[:3]) + ("等" if len(vis) > 3 else ""))
    parts.append("时间轴仅含交易日（周末与节假日压缩）。")
    fig.add_annotation(x=.006, y=1.06, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=20, color=DARK["font"]),
                       xanchor="left")
    fig.add_annotation(x=.998, y=-.128, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#7a8494"),
                       text=" ".join(parts))


def _daily_range(df):
    cols = [c for c in ("open", "high", "low", "close") if c in df]
    vals = np.concatenate([df[c].dropna().values for c in cols])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * .06, hi + span * .22
