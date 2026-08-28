"""通用绘图原语 → Plotly traces/shapes/annotations 翻译。不含任何计算。"""
import sys
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go


@dataclass
class Ctx:
    slots: object
    df: pd.DataFrame
    xaxis: str = "x"
    yaxis: str = "y"
    y2axis: str = "y2"


def _xof(ctx: Ctx, v) -> float:
    """时间字符串或数值 → 槽位pos。"""
    if isinstance(v, str):
        row = ctx.df[ctx.df["datetime"] == pd.Timestamp(v)]
        if row.empty:
            raise KeyError(f"时间点不在数据中: {v}")
        return float(row["pos"].iloc[0])
    return float(v)


def draw(fig: go.Figure, spec: dict, ctx: Ctx):
    fn = getattr(sys.modules[__name__], f"_{spec['type']}", None)
    if fn is None:
        raise KeyError(f"未知绘图原语: {spec['type']}")
    fn(fig, spec, ctx)


def _line(fig, spec, ctx):
    # 主轴引用名 "y" 是 plotly 默认（不设等价）；副轴必须显式绑定，否则 trace 落主图
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    fig.add_trace(go.Scatter(
        x=ctx.df["pos"], y=ctx.df[spec["col"]], yaxis=yax,
        mode="lines", name=spec.get("name", spec["col"]),
        line=dict(color=spec.get("color", "#1c4e9d"),
                  width=spec.get("width", 2),
                  dash=spec.get("dash", "solid"),
                  shape=spec.get("shape", "linear"))))


def _area(fig, spec, ctx):
    y = ctx.df[spec["col"]]
    x = ctx.df["pos"]
    pos = y.where(y >= 0, other=None)
    neg = y.where(y < 0, other=None)
    ax = spec.get("axis", "y2")
    fig.add_trace(go.Scatter(x=x, y=pos, yaxis=ax, fill="tozeroy", mode="none",
                             fillcolor=spec.get("pos_color", "rgba(214,64,76,.30)"),
                             name=spec.get("name_pos", "贴水（现货>期货）")))
    fig.add_trace(go.Scatter(x=x, y=neg, yaxis=ax, fill="tozeroy", mode="none",
                             fillcolor=spec.get("neg_color", "rgba(46,158,99,.42)"),
                             name=spec.get("name_neg", "升水（现货<期货）")))
    fig.add_trace(go.Scatter(x=x, y=y, yaxis=ax, mode="lines",
                             line=dict(color=spec.get("line_color", "#d6404c"), width=1),
                             showlegend=False, hoverinfo="skip"))


def _zone(fig, spec, ctx):
    x0, x1 = _xof(ctx, spec["from"]), _xof(ctx, spec["to"])
    plo, phi = spec["price"]
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=plo, y1=phi,
                  xref=ctx.xaxis, yref=ctx.yaxis,
                  fillcolor=spec.get("fillcolor", "#c2c7cf"),
                  opacity=spec.get("opacity", .32),
                  line=dict(color=spec.get("edgecolor", "#8f959d"),
                            width=.9, dash="dash"), layer="above")
    if spec.get("label"):
        fig.add_annotation(x=(x0 + x1) / 2, y=plo, yref=ctx.yaxis,
                           text=spec["label"], showarrow=False,
                           yanchor="bottom", yshift=6,
                           font=dict(size=11, color="#3a3f46"),
                           bgcolor="white", bordercolor="#c4c9d0",
                           borderpad=3, opacity=.92)


def _hline(fig, spec, ctx):
    yref = spec.get("axis", "y2")
    if spec.get("from") or spec.get("to"):
        x0 = _xof(ctx, spec.get("from", ctx.df["pos"].min()))
        x1 = _xof(ctx, spec.get("to", ctx.df["pos"].max()))
    else:
        x0, x1 = 0, 1
        xref = "paper"
        if yref != ctx.yaxis:
            raise ValueError("纸面全宽hline只支持主轴；副轴请给 from/to")
    yv = spec.get("value")
    if yv is None and spec.get("col_last"):
        yv = float(ctx.df[spec["col_last"]].dropna().iloc[-1])
    xref = ctx.xaxis if (spec.get("from") or spec.get("to")) else "paper"
    fig.add_shape(type="line", x0=x0, x1=x1, y0=yv, y1=yv, xref=xref, yref=yref,
                  line=dict(color=spec.get("color", "#83898f"),
                            width=spec.get("width", 1.1), dash=spec.get("dash", "dash")))
    if spec.get("label"):
        fig.add_annotation(x=x0, y=yv, yref=yref,
                           xref=ctx.xaxis if spec.get("from") else "paper",
                           text=spec["label"], showarrow=False,
                           xanchor="left", yanchor="bottom",
                           font=dict(size=10.5, color=spec.get("color", "#55595f")),
                           bgcolor="white", opacity=.9)


