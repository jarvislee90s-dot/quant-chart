"""面板组装：槽位X轴 + 双右轴 + 标题/图例/日期行/质量脚注（布局源自已验证样张）。

N==1 走 _build_single（MVP 原路径零改动）；N>1 走 _build_multi（make_subplots 多行，
面板0 保留贴水双右轴、轴号重映射，其余面板各一主轴）。
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .primitives import Ctx, draw

MARGIN = dict(l=68, r=168, t=108, b=130)

# 贴水副轴历史刻度（P2#4 遗留包络内原样保留，既有图零变化）
_LEGACY_BASIS_TICKS = [0] + [float(t) for t in np.arange(240, 400, 20)]
_LEGACY_RATE_TICKS = [float(t) for t in np.arange(0, 5.51, .5)]


def _nice_step(span: float, choices: tuple) -> float:
    """按量级选整齐步长：目标刻度数 ≤ 12；候选全不达标时退化为 span/10（不崩）。"""
    return next((s for s in choices if span / s <= 12), span / 10.0)


def _basis_axis(b0: float, b1: float):
    """贴水副轴（点）范围与刻度：数据自适应（P2#4，消除 240–400/-15 硬编码裁切）。

    遗留包络（b0≥-15 且 b1≤400）保持历史范围 [-15, b1+42%margin] 与历史刻度
    [0, 240..380] 原样——既有图渲染零变化；超出包络（贴水>400 或深贴水<-15）
    时下限随数据下扩、刻度按数据范围整齐生成。
    """
    span = (b1 - b0) if b1 > b0 else 1.0
    margin = span * .42
    bylo = min(-15.0, b0 - span * .1)
    byhi = b1 + margin
    if b0 >= -15.0 and b1 <= 400.0:
        return bylo, byhi, list(_LEGACY_BASIS_TICKS)
    step = _nice_step(byhi - bylo, (5, 10, 20, 25, 50, 100, 200, 500))
    t0 = np.floor(bylo / step) * step
    ticks = [round(float(t), 6) for t in np.arange(t0, byhi + step * .5, step)]
    return bylo, byhi, ticks


def _basis_rate_ticks(bylo: float, byhi: float, rate_factor: float):
    """贴水率副轴（%）刻度：包络内（byhi/rate≤5.55）保持历史 0..5.5/.5；超包络自适应。"""
    if byhi / rate_factor <= 5.55:
        return list(_LEGACY_RATE_TICKS)
    step = _nice_step((byhi - bylo) / rate_factor, (.25, .5, 1, 2, 5))
    t0 = np.floor((bylo / rate_factor) / step) * step
    return [round(float(t), 6)
            for t in np.arange(t0, byhi / rate_factor + step * .5, step)]


def build_figure(df, slots, panels: list[dict], rep, title: str = "",
                 row_heights: list | None = None) -> go.Figure:
    if len(panels) == 1:
        return _build_single(df, slots, panels[0], rep, title)
    return _build_multi(df, slots, panels, rep, title, row_heights)


def _build_single(df, slots, panel, rep, title: str) -> go.Figure:
    fig = go.Figure()
    ctx = Ctx(slots=slots, df=df)
    for spec in panel.get("layers", []):
        draw(fig, spec, ctx)

    by = df["basis"] if "basis" in df else None
    if by is not None and by.notna().any():
        bylo, byhi, by_ticks = _basis_axis(float(by.min()), float(by.max()))
    else:
        bylo, byhi, by_ticks = -15.0, 400.0, list(_LEGACY_BASIS_TICKS)
    ylo, yhi = _auto_range(df, ["fut_close", "fut_open", "fut_high", "fut_low"])
    rate_factor = float(df["idx_close"].mean()) / 100.0 if "idx_close" in df else 75.0

    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Microsoft YaHei, Arial", size=12, color="#222"),
        margin=MARGIN,
        xaxis=dict(range=[-8, slots.n_all + 2.5], domain=[0.0, 0.845],
                   tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                   tickangle=-90, tickfont=dict(size=9, color="#444"),
                   showgrid=False, zeroline=False, linecolor="#333"),
        yaxis=dict(range=[ylo, yhi], title=dict(text="价格（点）", font=dict(size=13)),
                   gridcolor="#dfe3ea", griddash="dot", zeroline=False,
                   linecolor="#333"),
        yaxis2=dict(overlaying="y", side="right", range=[bylo, byhi], position=.848,
                    title=dict(text="贴水（点）", font=dict(size=13, color="#a03340")),
                    tickvals=by_ticks,
                    tickfont=dict(size=10.5, color="#a03340"),
                    showgrid=False, zeroline=False, linecolor="#d8a0a8"),
        yaxis3=dict(overlaying="y", side="right", position=.955,
                    range=[bylo / rate_factor, byhi / rate_factor],
                    title=dict(text="贴水率（%）", font=dict(size=11, color="#777")),
                    tickvals=_basis_rate_ticks(bylo, byhi, rate_factor),
                    tickfont=dict(size=9.5, color="#888"),
                    showgrid=False, zeroline=False, linecolor="#c8c8c8"),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.0, yanchor="bottom",
                    font=dict(size=11.5), bgcolor="white",
                    bordercolor="#d9dde3", borderwidth=1, itemsizing="constant"),
    )
    fig.add_annotation(x=.005, y=1.075, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=21, color="#111"),
                       xanchor="left")
    fig.add_annotation(x=.998, y=-.152, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#999"),
                       text=rep.footnote() + " 时间轴仅含交易时段（09:30–11:30、13:00–15:00）。")
    return fig


_AXIS_REMAP_DOC = "面板0：y2→y{n+1}(贴水)、y3→y{n+2}(贴水率)；其余面板缺省 axis 注入本面板主轴"


def _remap_axes(layers: list[dict], overlay_y2: str, overlay_y3: str,
                default_axis: str | None) -> list[dict]:
    out = []
    for spec in layers:
        s = dict(spec)
        if s.get("axis") == "y2":
            s["axis"] = overlay_y2
        elif s.get("axis") == "y3":
            s["axis"] = overlay_y3
        elif "axis" not in s and s.get("type") in ("area", "events", "hline"):
            # 原语缺省轴重映射：面板0 缺省 y2/y3 是贴水 overlay（重映射到本图 ov2/ov3）；
            # 其余面板缺省注入本面板主轴。单面板路径不经此处，MVP 行为不变。
            s["axis"] = default_axis or overlay_y2
        elif s.get("axis") == "y" and default_axis:
            # 配置里 axis: "y" 意为"本面板主轴"（如仓位面板的 0 基准线），
            # 非面板0 时需换成本面板实际主轴名，避免落到全局 y 轴/被 _hline 拒绝
            s["axis"] = default_axis
        out.append(s)
    return out


def _build_multi(df, slots, panels, rep, title, row_heights):
    n = len(panels)
    heights = row_heights or ([0.72] + [0.28 / (n - 1)] * (n - 1))
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, row_heights=heights)
    ov2, ov3 = f"y{n + 1}", f"y{n + 2}"
    for i, panel in enumerate(panels, start=1):
        # plotly 主轴（第1行）引用名固定为 x/y（无编号）；y1/x1 不是合法轴引用
        xax = "x" if i == 1 else f"x{i}"
        yax = "y" if i == 1 else f"y{i}"
        layers = _remap_axes(panel.get("layers", []), ov2, ov3,
                             default_axis=(None if i == 1 else yax))
        ctx = Ctx(slots=slots, df=df, xaxis=xax, yaxis=yax)
        for spec in layers:
            draw(fig, spec, ctx)

    ylo, yhi = _auto_range(df, ["fut_close", "fut_open", "fut_high", "fut_low"])
    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Microsoft YaHei, Arial", size=12, color="#222"),
        margin=MARGIN,
        # 顶轴被 shared_xaxes 隐藏刻度（showticklabels=False），刻度配置画在最底面板（spec §2.1）
        xaxis=dict(range=[-8, slots.n_all + 2.5], domain=[0.0, 0.845],
                   showgrid=False, zeroline=False, linecolor="#333"),
        yaxis=dict(range=[ylo, yhi], title=dict(text="价格（点）", font=dict(size=13)),
                   gridcolor="#dfe3ea", griddash="dot", zeroline=False, linecolor="#333"),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.0, yanchor="bottom",
                    font=dict(size=11.5), bgcolor="white",
                    bordercolor="#d9dde3", borderwidth=1, itemsizing="constant"),
    )
    for i in range(2, n + 1):
        cols = panels[i - 1].get("range_cols") or [s["col"] for s in panels[i - 1].get("layers", [])
                                                   if s.get("type") == "line" and "col" in s]
        lo, hi = _auto_range(df, cols or ["fut_close"])
        is_bottom = i == n
        xconf = dict(domain=[0.0, 0.845], showgrid=False, zeroline=False,
                     showticklabels=bool(is_bottom))   # 仅最底面板画刻度（spec §2.1）
        if is_bottom:
            xconf.update(tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                         tickangle=-90, tickfont=dict(size=9, color="#444"),
                         linecolor="#333", range=[-8, slots.n_all + 2.5])
        fig.update_layout(**{f"xaxis{i}": xconf,
                             f"yaxis{i}": dict(range=[lo, hi],
                                               title=dict(text=panels[i - 1].get("y_title", "")),
                                               gridcolor="#dfe3ea", griddash="dot",
                                               zeroline=False, linecolor="#333")})
    by = df["basis"] if "basis" in df else None
    if by is not None and by.notna().any():
        bylo, byhi, by_ticks = _basis_axis(float(by.min()), float(by.max()))
    else:
        bylo, byhi, by_ticks = -15.0, 400.0, list(_LEGACY_BASIS_TICKS)
    rate_factor = float(df["idx_close"].mean()) / 100.0 if "idx_close" in df else 75.0
    fig.update_layout(**{
        f"yaxis{ov2[1:]}": dict(overlaying="y", side="right", range=[bylo, byhi], position=.848,
                  title=dict(text="贴水（点）", font=dict(size=13, color="#a03340")),
                  tickvals=by_ticks,
                  tickfont=dict(size=10.5, color="#a03340"),
                  showgrid=False, zeroline=False, linecolor="#d8a0a8"),
        f"yaxis{ov3[1:]}": dict(overlaying="y", side="right", position=.955,
                  range=[bylo / rate_factor, byhi / rate_factor],
                  title=dict(text="贴水率（%）", font=dict(size=11, color="#777")),
                  tickvals=_basis_rate_ticks(bylo, byhi, rate_factor),
                  tickfont=dict(size=9.5, color="#888"),
                  showgrid=False, zeroline=False, linecolor="#c8c8c8")})
    fig.add_annotation(x=.005, y=1.075, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=21, color="#111"), xanchor="left")
    fig.add_annotation(x=.998, y=-.152, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#999"),
                       text=rep.footnote() + " 时间轴仅含交易时段（09:30–11:30、13:00–15:00）。")
    return fig


def _auto_range(df, cols, pad_lo=.10, pad_hi=.16):
    vals = np.concatenate([df[c].dropna().values for c in cols if c in df])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * pad_lo, hi + span * pad_hi