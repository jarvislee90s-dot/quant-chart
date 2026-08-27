"""面板组装：槽位X轴 + 双右轴 + 标题/图例/日期行/质量脚注（布局源自已验证样张）。"""
import numpy as np
import plotly.graph_objects as go

from .primitives import Ctx, draw

MARGIN = dict(l=68, r=168, t=108, b=130)


def build_figure(df, slots, panels: list[dict], rep, title: str = "") -> go.Figure:
    assert len(panels) == 1, "MVP 支持单面板（多面板属二期）"
    fig = go.Figure()
    ctx = Ctx(slots=slots, df=df)
    for spec in panels[0].get("layers", []):
        draw(fig, spec, ctx)

    by = df["basis"] if "basis" in df else None
    if by is not None and by.notna().any():
        b0, b1 = float(by.min()), float(by.max())
        margin = (b1 - b0) * .42
        bylo, byhi = -15.0, b1 + margin
    else:
        bylo, byhi = -15.0, 400.0
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
                    tickvals=[0] + list(np.arange(240, 400, 20)),
                    tickfont=dict(size=10.5, color="#a03340"),
                    showgrid=False, zeroline=False, linecolor="#d8a0a8"),
        yaxis3=dict(overlaying="y", side="right", position=.955,
                    range=[bylo / rate_factor, byhi / rate_factor],
                    title=dict(text="贴水率（%）", font=dict(size=11, color="#777")),
                    tickvals=list(np.arange(0, 5.51, .5)),
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


def _auto_range(df, cols, pad_lo=.10, pad_hi=.16):
    vals = np.concatenate([df[c].dropna().values for c in cols if c in df])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * pad_lo, hi + span * pad_hi