def _events(fig, spec, ctx):
    """事件点标记：marker + 数值标签；style_map 按事件 meta.action 覆盖样式。

    按样式（符号,颜色）分组出 trace：单一样式时仅一个 trace、symbol 为标量
    （与 MVP 行为一致）；混合样式时各组分属不同 trace，避免 plotly 把
    symbol 归一成元组导致断言/下游取值形态改变。
    """
    ax = spec.get("axis", "y2")
    evs = spec["events"][spec["ref"]]
    style_map = spec.get("style_map", {})
    groups: dict[tuple, list] = {}
    for e in evs:
        st = style_map.get((e.meta or {}).get("action"), {})
        key = (st.get("symbol", spec.get("symbol", "triangle-down")),
               st.get("color", spec.get("color", "#701820")))
        groups.setdefault(key, []).append(e)
    for (sym, col), ge in groups.items():
        fig.add_trace(go.Scatter(
            x=[e.pos for e in ge], y=[e.value for e in ge], yaxis=ax,
            mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(symbol=sym, size=spec.get("size", 8), color=col,
                        line=dict(color="white", width=.8))))
        for e in ge:
            fig.add_annotation(x=e.pos, y=e.value, yref=ax, text=e.label,
                               showarrow=False, yanchor="top", yshift=-8,
                               font=dict(size=10.5, color=col),
                               bgcolor="white", opacity=.72, borderpad=1)


def _leader_tag(fig, spec, ctx):
    """低点事件 → 连线至基准线 + 价差/涨幅标注（含引导线）。"""
    evs = spec["events"][spec["ref"]]
    ref = float(ctx.df[spec["ref_value_col"]].dropna().iloc[-1])
    for e in evs:
        diff = ref - e.value
        pct = (ref / e.value - 1) * 100
        txt = spec.get("text", "+{diff}（{pct}%）").format(
            diff=f"{diff:.0f}", pct=f"{pct:+.1f}", value=f"{e.value:,.0f}", ref=f"{ref:,.1f}")
        fig.add_trace(go.Scatter(x=[e.pos, e.pos], y=[e.value, ref], mode="lines",
                                 line=dict(color="#606a75", width=1, dash="dot"),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[e.pos], y=[e.value], mode="markers",
                                 marker=dict(symbol="circle-open", size=7,
                                             color="#39414a", line=dict(width=1.1)),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=e.pos, y=e.value, text=txt, showarrow=True,
                           arrowhead=0, arrowcolor="#b3a5dd", arrowwidth=.9, standoff=6,
                           ax=spec.get("ax", 92), ay=spec.get("ay", -120),
                           font=dict(size=10.5, color="#8465c1"),
                           bgcolor="white", bordercolor="#b3a5dd",
                           borderpad=3, opacity=.95,
                           xanchor=spec.get("xanchor", "left"))
        fig.add_annotation(x=e.pos, y=e.value, text=f"{e.value:,.0f}",
                           showarrow=False, yanchor="top", yshift=-7,
                           font=dict(size=10, color="#454b52"),
                           bgcolor="white", opacity=.75, borderpad=1)


def _day_seps(fig, spec, ctx):
    for p in ctx.slots.sep_center:
        fig.add_shape(type="line", x0=p, x1=p, y0=0, y1=1,
                      xref=ctx.xaxis, yref="paper",
                      line=dict(color=spec.get("color", "#b3b9c2"),
                                width=1, dash="dash"))


def _day_labels(fig, spec, ctx):
    for d, (s, e) in ctx.slots.day_span.items():
        fig.add_annotation(x=(s + e) / 2, y=spec.get("y", -.108), yref="paper",
                           text=d.strftime("%m-%d"), showarrow=False,
                           font=dict(size=11.5),
                           bgcolor="#f2f3f5", bordercolor="#d5d8dd", borderpad=3)
